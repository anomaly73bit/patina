"""Il robot impara dal mercato: per ogni modello calcola i prezzi richiesti in questo giro
e corregge la stima a metà strada tra l'esperto (models.json) e il mercato.
Salva _data/market.json (usato dal sito) e _data/history.json (mediana giorno per giorno)."""
import datetime as dt
import statistics

from common import load, save
from evaluate import variant

MIN_N = 5          # annunci minimi per fidarsi del mercato
ASK_TO_SALE = 0.95  # i prezzi richiesti sono un po' sopra i prezzi di vendita
WEIGHT = 0.5       # peso del mercato rispetto alla stima dell'esperto


def calibrate(models, listings, today=None):
    today = (today or dt.date.today()).isoformat()
    history = load("history.json", {})
    market, adjusted = {}, []
    for m in models:
        # solo annunci della versione "base": le versioni speciali hanno prezzi propri
        prices = sorted(\n            l["total"] for l in listings\n            if l["m"] == m["id"]\n            and not l.get("auction")\n            and not l.get("sold")\n            and not variant(m, l.get("title", ""))[0]\n            and 0.4 * ((m["lo"] + m["hi"]) / 2) <= l["total"] <= 2.0 * ((m["lo"] + m["hi"]) / 2)\n        )
        m2 = dict(m)
        if len(prices) >= MIN_N:
            med = statistics.median(prices)
            q = statistics.quantiles(prices, n=4) if len(prices) >= 4 else [prices[0], med, prices[-1]]
            mid = (m["lo"] + m["hi"]) / 2
            factor = max(0.6, min(1.3, ((1 - WEIGHT) * mid + WEIGHT * ASK_TO_SALE * med) / mid))
            m2["lo"], m2["hi"] = round(m["lo"] * factor, -1), round(m["hi"] * factor, -1)
            m2["p25"] = q[0]  # un'occasione deve costare meno di 3 annunci su 4 dello stesso modello
            h = history.setdefault(m["id"], {})
            h[today] = round(med)
            for d in sorted(h)[:-400]:
                h.pop(d)
            # andamento misurato quando c'è uno storico di almeno 11 mesi
            old = [d for d in sorted(h) if d <= (dt.date.fromisoformat(today) - dt.timedelta(days=330)).isoformat()]
            if old:
                m2["t"] = round((med / h[old[-1]] - 1) * 100)
            market[m["id"]] = {"n": len(prices), "median": round(med), "p25": round(q[0]), "p75": round(q[-1]),
                               "lo": m2["lo"], "hi": m2["hi"], "t": m2["t"], "measured": bool(old)}
        adjusted.append(m2)
    save("market.json", market)
    save("history.json", history)
    return adjusted
