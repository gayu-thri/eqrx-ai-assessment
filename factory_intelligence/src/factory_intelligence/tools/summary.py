"""
Tool 4 — KPI Summary Bundle

Calls Tools 1-3 and bundles all results into a single response.
"""

from factory_intelligence.tools.downtime import get_downtime_kpi
from factory_intelligence.tools.productivity import get_productivity_kpi
from factory_intelligence.tools.quality import get_quality_kpi
from factory_intelligence.utilities.response import (error_response,
                                                     success_response)
from factory_intelligence.utilities.validation import validate_time_range

TOOL_NAME = "get_kpi_summary"


async def get_kpi_summary(start_time, end_time, line_id=None, equipment_id=None):
    inputs = {"start_time": start_time, "end_time": end_time}
    if line_id is not None:
        inputs["line_id"] = line_id
    if equipment_id is not None:
        inputs["equipment_id"] = equipment_id

    # Validate inputs
    try:
        validate_time_range(start_time, end_time)
    except ValueError as e:
        return error_response(TOOL_NAME, inputs, str(e))

    # Call each tool, passing optional filters
    productivity = await get_productivity_kpi(start_time, end_time, line_id, equipment_id)
    quality = await get_quality_kpi(start_time, end_time, line_id, equipment_id)
    downtime = await get_downtime_kpi(start_time, end_time, line_id, equipment_id)

    # Collect errors from any failed tools
    errors = []
    if productivity["status"] == "error":
        errors.append(f"Productivity: {productivity['errors']}")
    if quality["status"] == "error":
        errors.append(f"Quality: {quality['errors']}")
    if downtime["status"] == "error":
        errors.append(f"Downtime: {downtime['errors']}")

    # If all failed, return error
    if len(errors) == 3:
        return error_response(
            TOOL_NAME, inputs, "All KPI tools failed: " + "; ".join(errors)
        )

    summary = {
        "kpi_name": "KPI Summary",
        "productivity": (
            productivity["result"]["summary"]
            if productivity["status"] == "ok"
            else None
        ),
        "quality": quality["result"]["summary"] if quality["status"] == "ok" else None,
        "downtime": (
            downtime["result"]["summary"] if downtime["status"] == "ok" else None
        ),
    }

    metadata = {
        "data_source": "agg_counter_1min, agg_counter_10sec_delta",
        "computation_note": "Bundle of productivity, quality, and downtime KPIs",
        "partial_errors": errors if errors else [],
    }

    return success_response(TOOL_NAME, inputs, summary, metadata=metadata)
