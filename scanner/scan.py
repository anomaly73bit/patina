"""Scanner Patina: raccoglie gli annunci, calcola lo sconto sulla stima, scrive _data/listings.json."""
import datetime as dt

import ebay
from common import load, save, score

SOURCES = [ebay]  # aggiungi qui i moduli di nuove fonti (stessa firma: fetch(models) -> list)


def main():
    models = load("models.json")
    by_id = {m["id"]: m for m in models}
    fees = load("sources.json")

    found = []
    for src in SOURCES:
        try:
            found += src.fetch(models)
        except Exception as e:
            print(f"{src.__name__}: errore {e}")

    if not found:
        print("Nessun annuncio reale: lascio i dati attuali invariati")
        return

    seen, listings = set(), []
    for l in found:
        if l.get("url") in seen:
            continue
        seen.add(l.get("url"))
        src = fees.get(l["src"], {"type": "Marketplace", "fee": 0})
        l["type"] = "Asta" if l.get("auction") else src["type"]
        listings.append(score(l, by_id[l["m"]], src["fee"]))

    listings.sort(key=lambda l: -l["disc"])
    save("listings.json", {
        "updated": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "example": False,
        "items": listings[:400],
    })
    print(f"Salvati {len(listings)} annunci")


if __name__ == "__main__":
    main()
