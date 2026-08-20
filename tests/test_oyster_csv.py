"""Tests for Oyster CSV importer."""

from unittest.mock import MagicMock

from lifestream.importers.oyster_csv import OysterCsvImporter

CSV_CONTENT = (
    "Date,Start Time,End Time,Journey/Action,Charge,Credit,Balance,Note\n"
    "01-Jan-2024,08:15,08:45,Bus journey,1.65,0.00,10.00,\n"
)


class TestOysterCsvImporter:
    def _make_importer(self, filename):
        imp = OysterCsvImporter()
        imp._args = imp.parse_args([filename])
        imp._entry_store = MagicMock()
        return imp

    def test_run_adds_entry_with_utc_converted_date(self, tmp_path):
        """A journey row is converted from local London time to UTC and stored."""
        csv_file = tmp_path / "oyster.csv"
        csv_file.write_text(CSV_CONTENT)

        imp = self._make_importer(str(csv_file))
        imp.run()

        imp._entry_store.add_entry.assert_called_once()
        args = imp._entry_store.add_entry.call_args.args
        assert args[0] == "oyster"
        assert args[2] == "Bus journey"
        assert args[3] == "oyster"
        assert args[4] == "2024-01-01 08:15"  # GMT in January, no DST shift

    def test_run_skips_blank_rows(self, tmp_path):
        """Blank rows in the CSV don't crash or produce entries."""
        csv_file = tmp_path / "oyster.csv"
        csv_file.write_text(
            "Date,Start Time,End Time,Journey/Action,Charge,Credit,Balance,Note\n\n"
        )

        imp = self._make_importer(str(csv_file))
        imp.run()

        imp._entry_store.add_entry.assert_not_called()

    def test_run_handles_missing_start_time(self, tmp_path):
        """A missing start time falls back to the end time, or midnight if both are blank."""
        csv_file = tmp_path / "oyster.csv"
        csv_file.write_text(
            "Date,Start Time,End Time,Journey/Action,Charge,Credit,Balance,Note\n"
            "01-Jan-2024,,09:00,Top up,5.00,0.00,15.00,\n"
        )

        imp = self._make_importer(str(csv_file))
        imp.run()

        args = imp._entry_store.add_entry.call_args.args
        assert args[4] == "2024-01-01 09:00"
