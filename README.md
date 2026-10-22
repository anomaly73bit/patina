# Patina · versione Minimal Mistakes

Questo branch contiene solo il sito con il tema [Minimal Mistakes](https://mmistakes.github.io/minimal-mistakes/). Lo scanner e il workflow stanno nel branch `main`.

Il workflow di `main` compila anche questo branch, ci copia i dati aggiornati dello scanner (`_data/*.json`) e lo pubblica su `/patina/mm/`.

- Articoli: nuovi file in `_posts/` (formato `AAAA-MM-GG-titolo.md`)
- Menu: `_data/navigation.yml`
- Skin del tema: `minimal_mistakes_skin` in `_config.yml` (air, contrast, dark, dirt, mint, neon, plum, sunrise…)
