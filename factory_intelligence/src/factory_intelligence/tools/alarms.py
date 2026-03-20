"""
Tool 5 - Downtime Alarms Analysis

Step 1: Find downtime periods from agg_counter_10sec_delta (production = 0)
Step 2: Get alarm tag names from tags_metadata (is_alarm = true)
Step 3: Find alarms active during downtime from agg_boolean_state_durations
"""

from psycopg.rows import dict_row

from factory_intelligence.utilities.db import get_pool
from factory_intelligence.utilities.response import (error_response,
                                                     success_response)
from factory_intelligence.utilities.validation import validate_time_range

TOOL_NAME = "get_downtime_alarms"
GOOD_TAG = "HMI_TOTAL_GOOD_BOTTLES"
BAD_TAG = "HMI_TOTAL_BAD_BOTTLES"


async def get_downtime_alarms(start_time, end_time):
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

                # Step 1: Find downtime periods (group consecutive 0-production intervals)
                await cur.execute(
                    """
                    WITH per_bucket AS (
                        SELECT
                            bucket,
                            SUM(CASE WHEN tag_name = %(good)s THEN delta ELSE 0 END)
                          + SUM(CASE WHEN tag_name = %(bad)s  THEN delta ELSE 0 END) AS total
                        FROM agg_counter_10sec_delta
                        WHERE bucket >= %(start)s AND bucket < %(end)s
                          AND tag_name IN (%(good)s, %(bad)s)
                        GROUP BY bucket
                    ),
                    downtime_buckets AS (
                        SELECT bucket FROM per_bucket WHERE total = 0 ORDER BY bucket
                    ),
                    grouped AS (
                        SELECT
                            bucket,
                            bucket - (ROW_NUMBER() OVER (ORDER BY bucket)) * INTERVAL '10 seconds' AS grp
                        FROM downtime_buckets
                    )
                    SELECT
                        MIN(bucket) AS downtime_start,
                        MAX(bucket) + INTERVAL '10 seconds' AS downtime_end,
                        COUNT(*) AS intervals,
                        COUNT(*) * 10 AS duration_seconds
                    FROM grouped
                    GROUP BY grp
                    ORDER BY downtime_start
                    """,
                    {"good": GOOD_TAG, "bad": BAD_TAG, "start": start, "end": end},
                )
                downtime_periods = await cur.fetchall()

                if not downtime_periods:
                    return success_response(
                        TOOL_NAME,
                        inputs,
                        {
                            "kpi_name": "Downtime Alarms",
                            "message": "No downtime periods found in the given time range",
                            "downtime_events": 0,
                            "alarms": [],
                        },
                    )

                # Step 2: Get alarm tag names
                await cur.execute(
                    "SELECT tag_name, description FROM tags_metadata WHERE is_alarm = true"
                )
                alarm_tags = await cur.fetchall()

                if not alarm_tags:
                    return success_response(
                        TOOL_NAME,
                        inputs,
                        {
                            "kpi_name": "Downtime Alarms",
                            "message": "No alarm tags found in tags_metadata",
                            "downtime_events": len(downtime_periods),
                            "alarms": [],
                        },
                    )

                alarm_tag_names = [t["tag_name"] for t in alarm_tags]

                # Step 3: Find alarms active during any downtime period
                overall_start = downtime_periods[0]["downtime_start"]
                overall_end = downtime_periods[-1]["downtime_end"]

                await cur.execute(
                    """
                    SELECT
                        tag_name,
                        start_time,
                        end_time,
                        duration_seconds
                    FROM agg_boolean_state_durations
                    WHERE tag_name = ANY(%(alarm_names)s)
                      AND value = true
                      AND start_time <= %(overall_end)s
                      AND (end_time >= %(overall_start)s OR end_time IS NULL)
                    ORDER BY start_time
                    """,
                    {
                        "alarm_names": alarm_tag_names,
                        "overall_start": overall_start,
                        "overall_end": overall_end,
                    },
                )
                active_alarms = await cur.fetchall()

        # Step 4: Build alarm summary
        alarm_stats = {}
        for alarm in active_alarms:
            name = alarm["tag_name"]
            if name not in alarm_stats:
                alarm_stats[name] = {"count": 0, "total_duration_seconds": 0}
            alarm_stats[name]["count"] += 1
            if alarm["duration_seconds"]:
                alarm_stats[name]["total_duration_seconds"] += float(
                    alarm["duration_seconds"]
                )

        # Sort by total duration descending
        sorted_alarms = sorted(
            alarm_stats.items(),
            key=lambda x: x[1]["total_duration_seconds"],
            reverse=True,
        )

        alarm_list = []
        for name, stats in sorted_alarms:
            alarm_list.append(
                {
                    "alarm_name": name,
                    "occurrences": stats["count"],
                    "total_duration_seconds": round(stats["total_duration_seconds"], 2),
                    "total_duration_minutes": round(
                        stats["total_duration_seconds"] / 60, 2
                    ),
                }
            )

        # Build downtime events list
        downtime_events = []
        for period in downtime_periods:
            downtime_events.append(
                {
                    "start": period["downtime_start"].isoformat(),
                    "end": period["downtime_end"].isoformat(),
                    "duration_seconds": period["duration_seconds"],
                }
            )

        summary = {
            "kpi_name": "Downtime Alarms",
            "downtime_events": len(downtime_periods),
            "total_alarms_found": len(active_alarms),
            "unique_alarms": len(alarm_list),
            "top_alarms": alarm_list[:10],
        }

        metadata = {
            "data_source": "agg_counter_10sec_delta, agg_boolean_state_durations, tags_metadata",
            "computation_note": "Alarms active during periods where production = 0",
        }

        return success_response(
            TOOL_NAME, inputs, summary, timeseries=downtime_events, metadata=metadata
        )

    except Exception as e:
        return error_response(TOOL_NAME, inputs, f"Database error: {str(e)}")
