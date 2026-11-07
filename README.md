# telefriuli_epg

Generates an XMLTV (`epg.xml`) file for the Italian regional channel **Telefriuli**, for use
as an EPG source in [Dispatcharr](https://github.com/Dispatcharr/Dispatcharr).

Source of truth: <https://www.telefriuli.it/palinsesto/> — a WordPress/Elementor page with one
tab per weekday, each holding a pasted Word-style list of `HH.MM   Title` lines.

## Status

Scaffolding + analysis. The generator is not written yet; see [PLAN.md](PLAN.md).

## Usage

Dispatcharr can read the published copy directly (regenerated daily by the GitHub Action):

```
https://raw.githubusercontent.com/grassoste/Telefriuli-EPG/main/epg.xml
```

Or run it yourself:

```bash
python3 telefriuli_epg.py                      # writes epg.xml, next 7 days
python3 telefriuli_epg.py -o /path/epg.xml     # custom path
python3 telefriuli_epg.py --days 3 --channel-id 'Telefriuli.it@SD'
python3 telefriuli_epg.py --input tests/fixtures/palinsesto.html   # offline parse
```

Options: `--days 1-7`, `--channel-id` (default `Telefriuli.it`), `--channel-name`, `--icon`,
`--last-duration` (minutes for the last programme of a day, default 60), `--input`.

Point Dispatcharr at the generated file (EPG source → file path, or serve the directory over
HTTP). Weekly cron is enough:

```cron
0 4 * * * cd /path/to/telefriuli_epg && python3 telefriuli_epg.py -o /srv/epg/epg.xml
```

## Tests

```bash
python3 -m unittest discover -s tests -t .
```

Tests parse the saved fixture in `tests/fixtures/palinsesto.html`, never the live site.

## How it works

Two sources, merged:

1. **`/palinsesto/`** (via `GET /wp-json/wp/v2/pages/494` → `content.rendered`) — the weekly
   plan, 7 days, but hand-typed and often a week behind. The page itself is cached per URL and
   can serve last week; it is only the fallback.
2. **`/streaming/`** — the playout log behind the live player: a dated day guide with
   minute-accurate starts (`01:25 FOCUS ALLUVIONE FORNI AVOLTRI`) and an "Ora in Onda" /
   "Successivo" widget. It only covers today and part of tomorrow, but it is what is really airing.

The live log wins for every day it covers; the weekly page fills the remaining days. Then:

3. Each day is re-projected onto the coming week by weekday — the weekly page's heading dates
   drift by weeks.
4. XMLTV is emitted: durations from the next start time, times with explicit `+0100`/`+0200`.
   Rows are sorted by time, since the page occasionally lists one out of order.

## Requirements

Python 3.9+ only, standard library. No API keys, no paid services.

## Related

- `tvit/` — shallow clone of <https://github.com/leicaflorian/tvit> (Laravel IPTV/EPG app for
  Italian channels). Kept git-ignored in this repo; used as reference and as the place to
  develop a possible upstream contribution (a `Telefriuli` scraper).
