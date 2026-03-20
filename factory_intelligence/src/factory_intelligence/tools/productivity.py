"""
Tool 1 — Productivity KPI

Tags:  HMI_TOTAL_GOOD_BOTTLES, HMI_TOTAL_BAD_BOTTLES
Table: agg_counter_1min (columns: tag_name, delta)

Formulas calculation:
  total_production = good + bad
  productivity = total_production / target (if available)
"""

from psycopg.rows import dict_row

from factory_intelligence.utilities.db import get_pool
from factory_intelligence.utilities.response import (error_response,
                                                     success_response)
from factory_intelligence.utilities.validation import validate_time_range

TOOL_NAME = "get_productivity_kpi"
GOOD_TAG = "HMI_TOTAL_GOOD_BOTTLES"
BAD_TAG = "HMI_TOTAL_BAD_BOTTLES"


async def get_productivity_kpi(start_time, end_time):
    inputs = {"start_time": start_time, "end_time": end_time}

    # Validate time inputs
    try:
        start, end = validate_time_range(start_time, end_time)
    except ValueError as e:
        return error_response(TOOL_NAME, inputs, str(e))

    try:
        pool = await get_pool()
        async with pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:

                # Query aggregate table
                await cur.execute(
                    """
                    SELECT
                        bucket,
                        SUM(CASE WHEN tag_name = %(good)s THEN delta ELSE 0 END) AS good,
                        SUM(CASE WHEN tag_name = %(bad)s  THEN delta ELSE 0 END) AS bad
                    FROM agg_counter_1min
                    WHERE bucket >= %(start)s AND bucket < %(end)s
                      AND tag_name IN (%(good)s, %(bad)s)
                    GROUP BY bucket
                    ORDER BY bucket
                    """,
                    {"good": GOOD_TAG, "bad": BAD_TAG, "start": start, "end": end},
                )
                rows = await cur.fetchall()  # all good & bad rows

        if not rows:
            return error_response(
                TOOL_NAME, inputs, "No data found for the given time range"
            )

        # Compute summary
        total_good = sum(row["good"] for row in rows)
        total_bad = sum(row["bad"] for row in rows)
        total_production = total_good + total_bad

        summary = {
            "kpi_name": "Productivity",
            "total_production": float(total_production),
            "good_bottles": float(total_good),
            "bad_bottles": float(total_bad),
            "unit": "bottles",
        }

        # Build timeseries
        timeseries = []
        for row in rows:
            timeseries.append(
                {
                    "timestamp": row["bucket"].isoformat(),
                    "good": float(row["good"]),
                    "bad": float(row["bad"]),
                    "total": float(row["good"] + row["bad"]),
                }
            )

        metadata = {
            "data_source": "agg_counter_1min",
            "computation_note": "Total production = good + bad bottles",
        }

        return success_response(TOOL_NAME, inputs, summary, timeseries, metadata)

    except Exception as e:
        return error_response(TOOL_NAME, inputs, f"Database error: {str(e)}")
