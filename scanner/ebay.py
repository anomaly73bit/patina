"""Fonte eBay tramite Browse API ufficiale.

Serve un'app gratuita su https://developer.ebay.com (chiavi Production):
imposta i secret del repository EBAY_CLIENT_ID e EBAY_CLIENT_SECRET.
"""
import base64
import os

import requests

from common import FX, matches, to_eur

TOKEN_URL = "https://api.ebay.com/identity/v1/oauth2/token"
SEARCH_URL = "https://api.ebay.com/buy/browse/v1/item_summary/search"
# mercato -> (nome fonte, valuta del mercato)
MARKETS = {"EBAY_DE": ("eBay.de", "EUR"), "EBAY_IT": ("eBay.it", "EUR"), "EBAY_FR": ("eBay.fr", "EUR"),
           "EBAY_AT": ("eBay.at", "EUR"), "EBAY_NL": ("eBay.nl", "EUR"), "EBAY_ES": ("eBay.es", "EUR"),
           "EBAY_CH": ("eBay.ch", "CHF"), "EBAY_GB": ("eBay.co.uk", "GBP")}
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
    for market, (label, cur) in MARKETS.items():
        for m in models:
            min_price = int(m["lo"] * 0.4 / FX[cur])  # sotto il 40% della stima è quasi sempre un ricambio o un falso
            r = requests.get(
                SEARCH_URL,
                headers={"Authorization": f"Bearer {token}", "X-EBAY-C-MARKETPLACE-ID": market},
                params={
                    "q": m["query"],
                    "category_ids": WRISTWATCHES,
                    "filter": f"price:[{min_price}..],priceCurrency:{cur},buyingOptions:{{FIXED_PRICE}}",  # niente aste
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
                if "FIXED_PRICE" not in it.get("buyingOptions", []):
                    continue
                auction = False
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
                    "posted": it.get("itemCreationDate") or it.get("itemOriginDate"),
                    "desc": it.get("shortDescription"),
                })
    if not ok_calls:
        raise RuntimeError("nessuna ricerca eBay riuscita")
    return out
