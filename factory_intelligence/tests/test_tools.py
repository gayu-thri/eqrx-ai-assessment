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
    # Test time range — one day of data (December 10, 2025)
    start = "2025-12-10T00:00:00Z" # start of the day in UTC
    end = "2025-12-10T23:59:59Z" #  one second before midnight, end of the day

    print(f"Testing with range: {start} to {end}")

    # Test 1: Productivity
    result = await get_productivity_kpi(start, end)
    print_result("Productivity KPI", result)
    assert result["status"] == "ok", "Productivity failed!"

    # Test 2: Quality
    result = await get_quality_kpi(start, end)
    print_result("Quality KPI", result)
    assert result["status"] == "ok", "Quality failed!"

    # Test 3: Downtime
    result = await get_downtime_kpi(start, end)
    print_result("Downtime KPI", result)
    assert result["status"] == "ok", "Downtime failed!"

    # Test 4: Summary
    result = await get_kpi_summary(start, end)
    print_result("KPI Summary", result)
    assert result["status"] == "ok", "Summary failed!"

    # Test 5: Alarms
    result = await get_downtime_alarms(start, end)
    print_result("Downtime Alarms", result)
    assert result["status"] == "ok", "Alarms failed!"

    # Test 6: Invalid range (should return error)
    result = await get_productivity_kpi(end, start)
    print_result("Invalid Range Test", result)
    assert result["status"] == "error", "Should have returned error!"

    await close_pool()
    print(f"\n{'='*60}  All tests passed! {'='*60}")


if __name__ == "__main__":
    asyncio.run(main())
    # Tool functions are all async (they use await for DB queries), 
    # hence start a event loop using asyncio to drive the calls
    # main() # RuntimeWarning: coroutine 'main' was never awaited; 
    