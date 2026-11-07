# telefriuli_epg

Generates an XMLTV (`epg.xml`) file for the Italian regional channel **Telefriuli**, for use
as an EPG source in [Dispatcharr](https://github.com/Dispatcharr/Dispatcharr).

Source of truth: <https://www.telefriuli.it/palinsesto/> — a WordPress/Elementor page with one
tab per weekday, each holding a pasted Word-style list of `HH.MM   Title` lines.

## Status

Scaffolding + analysis. The generator is not written yet; see [PLAN.md](PLAN.md).

## Planned usage

```bash
python3 telefriuli_epg.py                 # writes epg.xml, next 7 days
python3 telefriuli_epg.py -o /path/epg.xml --days 7
```

Then point Dispatcharr at the file (or at a static HTTP URL serving it).

## Requirements

Python 3.9+ only, standard library. No API keys, no paid services.

## Related

- `tvit/` — shallow clone of <https://github.com/leicaflorian/tvit> (Laravel IPTV/EPG app for
  Italian channels). Kept git-ignored in this repo; used as reference and as the place to
  develop a possible upstream contribution (a `Telefriuli` scraper).
