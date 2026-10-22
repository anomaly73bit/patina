"""Robot di Patina: leggono le pagine di ricerca pubbliche dei siti di annunci e aste
in tutta Europa (elenco in SITES), una richiesta alla volta e con pause.

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
PAUSE = (1.5, 3.0)  # secondi tra una richiesta e l'altra

def _h(url, item, lang, cty, cur="EUR", auction=False):
    """Sito letto dalla pagina HTML di ricerca."""
    return {"kind": "html", "url": url, "item": re.compile(item), "lang": lang, "cty": cty, "cur": cur, "auction": auction}


def _olx(domain, lang, cty, cur):
    """Siti OLX: stessa piattaforma in più paesi, con dati di ricerca pubblici in JSON."""
    return {"kind": "olx", "url": lambda q: f"https://www.{domain}/api/v1/offers/?offset=0&limit=40&query={quote(q)}",
            "lang": lang, "cty": cty, "cur": cur, "auction": False}


def _mp(domain, lang, cty):
    """Marktplaats e 2dehands: stessa piattaforma, ricerca pubblica in JSON."""
    return {"kind": "marktplaats", "base": f"https://www.{domain}",
            "url": lambda q: f"https://www.{domain}/lrp/api/search?query={quote_plus(q)}&limit=30",
            "lang": lang, "cty": cty, "cur": "EUR", "auction": False}


q_slug = lambda q: quote(q.lower().replace(" ", "-"))
# Bloccano le richieste dai server di GitHub (HTTP 403, verificato il 22/10/2026):
# Chrono24, Catawiki, Subito, Leboncoin, Ricardo, Tutti, OLX (PL, RO, BG, UA, PT), Aukro, Jófogás, Vatera.
# Si possono riprovare da una connessione domestica.
SITES = {
    # Europa occidentale
    "Kleinanzeigen": _h(lambda q: f"https://www.kleinanzeigen.de/s-{q_slug(q)}/k0", r"/s-anzeige/[^\"'?#]+/\d+", "de-DE,de;q=0.9", "DE"),
    "Willhaben": _h(lambda q: f"https://www.willhaben.at/iad/kaufen-und-verkaufen/marktplatz?keyword={quote_plus(q)}", r"/iad/kaufen-und-verkaufen/d/[^\"'?#]+", "de-AT,de;q=0.9", "AT"),
    "Marktplaats": _mp("marktplaats.nl", "nl-NL,nl;q=0.9", "NL"),
    "2dehands": _mp("2dehands.be", "nl-BE,nl;q=0.9", "BE"),
    # Europa dell'Est
    "Bazoš CZ": _h(lambda q: f"https://www.bazos.cz/search.php?hledat={quote_plus(q)}&rubriky=www&Submit=Hledat", r"/inzerat/\d+/", "cs-CZ,cs;q=0.9", "CZ", "CZK"),
    "Bazoš SK": _h(lambda q: f"https://www.bazos.sk/search.php?hledat={quote_plus(q)}&rubriky=www&Submit=H%C4%BEada%C5%A5", r"/inzerat/\d+/", "sk-SK,sk;q=0.9", "SK"),
    "Bolha": _h(lambda q: f"https://www.bolha.com/?ctl=search_ads&keywords={quote_plus(q)}", r"-oglas-\d+", "sl-SI,sl;q=0.9", "SI"),
    # Scandinavia
    "Blocket": _h(lambda q: f"https://www.blocket.se/annonser/hela_sverige?q={quote_plus(q)}", r"/annons/[^\"'?#]+/\d+|/recommerce/forsale/item/\d+", "sv-SE,sv;q=0.9", "SE", "SEK"),
    "DBA": _h(lambda q: f"https://www.dba.dk/soeg/?soeg={quote_plus(q)}", r"dba\.dk/[^\"'?#]+/id-\d+|/recommerce/forsale/item/\d+", "da-DK,da;q=0.9", "DK", "DKK"),
    "Tori": _h(lambda q: f"https://www.tori.fi/recommerce/forsale/search?q={quote_plus(q)}", r"/recommerce/forsale/item/\d+", "fi-FI,fi;q=0.9", "FI"),
    "Finn": _h(lambda q: f"https://www.finn.no/recommerce/forsale/search?q={quote_plus(q)}", r"/recommerce/forsale/item/\d+|/bap/forsale/ad\.html\?finnkode=\d+", "nb-NO,nb;q=0.9", "NO", "NOK"),
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}
BLOCKED = ("captcha", "datadome", "cf-chl", "access denied", "are you a robot", "bot protection", "px-captcha")

CUR_TOK = r"€|EUR|CHF|Fr\.|Kč|CZK|zł|PLN|lei|RON|лв\.?|BGN|Ft|HUF|kr\.?|SEK|DKK|NOK|£|GBP|грн\.?|UAH"
NUM = r"(?<!\d)(?:\d{1,3}(?:[.\s'’,\u00a0]\d{3})+|\d{3,8})"
PRICE_TXT = re.compile(rf"(?:({CUR_TOK})\s*({NUM}))|(?:({NUM})(?:[.,]\d{{2}})?\s*({CUR_TOK}))", re.I)
TOK2ISO = {"€": "EUR", "eur": "EUR", "chf": "CHF", "fr.": "CHF", "kč": "CZK", "czk": "CZK", "zł": "PLN", "pln": "PLN",
           "lei": "RON", "ron": "RON", "лв": "BGN", "лв.": "BGN", "bgn": "BGN", "ft": "HUF", "huf": "HUF", "sek": "SEK",
           "dkk": "DKK", "nok": "NOK", "£": "GBP", "gbp": "GBP", "грн": "UAH", "грн.": "UAH", "uah": "UAH"}


CUR_FIRST = re.compile(rf"({CUR_TOK})\s*({NUM})", re.I)
NUM_FIRST = re.compile(rf"({NUM})(?:[.,]\d{{2}})?\s*({CUR_TOK})", re.I)


def _price_cur(text, default):
    """(valore, valuta) dal testo. Tra i numeri vicini a una valuta prende il più alto,
    così una referenza come «2447 CHF 9'800» non viene scambiata per il prezzo.
    'kr' prende la corona del paese del sito."""
    cands = [(m.group(2), m.group(1)) for m in CUR_FIRST.finditer(text or "")]
    cands += [(m.group(1), m.group(2)) for m in NUM_FIRST.finditer(text or "")]
    best = None
    for num, tok in cands:
        v = float(re.sub(r"\D", "", num))
        if best is None or v > best[0]:
            best = (v, TOK2ISO.get(tok.lower(), default))
    return best if best else (None, default)


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
        # titolo: intestazione dell'annuncio, altrimenti il testo più lungo tra i link allo stesso annuncio
        head = node.find(["h2", "h3"])
        links = [x.get_text(" ", strip=True) for x in node.find_all("a", href=a["href"])]
        title = (head.get_text(" ", strip=True) if head else "") or max(links + [a.get("title") or ""], key=len)
        if len(title) < 6:
            continue
        price, cur = _price_cur(text, None)
        out.append({"title": title, "text": text, "cur": cur,
                    "url": urljoin(base, a["href"]), "price": price,
                    "img": src if src and src.startswith("http") else None, "end": None})
    return out


# ---------- 3. siti con ricerca pubblica in JSON ----------
def _api_items(cfg, r):
    try:
        data = r.json()
    except ValueError:
        return []
    out = []
    if cfg["kind"] == "olx":
        for o in data.get("data", []):
            price = next((p.get("value", {}) for p in o.get("params", []) if p.get("key") == "price"), {})
            photo = (o.get("photos") or [{}])[0].get("link", "")
            out.append({"title": o.get("title", ""), "url": o.get("url", ""),
                        "price": _num(price.get("value")), "cur": price.get("currency") or cfg["cur"],
                        "img": photo.replace("{width}", "600").replace("{height}", "450") or None, "end": None,
                        "city": ((o.get("location") or {}).get("city") or {}).get("name")})
    elif cfg["kind"] == "marktplaats":
        for o in data.get("listings", []):
            cents = (o.get("priceInfo") or {}).get("priceCents")
            pics = o.get("pictures") or [{}]
            out.append({"title": o.get("title", ""), "url": urljoin(cfg["base"], o.get("vipUrl", "")),
                        "price": cents / 100 if cents else None, "cur": "EUR",
                        "img": pics[0].get("mediumUrl") or pics[0].get("largeUrl"), "end": None,
                        "city": (o.get("location") or {}).get("cityName")})
    return out


# ---------- giro completo ----------
def _get(session, url, lang):
    accept = {"Accept": "application/json, text/plain, */*"} if "/api/" in url else {}
    r = session.get(url, headers={**HEADERS, **accept, "Accept-Language": lang}, timeout=25)
    low = r.text[:5000].lower()
    blocked = r.status_code in (401, 403, 429) or any(b in low for b in BLOCKED)
    return r, blocked


def fetch_site(site, models, session):
    cfg = SITES[site]
    found, blocked_hits, sample, ok_sample = [], 0, None, None
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
        if cfg["kind"] == "html":
            soup = BeautifulSoup(r.text, "html.parser")
            raw = _structured(soup, cfg["item"], url) or _html_cards(soup, cfg["item"], url)
        else:
            raw = _api_items(cfg, r)
        if not raw:
            sample = sample or r
        elif ok_sample is None:
            ok_sample = r
        for it in raw:
            if not matches(m, it["title"]) or not it["price"]:  # solo il titolo: la descrizione cita spesso altre referenze
                continue
            eur = to_eur(it["price"], it.get("cur") or cfg["cur"])
            if not eur or eur < m["lo"] * 0.4 or eur > m["hi"] * 4:
                continue
            found.append({
                "m": m["id"], "src": site, "title": PRICE_TXT.sub("", it["title"]).strip(" ·-")[:140], "p": round(eur),
                "url": it["url"].split("?")[0], "img": it["img"],
                "cty": f'{cfg["cty"]} · {it["city"]}' if it.get("city") else cfg["cty"], "cond": "",
                "auction": cfg["auction"], "endDate": it["end"] if cfg["auction"] else None,
            })
        time.sleep(random.uniform(*PAUSE))
    if sample is not None:
        DEBUG.mkdir(exist_ok=True)
        (DEBUG / f"{site.lower().replace('.', '')}.html").write_text(
            f"<!-- HTTP {sample.status_code} {sample.url} -->\n" + sample.text[:200000], encoding="utf-8")
    if ok_sample is not None:  # una pagina con risultati, per affinare la lettura
        DEBUG.mkdir(exist_ok=True)
        (DEBUG / f"{site.lower().replace('.', '')}_ok.html").write_text(
            f"<!-- HTTP {ok_sample.status_code} {ok_sample.url} -->\n" + ok_sample.text[:300000], encoding="utf-8")
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
