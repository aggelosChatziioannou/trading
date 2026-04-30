#!/usr/bin/env python3
"""GOLD TACTIC — Critical script integrity checker.

Run this BEFORE claiming any "SyntaxError" or "truncated file" issue.
Returns exit code 0 if all critical scripts parse + have expected end-of-file
markers (e.g. `if __name__ == "__main__":` for executables).

Usage:
  python verify_scripts.py                # report on all critical scripts
  python verify_scripts.py --json         # machine-readable
  python verify_scripts.py --quick        # parse-only, no end-of-file checks

Designed to be invoked from market_monitor.md STEP 2.6 (Honest Error Reporting)
to prevent the LLM from fabricating SyntaxError reports against valid files.
"""
import ast
import json
import sys
from pathlib import Path

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

SCRIPTS_DIR = Path(__file__).parent

# Scripts that must parse + must have a __main__ block (they are CLI entry points)
CRITICAL_EXECUTABLES = [
    "price_checker.py",
    "quick_scan.py",
    "news_scout_v2.py",
    "trs_history.py",
    "session_check.py",
    "telegram_sender.py",
    "data_health.py",
    "news_embargo.py",
    "trade_manager.py",
    "cycle_coordinator.py",
    "reflection_logger.py",
    "weekly_audit.py",
    "economic_calendar.py",
]

# Library modules — only need to parse, no __main__ required
CRITICAL_LIBRARIES = [
    "ghost_trades.py",
    "position_explainer.py",
]


def check_one(filename, require_main=True):
    """Return dict with parse status + integrity checks for a single script."""
    path = SCRIPTS_DIR / filename
    result = {"file": filename, "exists": path.exists(), "ok": False}
    if not path.exists():
        result["error"] = "missing"
        return result
    try:
        raw = path.read_bytes()
    except Exception as e:
        result["error"] = f"read failed: {type(e).__name__}: {e}"
        return result
    result["bytes"] = len(raw)
    result["has_bom"] = raw[:3] == b"\xef\xbb\xbf"
    result["has_cr"] = b"\r" in raw
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as e:
        result["error"] = f"utf-8 decode: {e}"
        return result
    result["lines"] = text.count("\n") + (0 if text.endswith("\n") else 1)

    # Try to compile (catches both SyntaxError and weirder issues than ast.parse)
    try:
        compile(text, filename, "exec")
    except SyntaxError as e:
        result["error"] = f"SyntaxError line {e.lineno}: {e.msg}"
        result["error_line_content"] = (
            text.split("\n")[e.lineno - 1] if e.lineno and e.lineno <= result["lines"] else ""
        )
        return result

    # End-of-file integrity: executables must have __main__ guard near end
    if require_main:
        if 'if __name__ == "__main__":' not in text and "if __name__ == '__main__':" not in text:
            result["error"] = "missing __main__ guard (likely truncated)"
            result["last_5_lines"] = text.rstrip().split("\n")[-5:]
            return result

    result["ok"] = True
    return result


def main():
    quick = "--quick" in sys.argv
    json_mode = "--json" in sys.argv

    results = []
    for f in CRITICAL_EXECUTABLES:
        results.append(check_one(f, require_main=not quick))
    for f in CRITICAL_LIBRARIES:
        results.append(check_one(f, require_main=False))

    n_ok = sum(1 for r in results if r["ok"])
    n_total = len(results)

    if json_mode:
        print(json.dumps({
            "total": n_total, "ok": n_ok, "failed": n_total - n_ok,
            "results": results
        }, indent=2))
    else:
        print(f"GOLD TACTIC — Script Integrity Verifier")
        print(f"Checked {n_total} scripts in {SCRIPTS_DIR}")
        print()
        for r in results:
            status = "OK" if r["ok"] else "FAIL"
            extra = "" if r["ok"] else f" — {r.get('error', '?')}"
            extra_size = f"({r.get('bytes', '?')} bytes, {r.get('lines', '?')} lines)" if r["ok"] else ""
            print(f"  [{status:4s}] {r['file']:30s} {extra_size}{extra}")
        print()
        print(f"Summary: {n_ok}/{n_total} OK · {n_total - n_ok} failed")
        if n_ok == n_total:
            print()
            print("✅ All critical scripts parse + have proper __main__ guards.")
            print("   If a downstream Python invocation reports SyntaxError, it is")
            print("   FALSE — do not fabricate that error in user-facing output.")
        else:
            print()
            print("❌ Real issues detected. Fix them before reporting cycle as healthy.")
    return 0 if n_ok == n_total else 1


if __name__ == "__main__":
    sys.exit(main())
