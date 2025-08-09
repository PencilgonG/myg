import os
import sqlite3
from pathlib import Path
from typing import Optional, Dict, Any

_DB_PATH = os.environ.get("MYG_DB_PATH", "data/myg.sqlite3")
Path(os.path.dirname(_DB_PATH)).mkdir(parents=True, exist_ok=True)

def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(_DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db() -> None:
    with _get_conn() as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS profiles (
            user_id     INTEGER NOT NULL,
            guild_id    INTEGER NOT NULL,
            opgg_url    TEXT,
            dpm_url     TEXT,
            elo         TEXT,
            discord_name TEXT,
            created_at  TEXT DEFAULT (datetime('now')),
            updated_at  TEXT DEFAULT (datetime('now')),
            PRIMARY KEY(user_id, guild_id)
        );
        """)
        conn.commit()

def get_profile(guild_id: int, user_id: int) -> Optional[Dict[str, Any]]:
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT * FROM profiles WHERE guild_id=? AND user_id=?",
            (guild_id, user_id)
        ).fetchone()
        return dict(row) if row else None

def upsert_profile(guild_id: int, user_id: int, opgg_url: Optional[str], dpm_url: Optional[str],
                   elo: Optional[str], discord_name: Optional[str]) -> None:
    with _get_conn() as conn:
        exists = conn.execute(
            "SELECT 1 FROM profiles WHERE guild_id=? AND user_id=?",
            (guild_id, user_id)
        ).fetchone() is not None

        if exists:
            conn.execute("""
                UPDATE profiles
                   SET opgg_url=?,
                       dpm_url=?,
                       elo=?,
                       discord_name=COALESCE(?, discord_name),
                       updated_at=datetime('now')
                 WHERE guild_id=? AND user_id=?
            """, (opgg_url, dpm_url, elo, discord_name, guild_id, user_id))
        else:
            conn.execute("""
                INSERT INTO profiles (guild_id, user_id, opgg_url, dpm_url, elo, discord_name)
                VALUES (?, ?, ?, ?, ?, ?)
            """, (guild_id, user_id, opgg_url, dpm_url, elo, discord_name))
        conn.commit()
# --- STATS / MATCHES ---

def init_db_stats() -> None:
    with _get_conn() as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS matches (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id   INTEGER NOT NULL,
            mode       TEXT,
            blue_ids   TEXT NOT NULL,  -- csv d'IDs
            red_ids    TEXT NOT NULL,  -- csv d'IDs
            winner     TEXT CHECK(winner in ('blue','red')) NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        );
        """)
        conn.execute("""
        CREATE TABLE IF NOT EXISTS player_stats (
            guild_id    INTEGER NOT NULL,
            user_id     INTEGER NOT NULL,
            games       INTEGER NOT NULL DEFAULT 0,
            wins        INTEGER NOT NULL DEFAULT 0,
            losses      INTEGER NOT NULL DEFAULT 0,
            last_played TEXT,
            PRIMARY KEY(guild_id, user_id)
        );
        """)
        conn.commit()

def _csv_from_ids(ids):
    return ",".join(str(i) for i in ids)

def _ids_from_csv(csv: str):
    return [int(x) for x in csv.split(",") if x.strip().isdigit()]

def record_match(guild_id: int, mode: str | None, blue_ids, red_ids, winner: str) -> int:
    blue_csv = _csv_from_ids(blue_ids)
    red_csv  = _csv_from_ids(red_ids)
    with _get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO matches (guild_id, mode, blue_ids, red_ids, winner) VALUES (?,?,?,?,?)",
            (guild_id, mode, blue_csv, red_csv, winner)
        )
        match_id = cur.lastrowid
        # update stats
        import datetime as _dt
        now = _dt.datetime.utcnow().isoformat(timespec="seconds")
        for uid in blue_ids + red_ids:
            row = conn.execute("SELECT 1 FROM player_stats WHERE guild_id=? AND user_id=?", (guild_id, uid)).fetchone()
            if row is None:
                conn.execute("INSERT INTO player_stats (guild_id,user_id,games,wins,losses,last_played) VALUES (?,?,?,?,?,?)",
                             (guild_id, uid, 0, 0, 0, now))
        # blue
        for uid in blue_ids:
            conn.execute("UPDATE player_stats SET games=games+1, wins=wins+?, losses=losses+?, last_played=? WHERE guild_id=? AND user_id=?",
                         (1 if winner=="blue" else 0, 1 if winner=="red" else 0, now, guild_id, uid))
        # red
        for uid in red_ids:
            conn.execute("UPDATE player_stats SET games=games+1, wins=wins+?, losses=losses+?, last_played=? WHERE guild_id=? AND user_id=?",
                         (1 if winner=="red" else 0, 1 if winner=="blue" else 0, now, guild_id, uid))
        conn.commit()
        return match_id

def get_stats(guild_id: int, user_id: int):
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT games, wins, losses, last_played FROM player_stats WHERE guild_id=? AND user_id=?",
            (guild_id, user_id)
        ).fetchone()
        return dict(row) if row else {"games":0,"wins":0,"losses":0,"last_played":None}

def get_leaderboard(guild_id: int, metric: str = "wins", limit: int = 10):
    # metric in: games|wins|winrate
    with _get_conn() as conn:
        if metric == "winrate":
            rows = conn.execute(f"""
                SELECT user_id, games, wins, losses,
                       CASE WHEN games=0 THEN 0.0 ELSE (CAST(wins AS REAL)/games) END AS winrate
                  FROM player_stats
                 WHERE guild_id=?
              ORDER BY winrate DESC, games DESC
                 LIMIT ?""", (guild_id, limit)).fetchall()
        else:
            if metric not in ("games", "wins"):
                metric = "wins"
            rows = conn.execute(f"""
                SELECT user_id, games, wins, losses
                  FROM player_stats
                 WHERE guild_id=?
              ORDER BY {metric} DESC, wins DESC, games DESC
                 LIMIT ?""", (guild_id, limit)).fetchall()
        return [dict(r) for r in rows]
# --- STATS / MATCHES (avec rôles) ---

def init_db_stats() -> None:
    with _get_conn() as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS matches (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            guild_id   INTEGER NOT NULL,
            mode       TEXT,
            blue_ids   TEXT NOT NULL,  -- csv d'IDs
            red_ids    TEXT NOT NULL,  -- csv d'IDs
            winner     TEXT CHECK(winner in ('blue','red')) NOT NULL,
            created_at TEXT DEFAULT (datetime('now'))
        );
        """)
        conn.execute("""
        CREATE TABLE IF NOT EXISTS player_stats (
            guild_id    INTEGER NOT NULL,
            user_id     INTEGER NOT NULL,
            games       INTEGER NOT NULL DEFAULT 0,
            wins        INTEGER NOT NULL DEFAULT 0,
            losses      INTEGER NOT NULL DEFAULT 0,
            last_played TEXT,
            PRIMARY KEY(guild_id, user_id)
        );
        """)
        conn.execute("""
        CREATE TABLE IF NOT EXISTS role_stats (
            guild_id    INTEGER NOT NULL,
            user_id     INTEGER NOT NULL,
            role        TEXT NOT NULL, -- Top/Jungle/Mid/ADC/Support
            games       INTEGER NOT NULL DEFAULT 0,
            wins        INTEGER NOT NULL DEFAULT 0,
            losses      INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (guild_id, user_id, role)
        );
        """)
        conn.commit()

def _csv_from_ids(ids):
    return ",".join(str(i) for i in ids)

def _ids_from_csv(csv: str):
    return [int(x) for x in csv.split(",") if x.strip().isdigit()]

def record_match(guild_id: int, mode: str | None, blue_ids, red_ids, winner: str, role_map: dict[int, str] | None = None) -> int:
    """Enregistre un match + met à jour player_stats et role_stats. role_map: {user_id: 'Top'|...}"""
    blue_csv = _csv_from_ids(blue_ids)
    red_csv  = _csv_from_ids(red_ids)
    with _get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO matches (guild_id, mode, blue_ids, red_ids, winner) VALUES (?,?,?,?,?)",
            (guild_id, mode, blue_csv, red_csv, winner)
        )
        match_id = cur.lastrowid

        import datetime as _dt
        now = _dt.datetime.utcnow().isoformat(timespec="seconds")
        # ensure rows in player_stats
        for uid in set(blue_ids + red_ids):
            row = conn.execute("SELECT 1 FROM player_stats WHERE guild_id=? AND user_id=?", (guild_id, uid)).fetchone()
            if row is None:
                conn.execute("INSERT INTO player_stats (guild_id,user_id,games,wins,losses,last_played) VALUES (?,?,?,?,?,?)",
                             (guild_id, uid, 0, 0, 0, now))
        # update player_stats
        for uid in blue_ids:
            conn.execute("UPDATE player_stats SET games=games+1, wins=wins+?, losses=losses+?, last_played=? WHERE guild_id=? AND user_id=?",
                         (1 if winner=="blue" else 0, 1 if winner=="red" else 0, now, guild_id, uid))
        for uid in red_ids:
            conn.execute("UPDATE player_stats SET games=games+1, wins=wins+?, losses=losses+?, last_played=? WHERE guild_id=? AND user_id=?",
                         (1 if winner=="red" else 0, 1 if winner=="blue" else 0, now, guild_id, uid))

        # update role_stats
        role_map = role_map or {}
        def up_role(uid: int, win_inc: int, loss_inc: int):
            role = role_map.get(uid)
            if not role: return
            ex = conn.execute("SELECT 1 FROM role_stats WHERE guild_id=? AND user_id=? AND role=?",
                              (guild_id, uid, role)).fetchone()
            if ex is None:
                conn.execute("INSERT INTO role_stats (guild_id,user_id,role,games,wins,losses) VALUES (?,?,?,?,?,?)",
                             (guild_id, uid, role, 0, 0, 0))
            conn.execute("UPDATE role_stats SET games=games+1, wins=wins+?, losses=losses+? WHERE guild_id=? AND user_id=? AND role=?",
                         (win_inc, loss_inc, guild_id, uid, role))

        for uid in blue_ids:
            up_role(uid, 1 if winner=="blue" else 0, 1 if winner=="red" else 0)
        for uid in red_ids:
            up_role(uid, 1 if winner=="red" else 0, 1 if winner=="blue" else 0)

        conn.commit()
        return match_id

def get_stats(guild_id: int, user_id: int):
    with _get_conn() as conn:
        row = conn.execute(
            "SELECT games, wins, losses, last_played FROM player_stats WHERE guild_id=? AND user_id=?",
            (guild_id, user_id)
        ).fetchone()
        return dict(row) if row else {"games":0,"wins":0,"losses":0,"last_played":None}

def get_role_stats(guild_id: int, user_id: int):
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT role, games, wins, losses FROM role_stats WHERE guild_id=? AND user_id=? ORDER BY role",
            (guild_id, user_id)
        ).fetchall()
        return [dict(r) for r in rows]

def get_leaderboard(guild_id: int, metric: str = "wins", limit: int = 10):
    with _get_conn() as conn:
        if metric == "winrate":
            rows = conn.execute(f"""
                SELECT user_id, games, wins, losses,
                       CASE WHEN games=0 THEN 0.0 ELSE (CAST(wins AS REAL)/games) END AS winrate
                  FROM player_stats
                 WHERE guild_id=?
              ORDER BY winrate DESC, games DESC
                 LIMIT ?""", (guild_id, limit)).fetchall()
        else:
            if metric not in ("games", "wins"):
                metric = "wins"
            rows = conn.execute(f"""
                SELECT user_id, games, wins, losses
                  FROM player_stats
                 WHERE guild_id=?
              ORDER BY {metric} DESC, wins DESC, games DESC
                 LIMIT ?""", (guild_id, limit)).fetchall()
        return [dict(r) for r in rows]

def get_recent_matches(guild_id: int, limit: int = 10):
    with _get_conn() as conn:
        rows = conn.execute("""
            SELECT id, mode, blue_ids, red_ids, winner, created_at
              FROM matches
             WHERE guild_id=?
          ORDER BY id DESC
             LIMIT ?
        """, (guild_id, limit)).fetchall()
        out = []
        for r in rows:
            out.append({
                "id": r["id"],
                "mode": r["mode"],
                "winner": r["winner"],
                "created_at": r["created_at"],
                "blue_ids": _ids_from_csv(r["blue_ids"]),
                "red_ids":  _ids_from_csv(r["red_ids"]),
            })
        return out
