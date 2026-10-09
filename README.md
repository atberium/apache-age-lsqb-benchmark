# LSQB on Apache AGE

The nine [LSQB](https://github.com/ldbc/lsqb) queries run on Apache AGE (PostgreSQL 19 beta 1) at six scale
factors, SF 0.1–30, under the protocol of campaign 2 of the
[SQL/PGQ study](https://ldbcouncil.org/docs/papers/postgres-sql-pgq-benchmark-report.pdf)
([data](https://github.com/atberium/postgres-lsqb-benchmark)), so that the two can be compared. This
repository holds the harness, the schemas and queries, and every result: timings, table statistics and query
plans.

## What is measured

LSQB's `Message` vertex is a supertype of `Comment` and `Post`. AGE has no multi-label vertices, so the
dataset can be loaded in more than one way. Four representations were measured:

| Name | Directory | `Message` is represented as |
|---|---|---|
| TP (Type Property) | `queries/with-type-property` | one `Message` label; the subtype in a `type` property |
| TP+GIN | `queries/with-type-property` | TP plus a GIN index on `Message.properties` (last line of `graph.sql`, uncommented) |
| AMV (Additional Message Vlabel) | `queries/with-additional-message-vlabel` | `Comment` and `Post` labels, plus a copy of every vertex and edge under `Message` |
| IH (InHeritance) | `queries/with-inheritance` | `Comment` and `Post` tables that inherit from `Message` (`ALTER TABLE … INHERIT`) |

Each configuration — one representation at one scale factor — runs on its own instance: one load, one
`ANALYZE`, then each query five times with a 600-second timeout.

## Layout

```
harness.py                  runs the queries and records timings, statistics and plans
queries/<representation>/
  graph.sql                 creates the graph and labels and loads the CSV files
  q1.sql … q9.sql           the LSQB queries in Cypher, wrapped in cypher()
runs/<SF>-<mode>/           one directory per configuration; mode is TP, TP-with-index, AMV or IH
  <SF>.<mode>.<timestamp>.result.txt    load log and timings
  <SF>.<mode>.<timestamp>.result/
    _state.json             server settings and table statistics before and after ANALYZE
    qN.json                 plan of query N, EXPLAIN (VERBOSE, COSTS, SETTINGS, FORMAT JSON)
    qN.txt                  the same plan rendered in PostgreSQL's text layout
```

## Result file format

The `.result.txt` file starts with the output of loading `graph.sql`, then:

- `Time load data,<seconds>` — wall-clock time of the `psql` call that ran `graph.sql`;
- `Before` / `After` — `pg_database_size(current_database())` before and after the load;
- one line per query:

  ```
  <timestamp>,<query file>,<result>,<median s>,<mean s>,<peak memory kB>,[<run 1>;…;<run 5>]
  ```

  Each run is a time in seconds, `timeout` or `error:<class>`. The median and mean are empty unless all five
  runs succeeded. Peak memory is the backend's `VmHWM` minus its `VmRSS` before the query;
- `failure_rate,<percent>` — the share of runs that timed out or failed.

Every LSQB query returns a single count; `<result>` is that count.

## Query plans

Plans are captured with `EXPLAIN` without `ANALYZE`, once per query and before its timed runs, in the same
statistics state as the timings. They show the planner's choices and row estimates, not actual row counts.
`qN.txt` carries the same information as `qN.json`, laid out like PostgreSQL's text `EXPLAIN`; fields that
PostgreSQL omits in text when they hold their default value are omitted there too.

## Running it

Requirements: an AGE-enabled PostgreSQL server started with `shared_preload_libraries=age`, Python 3 with
`psycopg2` and `pydantic`, and the LSQB dataset as CSV files named as in `graph.sql`. Vertex files have an `id`
column followed by property columns; edge files have `start_id`, `start_vertex_type`, `end_id` and
`end_vertex_type`. For TP, for example, `Post.csv` looks like this (ids illustrative):

```
"id","type"
1099511627776,"Post"
1099511627777,"Post"
```

`graph.sql` refers to the files by name only; AGE resolves them in its load directory, which was `/tmp/age` in
these runs.

1. Load the graph:

   ```
   psql -v ON_ERROR_STOP=1 -U postgres -f queries/with-inheritance/graph.sql
   ```

2. Run the queries. The harness treats every `.sql` file in `--queries-path` as a query, so point it at a
   directory that holds only `q1.sql` … `q9.sql`:

   ```
   mkdir -p /tmp/lsqb-queries && cp queries/with-inheritance/q?.sql /tmp/lsqb-queries/
   python harness.py \
       --queries-path /tmp/lsqb-queries \
       --result-path ./out/1.IH.result.txt \
       --times 5 \
       --timeout-millis 600000
   ```

   The connection defaults to `postgres@localhost:5432`; `--db-host`, `--db-port` and `--db-user` change it.
   Plans and `_state.json` are written to a directory named after the result file without its extension.

## What the measurements are not

- **Untuned.** The server ran on packaged defaults (`shared_buffers` 128 MB, `work_mem` 4 MB, two workers
  per gather); only the session timeout was set.
- **One load per configuration.** A median describes the timing of one plan; variation between independent
  loads was not measured.
- **Not a release build.** AGE is the development snapshot published as `apache/age:dev_snapshot_PG19`
  (AGE 1.8.0 on PostgreSQL 19 beta 1), image digest
  `sha256:db765e1bf2d486176ed9b354befd82c8b0c3739416af8d56015eed268c33c2dd`.
- **Implementations, not languages.** Comparisons with SQL/PGQ compare these schemas and queries with the
  ones published for the SQL/PGQ study, over different physical layouts.

## References

- LSQB: <https://github.com/ldbc/lsqb>
- SQL/PGQ study, report: <https://ldbcouncil.org/docs/papers/postgres-sql-pgq-benchmark-report.pdf>
- SQL/PGQ study, harness and data: <https://github.com/atberium/postgres-lsqb-benchmark>
- Apache AGE: <https://github.com/apache/age>
