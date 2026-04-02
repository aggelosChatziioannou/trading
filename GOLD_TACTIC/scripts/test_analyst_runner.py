"""Tests for analyst_runner.py — pure function contracts."""
from datetime import datetime, time
import pytest

# Functions are importable once analyst_runner.py exists
from analyst_runner import parse_run_at, is_active_window, bootstrap_cycle_type


# ── parse_run_at ──────────────────────────────────────────────────────────────

def test_parse_run_at_valid_times():
    assert parse_run_at("08:30") == time(8, 30)
    assert parse_run_at("00:00") == time(0, 0)
    assert parse_run_at("23:59") == time(23, 59)
    assert parse_run_at("15:45") == time(15, 45)

def test_parse_run_at_invalid_format():
    assert parse_run_at("8:30") is None    # missing leading zero
    assert parse_run_at("08:5") is None    # missing leading zero on minutes
    assert parse_run_at("abcd") is None    # not a time
    assert parse_run_at("") is None        # empty
    assert parse_run_at(None) is None      # None
    assert parse_run_at("08:30:00") is None  # too many parts

def test_parse_run_at_invalid_range():
    assert parse_run_at("25:00") is None   # hour out of range
    assert parse_run_at("00:72") is None   # minute out of range
    assert parse_run_at("24:00") is None   # 24:00 not valid


# ── is_active_window ──────────────────────────────────────────────────────────

def _dt(weekday, hour, minute=0):
    """Helper: create datetime for given weekday (0=Mon) and time."""
    from datetime import date, timedelta
    base = date(2026, 3, 30)  # Monday
    d = base + timedelta(days=weekday)
    return datetime(d.year, d.month, d.day, hour, minute)

def test_is_active_weekday_inside():
    assert is_active_window(_dt(0, 8, 0)) is True    # Mon 08:00 — boundary
    assert is_active_window(_dt(0, 14, 0)) is True   # Mon 14:00
    assert is_active_window(_dt(0, 21, 59)) is True  # Mon 21:59

def test_is_active_weekday_outside():
    assert is_active_window(_dt(0, 7, 59)) is False  # Mon 07:59 — before open
    assert is_active_window(_dt(0, 22, 0)) is False  # Mon 22:00 — at boundary
    assert is_active_window(_dt(0, 23, 0)) is False  # Mon 23:00

def test_is_active_weekend_inside():
    assert is_active_window(_dt(5, 10, 0)) is True   # Sat 10:00 — boundary
    assert is_active_window(_dt(5, 15, 0)) is True   # Sat 15:00
    assert is_active_window(_dt(6, 19, 59)) is True  # Sun 19:59

def test_is_active_weekend_outside():
    assert is_active_window(_dt(5, 9, 59)) is False  # Sat 09:59
    assert is_active_window(_dt(5, 20, 0)) is False  # Sat 20:00 — boundary
    assert is_active_window(_dt(6, 8, 0)) is False   # Sun 08:00


# ── bootstrap_cycle_type ─────────────────────────────────────────────────────

def test_bootstrap_weekday_before_10():
    assert bootstrap_cycle_type(_dt(0, 8, 0)) == "scanner_morning"
    assert bootstrap_cycle_type(_dt(1, 9, 59)) == "scanner_morning"

def test_bootstrap_weekday_after_10():
    assert bootstrap_cycle_type(_dt(0, 10, 0)) == "analyst"
    assert bootstrap_cycle_type(_dt(0, 15, 0)) == "analyst"

def test_bootstrap_weekend_scanner_window():
    assert bootstrap_cycle_type(_dt(5, 10, 0)) == "scanner_morning"   # Sat 10:00
    assert bootstrap_cycle_type(_dt(5, 10, 14)) == "scanner_morning"  # Sat 10:14

def test_bootstrap_weekend_after_scanner_window():
    assert bootstrap_cycle_type(_dt(5, 10, 15)) == "analyst"  # Sat 10:15
    assert bootstrap_cycle_type(_dt(6, 15, 0)) == "analyst"   # Sun 15:00
