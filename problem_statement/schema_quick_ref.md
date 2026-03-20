# Database Schema Quick Reference

> [!NOTE]
> All timestamps in the database are stored in **UTC format** (timestamptz). For local timezone conversion, use the `timezone` field from the `sites` table, which contains the IANA timezone identifier for each site (e.g., 'America/Chicago', 'Asia/Kolkata').

## Hierarchy Tables (6 levels)

### 1. enterprises
- `id`, `enterprise_name`, `enterprise_code`, `description`, `is_active`, `metadata`

### 2. sites
- `id`, `enterprise_id`, `site_name`, `site_code`, `timezone`, `location`, `is_active`, `metadata`

### 3. factories
- `id`, `enterprise_id`, `site_id`, `factory_name`, `factory_code`, `description`, `is_active`, `metadata`

### 4. zones
- `id`, `enterprise_id`, `site_id`, `factory_id`, `zone_name`, `zone_code`, `description`, `is_active`, `metadata`

### 5. lines
- `id`, `enterprise_id`, `site_id`, `factory_id`, `zone_id`, `line_name`, `line_code`, `description`, `is_active`, `metadata`

### 6. equipment
- `id`, `enterprise_id`, `site_id`, `factory_id`, `zone_id`, `line_id`, `equipment_name`, `equipment_code`, `equipment_type`, `has_production_metric`, `is_line_production_source`, `description`, `is_active`, `metadata`

---

## Tag Metadata

### tags_metadata
- `id`, `enterprise_id`, `site_id`, `factory_id`, `zone_id`, `line_id`, `equipment_id`, `tag_name`, `display_name`, `data_type` (numeric/boolean/text/counter), `is_counter`, `is_kpi`, `is_alarm`, `counter_max_increment`, `unit`, `category`, `display_priority`, `description`, `is_active`, `metadata`

---

## Shifts

### shifts
- `id`, `enterprise_id`, `site_id`, `factory_id`, `shift_name`, `shift_code`, `start_time`, `end_time`, `description`, `is_active`, `metadata`

---

## Aggregates

### 1) Counter Aggregates (Delta-based Production Tracking)

#### agg_counter_10sec_delta (hypertable - base delta table)
Primary table for **accurate production counting** with delta values calculated from raw counter data.

**Columns:**
- `bucket` (timestamptz) - 10-second time bucket
- `tag_id` (integer) - Reference to tags_metadata
- `enterprise_id`, `site_id`, `factory_id`, `zone_id`, `line_id`, `equipment_id` - Full hierarchy for filtering
- `delta_value` (numeric) - Actual production count for this 10-second interval
- `is_reset` (boolean) - Indicates if counter was reset during this interval
- `is_gap` (boolean) - Indicates if there was a data gap

**Usage:** This is the **source of truth for production counts**. Query this table directly for accurate 10-second granularity data.

#### agg_counter_30sec (continuous aggregate)
**Columns:**
- `bucket` (timestamptz) - 30-second time bucket
- `tag_id`, hierarchy IDs (same as above)
- `total_delta` (numeric) - Sum of delta_value from agg_counter_10sec_delta

**Usage:** Pre-aggregated 30-second production totals. Faster queries for medium-granularity data.

#### agg_counter_1min (continuous aggregate)
**Columns:**
- `bucket` (timestamptz) - 1-minute time bucket
- `tag_id`, hierarchy IDs (same as above)
- `total_delta` (numeric) - Sum of delta_value from agg_counter_10sec_delta

**Usage:** Pre-aggregated 1-minute production totals. Commonly used for **dashboard KPIs**.

#### agg_counter_30min (continuous aggregate)
**Columns:**
- `bucket` (timestamptz) - 30-minute time bucket
- `tag_id`, hierarchy IDs (same as above)
- `total_delta` (numeric) - Sum of delta_value from agg_counter_10sec_delta

**Usage:** Pre-aggregated 30-minute production totals. Useful for **hourly trend analysis**.

#### agg_counter_1hour (continuous aggregate)
**Columns:**
- `bucket` (timestamptz) - 1-hour time bucket
- `tag_id`, hierarchy IDs (same as above)
- `total_delta` (numeric) - Sum of delta_value from agg_counter_10sec_delta

**Usage:** Pre-aggregated hourly production totals. Ideal for **shift reports and daily summaries**.

### 2) Numeric Aggregates (Statistical Aggregates)

#### agg_numeric_10sec (continuous aggregate)
**Columns:**
- `bucket` (timestamptz) - 10-second time bucket
- `tag_id` (integer) - Reference to tags_metadata
- `enterprise_id`, `site_id`, `factory_id`, `zone_id`, `line_id`, `equipment_id` - Full hierarchy for filtering
- `avg_value` (numeric) - Average value during the interval
- `min_value` (numeric) - Minimum value during the interval
- `max_value` (numeric) - Maximum value during the interval
- `stddev_value` (numeric) - Standard deviation during the interval
- `count` (bigint) - Number of data points in the interval

**Usage:** **High-resolution statistical data for process parameters (temperature, pressure, speed, etc.)**

#### agg_numeric_30sec (continuous aggregate)
**Columns:** Same as agg_numeric_10sec with 30-second buckets

**Usage:** Medium-resolution statistical aggregates for trend analysis

#### agg_numeric_1min (continuous aggregate)
**Columns:** Same as agg_numeric_10sec with 1-minute buckets

**Usage:** Standard resolution for most **dashboard visualizations and KPI calculations**

#### agg_numeric_30min (continuous aggregate)
**Columns:** Same as agg_numeric_10sec with 30-minute buckets

**Usage:** **Hourly trend** analysis and **shift-level summaries**

#### agg_numeric_1hour (continuous aggregate)
**Columns:** Same as agg_numeric_10sec with 1-hour buckets

**Usage:** **Daily/weekly reports** and **long-term trend** analysis

### 3) Boolean Aggregates (State Duration Tracking)

#### agg_boolean_state_durations (hypertable)
Tracks duration of boolean states (ON/OFF, Running/Stopped, etc.) with start and end times.

**Columns:**
- `start_time` (timestamptz) - When the state began
- `end_time` (timestamptz) - When the state ended (NULL for active/ongoing states)
- `tag_id` (integer) - Reference to tags_metadata
- `enterprise_id`, `site_id`, `factory_id`, `zone_id`, `line_id`, `equipment_id` - Full hierarchy for filtering
- `value` (boolean) - The state value (true/false)
- `duration_seconds` (numeric) - Duration of this state in seconds (NULL for active states)

**Usage:** 
- Calculate total uptime/downtime
- Identify state change events
- Analyze machine availability patterns
- Active states have `end_time IS NULL`

---

## Key Concepts

**Hierarchy:** All tables include full parent IDs (enterprise → site → factory → zone → line → equipment) for fast multi-tenant queries

**Counter Aggregates:** 2-stage delta architecture - `agg_counter_10sec_delta` hypertable stores accurate delta values with reset/gap handling, higher-level aggregates (30sec, 1min, 30min, 1hour) sum these deltas

**Numeric Aggregates:** Independent continuous aggregates at each time granularity (10sec, 30sec, 1min, 30min, 1hour) with statistical values (avg, min, max, stddev, count)

**Boolean Aggregates:** Event-based state duration tracking with `start_time`, `end_time`, and `duration_seconds`. Active states have `end_time IS NULL`