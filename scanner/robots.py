"""Robot di Patina: leggono le pagine di ricerca pubbliche di Chrono24, Catawiki,
Kleinanzeigen, Subito e Leboncoin, una richiesta alla volta e con pause.

Ogni pagina viene letta in tre modi, dal più preciso al più generico:
1. i dati strutturati che il sito incorpora nella pagina (__NEXT_DATA__, JSON-LD);
2. i blocchi di annuncio nell'HTML (link all'annuncio + prezzo vicino);
Se un sito risponde con un blocco (403, CAPTCHA) il robot non insiste e passa oltre.

Quando un sito non dà risultati, la pagina ricevuta viene salvata in scanner/debug/
per poter correggere il robot.
"""
import json
import pathlib
import random
import re
import time
from urllib.parse import quote, quote_plus, urljoin

import requests
from bs4 import BeautifulSoup

from common import matches, to_eur

DEBUG = pathlib.Path(__file__).resolve().parent / "debug"
PAUSE = (2.0, 4.0)  # secondi tra una richiesta e l'altra

SITES = {
    "Kleinanzeigen": {
        "url": lambda q: f"https://www.kleinanzeigen.de/s-{quote(q.lower().replace(' ', '-'))}/k0",
        "item": re.compile(r"/s-anzeige/[^\"'?#]+/\d+"), "lang": "de-DE,de;q=0.9", "cty": "DE", "auction": False,
    },
    "Subito.it": {
        "url": lambda q: f"https://www.subito.it/annunci-italia/vendita/usato/?q={quote_plus(q)}",
        "item": re.compile(r"subito\.it/[a-z\-]+/[^\"'?#]*-\d+\.htm"), "lang": "it-IT,it;q=0.9", "cty": "IT", "auction": False,
    },
    "Leboncoin": {
        "url": lambda q: f"https://www.leboncoin.fr/recherche?text={quote_plus(q)}",
        "item": re.compile(r"/ad/[a-z_]+/\d+|leboncoin\.fr/[a-z_]+/\d+\.htm"), "lang": "fr-FR,fr;q=0.9", "cty": "FR", "auction": False,
    },
    "Chrono24": {
        "url": lambda q: f"https://www.chrono24.de/search/index.htm?dosearch=true&query={quote_plus(q)}",
        "item": re.compile(r"--id\d+\.htm"), "lang": "de-DE,de;q=0.9", "cty": "", "auction": False,
    },
    "Catawiki": {
        "url": lambda q: f"https://www.catawiki.com/en/s?q={quote_plus(q)}",
        "item": re.compile(r"/l/\d+"), "lang": "en-GB,en;q=0.9", "cty": "", "auction": True,
    },
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}
BLOCKED = ("captcha", "datadome", "cf-chl", "access denied", "are you a robot", "bot protection", "px-captcha")

PRICE_TXT = re.compile(
    r"(?:(€|EUR|CHF)\s*(\d{1,3}(?:[.\s'’,]\d{3})+|\d{3,7}))|(?:(\d{1,3}(?:[.\s'’,]\d{3})+|\d{3,7})(?:[.,]\d{2})?\s*(€|EUR|CHF))", re.I)
TITLE_KEYS = ("title", "subject", "name", "headline")
PRICE_KEYS = ("price", "bid", "amount")
END_KEY = re.compile(r"(bidding)?_?end(s)?_?(at|time|date)|closing|close_?at", re.I)
ISO = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}")


# ---------- utilità ----------
def _num(v):
    if isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        m = PRICE_TXT.search(v)
        if m:
            return float(re.sub(r"\D", "", m.group(2) or m.group(3)))
        d = re.sub(r"[^\d]", "", v.split(",")[0])
        return float(d) if d and len(d) <= 7 else None
    return None


def _first_price(obj, depth=0):
    """Primo numero plausibile dentro un sotto-albero il cui nome parla di prezzo/offerta."""
    if depth > 5:
        return None
    if isinstance(obj, dict):
        for k, v in obj.items():
            if any(p in k.lower() for p in PRICE_KEYS) and "shipping" not in k.lower():
                n = _deep_num(v)
                if n:
                    return n
        for v in obj.values():
            if isinstance(v, (dict, list)):
                n = _first_price(v, depth + 1)
                if n:
                    return n
    elif isinstance(obj, list):
        for v in obj[:5]:
            n = _first_price(v, depth + 1)
            if n:
                return n
    return None


def _deep_num(v, depth=0):
    if depth > 4:
        return None
    n = _num(v)
    if n and n >= 100:
        return n
    if isinstance(v, dict):
        for k in ("value", "amount", "key", "raw", "cents"):
            if k in v:
                n = _deep_num(v[k], depth + 1)
                if n:
                    return n / 100 if k == "cents" else n
        for x in v.values():
            n = _deep_num(x, depth + 1)
            if n:
                return n
    if isinstance(v, list) and v:
        return _deep_num(v[0], depth + 1)
    return None


def _strings(obj, depth=0):
    if depth > 4:
        return
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from _strings(v, depth + 1)
    elif isinstance(obj, list):
        for v in obj[:8]:
            yield from _strings(v, depth + 1)


def _image(obj):
    for s in _strings(obj):
        if s.startswith("http") and re.search(r"\.(jpe?g|png|webp)|image|img|photo|cdn", s, re.I):
            return s
    return None


def _end(obj, depth=0):
    if depth > 3 or not isinstance(obj, dict):
        return None
    for k, v in obj.items():
        if END_KEY.search(k) and isinstance(v, str) and ISO.match(v):
            return v
        if END_KEY.search(k) and isinstance(v, (int, float)) and v > 1.6e9:
            ts = v / 1000 if v > 1e12 else v
            return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts))
    for v in obj.values():
        if isinstance(v, dict):
            r = _end(v, depth + 1)
            if r:
                return r
    return None


# ---------- 1. dati strutturati nella pagina ----------
def _harvest(obj, pattern, base, out, depth=0):
    """Cerca nel JSON gli oggetti che sembrano annunci: hanno un titolo, un link all'annuncio e un prezzo."""
    if depth > 14:
        return
    if isinstance(obj, dict):
        title = next((obj[k] for k in TITLE_KEYS if isinstance(obj.get(k), str) and len(obj[k]) > 4), None)
        if title:
            url = next((s for s in _strings(obj) if pattern.search(s)), None)
            price = _first_price(obj)
            if url and price:
                out.append({"title": title, "url": urljoin(base, url), "price": price,
                            "img": _image(obj.get("images") or obj.get("image") or obj.get("pictures") or obj),
                            "end": _end(obj)})
                return
        for v in obj.values():
            if isinstance(v, (dict, list)):
                _harvest(v, pattern, base, out, depth + 1)
    elif isinstance(obj, list):
        for v in obj:
            _harvest(v, pattern, base, out, depth + 1)


def _structured(soup, pattern, base):
    out = []
    nd = soup.find("script", id="__NEXT_DATA__")
    blobs = [nd.string] if nd and nd.string else []
    blobs += [s.string for s in soup.find_all("script", type="application/ld+json") if s.string]
    for b in blobs:
        try:
            _harvest(json.loads(b), pattern, base, out)
        except (ValueError, TypeError):
            continue
    return out


# ---------- 2. blocchi di annuncio nell'HTML ----------
def _html_cards(soup, pattern, base):
    out = []
    for a in soup.find_all("a", href=True):
        if not pattern.search(a["href"]):
            continue
        node, text = a, a.get_text(" ", strip=True)
        for _ in range(6):
            if node.parent is None:
                break
            node = node.parent
            text = node.get_text(" ", strip=True)
            if PRICE_TXT.search(text) or len(text) > 600:
                break
        m = PRICE_TXT.search(text)
        if not m or len(text) > 800:
            continue
        img = node.find("img")
        src = img and (img.get("src") or img.get("data-src") or img.get("data-imgsrc"))
        out.append({"title": a.get("title") or a.get_text(" ", strip=True) or text[:140], "text": text,
                    "url": urljoin(base, a["href"]), "price": _num(m.group(0)),
                    "img": src if src and src.startswith("http") else None, "end": None})
    return out


# ---------- giro completo ----------
def _get(session, url, lang):
    r = session.get(url, headers={**HEADERS, "Accept-Language": lang}, timeout=25)
    low = r.text[:5000].lower()
    blocked = r.status_code in (401, 403, 429) or any(b in low for b in BLOCKED)
    return r, blocked


def fetch_site(site, models, session):
    cfg = SITES[site]
    found, blocked_hits, sample = [], 0, None
    for m in models:
        url = cfg["url"](m["query"])
        try:
            r, blocked = _get(session, url, cfg["lang"])
        except requests.RequestException as e:
            print(f"{site} {m['id']}: {e}")
            continue
        if blocked:
            blocked_hits += 1
            sample = sample or r
            if blocked_hits >= 2:  # il sito ci blocca: non insisto
                print(f"{site}: bloccato (HTTP {r.status_code}), salto il resto")
                break
            continue
        soup = BeautifulSoup(r.text, "html.parser")
        raw = _structured(soup, cfg["item"], url) or _html_cards(soup, cfg["item"], url)
        if not raw:
            sample = sample or r
        for it in raw:
            text = f'{it["title"]} {it.get("text", "")}'
            if not matches(m, text) or not it["price"]:
                continue
            eur = to_eur(it["price"], "CHF" if "CHF" in it.get("text", "") else "EUR")
            if not eur or eur < m["lo"] * 0.3 or eur > m["hi"] * 4:
                continue
            found.append({
                "m": m["id"], "src": site, "title": PRICE_TXT.sub("", it["title"]).strip(" ·-")[:140], "p": round(eur),
                "url": it["url"].split("?")[0], "img": it["img"], "cty": cfg["cty"], "cond": "",
                "auction": cfg["auction"], "endDate": it["end"] if cfg["auction"] else None,
            })
        time.sleep(random.uniform(*PAUSE))
    if sample is not None:
        DEBUG.mkdir(exist_ok=True)
        (DEBUG / f"{site.lower().replace('.', '')}.html").write_text(
            f"<!-- HTTP {sample.status_code} {sample.url} -->\n" + sample.text[:200000], encoding="utf-8")
    if blocked_hits >= 2 and not found:
        raise RuntimeError("bloccato dal sito")
    return found


def fetch(models):
    session = requests.Session()
    found, ok = [], 0
    for site in SITES:
        try:
            items = fetch_site(site, models, session)
            ok += 1
            print(f"Robot {site}: {len(items)} annunci riconosciuti")
            found += items
        except Exception as e:
            print(f"Robot {site}: {e}")
    if not ok:
        raise RuntimeError("tutti i siti hanno bloccato i robot")
    return found
