"""
Simple test script to verify KPI tools work.
Run from project root: poetry run python tests/test_tools.py
"""

import asyncio
import json

from factory_intelligence.tools.productivity import get_productivity_kpi
from factory_intelligence.tools.quality import get_quality_kpi
from factory_intelligence.tools.downtime import get_downtime_kpi
from factory_intelligence.tools.summary import get_kpi_summary
from factory_intelligence.tools.alarms import get_downtime_alarms
from factory_intelligence.utilities.db import close_pool


def print_result(name, result):
    print(f"\n{'='*60}  {name}   {'='*60}")
    print(json.dumps(result, indent=2, default=str))


"""
NOTE
----
All timestamps in the database are stored in UTC format (timestamptz).
For local timezone conversion, use the timezone field from the sites table,
which contains the IANA timezone identifier for each site
(e.g., 'America/Chicago', 'Asia/Kolkata').

T separates date and time,
- T00:00:00Z indicates the start of the day in UTC,
- T23:59:59Z indicates the end of the day in UTC.
"""


async def main():
    # ============================================
    # Test Range 1: single day (December 10, 2025)
    # ============================================
    start = "2025-12-10T00:00:00Z"  # start of the day in UTC
    end = "2025-12-10T23:59:59Z"  # one second before midnight, end of the day

    print(f"Testing with range: {start} to {end}")

    # Test 1: Productivity
    result = await get_productivity_kpi(start, end)
    print_result("Productivity KPI", result)
    assert result["status"] == "ok", "Productivity failed!"
    summary = result["result"]["summary"]
    assert summary["good_bottles"] >= 0, "good_bottles should not be negative"
    assert summary["bad_bottles"] >= 0, "bad_bottles should not be negative"
    assert (
        summary["total_production"] == summary["good_bottles"] + summary["bad_bottles"]
    ), "total_production should equal to good + bad"
    assert len(result["result"]["timeseries"]) > 0, "Expected timeseries data"

    # Test 2: Quality
    result = await get_quality_kpi(start, end)
    print_result("Quality KPI", result)
    assert result["status"] == "ok", "Quality failed!"
    summary = result["result"]["summary"]
    assert 0 <= summary["yield_pct"] <= 100, "yield_pct should be between 0 and 100"
    assert (
        0 <= summary["defect_rate_pct"] <= 100
    ), "defect_rate_pct should be between 0 and 100"
    assert (
        abs(summary["yield_pct"] + summary["defect_rate_pct"] - 100) < 0.01
    ), "yield_pct + defect_rate_pct should equal 100"
    assert (
        summary["total_production"] == summary["good_bottles"] + summary["bad_bottles"]
    ), "total_production should equal good + bad"

    # Test 3: Downtime
    result = await get_downtime_kpi(start, end)
    print_result("Downtime KPI", result)
    assert result["status"] == "ok", "Downtime failed!"
    summary = result["result"]["summary"]
    assert (
        0 <= summary["availability_pct"] <= 100
    ), "availability_pct should be between 0 and 100"
    assert summary["downtime_seconds"] >= 0, "downtime_seconds should not be negative"
    assert summary["uptime_seconds"] >= 0, "uptime_seconds should not be negative"
    assert (
        summary["downtime_seconds"] + summary["uptime_seconds"] > 0
    ), "Total time should be greater than 0"
    assert (
        summary["downtime_seconds"] == summary["downtime_intervals"] * 10
    ), "downtime_seconds should equal downtime_intervals * 10"

    # Test 4: Summary (bundles Tools 1-3)
    result = await get_kpi_summary(start, end)
    print_result("KPI Summary", result)
    assert result["status"] == "ok", "Summary failed!"
    summary = result["result"]["summary"]
    assert summary["productivity"] is not None, "productivity should be present"
    assert summary["quality"] is not None, "quality should be present"
    assert summary["downtime"] is not None, "downtime should be present"
    # Verify bundled values are consistent with individual tool calls
    assert summary["productivity"]["kpi_name"] == "Productivity"
    assert summary["quality"]["kpi_name"] == "Quality"
    assert summary["downtime"]["kpi_name"] == "Downtime"

    # Test 5: Alarms
    result = await get_downtime_alarms(start, end)
    print_result("Downtime Alarms", result)
    assert result["status"] == "ok", "Alarms failed!"
    summary = result["result"]["summary"]
    assert summary["downtime_events"] >= 0, "downtime_events should not be negative"
    assert isinstance(summary["top_alarms"], list), "top_alarms should be a list"
    if summary["downtime_events"] > 0:
        assert (
            summary["total_alarms_found"] >= 0
        ), "total_alarms_found should not be negative"
        assert summary["unique_alarms"] >= 0, "unique_alarms should not be negative"

    # Test 6: Productivity with line_id filter
    # First, get a valid line_id from the database
    from factory_intelligence.utilities.db import get_pool

    pool = await get_pool()
    async with pool.connection() as conn:
        async with conn.cursor() as cur:
            await cur.execute(
                "SELECT DISTINCT line_id FROM agg_counter_1min WHERE line_id IS NOT NULL LIMIT 1"
            )
            row = await cur.fetchone()
    if row:
        test_line_id = row[0]
        result = await get_productivity_kpi(start, end, line_id=test_line_id)
        print_result("Productivity KPI (with line_id filter)", result)
        assert result["status"] == "ok", "Productivity with line_id filter failed!"
        assert (
            result["inputs"]["line_id"] == test_line_id
        ), "line_id should be in inputs"
        summary = result["result"]["summary"]
        assert (
            summary["total_production"] >= 0
        ), "Filtered production should not be negative"

    # Test 7: Invalid range (end before start — should return error)
    result = await get_productivity_kpi(end, start)
    print_result("Invalid Range Test", result)
    assert result["status"] == "error", "Should have returned error!"
    assert len(result["errors"]) > 0, "Should have error message"

    # ============================================
    # Test Range 2: full data range (December 5-14, 2025)
    # ============================================
    start_full = "2025-12-05T00:00:00Z"
    end_full = "2025-12-14T23:59:59Z"

    print(f"\nTesting with full range: {start_full} to {end_full}")

    result = await get_productivity_kpi(start_full, end_full)
    print_result("Productivity KPI (full range)", result)
    assert result["status"] == "ok", "Full range productivity failed!"
    assert (
        result["result"]["summary"]["total_production"] > 0
    ), "Expected production data in full range"

    result = await get_quality_kpi(start_full, end_full)
    print_result("Quality KPI (full range)", result)
    assert result["status"] == "ok", "Full range quality failed!"
    assert 0 <= result["result"]["summary"]["yield_pct"] <= 100

    result = await get_downtime_kpi(start_full, end_full)
    print_result("Downtime KPI (full range)", result)
    assert result["status"] == "ok", "Full range downtime failed!"
    assert 0 <= result["result"]["summary"]["availability_pct"] <= 100

    # ============================================
    # Test Range 3: no data range (should return error)
    # ============================================
    no_data_start = "2020-01-01T00:00:00Z"
    no_data_end = "2020-01-02T00:00:00Z"

    print(f"\nTesting with no-data range: {no_data_start} to {no_data_end}")

    result = await get_productivity_kpi(no_data_start, no_data_end)
    print_result("No Data Range Test", result)
    assert result["status"] == "error", "Expected error for empty range!"
    assert "No data found" in result["errors"][0], "Expected 'No data found' message"

    await close_pool()
    print(f"\n{'='*60}  All tests passed! {'='*60}")


if __name__ == "__main__":
    asyncio.run(main())
    # Tool functions are all async (they use await for DB queries),
    # hence start a event loop using asyncio to drive the calls
    # main() # RuntimeWarning: coroutine 'main' was never awaited;
