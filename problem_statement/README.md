# Factory Intelligence – Sample Task

## 1) Context (High Level)

You will work on a prototype feature for **Factory Intelligence**: an interactive chat-driven system where users ask natural-language questions such as:

- "Show me productivity KPI for last week"
- "How was the quality KPI on 2025-12-10?"

Based on these requests, dashboard widgets are created or updated in near real time.

The system uses an **LLM agent** (LangGraph-based) that calls predefined tools via **MCP (Model Context Protocol)**.

Your task is to implement a small set of these tools in Python.

> [!NOTE]
> This is a sample technical task focused on data access, KPI computation, and tool interfaces. No additional service or business context is required or expected.

---

## 2) What We Will Provide

You will receive:

- **A PostgreSQL database schema** (`TIMESCALEDB_SETUP.md`), including:
  - A raw "big table" where factory data is ingested approximately every 2 seconds
  - One or more continuous aggregate tables (pre-aggregated for KPI queries)

- **A data dictionary** (`SCHEMA_QUICK_REFERENCE.md`) describing:
  - Column meanings
  - Units
  - Metric definitions

- **A KPI definition document** specifying formulas and aggregation logic for:
  - Productivity
  - Quality
  - Downtime
  - One additional KPI category

---

## 3) Task Objective

Implement an **MCP server in Python** that exposes four KPI tools. These tools will be called by an LLM agent through MCP.

Each tool must:

- Accept time-range inputs
- Query PostgreSQL using appropriate SQL
- Apply the provided KPI formulas
- Return results in a structured JSON format compatible with LLM tool-calling
- The MCP server must run locally

---

## 4) Tools to Implement

> [!NOTE]
> Please check the `tags_metadata` table for comprehensive information about all available tags, including descriptions, units, and data types.

Implement the following four tools (exact names may vary, but clarity matters):

### Tool 1 — Productivity KPI

Computes productivity metrics for a given time range.

**Data Tags Required:**
- `HMI_TOTAL_GOOD_BOTTLES` (Good production count)
- `HMI_TOTAL_BAD_BOTTLES` (Defect/reject count)

**Calculation:**
```
Total Production = HMI_TOTAL_GOOD_BOTTLES + HMI_TOTAL_BAD_BOTTLES
Productivity = Total Production / Target Production (if available)
```

**Typical outputs may include:**
- Productivity value (as defined in the KPI document)
- Total production count
- Good vs. bad bottle breakdown
- Optional time series for trend visualization
- Summary statistics

### Tool 2 — Quality KPI

Computes quality-related metrics.

**Data Tags Required:**
- `HMI_TOTAL_GOOD_BOTTLES` (Good production count)
- `HMI_TOTAL_BAD_BOTTLES` (Defect/reject count)

**Calculation:**
```
Total Production = HMI_TOTAL_GOOD_BOTTLES + HMI_TOTAL_BAD_BOTTLES
Quality (Yield %) = (HMI_TOTAL_GOOD_BOTTLES / Total Production) × 100
Defect Rate % = (HMI_TOTAL_BAD_BOTTLES / Total Production) × 100
```

**Typical outputs may include:**
- Yield percentage / defect rate / scrap rate (as defined)
- Good vs. bad counts
- Summary + optional time series

### Tool 3 — Downtime KPI

Computes downtime and availability metrics.

**Data Source:**
- `agg_counter_10sec_delta` table

**Data Tags Required:**
- `HMI_TOTAL_GOOD_BOTTLES` (Good production count)
- `HMI_TOTAL_BAD_BOTTLES` (Defect/reject count)

**Downtime Logic:**
```
For each 10-second interval in agg_counter_10sec_delta:
  Total Production = HMI_TOTAL_GOOD_BOTTLES + HMI_TOTAL_BAD_BOTTLES
  
  If Total Production = 0:
    → Downtime (machine not producing)
  Else:
    → Uptime (machine producing)

Total Downtime Duration = Count of intervals where Total Production = 0 × 10 seconds
Total Uptime Duration = Count of intervals where Total Production > 0 × 10 seconds
Availability % = (Total Uptime Duration / (Total Uptime + Total Downtime)) × 100
```

**Typical outputs may include:**
- Total downtime duration (in seconds/minutes/hours)
- Total uptime duration
- Availability percentage
- Number of downtime intervals
- Time series showing uptime/downtime periods

### Tool 4 — KPI Summary / Bundle

Returns multiple KPIs together for a single time window, suitable for a high-level dashboard widget.

**Data Tags Required:**
- All tags from Tools 1-3 combined

**Returns:**
- Productivity metrics
- Quality metrics
- Downtime/availability metrics
- Aggregated summary suitable for dashboard overview

### Tool 5 — Downtime Alarms Analysis

Identifies and analyzes alarms that were active during downtime periods, helping to diagnose root causes of production stoppages.

**Data Source:**
- `agg_boolean_state_durations` table
- `tags_metadata` table (filtered by `is_alarm = true`)
- `agg_counter_10sec_delta` table (to identify downtime periods)

**Logic:**
```
Step 1: Identify downtime periods
  - Query agg_counter_10sec_delta for intervals where (HMI_TOTAL_GOOD_BOTTLES + HMI_TOTAL_BAD_BOTTLES) = 0
  - Group consecutive downtime intervals into downtime events

Step 2: Find active alarms during downtime
  - Query tags_metadata WHERE is_alarm = true to get alarm tag IDs
  - Query agg_boolean_state_durations for alarm tags WHERE:
    - value = true (alarm is active)
    - Time range overlaps with downtime periods
    - (start_time <= downtime_end AND (end_time >= downtime_start OR end_time IS NULL))

Step 3: Correlate alarms with downtime
  - Match alarm activation times with downtime periods
  - Calculate alarm duration during downtime
  - Rank alarms by frequency and duration
```

**Typical outputs may include:**
- List of alarms active during each downtime period
- Alarm frequency (how many times each alarm occurred during downtime)
- Total duration of each alarm during downtime
- Alarm timeline showing when alarms started/ended relative to downtime
- Top alarms contributing to downtime (ranked by duration or frequency)
- Correlation between specific alarms and production stoppages

**Example Use Cases:**
- "What alarms were active during the downtime on 2025-12-10?"
- "Which alarm occurs most frequently during production stops?"
- "Show me all downtime events with their associated alarms for last week"


---

## 5) Tool Input Contract

All MCP tools must accept the following inputs:

### Required:
- `start_time` (ISO 8601 string)
- `end_time` (ISO 8601 string)

### Optional (only if supported by the schema):
- `timezone`
- `line_id`
- `station_id`
- `shift`
- Other logical production filters

> [!IMPORTANT]
> Input validation is expected (for example: invalid date ranges).

---

## 6) Tool Output Contract

Each tool must return structured JSON suitable for consumption by an LLM agent and downstream dashboard logic.

### Example Response Structure:

```json
{
  "tool": "get_productivity_kpi",
  "inputs": {
    "start_time": "2025-12-01T00:00:00Z",
    "end_time": "2025-12-07T23:59:59Z",
    "filters": {
      "line_id": "L1"
    }
  },
  "result": {
    "summary": {
      "kpi_name": "Productivity",
      "value": 0.87,
      "unit": "ratio"
    },
    "timeseries": [
      { "timestamp": "2025-12-01T00:00:00Z", "value": 0.85 },
      { "timestamp": "2025-12-02T00:00:00Z", "value": 0.88 }
    ],
    "metadata": {
      "data_source": "continuous_aggregate_table",
      "computation_note": "As per KPI definition v1"
    }
  },
  "status": "ok",
  "errors": []
}
```

### Error Cases

Error cases should return:
- `status = "error"`
- A meaningful error message
- No partial or ambiguous results

---

## 7) Technical Requirements

| Requirement | Specification |
|------------|---------------|
| **Language** | Python 3.10+ |
| **Database** | PostgreSQL with TimescaleDB extension |
| **DB Access** | Any standard PostgreSQL client library (e.g., psycopg / psycopg2 / SQLAlchemy) |
| **Queries** | Parameterized SQL only |
| **Execution** | MCP server must run locally and expose all tools |

---

## 8) Timebox

**Total duration:** 3 days

**Focus on:**
- Correctness
- Clean tool contracts
- Reasonable performance

> [!WARNING]
> Do not over-engineer deployment, security, or UI aspects

---

## 9) Deliverables

### Code Repository (zip or Git link):
- MCP server implementation
- Four KPI tools

### README.md including:
- How to run the MCP server locally
- Tool descriptions and input/output schemas
- Example tool calls and example outputs

### Tests or Validation Script
- Simple tests or scripts demonstrating correct KPI results

### Engineering Notes
- Why specific tables were used
- Assumptions made
- Performance considerations

### Video Recording or Screenshot:
- A video recording or screenshot of results explaining the output
- Should clearly demonstrate the MCP server running and tools returning correct results

---

## 10) Evaluation Criteria

Submissions will be evaluated on:

- ✅ Correctness of KPI computation
- ✅ Quality of MCP tool design
- ✅ Clarity of JSON responses
- ✅ PostgreSQL query efficiency
- ✅ Code readability and structure
- ✅ Ability to reason about trade-offs and assumptions

> [!CAUTION]
> **The README.md file should be clear enough to reproduce the results.** If the file lacks clarity and we are unable to reproduce the result, **we will not shortlist you for the final round.**

---

## 11) Suggested Approach

1. Review schema and KPI definitions
2. Write PostgreSQL queries for each KPI
3. Wrap queries in Python tool functions
4. Expose tools via an MCP server
5. Test with multiple time ranges
6. Document assumptions and examples

---

## 12) Contact for Clarifications

If you have any questions or need clarifications, please email:

- **arun.nivethan@mail.eqrx.xyz**
- **Dp@flowgentic.ai**