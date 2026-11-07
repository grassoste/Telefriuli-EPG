# Analysis & Plan — Telefriuli EPG

## 1. The problem

Dispatcharr needs an XMLTV guide for the Telefriuli channel. Telefriuli publishes no EPG feed:
no `tvg-id` in any public XMLTV repository was found, and `tvit` (the closest upstream project)
covers Italian national + a few regional channels, but not Telefriuli.

The only schedule is a hand-maintained WordPress page: <https://www.telefriuli.it/palinsesto/>.

## 2. Source analysis (verified 2026-11-07)

| Fact | Detail |
|---|---|
| Render | Server-side HTML. No AJAX, no JS needed. `curl` alone is enough. |
| Container | 7 Elementor tabpanels: `class="elementor-tab-content elementor-clearfix"`, `data-tab="1"…"7"` = Monday…Sunday |
| Day heading | first `<p>`: `Programmazione di Lunedì 02/11/26` |
| Programme row | one `<p class="MsoNormal">` each: `06.20` + `&nbsp;` padding + `Title`, sometimes split across lines |
| Volume | 192 programme rows for the week (29/29/24/30/32/23/25) |
| Parse rate | **192/192 rows** match `^(\d{1,2})[.:](\d{2})\s+(.+)$` after `\s+` collapse — no odd formats |
| Subtitle | some titles end with ` – <subtitle>` (`News, cappuccino e brioche – diretta`) |
| Duplicates | consecutive entries may repeat a title (`Un pinsir par vuè` several times/day) — that is normal |
| **Date drift** | **the 7 headings are not the same week**: Mon 02/11/26, Tue 03/11/26, Wed 28/10/26, Thu 29/10, Fri 30/10, Sat 24/10, Sun 25/10. Each date matches its weekday, but several are 1–2 weeks old. |
| No durations | only start times are given; an end time must be derived from the next start |

### Consequences

1. **Never trust the heading date as the emission date.** The page is a weekly template that is
   updated late and unevenly. Emitting the literal dates gives an EPG that is partly in the past.
2. **Duration = next entry's start**, last entry of the day = +60 min (default, `--last-duration`).
3. Titles are the only text available; there is no description, genre or episode data. `– subtitle`
   becomes the XMLTV `<sub-title>`; `<desc>` stays absent rather than fake.

## 3. Design

One script, stdlib only.

```
telefriuli_epg.py
  fetch(url) -> html                      # urllib, UA header, 10s timeout, retry once
  parse_days(html) -> [Day(weekday, date, entries)]   # regex over tabpanels, html.unescape
  resolve_dates(days, today, days_ahead)  # shift each day's date by whole weeks into [today, today+6]
  to_xmltv(days) -> str                   # channel + programme elements, Europe/Rome offsets
```

- **Date resolution (hybrid, recommended):** keep the heading date if it lands inside the
  emission window `[today, today+6]`; otherwise shift it by a whole number of weeks until it does.
  The weekday is then always right and the EPG is always populated. One `while` loop.
- **Times:** `datetime` with `zoneinfo.ZoneInfo("Europe/Rome")` → `%Y%m%d%H%M%S %z`. Correct across
  a DST change inside the window.
- **Midnight wrap:** if a start time is earlier than the previous one in the same day, it belongs
  to the next calendar day (the source occasionally lists a 00:xx item at the end).
- **Channel identity:** `--channel-id` (default `Telefriuli.it`), `--channel-name` (default
  `Telefriuli`), `--icon` (logo URL, optional). Dispatcharr matches on the M3U's `tvg-id`, so the
  id is a one-flag change at install time.
- **Output:** `-o epg.xml` (default `epg.xml`), `--days N` (default 7, max 7 — the source only has 7).
- **Failure mode:** fewer than ~50 parsed rows → `SystemExit(1)` with a message. No silent empty EPG.

### XMLTV shape

```xml
<?xml version="1.0" encoding="UTF-8"?>
<tv generator-info-name="telefriuli_epg">
  <channel id="Telefriuli.it">
    <display-name>Telefriuli</display-name>
    <icon src="…"/>
  </channel>
  <programme start="20261107062000 +0100" stop="20261107063000 +0100" channel="Telefriuli.it">
    <title lang="it">Un pinsir par vuè</title>
  </programme>
</tv>
```

## 4. Phases

| # | Step | Done when |
|---|---|---|
| 0 | Scaffold repo, README, AGENTS, tvit clone | ✅ |
| 1 | Save `tests/fixtures/palinsesto.html`, write parser + date resolution | `python3 -m unittest` green, 192 rows |
| 2 | XMLTV emitter + fetcher + CLI flags | `epg.xml` validates, opens in Dispatcharr |
| 3 | Wire into Dispatcharr (file path or served URL), cron weekly | Dispatcharr shows the guide |
| 4 | *(optional)* upstream MR to `tvit`: `TelefriuliScrapper` + Regionali channel entry + fixture test | MR opened, CI green |

## 5. Upstream contribution (tvit), scoped

What upstream would need, matching its own conventions (`CLAUDE.md`: English code, scraper throws
when it finds nothing, fixture tests, `CHANGELOG.md` *Unreleased* entry):

- `app/Jobs/Scrappers/TelefriuliScrapper.php` — same shape as `SuperGuidaTvScrapper`: fetch
  `rawGuideLink`, parse the 7 tabpanels, upsert `Program` rows in **UTC**.
- `database/seeders/RegionaliSeeder.php` — add Telefriuli (`dtt_num` TBD, logo URL, `rawGuideLink`).
- `tests/Feature/TelefriuliScrapperTest.php` — parse the saved fixture, `Http::fake()`.
- No change to `EpgController`/`IptvController`: they already render any channel's programmes.

Risk: upstream's `ScrapSingleChannel` picks one scrapper per *channel group*, so a group-level
dispatch needs a per-channel scrapper lookup. That single line is the only architectural change.

## 6. Risks

- **Stale source** — the page can lag a week. The EPG will show the last published schedule; it
  cannot invent a new one. Detectable: log the heading dates and warn when all 7 are older than 7 days.
- **Markup change** — Elementor tabs are a theme artifact. Parser keys on `elementor-tab-content`
  + `Programmazione di <weekday>` and fails loudly, so breakage is visible on the next run.
- **No descriptions/categories** — inherent to the source; the XMLTV will be titles-only.
