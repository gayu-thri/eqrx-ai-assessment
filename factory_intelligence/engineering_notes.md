# Database

## Tables used for Tools

- Tools 1 & 2 (Productivity, Quality): 
    - Use `agg_counter_1min`
    - We only need **totals per time bucket**, 1-min granularity is enough
    - Faster than scanning 10-sec rows
- Tool 3 (Downtime):
    - MUST use `agg_counter_10sec_delta`
    - Downtime = any 10-sec interval where production = 0
    - If we used 1-min aggregates, a bucket could show total = 5 bottles but maybe 4 of the 6 ten-second intervals inside it had 0 production ---> That's why choose the smallest aggregate available to not miss even shortest downtime periods
- Tool 5 (Alarms):
    - Use `agg_counter_10sec_delta` for downtime detection
    - Then join with `agg_boolean_state_durations` for alarm states


## Key Tables in This Project
 
- **Hierarchy**: All tables include full parent IDs (enterprise → site → factory → zone → line → equipment) for fast multi-tenant queries
- **Counter Aggregates**: 2-stage delta architecture - agg_counter_10sec_delta hypertable stores accurate delta values with reset/gap handling, **higher-level aggregates (30sec, 1min, 30min, 1hour) sum these deltas**
- **Numeric Aggregates**: Independent continuous aggregates at each time granularity (10sec, 30sec, 1min, 30min, 1hour) with **statistical values (avg, min, max, stddev, count)**
- **Boolean Aggregates**: Event-based state duration tracking with start_time, end_time, and duration_seconds. **Active states have end_time IS NULL**

TimescaleDB automatically pre-aggregates it into coarser time buckets:

- agg_counter_10sec_delta — every 10 seconds, how many bottles were produced
- agg_counter_1min — every 1 minute (sums of the 10-sec data)
- agg_counter_30min, agg_counter_1hour — even coarser

- `agg_counter_10sec_delta`:
    - One row per 10-second interval per tag
    - Columns: `bucket`, `tag_name`, `delta` (production count in that interval)
    - `delta` = how many bottles produced in that 10-sec window
    - This is the **source of truth** for production counts
    - If `delta = 0` for both good and bad bottles → machine was idle (downtime)
 
- `agg_counter_1min`:
    - Same idea but pre-summed per minute
    - Columns: `bucket`, `tag_name`, `delta` (sum of 10-sec deltas within that minute)
    - Faster for queries that don't need 10-sec precision
 
- `agg_boolean_state_durations`:
    - Tracks duration of boolean states (ON/OFF, Running/Stopped, etc.) with start and end times.
    - Tracks how long a boolean tag stayed true or false
    - Columns: `start_time`, `end_time`, `tag_name`, `value` (true/false), `duration_seconds`
    - `end_time IS NULL` means the state is still active (ongoing)
    - Used for alarm analysis — **when `value = true`, an alarm is active**
 
- `tags_metadata`:
    - Master list of all 50 tags in the system
    - Important columns: `tag_name`, `data_type`, `is_counter`, `is_alarm`
    - Our production tags: `HMI_TOTAL_GOOD_BOTTLES`, `HMI_TOTAL_BAD_BOTTLES`
    - Alarm tags: any row where `is_alarm = true`
 
## Key Tags
 
- `HMI_TOTAL_GOOD_BOTTLES`:
    - Counter tag — increments every time a good bottle is produced
    - `delta` column = how many good bottles in that interval
    
- `HMI_TOTAL_BAD_BOTTLES`:
    - Counter tag — increments every time a defective bottle is produced
    - `delta` column = how many bad bottles in that interval
 
- Both are counters (not gauges):
    - Counter: only goes up (like an odometer). `delta` = difference between readings
    - Gauge: can go up or down (like temperature). Uses `avg_value`, `min_value`, etc.
    - Production tags are counters → `delta` column
 
## SQL Patterns Used
 
- Parameterized queries:
    ```sql
    -- psycopg3 uses %(name)s syntax
    WHERE tag_name = %(good)s AND bucket >= %(start)s
    -- NEVER do f-string interpolation like:
    -- f"WHERE tag_name = '{tag}'" <- WRONG
    ```
 
- CASE WHEN pivot (used in every tool):
    ```sql
    -- Turns two rows (one per tag) into two columns in one row
    SELECT
        bucket,
        SUM(CASE WHEN tag_name = %(good)s THEN delta ELSE 0 END) AS good,
        SUM(CASE WHEN tag_name = %(bad)s  THEN delta ELSE 0 END) AS bad
    FROM agg_counter_1min
    WHERE bucket >= %(start)s AND bucket < %(end)s
      AND tag_name IN (%(good)s, %(bad)s)
    GROUP BY bucket
    ```
    - Without this, you'd get separate rows for good and bad per bucket
    - With this, each row has both values side by side
 
- FILTER clause (used in downtime tool):
    ```sql
    -- Counts with conditions
    SELECT
        COUNT(*) FILTER (WHERE total = 0) AS downtime_intervals,
        COUNT(*) FILTER (WHERE total > 0) AS uptime_intervals
    FROM per_bucket
    ```
    - PostgreSQL-specific
 
- Consecutive grouping trick (used in alarms tool):
    ```sql
    -- Groups consecutive downtime intervals into events
    -- If buckets 10:00:00, 10:00:10, 10:00:20 are all downtime,
    -- they become one event: start=10:00:00, end=10:00:30, duration=30s
    
    -- subtract row_number * interval from each timestamp
    -- Consecutive timestamps produce the same "grp" value
    bucket - (ROW_NUMBER() OVER (ORDER BY bucket)) * INTERVAL '10 seconds' AS grp
    
    -- Then GROUP BY grp to get start/end of each downtime event
    ```
 
## MCP (Model Context Protocol)
 
- about MCP:
    - A protocol for LLM agents to call external tools
    - Like function calling / tool use, but standardized
    - The LLM sends a JSON request -> MCP server runs the tool -> returns JSON result
 
- Server workflow:
    - `FastMCP("factory-intelligence")` creates the server
    - **`@mcp.tool()` decorator registers a function as a callable tool**
    - The function's docstring becomes the tool description the LLM sees
    - The type hints become the input schema
    - `mcp.run(transport="stdio")` runs over stdin/stdout (agent launches the process)
 
- Testing:
    - `python tests/test_tools.py` -> calls tool functions directly
 
## async/await usages
 
- Why asyncnchronoyus:
    - psycopg3's async pool lets multiple tool calls share DB connections efficiently
    - MCP tools are async by default
    - `await` means "wait for this DB query to finish without blocking everything else"
 
- Pattern used everywhere:
    ```python
    pool = await get_pool() # get connection pool
    async with pool.connection() as conn: # borrow a connection
        async with conn.cursor(row_factory=dict_row) as cur: # create cursor 
            # cursor is pointer into DB - runs queries & hold results
            await cur.execute(query, params) # run query
            rows = await cur.fetchall() # get results
    ```
    - `dict_row` makes each row a dict (`row["bucket"]`, `row['good']`) instead of a tuple (`row[0]`)
    - Connection is auto-returned to pool when `async with` block ends
 