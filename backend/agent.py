import logging
import json
import sqlite3
import time
from concurrent.futures import ThreadPoolExecutor

try:
    from . import cache
    from .db import execute_stats_sql, execute_primary_sql
    from .llm import (
        combine_results,
        generate_stats_sql,
        generate_primary_sql,
        generate_sql_retry,
        #generate_summary,
        generate_viz,
        validate_and_route,
        verify_result,
    )
    from .logger import log_pipeline
except ImportError:
    import cache
    from db import execute_stats_sql, execute_primary_sql
    from llm import (
        combine_results,
        generate_stats_sql,
        generate_primary_sql,
        generate_sql_retry,
        #generate_summary,
        generate_viz,
        validate_and_route,
        verify_result,
    )
    from logger import log_pipeline

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

MAX_RETRIES = 3


def _dedupe_rows(rows: list[dict]) -> list[dict]:
    deduped = []
    seen = set()
    for row in rows:
        if not isinstance(row, dict):
            continue
        normalized = {
            str(k).lower().strip(): "" if v is None else str(v).lower().strip()
            for k, v in row.items()
        }
        signature = json.dumps(normalized, sort_keys=True)
        if signature in seen:
            continue
        seen.add(signature)
        deduped.append(row)
    return deduped


def _retrieve_source(question: str, source: str) -> dict:
    if source == "primary":
        sql = generate_primary_sql(question)
        execute = execute_primary_sql
    else:
        sql = generate_stats_sql(question)
        execute = execute_stats_sql

    rows  = []
    error = None

    for _ in range(MAX_RETRIES):
        try:
            rows  = execute(sql)
            error = None
            break
        except sqlite3.OperationalError as e:
            error = str(e)
            sql = generate_sql_retry(question, sql, error, source=source)

    return {"source": source, "sql": sql, "rows": rows, "error": error}


def _empty_source(source: str) -> dict:
    return {"source": source, "sql": None, "rows": [], "error": None}


def run(question: str, mode: str | None = None) -> dict:
    cached = cache.get(question, mode)
    if cached is not None:
        return cached

    start = time.time()
    decision = validate_and_route(question, mode)
    if not decision.get("valid", True):
        result = {
            "error": decision.get("reason", "Invalid question."),
            "sql": None, "rows": [], "viz": None, "summary": None
        }
        cache.set(question, result, mode)
        return result

    use_primary = decision.get("use_primary", True)
    use_stats      = decision.get("use_stats", False)
    logger.info(f"Routing: {decision}")

    if use_primary and use_stats:
        # independent LLM+DB round trips — run concurrently to cut wall-clock latency
        with ThreadPoolExecutor(max_workers=2) as pool:
            primary_future   = pool.submit(_retrieve_source, question, "primary")
            secondary_future = pool.submit(_retrieve_source, question, "secondary")
            primary   = primary_future.result()
            secondary = secondary_future.result()
    else:
        primary   = _retrieve_source(question, "primary")   if use_primary else _empty_source("primary")
        secondary = _retrieve_source(question, "secondary") if use_stats     else _empty_source("secondary")
    retrieval = {"primary": primary, "secondary": secondary}

    # if only one source was used, skip the combine LLM call — just use that source's rows directly
    if use_primary and not use_stats:
        rows = primary["rows"]
        combined = {"rows": rows, "reasoning": "Primary source only."}
    elif use_stats and not use_primary:
        rows = secondary["rows"]
        combined = {"rows": rows, "reasoning": "Secondary source only."}
    else:
        combined = {"rows": [], "reasoning": ""}
        for attempt in range(MAX_RETRIES):
            combined = combine_results(question, primary, secondary)
            rows = _dedupe_rows(combined.get("rows", []))
            combined["rows"] = rows

            verification = verify_result(question, retrieval, rows)
            if verification.get("valid", True):
                break

            reason = verification.get("reason", "Combined results incorrect.")
            bad_source = verification.get("bad_source") or "both"

            if bad_source in ("primary", "both"):
                primary["sql"] = generate_sql_retry(question, primary["sql"], reason, source="primary")
                try:
                    primary["rows"]  = execute_primary_sql(primary["sql"])
                    primary["error"] = None
                except sqlite3.OperationalError as e:
                    primary["rows"], primary["error"] = [], str(e)

            if bad_source in ("secondary", "both"):
                secondary["sql"] = generate_sql_retry(question, secondary["sql"], reason, source="secondary")
                try:
                    secondary["rows"]  = execute_stats_sql(secondary["sql"])
                    secondary["error"] = None
                except sqlite3.OperationalError as e:
                    secondary["rows"], secondary["error"] = [], str(e)

            retrieval = {"primary": primary, "secondary": secondary}

    # single-source verify pass (skipped above when both used, since combine loop already verified)
    if use_primary != use_stats:
        for attempt in range(MAX_RETRIES):
            verification = verify_result(question, retrieval, rows)
            if verification.get("valid", True):
                break
            reason = verification.get("reason", "Results incorrect.")
            source = "primary" if use_primary else "secondary"
            if source == "primary":
                primary["sql"] = generate_sql_retry(question, primary["sql"], reason, source="primary")
                try:
                    primary["rows"], primary["error"] = execute_primary_sql(primary["sql"]), None
                except sqlite3.OperationalError as e:
                    primary["rows"], primary["error"] = [], str(e)
                rows = primary["rows"]
            else:
                secondary["sql"] = generate_sql_retry(question, secondary["sql"], reason, source="secondary")
                try:
                    secondary["rows"], secondary["error"] = execute_stats_sql(secondary["sql"]), None
                except sqlite3.OperationalError as e:
                    secondary["rows"], secondary["error"] = [], str(e)
                rows = secondary["rows"]
            retrieval = {"primary": primary, "secondary": secondary}

    # charts are only offered in player mode — general/team/match questions never get one,
    # decided here rather than left to the prompt so it's guaranteed, not just requested
    viz = generate_viz(question, rows) if mode == "player" else None
    # summary = generate_summary(question, rows)

    elapsed = time.time() - start
    log_pipeline(question, decision, primary, secondary, rows, elapsed)

    result = {
        "sql": {
            "primary": primary["sql"],
            "secondary": secondary["sql"],
            "combine_reasoning": combined.get("reasoning", ""),
        },
        "rows": rows,
        "viz": viz,
        #"summary": summary,
        "error": None,
    }
    cache.set(question, result, mode)
    return result


if __name__ == "__main__":
    while True:
        q = input("\nQuestion: ").strip()
        if not q: break
        result = run(q)
        if result["error"]:
            print("Invalid:", result["error"])
        else:
            print("SQL:", result["sql"])
            print("VIZ:", result["viz"])
            print("Rows:", result["rows"][:2])