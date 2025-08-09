import json, os
from threading import RLock
from typing import Any, Dict, List
from time import time

DATA_PATH = os.path.join(os.path.dirname(__file__), "data.json")
_LOCK = RLock()

_DEFAULT = {
    "guild_settings": {},   # str(gid)-> {"announce_channel_id":int|None,"inhouse_role_id":int|None,"mod_role_id":int|None}
    "profiles": {},         # str(uid)-> {"name_tag":..., "joined":0, "subbed":0, "elo":..., "opgg_url":..., "dpm_url":...}
    "history": {},          # str(gid)-> [ {draft info} ]
}

def _ensure_file():
    if not os.path.exists(DATA_PATH):
        with open(DATA_PATH,"w",encoding="utf-8") as f: json.dump(_DEFAULT,f,ensure_ascii=False,indent=2)

def load()->Dict[str,Any]:
    _ensure_file()
    with _LOCK:
        with open(DATA_PATH,"r",encoding="utf-8") as f:
            try: data=json.load(f)
            except Exception: data=_DEFAULT.copy()
        # merge defaults
        for k,v in _DEFAULT.items():
            if k not in data:
                data[k]=v if not isinstance(v,dict) else v.copy()
        return data

def save(data:Dict[str,Any])->None:
    with _LOCK:
        with open(DATA_PATH,"w",encoding="utf-8") as f: json.dump(data,f,ensure_ascii=False,indent=2)

# ---------- Guild settings ----------
def _g(gid:int, data=None)->dict:
    d = load() if data is None else data
    key=str(gid)
    d["guild_settings"].setdefault(key, {"announce_channel_id":None,"inhouse_role_id":None,"mod_role_id":None})
    return d

def set_announce_channel(gid:int, cid:int|None):
    d=load(); g=_g(gid,d); g["guild_settings"][str(gid)]["announce_channel_id"]=cid; save(d)

def get_announce_channel(gid:int)->int|None:
    return load()["guild_settings"].get(str(gid),{}).get("announce_channel_id")

def set_inhouse_role(gid:int, rid:int|None):
    d=load(); g=_g(gid,d); g["guild_settings"][str(gid)]["inhouse_role_id"]=rid; save(d)

def get_inhouse_role(gid:int)->int|None:
    return load()["guild_settings"].get(str(gid),{}).get("inhouse_role_id")

def set_mod_role(gid:int, rid:int|None):
    d=load(); g=_g(gid,d); g["guild_settings"][str(gid)]["mod_role_id"]=rid; save(d)

def get_mod_role(gid:int)->int|None:
    return load()["guild_settings"].get(str(gid),{}).get("mod_role_id")

# ---------- Profiles ----------
def _ensure_profile(data:Dict[str,Any], uid:int)->dict:
    k=str(uid)
    prof=data["profiles"].setdefault(k, {"name_tag":None,"joined":0,"subbed":0,"elo":None,"opgg_url":None,"dpm_url":None})
    for key in ("elo","opgg_url","dpm_url"): prof.setdefault(key,None)
    return prof

def update_profile_join(uid:int, name_tag:str|None, as_sub:bool):
    d=load(); p=_ensure_profile(d,uid)
    if name_tag: p["name_tag"]=name_tag
    p["subbed" if as_sub else "joined"]=int(p.get("subbed" if as_sub else "joined",0))+1
    save(d)

def set_profile_fields(uid:int, name_tag:str|None=None, elo:str|None=None, opgg_url:str|None=None, dpm_url:str|None=None):
    d=load(); p=_ensure_profile(d,uid)
    if name_tag: p["name_tag"]=name_tag.strip()
    if elo: p["elo"]=elo.strip()
    if opgg_url: p["opgg_url"]=opgg_url.strip()
    if dpm_url: p["dpm_url"]=dpm_url.strip()
    save(d)

def get_profile(uid:int)->dict|None:
    d=load(); p=d["profiles"].get(str(uid))
    if p: [p.setdefault(k,None) for k in ("elo","opgg_url","dpm_url")]
    return p

# ---------- History ----------
def append_history(gid:int, entry:Dict[str,Any]):
    d=load()
    d["history"].setdefault(str(gid), [])
    entry.setdefault("ts", int(time()))
    d["history"][str(gid)].append(entry)
    save(d)

def get_history(gid:int, limit:int=10)->List[Dict[str,Any]]:
    return list(load()["history"].get(str(gid), []))[-limit:]
