#!/usr/bin/env python3
"""Generate an XMLTV guide for Telefriuli from the schedule on telefriuli.it.

The source is a weekly table hand-pasted into a WordPress Elementor widget: one tab per
weekday, one paragraph per programme ("06.20   Title"). Dates in the day headings drift by
weeks, so they are re-projected onto the coming week; only the weekday is trusted.
"""

import argparse
import json
import re
import sys
import time
import urllib.request
from datetime import date, datetime, time as dtime, timedelta
from html import unescape
from xml.sax.saxutils import escape, quoteattr
from zoneinfo import ZoneInfo

ROME = ZoneInfo("Europe/Rome")
REST_URL = "https://www.telefriuli.it/wp-json/wp/v2/pages/494"
PAGE_URL = "https://www.telefriuli.it/palinsesto/"
HORIZON = 7
MIN_PROGRAMMES = 50

WEEKDAYS = {
    "lunedì": 0,
    "martedì": 1,
    "mercoledì": 2,
    "giovedì": 3,
    "venerdì": 4,
    "sabato": 5,
    "domenica": 6,
}
HEADING_RE = re.compile(r"^programmazione di (\w+) (\d{2})/(\d{2})/(\d{2})$", re.I)
ROW_RE = re.compile(r"^(\d{1,2})[.:](\d{2})\s+(.+)$")


def fetch(url, timeout=20):
    req = urllib.request.Request(url, headers={"User-Agent": "telefriuli_epg/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as res:
        return res.read().decode("utf-8", "replace")


def load_html(timeout=20):
    """REST first: the rendered page sits behind a URL-keyed cache that can serve last week."""
    try:
        return json.loads(fetch(REST_URL, timeout))["content"]["rendered"]
    except Exception as err:  # noqa: BLE001 - any failure means "use the page"
        print(
            f"warning: REST fetch failed ({err}), falling back to the page",
            file=sys.stderr,
        )
    return fetch(f"{PAGE_URL}?v={int(time.time())}", timeout)


def _text(fragment):
    return re.sub(
        r"\s+", " ", unescape(re.sub(r"<[^>]+>", "", fragment)).replace("\xa0", " ")
    ).strip()


def parse_schedule(html):
    """-> [{'weekday': 0-6, 'date': date, 'entries': [(hour, minute, label)]}]"""
    days = []
    for raw in re.findall(r"<p[^>]*>(.*?)</p>", html, re.S):
        text = _text(raw)
        if not text:
            continue
        heading = HEADING_RE.match(text)
        if heading:
            weekday = WEEKDAYS.get(heading.group(1).lower())
            if weekday is None:
                continue
            day, month, year = (int(part) for part in heading.groups()[1:])
            days.append(
                {
                    "weekday": weekday,
                    "date": date(2000 + year, month, day),
                    "entries": [],
                }
            )
            continue
        row = ROW_RE.match(text)
        if row and days:
            hour, minute = int(row.group(1)), int(row.group(2))
            if hour < 24 and minute < 60:
                days[-1]["entries"].append((hour, minute, row.group(3)))
    return [day for day in days if day["entries"]]


def resolve_dates(days, today, horizon=HORIZON):
    """Put every day inside [today, today+horizon), keeping the weekday the tab claims."""
    resolved = []
    for day in days:
        when = day["date"]
        if when.weekday() != day["weekday"]:
            when = today + timedelta(days=(day["weekday"] - today.weekday()) % 7)
        while when < today:
            when += timedelta(weeks=1)
        while (when - today).days >= horizon:
            when -= timedelta(weeks=1)
        resolved.append({**day, "date": when})
    return sorted(resolved, key=lambda day: day["date"])


def build_programmes(days, last_duration=60):
    """-> [(start, stop, title, subtitle)], durations from the next start time in the day."""
    programmes = []
    for day in days:
        starts, previous, extra_days = [], None, 0
        for hour, minute, label in day["entries"]:
            start = datetime.combine(
                day["date"], dtime(hour, minute), tzinfo=ROME
            ) + timedelta(days=extra_days)
            if previous and start < previous:  # a 00:xx row listed after 23:xx
                start += timedelta(days=1)
                extra_days += 1
            previous = start
            starts.append((start, label.strip()))
        for index, (start, title) in enumerate(starts):
            stop = (
                starts[index + 1][0]
                if index + 1 < len(starts)
                else start + timedelta(minutes=last_duration)
            )
            programmes.append((start, stop, title))
    return programmes


def _xmltv_time(moment):
    return moment.astimezone(ROME).strftime("%Y%m%d%H%M%S %z")


def build_xmltv(programmes, channel_id, channel_name, icon=None, generated=None):
    generated = generated or datetime.now(ROME)
    lines = [
        '<?xml version="1.0" encoding="UTF-8"?>',
        f'<tv generator-info-name="telefriuli_epg" date="{generated.strftime("%Y%m%d")}">',
        f"  <channel id={quoteattr(channel_id)}>",
        f'    <display-name lang="it">{escape(channel_name)}</display-name>',
    ]
    if icon:
        lines.append(f"    <icon src={quoteattr(icon)} />")
    lines.append("  </channel>")
    for start, stop, title in programmes:
        lines.append(
            f'  <programme start="{_xmltv_time(start)}" stop="{_xmltv_time(stop)}" '
            f"channel={quoteattr(channel_id)}>"
        )
        lines.append(f'    <title lang="it">{escape(title)}</title>')
        lines.append("  </programme>")
    lines.append("</tv>")
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description="XMLTV guide for Telefriuli.")
    parser.add_argument(
        "-o", "--output", default="epg.xml", help="output file (default: epg.xml)"
    )
    parser.add_argument(
        "--days",
        type=int,
        default=7,
        choices=range(1, 8),
        metavar="1-7",
        help="days to emit, starting today (default: 7)",
    )
    parser.add_argument("--channel-id", default="Telefriuli.it")
    parser.add_argument("--channel-name", default="Telefriuli")
    parser.add_argument("--icon", default="https://i.imgur.com/He3uCs6.png")
    parser.add_argument(
        "--last-duration",
        type=int,
        default=60,
        help="minutes given to the last programme of a day (default: 60)",
    )
    parser.add_argument(
        "--input", help="parse this local HTML/JSON file instead of fetching"
    )
    args = parser.parse_args(argv)

    if args.input:
        raw = open(args.input, encoding="utf-8", errors="replace").read()
        html = (
            json.loads(raw)["content"]["rendered"]
            if raw.lstrip().startswith("{")
            else raw
        )
    else:
        html = load_html()

    days = parse_schedule(html)
    total = sum(len(day["entries"]) for day in days)
    if total < MIN_PROGRAMMES:
        raise SystemExit(
            f"error: parsed only {total} programmes — has the page structure changed?"
        )

    today = datetime.now(ROME).date()
    if max(day["date"] for day in days) < today:
        print(
            "warning: the source schedule has no day in the future; the guide may be stale",
            file=sys.stderr,
        )

    resolved = [
        day
        for day in resolve_dates(days, today)
        if (day["date"] - today).days < args.days
    ]
    programmes = build_programmes(resolved, args.last_duration)
    xml = build_xmltv(programmes, args.channel_id, args.channel_name, args.icon)

    with open(args.output, "w", encoding="utf-8") as handle:
        handle.write(xml)
    print(
        f"{len(programmes)} programmes, {resolved[0]['date']} .. {resolved[-1]['date']} -> {args.output}",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
