"""Fonte eBay tramite Browse API ufficiale.

Serve un'app gratuita su https://developer.ebay.com (chiavi Production):
imposta i secret del repository EBAY_CLIENT_ID e EBAY_CLIENT_SECRET.
"""
import base64
import os

import requests

from common import matches, to_eur

TOKEN_URL = "https://api.ebay.com/identity/v1/oauth2/token"
SEARCH_URL = "https://api.ebay.com/buy/browse/v1/item_summary/search"
MARKETS = {"EBAY_DE": "eBay.de", "EBAY_IT": "eBay.it", "EBAY_FR": "eBay.fr"}
WRISTWATCHES = "31387"  # categoria eBay "Orologi da polso"


def _token():
    cid, secret = os.environ.get("EBAY_CLIENT_ID"), os.environ.get("EBAY_CLIENT_SECRET")
    if not cid or not secret:
        return None
    auth = base64.b64encode(f"{cid}:{secret}".encode()).decode()
    r = requests.post(
        TOKEN_URL,
        headers={"Authorization": f"Basic {auth}", "Content-Type": "application/x-www-form-urlencoded"},
        data={"grant_type": "client_credentials", "scope": "https://api.ebay.com/oauth/api_scope"},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()["access_token"]


def fetch(models):
    token = _token()
    if not token:
        print("eBay: chiavi mancanti, salto la fonte")
        return None
    out, ok_calls = [], 0
    for market, label in MARKETS.items():
        for m in models:
            min_price = int(m["lo"] * 0.3)  # sotto il 30% della stima è quasi sempre un ricambio
            r = requests.get(
                SEARCH_URL,
                headers={"Authorization": f"Bearer {token}", "X-EBAY-C-MARKETPLACE-ID": market},
                params={
                    "q": m["query"],
                    "category_ids": WRISTWATCHES,
                    "filter": f"price:[{min_price}..],priceCurrency:EUR",
                    "limit": 50,
                },
                timeout=30,
            )
            if r.status_code != 200:
                print(f"eBay {market} {m['id']}: HTTP {r.status_code}")
                continue
            ok_calls += 1
            for it in r.json().get("itemSummaries", []):
                title = it.get("title", "")
                if not matches(m, title):
                    continue
                price = it.get("currentBidPrice") or it.get("price") or {}
                eur = to_eur(price.get("value", 0), price.get("currency", "EUR"))
                if not eur:
                    continue
                auction = "AUCTION" in it.get("buyingOptions", [])
                out.append({
                    "m": m["id"],
                    "src": label,
                    "title": title,
                    "p": round(eur),
                    "url": it.get("itemWebUrl"),
                    "img": (it.get("image") or {}).get("imageUrl"),
                    "cty": (it.get("itemLocation") or {}).get("country", ""),
                    "cond": it.get("condition", ""),
                    "auction": auction,
                    "endDate": it.get("itemEndDate") if auction else None,
                })
    if not ok_calls:
        raise RuntimeError("nessuna ricerca eBay riuscita")
    return out
