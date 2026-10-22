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


def search(model, limit=6):
    params = {
        "action": "query", "format": "json",
        "generator": "search", "gsrnamespace": 6, "gsrlimit": 15,
        "gsrsearch": f'{model["brand"]} {model["ref"]} filetype:bitmap',
        "prop": "imageinfo", "iiprop": "url|extmetadata", "iiurlwidth": 900,
    }
    r = requests.get(API, params=params, headers=HEADERS, timeout=30)
    r.raise_for_status()
    pages = (r.json().get("query") or {}).get("pages", {}).values()
    brand = model["brand"].lower().split()[0]
    photos = []
    for p in sorted(pages, key=lambda x: x.get("index", 99)):
        title = p.get("title", "").lower()
        has_ref = any(t.lower() in title for t in model["match"])
        has_name = brand in title and model["name"].lower().split()[0] in title
        if not (has_ref or has_name):
            continue  # scarta foto che non nominano referenza o marca+modello
        info = (p.get("imageinfo") or [{}])[0]
        meta = info.get("extmetadata", {})
        lic = _clean(meta.get("LicenseShortName", {}).get("value"))
        if not FREE.match(lic):
            continue
        photos.append({
            "src": info.get("thumburl") or info.get("url"),
            "page": info.get("descriptionurl"),
            "author": _clean(meta.get("Artist", {}).get("value"))[:80] or "Wikimedia Commons",
            "license": lic,
        })
        if len(photos) >= limit:
            break
    return photos


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
