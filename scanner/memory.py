"""Memoria delle descrizioni lette: per ogni annuncio solo i segnali trovati, l'anno e la data.
Così un annuncio non viene riletto a ogni giro. I testi degli annunci non vengono salvati."""
import datetime as dt
import json
import pathlib

PATH = pathlib.Path(__file__).resolve().parent / "cache" / "descrizioni.json"
DAYS = 7


def load_mem():
    try:
        mem = json.loads(PATH.read_text(encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return {}
    limit = (dt.date.today() - dt.timedelta(days=DAYS)).isoformat()
    return {u: v for u, v in mem.items() if v.get("read", "") >= limit}


def save_mem(listings):
    mem = load_mem()
    today = dt.date.today().isoformat()
    for l in listings:
        m = l.pop("_dmem", None)
        if m:
            mem[l["url"]] = {**m, "posted": l.get("posted") if isinstance(l.get("posted"), str) and len(l.get("posted", "")) < 40 else None, "read": today}
    PATH.parent.mkdir(exist_ok=True)
    PATH.write_text(json.dumps(mem, ensure_ascii=False, indent=0), encoding="utf-8")
