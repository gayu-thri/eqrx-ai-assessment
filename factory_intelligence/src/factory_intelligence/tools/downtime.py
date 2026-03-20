"""
Tool 3 — Downtime KPI

Tags:  HMI_TOTAL_GOOD_BOTTLES, HMI_TOTAL_BAD_BOTTLES
Table: agg_counter_10sec_delta (columns: tag_name, delta)

Logic:
  For each 10-second interval:
    if (good + bad) == 0 → downtime
    if (good + bad) >  0 → uptime

  availability_pct = (uptime / (uptime + downtime)) * 100
"""

from psycopg.rows import dict_row

from factory_intelligence.utilities.db import get_pool
from factory_intelligence.utilities.response import (error_response,
                                                     success_response)
from factory_intelligence.utilities.validation import validate_time_range

TOOL_NAME = "get_downtime_kpi"
GOOD_TAG = "HMI_TOTAL_GOOD_BOTTLES"
BAD_TAG = "HMI_TOTAL_BAD_BOTTLES"


async def get_downtime_kpi(start_time, end_time, line_id=None, equipment_id=None):
    inputs = {"start_time": start_time, "end_time": end_time}
    if line_id is not None:
        inputs["line_id"] = line_id
    if equipment_id is not None:
        inputs["equipment_id"] = equipment_id

    # Validate time inputs
    try:
        start, end = validate_time_range(start_time, end_time)
    except ValueError as e:
        return error_response(TOOL_NAME, inputs, str(e))

    try:
        pool = await get_pool()
        async with pool.connection() as conn:
            async with conn.cursor(row_factory=dict_row) as cur:

                # Build optional filters
                filters = ""
                params = {"good": GOOD_TAG, "bad": BAD_TAG, "start": start, "end": end}
                if line_id is not None:
                    filters += " AND line_id = %(line_id)s"
                    params["line_id"] = line_id
                if equipment_id is not None:
                    filters += " AND equipment_id = %(equipment_id)s"
                    params["equipment_id"] = equipment_id

                # Classify each 10sec interval as uptime or downtime
                await cur.execute(
                    f"""
                    WITH per_bucket AS (
                        SELECT
                            bucket,
                            SUM(CASE WHEN tag_name = %(good)s THEN delta ELSE 0 END)
                          + SUM(CASE WHEN tag_name = %(bad)s  THEN delta ELSE 0 END) AS total
                        FROM agg_counter_10sec_delta
                        WHERE bucket >= %(start)s AND bucket < %(end)s
                          AND tag_name IN (%(good)s, %(bad)s)
                          {filters}
                        GROUP BY bucket
                    )
                    SELECT
                        COUNT(*) FILTER (WHERE total = 0) AS downtime_intervals,
                        COUNT(*) FILTER (WHERE total > 0) AS uptime_intervals
                    FROM per_bucket
                    """,
                    params,
                )
                result = await cur.fetchone()

        if not result:
            return error_response(
                TOOL_NAME, inputs, "No data found for the given time range"
            )

        downtime_intervals = result["downtime_intervals"]
        uptime_intervals = result["uptime_intervals"]
        total_intervals = downtime_intervals + uptime_intervals

        downtime_seconds = downtime_intervals * 10
        uptime_seconds = uptime_intervals * 10

        if total_intervals == 0:
            availability_pct = 0.0
        else:
            availability_pct = (uptime_intervals / total_intervals) * 100

        summary = {
            "kpi_name": "Downtime",
            "availability_pct": round(availability_pct, 2),
            "downtime_seconds": downtime_seconds,
            "downtime_minutes": round(downtime_seconds / 60, 2),
            "uptime_seconds": uptime_seconds,
            "uptime_minutes": round(uptime_seconds / 60, 2),
            "downtime_intervals": downtime_intervals,
            "uptime_intervals": uptime_intervals,
            "unit": "percent",
        }

        metadata = {
            "data_source": "agg_counter_10sec_delta",
            "computation_note": "Each 10sec interval with 0 production = downtime",
        }

        return success_response(TOOL_NAME, inputs, summary, metadata=metadata)

    except Exception as e:
        return error_response(TOOL_NAME, inputs, f"Database error: {str(e)}")
