"""Scanner Patina: raccoglie gli annunci, calcola lo sconto sulla stima, scrive _data/listings.json.

Gli annunci venduti o scaduti spariscono: a ogni giro gli annunci di una fonte
vengono sostituiti da quelli che la fonte mostra ancora attivi. Se una fonte
non risponde, i suoi vecchi annunci restano al massimo 24 ore, poi vengono tolti.
"""
import datetime as dt

import alerts
import apify
import ebay
from common import load, save, score

SOURCES = [ebay, apify, alerts]  # aggiungi qui i moduli di nuove fonti: fetch(models) -> list, oppure None se la fonte è disattivata
MAX_STALE = dt.timedelta(hours=24)


def now():
    return dt.datetime.now(dt.timezone.utc)


def parse(ts):
    try:
        return dt.datetime.fromisoformat(ts.replace("Z", "+00:00"))
    except (AttributeError, ValueError):
        return None


def still_open(l, t):
    end = parse(l.get("endDate"))
    return not (end and end <= t) and not l.get("sold")


def main():
    t = now()
    models = load("models.json")
    by_id = {m["id"]: m for m in models}
    fees = load("sources.json")
    old = load("listings.json", {"items": [], "example": True})
    old_items = [] if old.get("example") else old.get("items", [])

    items, any_real = [], False
    for src in SOURCES:
        name = src.__name__
        try:
            found = src.fetch(models)
        except Exception as e:
            print(f"{name}: errore {e}")
            found = "errore"
        if found is None:  # fonte disattivata (chiavi mancanti)
            continue
        if found == "keep":
            # fonte che non gira a ogni giro (Apify, una volta al giorno): tengo i suoi annunci dell'ultimo giro
            kept = [l for l in old_items if l.get("via") == name and (parse(l.get("seen")) or t) > t - 2 * MAX_STALE]
            items += kept
            any_real = any_real or bool(old_items)
            print(f"{name}: tengo {len(kept)} annunci dall'ultimo giro")
            continue
        if found == "errore":
            # fonte non raggiungibile: tengo i suoi annunci solo se visti nelle ultime 24 ore
            kept = [l for l in old_items if l.get("via") == name and (parse(l.get("seen")) or t) > t - MAX_STALE]
            items += kept
            any_real = any_real or bool(old_items)  # riscrivo il file anche per togliere quelli vecchi
            print(f"{name}: tengo {len(kept)} annunci recenti")
            continue
        any_real = True
        for l in found:
            l["via"], l["seen"] = name, t.isoformat(timespec="seconds")
            src_info = fees.get(l["src"], {"type": "Marketplace", "fee": 0})
            l["type"] = "Asta" if l.get("auction") else src_info["type"]
            items.append(score(l, by_id[l["m"]], src_info["fee"]))
        print(f"{name}: {len(found)} annunci attivi")

    if not any_real:
        print("Nessuna fonte attiva: restano gli annunci di esempio")
        return

    seen, listings = set(), []
    for l in items:
        key = l.get("url") or (l["src"], l.get("title"), l["p"])
        if key in seen or not still_open(l, t):
            continue  # doppione, venduto o asta già chiusa
        seen.add(key)
        listings.append(l)

    listings.sort(key=lambda l: -l["disc"])
    save("listings.json", {
        "updated": t.strftime("%Y-%m-%d %H:%M UTC"),
        "example": False,
        "items": listings[:400],
    })
    print(f"Salvati {len(listings)} annunci attivi")


if __name__ == "__main__":
    main()
