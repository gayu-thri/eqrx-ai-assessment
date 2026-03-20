# Factory Intelligence

This project has MCP server that exposes 5 KPI tools for a factory production line. An LLM agent calls these tools via MCP to answer questions like "Show me productivity KPI for last week". 

Data flow
```
Factory sensors -> TimescaleDB (stores data) -> MCP tools (computes KPIs) -> LLM agent (interprets) -> User's dashboard (displays)
```

Project structure
```
├── tests
  ├── test_tools.py          <- Test for all 5 tools
  └── test_tools_output.log  <- Output from running tests
├── src/factory_intelligence/
  ├── mcp_server.py          <- MCP server entry point
  ├── config.py              <- DB connection settings
  ├── tools/
  │   ├── productivity.py    <- Tool 1: Production counts
  │   ├── quality.py         <- Tool 2: Yield % & defect rate
  │   ├── downtime.py        <- Tool 3: Availability %
  │   ├── summary.py         <- Tool 4: All KPIs bundled
  │   └── alarms.py          <- Tool 5: Alarms during downtime
  ├── utilities/
  │   ├── db.py              <- Async connection pool
  │   ├── validation.py      <- Input validation
  │   └── response.py        <- Standardized JSON responses
  └── database/
      ├── setup_timescaledb.sh
      ├── connect_db.sh
      └── verify.sql
```

## Setup
### 1. Environment
```bash
# Install poetry
$ curl -sSL https://install.python-poetry.org | python3 -
$ export PATH="$HOME/.local/bin:$PATH"
$ poetry --version
```

```bash
# Install dependencies
$ poetry install
```
### 2. Docker
Install docker desktop from docker.com
```bash
# Verify using below
docker --version
$ docker run hello-world
```

### 3. Database
Download dump file and place it in the below location and update the path of `DUMP_FILE` in `setup_timescaledb.sh`:

Path: `src/factory_intelligence/database/ProductionDB_aggregates_20251214.dump`
```bash
# Setup TimescaleDB
cd src/factory_intelligence/database
chmod +x setup_timescaledb.sh
./setup_timescaledb.sh
```
This pulls TimescaleDB, creates the database, restores the dump, and verifies row counts.

Data range: December 5–14, 2025 (9 days of production data).

## Run tests
Make sure Docker container is still running
```bash
# Be inside eqrx-ai-assessment/factory_intelligence level where 
# ls gives you onboarding.md, pyproject.to, tech_notes.md, poetry.lock, README.md, src, tests
$ poetry run python tests/test_tools.py
```

## Run MCP server locally
```bash
$ poetry run python -m factory_intelligence.mcp_server
```

## Tools
 
| Tool | Description | Data Source |
|------|-------------|------------|
| `get_productivity_kpi` | Total production, good/bad counts | `agg_counter_1min` |
| `get_quality_kpi` | Yield %, defect rate % | `agg_counter_1min` |
| `get_downtime_kpi` | Uptime/downtime, availability % | `agg_counter_10sec_delta` |
| `get_kpi_summary` | All KPIs bundled | Both tables above |
| `get_downtime_alarms` | Alarms active during downtime | `agg_counter_10sec_delta`, `agg_boolean_state_durations` |
 
### Input Schema (all tools)
| Parameter | Type | Required |
|-----------|------|----------|
| `start_time` | ISO 8601 string | Yes |
| `end_time` | ISO 8601 string | Yes |
| `line_id` | string | No |
| `equipment_id` | string | No |
 
### Example Tool Call
```json
{
  "start_time": "2025-12-10T00:00:00Z",
  "end_time": "2025-12-10T23:59:59Z"
}
```
 
### Example Output (Productivity)
```json
{
  "tool": "get_productivity_kpi",
  "inputs": {
    "start_time": "2025-12-10T00:00:00Z",
    "end_time": "2025-12-10T23:59:59Z"
  },
  "result": {
    "summary": {
      "kpi_name": "Productivity",
      "total_production": 12500.0,
      "good_bottles": 12100.0,
      "bad_bottles": 400.0,
      "unit": "bottles"
    },
    "timeseries": [
      {"timestamp": "2025-12-10T00:00:00+00:00", "good": 8.0, "bad": 0.0, "total": 8.0}
    ],
    "metadata": {
      "data_source": "agg_counter_1min",
      "computation_note": "Total production = good + bad bottles"
    }
  },
  "status": "ok",
  "errors": []
}
```
 
## Some Notes
 
### Table Selection
- **Tools 1 & 2** use `agg_counter_1min` — pre-aggregated 1-minute buckets for fast queries over hour/day ranges.
- **Tool 3** uses `agg_counter_10sec_delta` — 10-second granularity is required because downtime is defined per-interval (production = 0 in a 10s window). Higher aggregates would mask short downtime periods.
- **Tool 5** joins `agg_counter_10sec_delta` (downtime detection) with `agg_boolean_state_durations` (alarm states) and `tags_metadata` (alarm tag lookup).
 
### Assumptions
- Tags `HMI_TOTAL_GOOD_BOTTLES` and `HMI_TOTAL_BAD_BOTTLES` are the sole production counters.
- A 10-second interval with zero total production (good + bad = 0) is classified as downtime.
- All timestamps are stored in UTC.
 
### Performance Considerations
- Queries filter by `tag_name` and `bucket` range, both of which are indexed in TimescaleDB.
- The connection pool (`psycopg3 AsyncConnectionPool`) reuses connections across tool calls.
- Consecutive downtime grouping in Tool 5 uses SQL window functions (`ROW_NUMBER` gap detection) to avoid fetching all rows into Python.
