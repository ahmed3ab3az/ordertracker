"""Validation rules around the Excel import parser."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from openpyxl import Workbook

from ordertracker.services.excel_import import parse_excel


def _write(path: Path, rows: list[list[object]]) -> None:
    wb = Workbook()
    ws = wb.active
    for row in rows:
        ws.append(row)
    wb.save(str(path))


def test_happy_path(tmp_path: Path) -> None:
    path = tmp_path / "ok.xlsx"
    _write(
        path,
        [
            ["Name", "Address", "Price"],
            ["Aly", "Cairo", 150],
            ["Sara", "Giza", "200.50"],
        ],
    )
    preview = parse_excel(path)
    assert preview.ok, preview.errors
    assert len(preview.rows) == 2
    assert preview.rows[1].price == Decimal("200.50")


def test_missing_column(tmp_path: Path) -> None:
    path = tmp_path / "bad.xlsx"
    _write(path, [["name", "price"], ["Aly", 100]])
    preview = parse_excel(path)
    assert not preview.ok
    assert "address" in preview.errors[0].reason.lower()


def test_negative_price_rejected(tmp_path: Path) -> None:
    path = tmp_path / "negative.xlsx"
    _write(
        path,
        [
            ["name", "address", "price"],
            ["Aly", "Cairo", -5],
        ],
    )
    preview = parse_excel(path)
    assert not preview.ok
    assert preview.errors[0].column == "price"


def test_empty_workbook(tmp_path: Path) -> None:
    path = tmp_path / "empty.xlsx"
    _write(path, [["name", "address", "price"]])
    preview = parse_excel(path)
    assert not preview.ok
    assert "no data" in preview.errors[0].reason.lower()


def test_blank_rows_skipped(tmp_path: Path) -> None:
    path = tmp_path / "blank_rows.xlsx"
    _write(
        path,
        [
            ["name", "address", "price"],
            ["Aly", "Cairo", 100],
            [None, None, None],
            ["Sara", "Giza", 200],
        ],
    )
    preview = parse_excel(path)
    assert preview.ok, preview.errors
    assert len(preview.rows) == 2
