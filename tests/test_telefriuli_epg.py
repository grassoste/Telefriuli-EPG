import re
import unittest
import xml.etree.ElementTree as ET
from datetime import date, datetime
from pathlib import Path

import telefriuli_epg as epg

FIXTURE = Path(__file__).parent / "fixtures" / "palinsesto.html"
TODAY = date(2026, 11, 7)  # the day the fixture was saved


class ParserTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.days = epg.parse_schedule(FIXTURE.read_text(encoding="utf-8"))

    def test_all_seven_days_parsed(self):
        self.assertEqual(sorted(day["weekday"] for day in self.days), list(range(7)))

    def test_every_row_parsed(self):
        # If the fixture is refreshed, update the expected count.
        self.assertEqual(sum(len(day["entries"]) for day in self.days), 190)

    def test_no_heading_or_junk_leaked_into_titles(self):
        for day in self.days:
            for _, _, label in day["entries"]:
                self.assertNotIn("Programmazione", label)
                self.assertRegex(label, r"^\S")

    def test_garbage_input_yields_nothing(self):
        self.assertEqual(epg.parse_schedule("<html><p>hello</p></html>"), [])


class DatesTest(unittest.TestCase):
    def setUp(self):
        self.days = epg.parse_schedule(FIXTURE.read_text(encoding="utf-8"))
        self.resolved = epg.resolve_dates(self.days, TODAY)

    def test_dates_inside_emission_window(self):
        for day in self.resolved:
            self.assertGreaterEqual(day["date"], TODAY)
            self.assertLess((day["date"] - TODAY).days, 7)

    def test_one_day_per_weekday_sorted(self):
        self.assertEqual(
            sorted(day["date"] for day in self.resolved),
            [day["date"] for day in self.resolved],
        )
        self.assertEqual(len({day["date"] for day in self.resolved}), 7)

    def test_weekday_label_matches_date(self):
        for day in self.resolved:
            self.assertEqual(day["date"].weekday(), day["weekday"])


class XmltvTest(unittest.TestCase):
    def setUp(self):
        days = epg.parse_schedule(FIXTURE.read_text(encoding="utf-8"))
        resolved = epg.resolve_dates(days, TODAY)
        self.programmes = epg.build_programmes(resolved)
        self.xml = epg.build_xmltv(self.programmes, "Telefriuli.it", "Telefriuli")

    def test_well_formed_and_complete(self):
        root = ET.fromstring(self.xml)
        self.assertEqual(root.tag, "tv")
        self.assertEqual(root.find("channel").get("id"), "Telefriuli.it")
        self.assertEqual(len(root.findall("programme")), 190)

    def test_times_carry_explicit_offset(self):
        root = ET.fromstring(self.xml)
        for programme in root.findall("programme"):
            for key in ("start", "stop"):
                self.assertRegex(programme.get(key), r"^\d{14} [+-]\d{4}$")

    def test_durations_follow_next_start(self):
        first, second = self.programmes[0], self.programmes[1]
        self.assertEqual(first[0], datetime(2026, 11, 7, 6, 20, tzinfo=epg.ROME))
        self.assertEqual(first[1], second[0])
        self.assertEqual(second[0].strftime("%H:%M"), "06:30")

    def test_label_kept_whole(self):
        self.assertIn(
            "News, cappuccino e brioche –diretta",
            {title for _, _, title in self.programmes},
        )
        self.assertNotIn("sub-title", self.xml)


class StreamingTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.live = epg.parse_streaming(
            (FIXTURE.parent / "streaming.html").read_text(encoding="utf-8")
        )

    def test_parses_the_dated_live_days(self):
        self.assertEqual([day["weekday"] for day in self.live], [6, 0])
        self.assertEqual(
            [day["date"] for day in self.live], [date(2026, 11, 8), date(2026, 11, 9)]
        )

    def test_entries_are_minute_accurate(self):
        self.assertEqual(self.live[0]["entries"][0], (0, 12, "TELEGIORNALE FVG"))
        self.assertGreaterEqual(len(self.live[0]["entries"]), 50)

    def test_live_days_override_the_weekly_page(self):
        merged = epg.merge_days(
            self.live, epg.parse_schedule(FIXTURE.read_text(encoding="utf-8"))
        )
        self.assertEqual(len(merged), 7)
        self.assertEqual([day["weekday"] for day in merged], list(range(7)))
        sunday = merged[6]
        self.assertEqual(sunday["date"], date(2026, 11, 8))
        self.assertIn((1, 25, "FOCUS ALLUVIONE FORNI AVOLTRI"), sunday["entries"])

    def test_thin_live_day_is_ignored(self):
        html = (
            '<h3>Domenica 8 Novembre 2026</h3><ul class="programme-day">'
            '<li class="programme"><div class="time">10:00</div>'
            '<div class="title">ONLY ONE</div></li></ul>'
        )
        self.assertEqual(epg.parse_streaming(html), [])


class OrderingTest(unittest.TestCase):
    def _programmes(self, entries):
        day = {"weekday": 5, "date": date(2026, 11, 7), "entries": entries}
        return epg.build_programmes([day])

    def test_out_of_order_row_does_not_shift_the_day(self):
        programmes = self._programmes(
            [(11, 15, "Rugby"), (10, 45, "Screenshot"), (12, 0, "News")]
        )
        self.assertEqual(
            [title for _, _, title in programmes], ["Screenshot", "Rugby", "News"]
        )
        self.assertEqual(
            {start.date() for start, _, _ in programmes}, {date(2026, 11, 7)}
        )

    def test_equal_times_stay_on_the_same_day(self):
        programmes = self._programmes([(10, 0, "A"), (10, 0, "B"), (11, 0, "C")])
        self.assertEqual(programmes[1][0].strftime("%Y-%m-%d"), "2026-11-07")
        self.assertEqual(programmes[1][1].strftime("%H:%M"), "11:00")

    def test_thursday_tab_stays_on_its_own_day(self):
        # Regression: the 11.15/10.45 swap used to push 22 rows into the next day.
        days = [
            day
            for day in epg.parse_schedule(FIXTURE.read_text(encoding="utf-8"))
            if day["weekday"] == 3
        ]
        programmes = epg.build_programmes(epg.resolve_dates(days, TODAY))
        self.assertEqual(len(programmes), 30)
        self.assertEqual(len({start.date() for start, _, _ in programmes}), 1)
        self.assertTrue(all(stop > start for start, stop, _ in programmes))


if __name__ == "__main__":
    unittest.main()
