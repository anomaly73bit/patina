"""Fonte: avvisi email dei siti di annunci e aste, letti da una casella dedicata (IMAP).

Su ogni sito si salva una ricerca per referenza con avviso via email verso la
casella di Patina. Questo modulo legge le email degli ultimi giorni, trova i
link agli annunci, riconosce l'orologio dal testo e prende prezzo e foto.

Secret del repository: IMAP_USER, IMAP_PASSWORD (facoltativo IMAP_HOST, default posteo.de).
"""
import datetime as dt
import email
import email.utils
import imaplib
import os
import re
from email.header import decode_header, make_header
from urllib.parse import urlsplit, urlunsplit

import requests
from bs4 import BeautifulSoup

from common import matches, to_eur

DAYS = 14  # un annuncio arrivato via avviso resta al massimo 14 giorni, se nel frattempo non risulta venduto

# dominio del mittente o del link -> (nome fonte, è un'asta?)
SITES = {
    "chrono24": ("Chrono24", False),
    "catawiki": ("Catawiki", True),
    "kleinanzeigen": ("Kleinanzeigen", False),
    "subito": ("Subito.it", False),
    "leboncoin": ("Leboncoin", False),
    "bazos": ("Bazoš", False),
    "sbazar": ("Sbazar", False),
    "dorotheum": ("Dorotheum", True),
    "antiquorum": ("Antiquorum", True),
    "phillips": ("Phillips", True),
    "orologiepassioni": ("Orologi&Passioni", False),
}

PRICE = re.compile(
    r"(?:(?P<c1>€|EUR|CHF|Kč|CZK|£|GBP)\s*(?P<n1>\d{1,3}(?:[.\s'’]\d{3})+|\d{3,7})(?:[.,]\d{2})?)"
    r"|(?:(?P<n2>\d{1,3}(?:[.\s'’]\d{3})+|\d{3,7})(?:[.,]\d{2})?\s*(?P<c2>€|EUR|CHF|Kč|CZK|£|GBP))",
    re.I,
)
CUR = {"€": "EUR", "eur": "EUR", "chf": "CHF", "kč": "CZK", "czk": "CZK", "£": "GBP", "gbp": "GBP"}
UA = {"User-Agent": "Mozilla/5.0 (compatible; PatinaBot/1.0)"}


def _site(text):
    t = (text or "").lower()
    for key, val in SITES.items():
        if key in t:
            return val
    return None


def _clean_url(u):
    """Toglie i parametri di tracciamento (utm, ecc.) per riconoscere i doppioni."""
    p = urlsplit(u)
    return urlunsplit((p.scheme, p.netloc, p.path, "", ""))


def _price(text):
    for m in PRICE.finditer(text):
        num = (m.group("n1") or m.group("n2"))
        cur = CUR.get((m.group("c1") or m.group("c2")).lower())
        value = int(re.sub(r"\D", "", num))
        if value >= 300 and cur:
            return value, cur
    return None


def _decode(h):
    try:
        return str(make_header(decode_header(h or "")))
    except Exception:
        return h or ""


def _html(msg):
    for part in msg.walk():
        if part.get_content_type() == "text/html":
            return part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8", "replace")
    return None


def parse_email(msg, models):
    """Restituisce gli annunci trovati in una email di avviso."""
    sender = _decode(msg.get("From"))
    default_site = _site(sender)
    html = _html(msg)
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    date = email.utils.parsedate_to_datetime(msg.get("Date")) if msg.get("Date") else dt.datetime.now(dt.timezone.utc)
    out = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        site = _site(urlsplit(href).netloc) or default_site
        if not site or not href.startswith("http"):
            continue
        # risale finché il blocco contiene titolo e prezzo, senza prendere tutta l'email
        node, text = a, a.get_text(" ", strip=True)
        for _ in range(6):
            if node.parent is None:
                break
            node = node.parent
            text = node.get_text(" ", strip=True)
            if _price(text) or len(text) > 500:
                break
        if len(text) > 700:
            continue
        model = next((m for m in models if matches(m, text)), None)
        price = _price(text)
        if not model or not price:
            continue
        eur = to_eur(*price)
        img = node.find("img")
        out.append({
            "m": model["id"],
            "src": site[0],
            "title": a.get_text(" ", strip=True)[:140] or text[:140],
            "p": round(eur),
            "url": _clean_url(href),
            "img": img.get("src") if img and img.get("src", "").startswith("http") else None,
            "cty": "",
            "cond": "",
            "auction": site[1],
            "mailDate": date.isoformat(),
        })
    return out


def _alive(url):
    """False se il sito dice che l'annuncio non esiste più (404/410 o pagina di annuncio rimosso)."""
    try:
        r = requests.get(url, headers=UA, timeout=15, allow_redirects=True)
    except requests.RequestException:
        return True  # sito non raggiungibile: nel dubbio lo tengo
    if r.status_code in (404, 410):
        return False
    body = r.text[:20000].lower() if r.status_code == 200 else ""
    gone = ("nicht mehr verfügbar", "anzeige wurde gelöscht", "non è più disponibile", "annuncio non disponibile",
            "n'est plus disponible", "annonce n'existe plus", "inzerát byl smazán", "no longer available")
    return not any(g in body for g in gone)


def fetch(models):
    user, pwd = os.environ.get("IMAP_USER"), os.environ.get("IMAP_PASSWORD")
    if not user or not pwd:
        print("Avvisi email: casella non configurata, salto la fonte")
        return None
    host = os.environ.get("IMAP_HOST", "posteo.de")
    since = (dt.date.today() - dt.timedelta(days=DAYS)).strftime("%d-%b-%Y")
    box = imaplib.IMAP4_SSL(host, 993)
    box.login(user, pwd)
    box.select("INBOX", readonly=True)
    _, ids = box.search(None, f'(SINCE "{since}")')
    found, seen = [], set()
    for num in ids[0].split():
        _, data = box.fetch(num, "(RFC822)")
        msg = email.message_from_bytes(data[0][1])
        for l in parse_email(msg, models):
            if l["url"] not in seen:
                seen.add(l["url"])
                found.append(l)
    box.logout()
    alive = [l for l in found if _alive(l["url"])]
    print(f"Avvisi email: {len(found)} annunci nelle email, {len(alive)} ancora attivi")
    return alive
