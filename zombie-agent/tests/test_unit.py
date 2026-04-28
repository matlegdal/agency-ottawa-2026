"""Pure-unit tests — no SDK, no Postgres, no Anthropic API.

These cover the small bits of pure-Python logic that don't need a live
agent: hook helper functions and the ui_bridge tool's payload shape.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pytest

from src.hooks import (
    _DESTRUCTIVE,
    _count_rows,
    _extract_text,
    _first_meaningful_line,
    _needs_limit,
)


@pytest.mark.parametrize(
    "sql, expected",
    [
        ("SELECT 1", True),
        ("SELECT * FROM cra.cra_identification", True),
        ("SELECT 1 LIMIT 10", False),
        ("SELECT count(*) FROM x", False),
        ("SELECT a, sum(b) FROM x GROUP BY 1", False),
    ],
)
def test_needs_limit(sql, expected):
    assert _needs_limit(sql) is expected


@pytest.mark.parametrize(
    "sql, blocked",
    [
        ("DROP TABLE x", True),
        ("update foo set bar = 1", True),
        ("INSERT INTO foo VALUES (1)", True),
        ("DELETE FROM foo", True),
        ("ALTER TABLE foo ADD COLUMN x int", True),
        ("VACUUM ANALYZE", True),
        ("CREATE TABLE x (id int)", True),
        ("CREATE EXTENSION pg_trgm", True),
        ("SELECT 1", False),
        ("SELECT * FROM cra.cra_identification LIMIT 5", False),
        # CREATE inside an identifier context does NOT trip the destructive
        # filter (this previously caused the agent to retry harmless SQL).
        ("SELECT created_at FROM x WHERE updated_at > NOW()", False),
        # Subquery casts don't fire either.
        ("SELECT a FROM x WHERE id IN (SELECT id::int FROM y)", False),
    ],
)
def test_destructive_pattern(sql, blocked):
    matched = bool(_DESTRUCTIVE.search(sql))
    assert matched is blocked


def test_first_meaningful_line_skips_blanks():
    assert (
        _first_meaningful_line("\n\n  -- Step 1: hello\nSELECT 1")
        == "-- Step 1: hello"
    )


def test_first_meaningful_line_empty():
    assert _first_meaningful_line("") == "(empty SQL)"


# crystaldba/postgres-mcp returns rows as a single-line Python-list literal:
#   "[{'col': 'val', ...}, {'col': 'val', ...}, ...]"
_PG_ROWS_3 = (
    "[{'bn': '831282512RR0001', 'legal_name': 'Hill Pride Legacy Fund'}, "
    "{'bn': '872866694RR0001', 'legal_name': 'BARRIE HISTORICAL ASSOCIATION'}, "
    "{'bn': '835906348RR0001', 'legal_name': 'GARDENS FOR LIFE'}]"
)


def test_count_rows_handles_postgres_mcp_format():
    assert _count_rows(_PG_ROWS_3) == 3


def test_count_rows_handles_empty_list():
    assert _count_rows("[]") == 0


def test_count_rows_handles_non_list_text():
    assert _count_rows("query executed") == 0


def test_count_rows_handles_blank():
    assert _count_rows("") == 0


def test_extract_text_pulls_first_text_block():
    response = {
        "content": [
            {"type": "text", "text": _PG_ROWS_3},
        ],
        "isError": False,
    }
    assert _extract_text(response) == _PG_ROWS_3


def test_extract_text_missing():
    assert _extract_text({}) == ""
    assert _extract_text(None) == ""
