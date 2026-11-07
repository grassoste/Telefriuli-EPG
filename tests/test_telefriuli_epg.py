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

    def test_subtitle_split(self):
        titles = {(title, sub) for _, _, title, sub in self.programmes}
        self.assertIn(("News, cappuccino e brioche", "diretta"), titles)


class MidnightTest(unittest.TestCase):
    def _programmes(self, entries):
        day = {"weekday": 5, "date": date(2026, 11, 7), "entries": entries}
        return epg.build_programmes([day])

    def test_after_midnight_row_rolls_to_next_day(self):
        programmes = self._programmes([(23, 30, "Late"), (0, 15, "After midnight")])
        self.assertEqual(
            programmes[1][0].strftime("%Y-%m-%d %H:%M"), "2026-11-08 00:15"
        )

    def test_equal_times_stay_on_the_same_day(self):
        programmes = self._programmes([(10, 0, "A"), (10, 0, "B"), (11, 0, "C")])
        self.assertEqual(programmes[1][0].strftime("%Y-%m-%d"), "2026-11-07")
        self.assertEqual(programmes[1][1].strftime("%H:%M"), "11:00")


if __name__ == "__main__":
    unittest.main()
