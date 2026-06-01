"""Tests for /api/projects/{id}/export-excel."""

from __future__ import annotations

import io
import sys
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from openpyxl import load_workbook

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))


@pytest.fixture(scope="module")
def client():
    from api.export_excel import router
    app = FastAPI()
    app.include_router(router)
    return TestClient(app)


def test_export_returns_xlsx_with_ai_sheet(client):
    r = client.post("/api/projects/test/export-excel?fixture=berzas")
    assert r.status_code == 200
    assert "spreadsheetml" in r.headers["content-type"]
    wb = load_workbook(io.BytesIO(r.content), data_only=True)
    assert "AI Sąmata" in wb.sheetnames
    ws = wb["AI Sąmata"]
    # Header row should exist
    assert ws["A3"].value == "Kategorija"
    assert ws["B3"].value == "AI"
    assert ws["C3"].value == "Patikslinta"


def test_export_ai_sheet_carries_real_numbers(client):
    r = client.post("/api/projects/test/export-excel?fixture=berzas")
    wb = load_workbook(io.BytesIO(r.content), data_only=True)
    ws = wb["AI Sąmata"]
    # Find the dazymo row by label and check the AI column has a number > 0
    found = False
    for row in ws.iter_rows(min_row=4, values_only=True):
        if row[0] == "Dažymo plotas (visas)":
            assert isinstance(row[1], (int, float))
            assert row[1] > 0
            found = True
            break
    assert found, "Dažymo plotas row missing"


def test_export_includes_per_room_block(client):
    r = client.post("/api/projects/test/export-excel?fixture=berzas")
    wb = load_workbook(io.BytesIO(r.content), data_only=True)
    ws = wb["AI Sąmata"]
    # The per-room block has header "Patalpos"; scan for it
    found_block_header = False
    for row in ws.iter_rows(values_only=True):
        if row[0] == "Patalpos":
            found_block_header = True
            break
    assert found_block_header


def test_export_without_calibration_has_no_second_sheet(client):
    r = client.post("/api/projects/no-calibration-yet/export-excel?fixture=berzas")
    wb = load_workbook(io.BytesIO(r.content), data_only=True)
    assert wb.sheetnames == ["AI Sąmata"]


def test_unknown_fixture_returns_404(client):
    r = client.post("/api/projects/test/export-excel?fixture=does-not-exist")
    assert r.status_code == 404
