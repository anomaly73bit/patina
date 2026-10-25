"""Refresh EUR exchange rates from the European Central Bank.

The ECB publishes units of foreign currency per EUR. Patina needs EUR per unit.
If the ECB is unavailable, keep the previous cached rates unchanged.
"""
import datetime as dt
import json
import pathlib
import xml.etree.ElementTree as ET

import requests

DEST = pathlib.Path(__file__).resolve().parents[1] / "_data" / "fx_rates.json"
URL = "https://www.ecb.europa.eu/stats/eurofxref/eurofxref-daily.xml"


def refresh():
    response = requests.get(URL, timeout=20)
    response.raise_for_status()
    root = ET.fromstring(response.content)
    rates = {"EUR": 1.0}
    asof = None
    for node in root.iter():
        if "time" in node.attrib:
            asof = node.attrib["time"]
        currency = node.attrib.get("currency")
        value = node.attrib.get("rate")
        if currency and value:
            rate = float(value)
            if rate <= 0:
                raise ValueError("Invalid ECB exchange rate")
            rates[currency] = round(1.0 / rate, 9)
    if not asof or len(rates) < 10:
        raise ValueError("ECB response missing rates")
    if (dt.date.today() - dt.date.fromisoformat(asof)).days > 7:
        raise ValueError("ECB exchange rates are stale")
    DEST.write_text(json.dumps({"date": asof, "source": "ECB", "rates": rates}, indent=2) + "\n", encoding="utf-8")
    print(f"Updated {len(rates)} FX rates from ECB ({asof})")


if __name__ == "__main__":
    refresh()
