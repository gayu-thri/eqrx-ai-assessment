from mcp.server.fastmcp import FastMCP

mcp = FastMCP("factory-intelligence")


# Tool #1: Productivity KPI
@mcp.tool()
async def get_productivity_kpi():
    """
    Computes productivity metrics for a given time range
    """
    return await _get_productivity_kpi(start_time, end_time, line_id, equipment_id)


# Tool #2: Quality KPI
@mcp.tool()
async def get_quality_kpi():
    """
    Computes quality-related metrics
    """
    pass


# Tool #3: Downtime KPI
@mcp.tool()
async def get_downtime_kpi():
    """
    Computes downtime and availability metrics
    """
    pass


# Tool #4: KPI Summary/Bundle
@mcp.tool()
async def get_kpi_summary_bundle():
    """
    Returns multiple KPIs together for a single time window, suitable for a high-level dashboard widget
    """
    pass


# Tool #5: Downtime Alarms Analysis
@mcp.tool()
async def get_kpi_summary_bundle():
    """
    Identifies and analyzes alarms that were active during downtime periods, helping to diagnose root causes of production stoppages
    """
    pass
