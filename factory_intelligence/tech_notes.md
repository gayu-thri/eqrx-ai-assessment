# Database

- **ACID basics**
    - Atomicity: **won't half-finish**. All or nothing. If you're transferring money & debit succeeds but credit fails, whole thing rolls back. No half-done transactions.
    - Consistency: **won't break rules**. Rules stay enforced. If a column says "NOT NULL" or a foreign key must exist, no transaction can leave the DB in a state that breaks those rules.
    - Isolation: **won't interfere**. Two transactions happening at the same time don't see each other's half-finished work. Like two people editing different rows, they don't step on each other.
    - Durability: **won't forget**. Once a transaction is committed, it's saved permanently. Even if server crashes right after, data survives (written to disk, not just memory).

- **Hypertable vs Delta Table**:
    - Delta Table
        - Data Reliability & Versioning (Lakehouse)
        - Parquet Files + Transaction Log
        - ACID (Atomicity, Consistency, Isolation, Durability) transactions
    - Hypertable
        - core feature of TimescaleDB (built on PostgreSQL)
        - Designed for high-performance **time-series data** 
        - **Automatic Partitioning**: Breaks tables into time-based buckets (e.g., one day per chunk)
            - Making it act like a single table to the user, while managing thousands of small sub-tables (chunks) behind the scenes
        - **Faster Queries (Chunk Skipping)**: Queries can skip chunks that don't match the time range, improving speed
        - PostgreSQL ACID
- In this project,
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

# Model Context Protocol (MCP)

- **Connects AI applications to external systems**

- Using MCP, AI applications like Claude or ChatGPT can connect to data sources (e.g. local files, databases), tools (e.g. search engines, calculators) and workflows (e.g. specialized prompts)

- Enables to **access key information and perform tasks**

- Think of MCP like a USB-C port for AI applications. Just as USB-C provides a standardized way to connect electronic devices, MCP provides a standardized way to connect AI applications to external systems.
![https://mintcdn.com/mcp/bEUxYpZqie0DsluH/images/mcp-simple-diagram.png?w=1100&fit=max&auto=format&n=bEUxYpZqie0DsluH&q=85&s=341b88d6308188ab06bf05748c80a494](https://mintcdn.com/mcp/bEUxYpZqie0DsluH/images/mcp-simple-diagram.png?w=1100&fit=max&auto=format&n=bEUxYpZqie0DsluH&q=85&s=341b88d6308188ab06bf05748c80a494)