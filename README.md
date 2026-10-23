# Patina

Termometro del mercato degli orologi di lusso vintage in Europa. Per ogni referenza c'è una stima di valore, l'andamento e le occasioni trovate dallo scanner su marketplace, aste e mercatini.

## Come è fatto

| Parte | Dove |
|---|---|
| Sito (Jekyll, senza tema) | `index.html`, `_layouts/`, `assets/` |
| Una pagina per orologio | `_orologi/*.md` → `/orologi/<id>/` |
| Stime e schede modelli | `_data/models.json` (da modificare a mano) |
| Commissioni d'asta per fonte | `_data/sources.json` |
| Annunci trovati | `_data/listings.json` (scritto dallo scanner) |
| Foto | `_data/photos.json` (Wikimedia Commons, automatico) e `_data/photos_manual.json` (foto scelte a mano) |
| Scanner | `scanner/` (Python) |
| Automazione | `.github/workflows/scan.yml` |

## Messa in linea

1. Crea su GitHub un repository chiamato `patina` e carica tutti i file (compresa la cartella `.github`).
2. **Settings → Pages → Source: GitHub Actions.**
3. **Settings → Secrets and variables → Actions**: aggiungi `EBAY_CLIENT_ID` e `EBAY_CLIENT_SECRET` (app gratuita su developer.ebay.com, chiavi *Production*).
4. **Actions → Scanner e sito → Run workflow**, spunta «Aggiorna anche le foto».
5. Il sito è su `https://patina.pacificit.solutions/`.

Lo scanner gira da solo ogni 3 ore. Le foto si aggiornano ogni lunedì.

GitHub Pages su un repository **privato** richiede GitHub Pro; su repository pubblico è gratis.

## Aggiungere un modello

1. Aggiungi una voce in `_data/models.json`. Il campo `match` contiene le parole che devono comparire nel titolo dell'annuncio.
2. Crea `_orologi/<id>.md` con:
   ```
   ---
   model_id: <id>
   title: "Marca Modello Ref"
   ---
   ```

## Foto sbagliate o mancanti

In `_data/photos_manual.json`, con chiave l'id del modello:

```json
{"rolex-5513": [{"src": "https://upload.wikimedia.org/...jpg", "page": "https://commons.wikimedia.org/wiki/File:...", "author": "Nome", "license": "CC BY-SA 4.0"}]}
```

Le foto manuali compaiono per prime.

## Nuove fonti

Ogni fonte è un modulo in `scanner/` con una funzione `fetch(models)` che restituisce una lista di annunci (`m`, `src`, `p`, `url`, `img`, `cty`, `cond`, `auction`, `endDate`). Va aggiunto a `SOURCES` in `scan.py`.

Prima di aggiungere Chrono24, Catawiki, Kleinanzeigen e simili, leggi i loro termini d'uso: molti vietano la raccolta automatica.

## Stime

Le stime in `models.json` sono indicative: prezzi di aggiudicazione e transazioni note fino a metà 2026, condizioni medie, con scatola e senza documenti. Non sono una perizia.
