"""Fonte: robot Apify per Chrono24, Catawiki, Kleinanzeigen, Subito e Leboncoin.

Secret del repository: APIFY_TOKEN (Apify → Settings → API & Integrations).
I robot si pagano a consumo: per contenere la spesa girano una volta ogni
APIFY_EVERY_HOURS (default 24) e ogni robot ha un tetto di risultati e di costo.
Per spegnere un sito metti "enabled": false in SITES.
"""
import datetime as dt
import json
import os
import pathlib
import re
from urllib.parse import quote_plus

import requests

from common import load, matches, save, to_eur

API = "https://api.apify.com/v2/acts/{actor}/run-sync-get-dataset-items"
DEBUG = pathlib.Path(__file__).resolve().parent / "debug"
PER_QUERY = 20             # risultati massimi per ricerca
MAX_USD_BATCH_RUN = 1.00   # tetto di spesa per un robot che fa tutte le ricerche insieme
MAX_USD_SINGLE_RUN = 0.10  # tetto di spesa per una singola ricerca

SITES = {
    "Chrono24": {
        "enabled": True, "actor": "memo23~chrono24-scraper", "batch": True, "auction": False,
        "input": lambda qs: {"startUrls": [f"https://www.chrono24.de/search/index.htm?dosearch=true&query={quote_plus(q)}" for q in qs],
                             "maxItems": PER_QUERY * len(qs), "fetchListingDetails": False, "usedOrNew": "used"},
        "map": {"title": ["title"], "price": ["price"], "cur": ["currency"], "url": ["listingUrl"],
                "img": ["thumbnail", "images.0"], "cty": ["countryName", "countryCode"]},
    },
    "Catawiki": {
        "enabled": True, "actor": "scrapesage~catawiki-scraper", "batch": True, "auction": True,
        "input": lambda qs: {"searchQueries": qs, "maxItems": PER_QUERY * len(qs),
                             "includeLotDetails": True, "includeShippingRates": False},
        "map": {"title": ["title"], "price": ["currentBidEUR", "currentBid", "minNextBid"], "cur": [], "url": ["url"],
                "img": ["images.0", "thumbnail"], "cty": ["sellerCountry"], "end": ["biddingEndTime"]},
    },
    "Kleinanzeigen": {
        "enabled": True, "actor": "igolaizola~kleinanzeigen-scraper", "batch": False, "auction": False,
        "input": lambda q, m: {"query": q, "maxItems": PER_QUERY, "minPrice": int(m["lo"] * 0.3)},
        "map": {"title": ["title.value", "title"], "price": ["price.amount.value", "price"], "cur": [],
                "url": ["_meta.url", "url"], "img": ["_meta.image"], "cty": ["ad-address.state.value"]},
    },
    "Subito.it": {
        "enabled": True, "actor": "daddyapi~subito-scraper", "batch": False, "auction": False,
        "input": lambda q, m: {"searchQuery": q, "maxPages": 1, "sortBy": "newest",
                               "proxyConfiguration": {"useApifyProxy": True}},
        "map": {"title": ["title"], "price": ["price.amount", "price.display", "price"], "cur": ["price.currency"],
                "url": ["url"], "img": ["mainPhoto", "photos.0"], "cty": ["location.city"]},
    },
    "Leboncoin": {
        "enabled": True, "actor": "data_alchemist~leboncoin", "batch": True, "auction": False,
        "input": lambda qs: {"startUrls": [{"url": f"https://www.leboncoin.fr/recherche?text={quote_plus(q)}"} for q in qs]},
        "map": {"title": ["subject", "title"], "price": ["price.0", "price", "price_cents"], "cur": [],
                "url": ["url", "link"], "img": ["images.urls.0", "images.thumb_url", "images.0", "image"],
                "cty": ["location.city", "location.city_label", "location"]},
    },
}


def _get(item, path):
    cur = item
    for part in path.split("."):
        if isinstance(cur, list):
            cur = cur[int(part)] if part.isdigit() and int(part) < len(cur) else None
        elif isinstance(cur, dict):
            cur = cur.get(part)
        else:
            return None
        if cur is None:
            return None
    return cur


def _pick(item, paths):
    for p in paths:
        v = _get(item, p)
        if v not in (None, "", [], {}):
            return v
    return None


def _num(v):
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        digits = re.sub(r"[^\d]", "", v.split(",")[0])
        return float(digits) if digits else None
    return None


def _run(actor, payload, limit, max_usd):
    token = os.environ["APIFY_TOKEN"]
    r = requests.post(
        API.format(actor=actor),
        params={"token": token, "maxItems": limit, "maxTotalChargeUsd": max_usd, "timeout": 290},
        json=payload, timeout=320,
    )
    if r.status_code >= 400:
        raise RuntimeError(f"HTTP {r.status_code}: {r.text[:200]}")
    return r.json()


def _normalize(site, cfg, raw, models):
    out = []
    mp = cfg["map"]
    for it in raw:
        title = str(_pick(it, mp["title"]) or "")
        model = next((m for m in models if matches(m, title)), None)
        price = _num(_pick(it, mp["price"]))
        url = _pick(it, mp["url"])
        if not model or not price or not url:
            continue
        eur = to_eur(price, str(_pick(it, mp["cur"]) or "EUR").upper())
        if not eur or eur < model["lo"] * 0.3:
            continue
        cty = _pick(it, mp["cty"])
        out.append({
            "m": model["id"], "src": site, "title": title[:140], "p": round(eur), "url": url,
            "img": _pick(it, mp["img"]) if isinstance(_pick(it, mp["img"]), str) else None,
            "cty": cty if isinstance(cty, str) else "", "cond": "",
            "auction": cfg["auction"], "endDate": _pick(it, mp.get("end", [])) if cfg["auction"] else None,
        })
    return out


def fetch(models):
    if not os.environ.get("APIFY_TOKEN"):
        print("Apify: token mancante, salto la fonte")
        return None
    state = load("apify_state.json", {})
    every = float(os.environ.get("APIFY_EVERY_HOURS", 24))
    last = state.get("last")
    now = dt.datetime.now(dt.timezone.utc)
    if last and now - dt.datetime.fromisoformat(last) < dt.timedelta(hours=every):
        print(f"Apify: ultimo giro {last}, prossimo tra meno di {every:.0f} h")
        return "keep"

    DEBUG.mkdir(exist_ok=True)
    queries = [m["query"] for m in models]
    found, ok = [], 0
    for site, cfg in SITES.items():
        if not cfg["enabled"]:
            continue
        raw = []
        try:
            if cfg["batch"]:
                raw = _run(cfg["actor"], cfg["input"](queries), PER_QUERY * len(queries), MAX_USD_BATCH_RUN)
            else:
                for m in models:
                    raw += _run(cfg["actor"], cfg["input"](m["query"], m), PER_QUERY, MAX_USD_SINGLE_RUN)
            ok += 1
        except Exception as e:
            print(f"Apify {site}: errore {e}")
        (DEBUG / f"{site.lower().replace('.', '')}.json").write_text(
            json.dumps(raw[:3], ensure_ascii=False, indent=1), encoding="utf-8")  # campioni per affinare la lettura
        items = _normalize(site, cfg, raw, models)
        print(f"Apify {site}: {len(raw)} risultati, {len(items)} riconosciuti")
        found += items
    if not ok:
        raise RuntimeError("nessun robot Apify riuscito")
    save("apify_state.json", {"last": now.isoformat(timespec="seconds")})
    return found
