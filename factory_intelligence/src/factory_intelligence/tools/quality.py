"""
Tool 2 — Quality KPI

Tags:  HMI_TOTAL_GOOD_BOTTLES, HMI_TOTAL_BAD_BOTTLES
Table: agg_counter_1min (columns: tag_name, delta)

Formulas:
  total = good + bad
  yield_pct = (good / total) * 100
  defect_pct = (bad / total) * 100
"""

from psycopg.rows import dict_row

from factory_intelligence.utilities.db import get_pool
from factory_intelligence.utilities.response import (error_response,
                                                     success_response)
from factory_intelligence.utilities.validation import validate_time_range

TOOL_NAME = "get_quality_kpi"
GOOD_TAG = "HMI_TOTAL_GOOD_BOTTLES"
BAD_TAG = "HMI_TOTAL_BAD_BOTTLES"


async def get_quality_kpi(start_time, end_time, line_id=None, equipment_id=None):
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

                await cur.execute(
                    f"""
                    SELECT
                        bucket,
                        SUM(CASE WHEN tag_name = %(good)s THEN delta ELSE 0 END) AS good,
                        SUM(CASE WHEN tag_name = %(bad)s  THEN delta ELSE 0 END) AS bad
                    FROM agg_counter_1min
                    WHERE bucket >= %(start)s AND bucket < %(end)s
                      AND tag_name IN (%(good)s, %(bad)s)
                      {filters}
                    GROUP BY bucket
                    ORDER BY bucket
                    """,
                    params,
                )
                rows = await cur.fetchall()

        if not rows:
            return error_response(
                TOOL_NAME, inputs, "No data found for the given time range"
            )

        # Compute summary
        total_good = sum(row["good"] for row in rows)
        total_bad = sum(row["bad"] for row in rows)
        total_production = total_good + total_bad

        if total_production == 0:
            yield_pct = 0.0
            defect_pct = 0.0
        else:
            yield_pct = (total_good / total_production) * 100
            defect_pct = (total_bad / total_production) * 100

        summary = {
            "kpi_name": "Quality",
            "yield_pct": round(yield_pct, 2),
            "defect_rate_pct": round(defect_pct, 2),
            "good_bottles": float(total_good),
            "bad_bottles": float(total_bad),
            "total_production": float(total_production),
            "unit": "percent",
        }

        # Build timeseries
        timeseries = []
        for row in rows:
            total = row["good"] + row["bad"]
            y = (row["good"] / total * 100) if total > 0 else 0
            timeseries.append(
                {
                    "timestamp": row["bucket"].isoformat(),
                    "yield_pct": round(float(y), 2),
                    "good": float(row["good"]),
                    "bad": float(row["bad"]),
                }
            )

        metadata = {
            "data_source": "agg_counter_1min",
            "computation_note": "Yield = (good / total) * 100",
        }

        return success_response(TOOL_NAME, inputs, summary, timeseries, metadata)

    except Exception as e:
        return error_response(TOOL_NAME, inputs, f"Database error: {str(e)}")
