"""
MCP Server — Factory Intelligence

Exposes 5 KPI tools via MCP
An LLM agent calls these tools to answer questions about factory production

Run:
poetry run python -m factory_intelligence.mcp_server
"""

from mcp.server.fastmcp import FastMCP

from factory_intelligence.tools.productivity import (
    get_productivity_kpi as _get_productivity_kpi,
)
from factory_intelligence.tools.quality import get_quality_kpi as _get_quality_kpi
from factory_intelligence.tools.downtime import get_downtime_kpi as _get_downtime_kpi
from factory_intelligence.tools.summary import get_kpi_summary as _get_kpi_summary
from factory_intelligence.tools.alarms import (
    get_downtime_alarms as _get_downtime_alarms,
)

mcp = FastMCP("factory-intelligence")


# Tool #1: Productivity KPI
@mcp.tool()
async def get_productivity_kpi(
    start_time: str, end_time: str, line_id: int = None, equipment_id: int = None
):
    """
    Computes productivity metrics for a given time range.
    Returns total production, good bottles, and bad bottles with per-minute timeseries.
    Optionally filter by line_id or equipment_id.
    """
    return await _get_productivity_kpi(start_time, end_time, line_id, equipment_id)


# Tool #2: Quality KPI
@mcp.tool()
async def get_quality_kpi(
    start_time: str, end_time: str, line_id: int = None, equipment_id: int = None
):
    """
    Computes quality-related metrics including yield percentage and defect rate
    for a given time range.
    Optionally filter by line_id or equipment_id.
    """
    return await _get_quality_kpi(start_time, end_time, line_id, equipment_id)


# Tool #3: Downtime KPI
@mcp.tool()
async def get_downtime_kpi(
    start_time: str, end_time: str, line_id: int = None, equipment_id: int = None
):
    """
    Computes downtime and availability metrics for a given time range.
    Classifies each 10-second interval as uptime or downtime based on production counts.
    Optionally filter by line_id or equipment_id.
    """
    return await _get_downtime_kpi(start_time, end_time, line_id, equipment_id)


# Tool #4: KPI Summary/Bundle
@mcp.tool()
async def get_kpi_summary(
    start_time: str, end_time: str, line_id: int = None, equipment_id: int = None
):
    """
    Returns multiple KPIs together for a single time window, suitable for a
    high-level dashboard widget. Bundles productivity, quality, and downtime.
    Optionally filter by line_id or equipment_id.
    """
    return await _get_kpi_summary(start_time, end_time, line_id, equipment_id)


# Tool #5: Downtime Alarms Analysis
@mcp.tool()
async def get_downtime_alarms(
    start_time: str, end_time: str, line_id: int = None, equipment_id: int = None
):
    """
    Identifies and analyzes alarms that were active during downtime periods,
    helping to diagnose root causes of production stoppages.
    Optionally filter by line_id or equipment_id.
    """
    return await _get_downtime_alarms(start_time, end_time, line_id, equipment_id)


if __name__ == "__main__":
    mcp.run(transport="stdio")
