"""Funzioni condivise dallo scanner Patina."""
import json
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
DATA = ROOT / "_data"

# Cambi indicativi verso EUR (aggiornali ogni tanto)
FX = {"EUR": 1.0, "CHF": 1.06, "GBP": 1.17, "CZK": 0.040, "PLN": 0.23, "USD": 0.92}

# Parole che indicano ricambi, repliche o annunci da scartare
BLOCK = re.compile(
    r"\b(dial only|nur zifferblatt|zifferblatt|quadrante solo|cadran seul|"
    r"box only|nur box|solo scatola|bracelet only|nur armband|bezel insert|"
    r"case only|nur gehäuse|movement only|nur werk|for parts|ersatzteil|ricambi|pièces|"
    r"replica|homage|hommage|fake|aftermarket|"
    r"strap only|solo cinturino)\b",
    re.I,
)


def load(name, default=None):
    p = DATA / name
    if not p.exists():
        return default
    return json.loads(p.read_text(encoding="utf-8"))


def save(name, obj):
    (DATA / name).write_text(json.dumps(obj, ensure_ascii=False, indent=1), encoding="utf-8")


def mid(m):
    return (m["lo"] + m["hi"]) / 2


def to_eur(value, currency):
    rate = FX.get(currency)
    return None if rate is None else float(value) * rate


# annunci di chi cerca o compra, non di chi vende
WANTED = re.compile(r"\b(suche|gesucht|ankauf|kaufe|uhrenankauf|cerco|compro|acquisto|recherche|recherch[ée]|ach[eè]te|wanted|hledám|koupím)\b", re.I)


def matches(model, title):
    """True se il titolo parla davvero di questo modello e non di un ricambio o di una ricerca."""
    t = title.lower()
    if BLOCK.search(t) or WANTED.search(t):
        return False
    brand = model["brand"].lower().split()[0]  # "audemars", "patek", "universal"...
    brand_alt = {"universal": "universal", "jaeger-lecoultre": "lecoultre"}.get(brand, brand)
    if brand not in t and brand_alt not in t:
        return False
    return any(tok.lower() in t for tok in model["match"])


def score(listing, model, fee):
    total = listing["p"] * (1 + fee)
    disc = (mid(model) - total) / mid(model)
    listing["total"] = round(total)
    listing["disc"] = round(disc, 4)
    return listing
