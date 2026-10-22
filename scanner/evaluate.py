"""Valutazione di ogni annuncio, come farebbe un esperto.

Per ogni annuncio stabilisce:
- la versione dell'orologio (le serie di uno stesso modello valgono cifre diverse);
- il valore per QUESTO annuncio, corretto con i segnali della descrizione
  (difettoso, quadrante rifatto, pezzi non originali, set completo...);
- la fiducia (quante informazioni abbiamo, da quanto è online);
- il verdetto: occasione, prezzo giusto, caro, da verificare, sospetto;
- i motivi, mostrati sul sito.
"""
import datetime as dt
import re

# segnali nella descrizione: (nome, espressione, correzione del valore, testo per il sito)
SIGNALS = [
    ("difettoso", r"defekt|läuft nicht|funktioniert nicht|kaputt|stehen geblieben|for repair|not working|da riparare|non funziona|"
                  r"guasto|défectueux|ne fonctionne pas|en panne|niet werkend|defect|kapot|nefunkční|nejde|revisionsbedürftig|needs service",
     -0.35, "risulta difettoso o da revisionare"),
    ("rifatto", r"redial|service ?dial|neues zifferblatt|ersatzzifferblatt|quadrante rifatto|quadrante non originale|cadran refait|"
                r"restauriert|restored|refinished|nicht original|non originale|pas d'origine|niet origineel|aftermarket|ersatzteil|"
                r"zeiger erneuert|lancette sostituite",
     -0.40, "quadrante o parti non originali"),
    ("senza documenti", r"ohne papiere|ohne box|keine papiere|no papers|no box|senza scatola|senza documenti|senza garanzia|"
                        r"sans papiers|sans boîte|zonder papieren|zonder doos|bez dokladů|bez krabičky",
     -0.08, "senza scatola o documenti"),
    ("set completo", r"box und papiere|box & papiere|mit papieren|full set|fullset|scatola e garanzia|scatola e documenti|"
                     r"boîte et papiers|avec papiers|met doos en papieren|originalbox|extract from the archives|estratto d'archivio|stammbuchauszug",
     +0.10, "con scatola e documenti"),
    ("revisionato", r"revidiert|revision(?:iert)? 20[12]\d|serviced|revisionato|révisé|gereviseerd|frisch revidiert",
     +0.03, "revisionato di recente"),
]
SIGNALS = [(n, re.compile(r, re.I), adj, txt) for n, r, adj, txt in SIGNALS]

YEAR = re.compile(r"\b(19[4-9]\d|200\d)\b")

MONTHS = {"jan": 1, "feb": 2, "mrt": 3, "mar": 3, "mär": 3, "apr": 4, "mei": 5, "mai": 5, "may": 5, "jun": 6, "jul": 7,
          "aug": 8, "sep": 9, "okt": 10, "oct": 10, "nov": 11, "dec": 12, "dez": 12}


def parse_date(text, today=None):
    """Data di pubblicazione da testi come '15.10.2026', '30 aug 26', 'Heute', 'Gisteren', ISO."""
    today = today or dt.date.today()
    if not text:
        return None
    t = str(text).lower()
    if re.search(r"\b(heute|vandaag|today|oggi|aujourd'hui|dnes|tänään|i dag|idag)\b", t):
        return today
    if re.search(r"\b(gestern|gisteren|yesterday|ieri|hier|včera|eilen|i går|igår)\b", t):
        return today - dt.timedelta(days=1)
    m = re.search(r"\b(\d{4})-(\d{2})-(\d{2})", t)
    if m:
        return dt.date(int(m[1]), int(m[2]), int(m[3]))
    m = re.search(r"\b(\d{1,2})\.(\d{1,2})\.(\d{2,4})\b", t)
    if m:
        y = int(m[3]) + (2000 if len(m[3]) == 2 else 0)
        try:
            return dt.date(y, int(m[2]), int(m[1]))
        except ValueError:
            return None
    m = re.search(r"\b(\d{1,2})\s+([a-zä]{3})[a-z.]*\s+'?(\d{2,4})\b", t)
    if m and m[2] in MONTHS:
        y = int(m[3]) + (2000 if len(m[3]) == 2 else 0)
        try:
            return dt.date(y, MONTHS[m[2]], int(m[1]))
        except ValueError:
            return None
    return None


def read_signals(desc):
    """Segnali ricavati da una descrizione: nomi dei segnali trovati e anno. È quello che resta in memoria."""
    return {"sig": [n for n, rx, _, _ in SIGNALS if rx.search(desc)], "year": (YEAR.search(desc) or [""])[0]}


def variant(model, text):
    """La serie dell'orologio dal titolo (le descrizioni sono troppo ambigue: in tedesco "gilt" vuol dire "vale")."""
    for v in model.get("variants", []):
        if re.search(v["kw"], text, re.I):
            return v["name"], v["lo"], v["hi"]
    return None, model["lo"], model["hi"]


def evaluate(listing, model, today=None):
    today = today or dt.date.today()
    title = listing.get("title", "")
    desc = listing.get("desc") or ""
    reasons, conf = [], 2  # fiducia: 0 bassa … 4 alta

    vname, lo, hi = variant(model, title)
    # segnali: dalla descrizione appena letta, oppure dalla memoria di una lettura precedente
    mem = listing.pop("dmem", None)
    if desc:
        mem = read_signals(desc)
        listing["_dmem"] = mem  # scan.py lo salva in memoria
    sig_from_desc = set(mem["sig"]) if mem else set()
    if vname:
        reasons.append(f"versione: {vname}")

    adj = 0.0
    hits = set()
    for name, rx, a, txt in SIGNALS:
        if rx.search(title) or name in sig_from_desc:
            hits.add(name)
            adj += a
            reasons.append(txt)
    if "difettoso" in hits or "rifatto" in hits:
        conf -= 1
    adj = max(adj, -0.55)  # anche con più difetti insieme un pezzo vintage conserva un valore
    lo, hi = lo * (1 + adj), hi * (1 + adj)
    mid = (lo + hi) / 2

    # quante informazioni abbiamo
    year = YEAR.search(title) or (mem and mem["year"])
    if mem:
        conf += 1
        if year:
            conf += 1
    else:
        reasons.append("descrizione non letta")
    if not year:
        reasons.append("anno non indicato")
        conf -= 1

    # età dell'annuncio
    posted = parse_date(listing.get("posted"), today)
    age = (today - posted).days if posted else None
    if age is not None and age >= 0:
        listing["age"] = age
        if age > 60:
            reasons.append(f"online da {age} giorni: un'occasione vera non resta invenduta così a lungo")
            conf -= 2
        elif age > 30:
            reasons.append(f"online da {age} giorni")
            conf -= 1

    disc = (mid - listing["total"]) / mid
    if disc > 0.35:
        verdict = "sospetto"
        reasons.insert(0, f"{round(disc * 100)}% sotto il valore: troppo basso per un pezzo originale e funzionante")
    elif disc >= 0.12:
        # occasione solo se la descrizione è stata letta e non ci sono dubbi
        verdict = "occasione" if (mem and conf >= 2) else "da verificare"
    elif disc >= -0.05:
        verdict = "prezzo giusto"
    else:
        verdict = "caro"

    listing.update({
        "fair_lo": round(lo), "fair_hi": round(hi), "disc": round(disc, 4),
        "verdict": verdict, "conf": max(0, min(4, conf)), "reasons": reasons[:5],
    })
    listing.pop("desc", None)  # la descrizione serve solo per valutare: non la pubblichiamo
    return listing
