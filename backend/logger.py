import logging, time, json
from functools import wraps

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)s | %(message)s'
)
logger = logging.getLogger("worldcup")

def log_pipeline(question: str, decision: dict, primary: dict, secondary: dict, rows: list, elapsed: float):
    logger.info(json.dumps({
        "question": question,
        "valid": decision.get("valid"),
        "use_primary": decision.get("use_primary"),
        "use_fd": decision.get("use_fd"),
        "primary_sql": primary.get("sql") if primary else None,
        "primary_rows": len(primary.get("rows", [])) if primary else 0,
        "primary_error": primary.get("error") if primary else None,
        "secondary_sql": secondary.get("sql") if secondary else None,
        "secondary_rows": len(secondary.get("rows", [])) if secondary else 0,
        "secondary_error": secondary.get("error") if secondary else None,
        "final_row_count": len(rows),
        "elapsed_seconds": round(elapsed, 2)
    }))