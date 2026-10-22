"""Foto con licenza libera da Wikimedia Commons, con autore e licenza.

Scrive _data/photos.json. Le foto scelte a mano in _data/photos_manual.json
hanno la precedenza (utile se la ricerca automatica trova immagini sbagliate).
"""
import html
import re
import time

import requests

from common import load, save

API = "https://commons.wikimedia.org/w/api.php"
HEADERS = {"User-Agent": "PatinaBot/1.0 (vintage watch market site; contact via GitHub)"}
FREE = re.compile(r"^(cc0|cc by|cc-by|public domain|pd)", re.I)


def _clean(s):
    return html.unescape(re.sub(r"<[^>]+>", "", s or "")).strip()


FAKE = re.compile(r"inspired|homage|hommage|replica|fake|tribute|\bmod\b|style", re.I)


def _query(q):
    params = {
        "action": "query", "format": "json",
        "generator": "search", "gsrnamespace": 6, "gsrlimit": 20,
        "gsrsearch": f"{q} filetype:bitmap",
        "prop": "imageinfo", "iiprop": "url|extmetadata", "iiurlwidth": 900,
    }
    r = requests.get(API, params=params, headers=HEADERS, timeout=30)
    r.raise_for_status()
    pages = (r.json().get("query") or {}).get("pages", {}).values()
    return sorted(pages, key=lambda x: x.get("index", 99))


def search(model, limit=6):
    """Prima foto della referenza esatta, poi della stessa famiglia (marca + nome)."""
    brand = model["brand"].lower().split()[0]
    name_words = [w for w in re.split(r"[\s-]+", model["name"].lower()) if len(w) > 3]
    first_name = model["name"].split()[0]
    queries = [f'{model["brand"]} {model["ref"]}', f'{model["brand"]} {model["name"]}', f'{model["brand"]} {first_name}']
    photos, seen = [], set()
    for q in queries:
        for p in _query(q):
            title = p.get("title", "").lower().replace("_", " ")
            if p.get("pageid") in seen or FAKE.search(title):
                continue
            exact = any(t.lower() in title for t in model["match"])
            family = brand in title and any(w in title for w in name_words)
            if not (exact or family):
                continue
            info = (p.get("imageinfo") or [{}])[0]
            meta = info.get("extmetadata", {})
            lic = _clean(meta.get("LicenseShortName", {}).get("value"))
            if not FREE.match(lic):
                continue
            seen.add(p.get("pageid"))
            photos.append({
                "src": info.get("thumburl") or info.get("url"),
                "page": info.get("descriptionurl"),
                "author": _clean(meta.get("Artist", {}).get("value"))[:80] or "Wikimedia Commons",
                "license": lic,
                "exact": exact,
            })
        if len(photos) >= limit:
            break
        time.sleep(0.5)
    photos.sort(key=lambda x: not x["exact"])  # referenza esatta prima
    return photos[:limit]


def run():
    models = load("models.json")
    manual = load("photos_manual.json", {})
    out = {}
    for m in models:
        try:
            auto = search(m)
        except Exception as e:  # una ricerca fallita non blocca le altre
            print(f"Commons {m['id']}: {e}")
            auto = []
        out[m["id"]] = manual.get(m["id"], []) + auto
        print(f"Commons {m['id']}: {len(out[m['id']])} foto")
        time.sleep(1)
    save("photos.json", out)


if __name__ == "__main__":
    run()
