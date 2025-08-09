import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()

@dataclass(frozen=True)
class Settings:
    DISCORD_TOKEN: str
    GUILD_ID_TEST: int

def _to_int(value: str, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default

settings = Settings(
    DISCORD_TOKEN=os.getenv("DISCORD_TOKEN", "").strip(),
    GUILD_ID_TEST=_to_int(os.getenv("GUILD_ID_TEST", "0"))
)

if not settings.DISCORD_TOKEN:
    raise RuntimeError("DISCORD_TOKEN manquant dans .env")
