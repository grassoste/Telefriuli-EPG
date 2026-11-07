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

1. Fetch `GET /wp-json/wp/v2/pages/494` → `content.rendered` (the page itself is cached per URL
   and can serve last week; it is the fallback).
2. Parse the 7 Elementor tabs: `Programmazione di <weekday> DD/MM/YY` then `HH.MM  Title` rows.
3. Re-project each day onto the coming week by weekday — the heading dates drift by weeks.
4. Emit XMLTV: durations from the next start time, times with explicit `+0100`/`+0200`.

## Requirements

Python 3.9+ only, standard library. No API keys, no paid services.

## Related

- `tvit/` — shallow clone of <https://github.com/leicaflorian/tvit> (Laravel IPTV/EPG app for
  Italian channels). Kept git-ignored in this repo; used as reference and as the place to
  develop a possible upstream contribution (a `Telefriuli` scraper).
