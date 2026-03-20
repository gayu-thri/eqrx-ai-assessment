# Engineering Notes

## Why Specific Tables Were Used

- **Tools 1 & 2 (Productivity, Quality):** Use `agg_counter_1min` — pre-aggregated 1-minute buckets are sufficient for production totals and yield calculations. Faster than scanning 10-second rows since we only need totals per time bucket.

- **Tool 3 (Downtime):** Uses `agg_counter_10sec_delta` — 10-second granularity is required because downtime is defined as any interval where production = 0. Using 1-minute aggregates would mask short downtime periods (e.g., a 1-min bucket could show total = 5 bottles but 4 of the 6 ten-second intervals inside had 0 production).

- **Tool 4 (Summary):** Calls Tools 1-3 internally, so it uses both `agg_counter_1min` and `agg_counter_10sec_delta`.

- **Tool 5 (Alarms):** Uses `agg_counter_10sec_delta` for downtime detection, then joins with `agg_boolean_state_durations` for alarm states and `tags_metadata` to identify alarm tags (`is_alarm = true`).

## Assumptions

- `HMI_TOTAL_GOOD_BOTTLES` and `HMI_TOTAL_BAD_BOTTLES` are the sole production counters. Both are counter-type tags (delta values, not gauges).
- A 10-second interval with zero total production (good + bad = 0) is classified as downtime.
- No target production value is available in the schema, so productivity is reported as absolute counts rather than a ratio.
- All timestamps are stored and queried in UTC.
- `line_id` and `equipment_id` are optional filters — when omitted, queries return data across all lines/equipment.

## Performance Considerations

- Queries filter by `tag_name` and `bucket` range, both indexed by TimescaleDB's chunk-based partitioning.
- `agg_counter_1min` is used over `agg_counter_10sec_delta` for Tools 1 & 2 to reduce the number of rows scanned (6x fewer rows per time range).
- The async connection pool (`psycopg3 AsyncConnectionPool`, min=2, max=10) reuses connections across concurrent tool calls.
- Consecutive downtime grouping in Tool 5 uses SQL window functions (`ROW_NUMBER` gap detection) to group intervals server-side, avoiding fetching all individual rows into Python.
- The CASE WHEN pivot pattern combines two tags (good/bad) into a single row per bucket, halving the result set compared to separate queries.
