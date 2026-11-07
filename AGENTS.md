# AGENTS.md

## What this project is

A small script that scrapes the weekly schedule of Telefriuli (Italian regional TV) and emits
an XMLTV file for Dispatcharr. The broadcaster has no EPG feed; the schedule exists only as
HTML on <https://www.telefriuli.it/palinsesto/>.

## Rules

- **Standard library only.** No scraping framework, no dependency just to parse six tags.
  `urllib` + `re` + `xml.sax.saxutils` + `zoneinfo` are enough. A dependency needs a reason
  the stdlib cannot meet.
- **One script, one output.** `telefriuli_epg.py` fetches, parses, writes XMLTV. No database,
  no config file, no framework, no daemon. If a feature needs more than that, it is a new
  project.
- **Timezones are explicit.** Programme times are local Europe/Rome; XMLTV output carries an
  explicit numeric offset (`+0100` / `+0200`). Never emit naive local times.
- **Fail loudly.** If the page structure changes and no programmes parse, exit non-zero. A
  silently empty EPG is worse than a failed cron job.
- **Fixture-driven tests.** Save the fetched page as `tests/fixtures/palinsesto.html` and
  test the parser against it, never against the live site. Tests:
  `python3 -m unittest discover -s tests -t .`.
- **Commit every change.** Small, coherent commits. Never commit `tvit/` (separate upstream
  clone), `epg.xml` output, or `__pycache__`.

## Layout

```
telefriuli_epg.py       # the generator (fetch + parse + emit)
tests/                  # unittest for the parser, with a saved HTML fixture
tvit/                   # git-ignored clone of github.com/leicaflorian/tvit (reference / PR work)
docs/                   # design notes if the plan outgrows PLAN.md
PLAN.md                 # analysis of the source and the implementation plan
```

## Source facts (verified 2026-11-07)

- Furthest upstream source is hand-maintained: schedule lives in Elementor tabpanels with ids
  `elementor-tab-content-8271` … `8277` (Monday → Sunday).
- **Fetch `https://www.telefriuli.it/wp-json/wp/v2/pages/494` → `content.rendered`** (same markup,
  always current). `/palinsesto/` sits behind a URL-keyed page cache and can return last week.
- **`https://www.telefriuli.it/streaming/`** carries the playout log: `<h3>Domenica 8 Novembre
  2026</h3>` + `<ul class="programme-day">` with `<li class="programme">` / `.time` / `.title`.
  Minute-accurate, real broadcast names (`FOCUS ALLUVIONE FORNI AVOLTRI`), today + part of
  tomorrow only. It wins over the weekly page for the days it covers.
- The weekly page sometimes lists a row out of order (Thursday: `11.15` then `10.45`); rows are
  sorted before durations are computed, or one stray row shifts the rest of the day by 24 hours.
- Each tab starts with `<p><b>Programmazione di Lunedì 02/11/26</b></p>`, then one
  `<p class="MsoNormal">` per programme: `06.20` + nbsp padding + title.
- 190 programme lines across the 7 days; every non-empty line matches `^\d{1,2}[.:]\d{2}\s+\S`.
- Titles may carry a subtitle after ` –` (e.g. `News, cappuccino e brioche – diretta`).
- **The dates in the headings are stale and inconsistent between tabs** (e.g. Wed 28/10/26 next to
  Sat 07/11/26). They match their weekday but not the current week.
- Channel identity already exists in the ecosystem: iptv-org id `Telefriuli.it`, logo
  `https://i.imgur.com/He3uCs6.png`, `tvg-id="Telefriuli.it@SD"` in iptv-org `streams/it.m3u`.
- `tvit/` upstream does not cover Telefriuli; its scrapers dispatch by
  `ChannelGroup.scrapper` → `app/Jobs/Scrappers/<Name>Scrapper.php`.
