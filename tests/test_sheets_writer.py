import pytest
from unittest.mock import MagicMock, patch

from shared.models import StatItem


@pytest.fixture
def mock_gspread():
    with patch("data_fetcher.sheets_writer.gspread") as mock:
        mock_gc = MagicMock()
        mock.service_account.return_value = mock_gc
        mock_sheet = MagicMock()
        mock_gc.open_by_key.return_value.worksheet.return_value = mock_sheet
        yield mock_sheet


def test_write_sync(mock_gspread, monkeypatch):
    monkeypatch.setenv("SHEETS_SPREADSHEET_ID", "test_id")
    monkeypatch.setenv("SHEETS_WORKSHEET_NAME", "Sheet1")

    from data_fetcher.sheets_writer import SheetsWriter

    writer = SheetsWriter()

    stats = [StatItem(label=f"Stat {i}", value=str(i)) for i in range(5)]
    writer._write_sync("Test Player", stats, "2024-01-01T00:00:00Z")

    mock_gspread.clear.assert_called_once()
    mock_gspread.batch_update.assert_called_once()

    call_args = mock_gspread.batch_update.call_args[0][0]
    assert len(call_args) == 2
    labels_row = call_args[0]["values"][0]
    assert labels_row[0] == "Test Player"
    assert len(labels_row) == 8  # name + 5 labels + empty + timestamp
