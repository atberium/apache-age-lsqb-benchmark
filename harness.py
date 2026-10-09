import argparse
import gc
import json
import re
import statistics
import time
from contextlib import contextmanager
from datetime import datetime
from os import makedirs, path, walk
from typing import Any, Final, Generator

import psycopg2
from psycopg2 import errors
from psycopg2.extensions import connection as PgConnection
from pydantic import BaseModel

args_parser = argparse.ArgumentParser(description="Process command-line arguments.")
args_parser.add_argument('--queries-path', type=str, help='Path to directory with LSQB queries')
args_parser.add_argument('--times', type=int, default=1, help='Times to run each query')
args_parser.add_argument('--timeout-millis', type=int, default=60000, help='SQL query execution timeout in milliseconds')
args_parser.add_argument('--result-path', type=str, help='Path to output result file')
args_parser.add_argument("--db-host", type=str, default='localhost', help="PostgresQL host")
args_parser.add_argument("--db-port", type=int, default=5432, help="PostgresQL port")
args_parser.add_argument("--db-user", type=str, default='postgres', help="PostgresQL username")
args = args_parser.parse_args()

MEM_KEY_RSS: Final = 'VmRSS'
MEM_KEY_HWM: Final = 'VmHWM'

EXPLAIN_RUN: Final = "EXPLAIN (ANALYZE, BUFFERS, TIMING OFF, VERBOSE, SETTINGS ON, FORMAT JSON)"
EXPLAIN_EST: Final = "EXPLAIN (VERBOSE, COSTS ON, SETTINGS ON, FORMAT JSON)"

NAME_SCHEMA: Final = "lsqb"

RUN_TIMEOUT: Final = "timeout"
RUN_ERROR_PREFIX: Final = "error:"

STATS_SQL: Final = f"""
    SELECT c.relname, c.reltuples, c.relpages, s.n_live_tup, s.last_analyze, s.last_autoanalyze
    FROM pg_class c
    JOIN pg_namespace n ON n.oid = c.relnamespace
    LEFT JOIN pg_stat_user_tables s ON s.relid = c.oid
    WHERE n.nspname = '{NAME_SCHEMA}' AND c.relkind IN ('r', 'm')
    ORDER BY c.relname
"""

SETTINGS_SQL: Final = """
    SELECT name, setting, unit, source
    FROM pg_settings
    WHERE name IN ('server_version', 'work_mem', 'shared_buffers', 'effective_cache_size',
                'max_parallel_workers', 'max_parallel_workers_per_gather', 'jit',
                'statement_timeout', 'autovacuum_naptime', 'random_page_cost')
    ORDER BY name
"""


class BenchmarkResult(BaseModel):
    result: Any | None = None
    median: float | None = None      # None unless every repetition succeeded
    mean: float | None = None        # None unless every repetition succeeded
    memory: float = 0.0
    count_timeout: int = 0
    count_error: int = 0
    runs: list[str] = []             # one entry per repetition: "<seconds>" | "timeout" | "error:<Class>"
    ok_times: list[float] = []       # successful repetitions only

    @property
    def count_failed(self) -> int:
        return self.count_timeout + self.count_error

class PlanResult(BaseModel):
    query: str
    executed: bool
    plan: Any | None = None
    error: str | None = None

class MemoryResult(BaseModel):
    peak: int
    baseline: int

def read_memory(pid: int, mem_key: str) -> int:
    with open(f"/proc/{pid}/status") as f: 
        rss = [int(v.replace(' kB', '').strip()) for _, v  in [a.split("\t") for a in f.read().split("\n") if re.match(rf"{mem_key}", a)]]
        if len(rss) == 0:
            return 0
        
        return rss[0]

def run_query(query: str, result: BenchmarkResult, host: str, port: int, user: str, timeout: int) -> None:
    try:
        with get_connection(host, port, user, timeout) as connection:
            pid = get_pid(connection)
            baseline = read_memory(pid, MEM_KEY_RSS)

            with connection.cursor() as cursor:
                t0 = time.perf_counter()
                cursor.execute(query)
                rows = cursor.fetchall()
                elapsed = time.perf_counter() - t0

            peak = read_memory(pid, MEM_KEY_HWM)

        result.result = rows
        result.memory = max(result.memory, peak - baseline)
        result.ok_times.append(elapsed)
        result.runs.append(f"{elapsed:.6f}")

    except errors.QueryCanceled as e:
        result.count_timeout += 1
        result.runs.append(RUN_TIMEOUT)
        print(f"Query timed out: {e}")

    except Exception as e:
        result.count_error += 1
        result.runs.append(f"{RUN_ERROR_PREFIX}{type(e).__name__}")
        print(f"Query failed: {type(e).__name__}: {e}")


def execute_and_fetch(connection: PgConnection, query: str) -> Any:
    with connection.cursor() as cursor:
        cursor.execute(query)
        return cursor.fetchone()[0]


def execute_and_fetch_all(connection: PgConnection, query: str) -> list[tuple]:
    with connection.cursor() as cursor:
        cursor.execute(query)
        return cursor.fetchall()


def execute_no_result(connection: PgConnection, query: str) -> str:
    with connection.cursor() as cursor:
        cursor.execute(query)
        return str(cursor.statusmessage)


def get_pid(connection: PgConnection) -> int:
    return int(execute_and_fetch(connection, "SELECT pg_backend_pid();"))


def profile_metric(query: str, host: str, port: int, user: str, timeout: int, times_query: int) -> BenchmarkResult:
    result = BenchmarkResult()

    for _ in range(times_query):
        run_query(query, result, host, port, user, timeout)

    if result.count_failed == 0 and result.ok_times:
        result.median = statistics.median(result.ok_times)
        result.mean = statistics.mean(result.ok_times)

    gc.collect()

    return result


def collect_stats(connection: PgConnection) -> list[dict]:
    rows = execute_and_fetch_all(connection, STATS_SQL)
    return [
        {
            "relname": r[0],
            "reltuples": float(r[1]),
            "relpages": int(r[2]),
            "n_live_tup": None if r[3] is None else int(r[3]),
            "last_analyze": None if r[4] is None else r[4].isoformat(),
            "last_autoanalyze": None if r[5] is None else r[5].isoformat(),
        }
        for r in rows
    ]


def collect_settings(connection: PgConnection) -> list[dict]:
    rows = execute_and_fetch_all(connection, SETTINGS_SQL)
    return [{"name": r[0], "setting": r[1], "unit": r[2], "source": r[3]} for r in rows]


def run_analyze(connection: PgConnection) -> dict:
    connection.notices = []
    status = execute_no_result(connection, "ANALYZE VERBOSE;")
    return {"status": status, "notices": [n.rstrip() for n in connection.notices]}


def explain_query(connection: PgConnection, name: str, sql: str, execute_plan: bool = True) -> PlanResult:
    if not execute_plan:
        # estimate-only: does not run the query, so it cannot perturb the timings that follow
        try:
            plan = execute_and_fetch(connection, f"{EXPLAIN_EST} {sql}")
            return PlanResult(query=name, executed=False, plan=plan)
        except Exception as e:
            print(f"  {name}: planning failed: {e}")
            return PlanResult(query=name, executed=False, plan=None, error=str(e).strip())

    try:
        plan = execute_and_fetch(connection, f"{EXPLAIN_RUN} {sql}")
        return PlanResult(query=name, executed=True, plan=plan)
    except errors.QueryCanceled as e:
        print(f"  {name}: cancelled after the timeout, falling back to an estimate-only plan")
        fallback_error = str(e).strip()
    except Exception as e:
        print(f"  {name}: {e}")
        fallback_error = str(e).strip()

    try:
        plan = execute_and_fetch(connection, f"{EXPLAIN_EST} {sql}")
        return PlanResult(query=name, executed=False, plan=plan, error=fallback_error)
    except Exception as e:
        print(f"  {name}: planning failed: {e}")
        return PlanResult(query=name, executed=False, plan=None, error=str(e).strip())


def write_state(connection: PgConnection, plan_dir: str) -> list[dict]:
    before = collect_stats(connection)
    settings = collect_settings(connection)
    analyze_report = run_analyze(connection)
    after = collect_stats(connection)

    with open(path.join(plan_dir, "_state.json"), 'w') as s:
        json.dump({
            "captured_at": datetime.now().isoformat(),
            "settings": settings,
            "analyze": analyze_report,
            "stats_before_analyze": before,
            "stats_after_analyze": after,
        }, s, indent=1, default=str)

    analysed = sum(1 for r in after if r["last_analyze"] is not None)
    print(f"ANALYZE: {analyze_report['status']}, "
          f"{analysed} of {len(after)} relations now carry statistics")
    return after


def stats_fingerprint(stats: list[dict]) -> str:
    """Changes if anything the planner reads about the tables changes."""
    return json.dumps([[r["relname"], r["reltuples"], r["relpages"],
                        r["last_analyze"], r["last_autoanalyze"]] for r in stats], sort_keys=True)


def write_plan(plan_dir: str, file: str, result: PlanResult) -> str:
    plan_file = path.join(plan_dir, f"{path.splitext(file)[0]}.json")
    with open(plan_file, 'w') as p:
        json.dump({
            "query": file,
            "executed": result.executed,
            "error": result.error,
            "plan": result.plan,
        }, p, indent=1, default=str)
    return plan_file


def open_plan_connection(host: str, port: int, user: str, timeout: int) -> PgConnection:
    connection = connect(host, port, user, timeout)
    connection.autocommit = True
    return connection


def ensure_plan_connection(connection: PgConnection, host: str, port: int, user: str, timeout: int) -> PgConnection:
    if connection.closed == 0:
        return connection
    print("Plan connection was lost, reconnecting")
    return open_plan_connection(host, port, user, timeout)


def format_optional(value: float | None) -> str:
    return "" if value is None else f"{value:.6f}"


def benchmark(host: str, port: int, user: str, timeout: int, path_to_query: str, path_to_output: str, times_query: int) -> None:
    plan_dir = path.splitext(path_to_output)[0]
    makedirs(plan_dir, exist_ok=True)

    query_files = sorted(f for f in next(walk(path_to_query))[2] if f.endswith('.sql'))
    total_failed = 0
    plan_connection: PgConnection | None = None

    try:
        plan_connection = open_plan_connection(host, port, user, timeout)
        stats_at_start = write_state(plan_connection, plan_dir)

        for file in query_files:
            with open(f"{path_to_query}/{file}", 'r') as f:
                sql = f.read()

            print(f"Planning query of {file}")
            plan_connection = ensure_plan_connection(plan_connection, host, port, user, timeout)
            write_plan(plan_dir, file, explain_query(plan_connection, file, sql.strip().rstrip(';'), execute_plan=False))

            print(f"Running query of {file}")
            result = profile_metric(sql, host, port, user, timeout, times_query)
            runs = ";".join(result.runs)

            with open(path_to_output, 'a') as o:
                o.write(f"{datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]},{file},{result.result},"
                        f"{format_optional(result.median)},{format_optional(result.mean)},{result.memory},[{runs}]\n")
            total_failed += result.count_failed

        try:
            plan_connection = ensure_plan_connection(plan_connection, host, port, user, timeout)
            if stats_fingerprint(collect_stats(plan_connection)) != stats_fingerprint(stats_at_start):
                print("WARNING: the statistics state changed during the run, so the plans and the timings no longer share one state")
        except Exception as e:
            print(f"WARNING: could not re-check the statistics state: {e}")

    except Exception as e:
        print(f"Benchmark failed: {e}")

    finally:
        if plan_connection is not None and plan_connection.closed == 0:
            plan_connection.close()

        total_runs = len(query_files) * times_query
        rate = total_failed / total_runs * 100 if total_runs else 0.0
        with open(path_to_output, 'a') as o:
            o.write(f"failure_rate,{rate:.3f}%\n")


def connect(host: str, port: int, user: str, timeout: int) -> PgConnection:
    return psycopg2.connect(
        host=host,
        port=port,
        user=user,
        options=f"-c search_path=ag_catalog,$user,public -c statement_timeout={timeout}"
    )


@contextmanager
def get_connection(host: str, port: int, user: str, timeout: int) -> Generator[PgConnection]:
    connection = connect(host, port, user, timeout)

    try:
        yield connection
    finally:
        connection.close()


if __name__ == "__main__":
    benchmark(
        args.db_host,
        args.db_port,
        args.db_user,
        args.timeout_millis,
        args.queries_path,
        args.result_path,
        args.times
    )