import logging, os, json, threading
from pathlib import Path
from groq import Groq
from groq import RateLimitError as GroqRateLimitError
from groq import APIConnectionError as GroqConnectionError
from groq import APITimeoutError as GroqTimeoutError
from groq import InternalServerError as GroqInternalServerError
from openai import OpenAI
from openai import RateLimitError as OpenAIRateLimitError
from openai import APIConnectionError as OpenAIConnectionError
from openai import APITimeoutError as OpenAITimeoutError
from openai import InternalServerError as OpenAIInternalServerError
from dotenv import load_dotenv

try:
    from .prompts import (
        VALIDATE_PROMPT, PRIMARY_SQL_PROMPT, STATS_SQL_PROMPT,
        COMBINE_PROMPT, VERIFY_PROMPT, VIZ_PROMPT,
    )
except ImportError:
    from prompts import (
        VALIDATE_PROMPT, PRIMARY_SQL_PROMPT, STATS_SQL_PROMPT,
        COMBINE_PROMPT, VERIFY_PROMPT, VIZ_PROMPT,
    )

load_dotenv(Path(__file__).resolve().parent / ".env")
logger = logging.getLogger(__name__)

# --- Multi-provider failover (OpenAI -> Groq -> Cerebras -> OpenRouter) — active. ---
# --- OpenAI is primary (paid $5 credit, best quality); the free-tier providers ---
# --- behind it are pure fallback once that credit runs out or OpenAI has an outage. ---

# Errors worth failing over to the next provider for — the provider is rate
# limited, down, or timed out. Anything else (bad request, auth) is a real
# bug that would fail identically on every provider, so it isn't retried.
_FAILOVER_ERRORS = (
    GroqRateLimitError, GroqConnectionError, GroqTimeoutError, GroqInternalServerError,
    OpenAIRateLimitError, OpenAIConnectionError, OpenAITimeoutError, OpenAIInternalServerError,
)

# (name, client, strong model, fast model) — tried in order, falling over to
# the next provider on rate limit / outage. OpenAI first (paid, primary),
# then the free-tier providers as fallback if the $5 credit runs dry or OpenAI
# has an outage: Groq, then Cerebras, then OpenRouter as the broadest last resort.
# max_retries=0 on every client: both SDKs retry 429/5xx internally by default
# (with their own backoff, up to ~60s) BEFORE raising — that swallows the error
# our failover loop is waiting to catch, so a "stuck" provider blocks the whole
# chain instead of failing over immediately. Disabling it makes failover instant.
_PROVIDERS = [
    (
        "openai",
        OpenAI(api_key=os.getenv("OPENAI_API_KEY"), max_retries=0),
        "gpt-5.4-mini",   # SQL generation, combining, verification — needs strong reasoning
        "gpt-5.4-nano",   # routing/classification, viz type — simple JSON decisions
    ),
    (
        "groq",
        Groq(api_key=os.getenv("GROQ_API_KEY"), max_retries=0),
        "llama-3.3-70b-versatile",   # SQL generation, combining, verification — needs strong reasoning
        "llama-3.1-8b-instant",      # routing/classification, viz type — simple JSON decisions
    ),
    (
        "cerebras",
        OpenAI(api_key=os.getenv("CEREBRAS_API_KEY"), base_url="https://api.cerebras.ai/v1", max_retries=0),
        "gpt-oss-120b",
        "gemma-4-31b",
    ),
    (
        "openrouter",
        OpenAI(api_key=os.getenv("OPENROUTER_KEY"), base_url="https://openrouter.ai/api/v1", max_retries=0),
        "meta-llama/llama-3.3-70b-instruct",
        "meta-llama/llama-3.1-8b-instruct",
    ),
]


# Sticky provider index — once a call succeeds on a provider, every subsequent
# call (this request and later ones) starts there directly instead of re-trying
# a known-bad provider first. Only advances when the current one actually fails.
_preferred_provider = 0
_provider_lock = threading.Lock()


def _call_with_failover(build_messages, temperature: float, fast: bool) -> str:
    global _preferred_provider
    with _provider_lock:
        start = _preferred_provider

    n = len(_PROVIDERS)
    last_error = None
    for offset in range(n):
        idx = (start + offset) % n
        name, provider_client, model, model_fast = _PROVIDERS[idx]
        try:
            response = provider_client.chat.completions.create(
                model=model_fast if fast else model,
                messages=build_messages(),
                temperature=temperature,
            )
            with _provider_lock:
                _preferred_provider = idx
            return response.choices[0].message.content.strip()
        except _FAILOVER_ERRORS as e:
            logger.warning(f"{name} unavailable ({e.__class__.__name__}), trying next provider")
            last_error = e
    raise last_error


def _call(system: str, user: str, temperature: float = 0, fast: bool = False) -> str:
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    return _call_with_failover(lambda: messages, temperature, fast)

def _call_messages(messages: list, temperature: float = 0, fast: bool = False) -> str:
    return _call_with_failover(lambda: messages, temperature, fast)

# --- Gemini single-provider path, commented out for now (20 req/day free-tier cap) ---
# client     = OpenAI(api_key=os.getenv("GEMINI_API_KEY"), base_url="https://generativelanguage.googleapis.com/v1beta/openai/")
# MODEL      = "gemini-flash-latest"        # SQL generation, combining, verification — needs strong reasoning
# MODEL_FAST = "gemini-flash-lite-latest"   # routing/classification, viz type — simple JSON decisions
# # (only flash-tier models are available on this key's free quota — 2.5-pro / 2.0-flash / 3.1-pro all return 429 quota=0)
# # Gemini's flash models "think" by default before answering, which added ~5-20s per
# # call for no quality benefit on these JSON/SQL tasks — disabled via reasoning_effort.
# _NO_THINKING = {"reasoning_effort": "none"}
#
# def _call(system: str, user: str, temperature: float = 0, fast: bool = False) -> str:
#     response = client.chat.completions.create(
#         model=MODEL_FAST if fast else MODEL,
#         messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
#         temperature=temperature,
#         extra_body=_NO_THINKING,
#     )
#     return response.choices[0].message.content.strip()
#
# def _call_messages(messages: list, temperature: float = 0, fast: bool = False) -> str:
#     response = client.chat.completions.create(
#         model=MODEL_FAST if fast else MODEL,
#         messages=messages,
#         temperature=temperature,
#         extra_body=_NO_THINKING,
#     )
#     return response.choices[0].message.content.strip()

def _parse_json(raw: str, fallback):
    text = raw.strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return fallback

def validate_and_route(question: str, mode: str | None = None) -> dict:
    user = json.dumps({"mode": mode, "question": question})
    raw = _call(VALIDATE_PROMPT, user, fast=True)
    return _parse_json(raw, {"valid": True, "use_primary": True, "use_stats": False})

def generate_primary_sql(question: str) -> str:
    return _call(PRIMARY_SQL_PROMPT, question)

def generate_stats_sql(question: str) -> str:
    return _call(STATS_SQL_PROMPT, question)

def generate_sql_retry(question: str, failed_sql: str, error: str, source: str = "primary") -> str:
    prompt = PRIMARY_SQL_PROMPT if source == "primary" else STATS_SQL_PROMPT
    messages = [
        {"role": "system",    "content": prompt},
        {"role": "user",      "content": question},
        {"role": "assistant", "content": failed_sql},
        {"role": "user",      "content": f"That query failed.\nReason: {error}\nFix and return only the corrected SQL."}
    ]
    return _call_messages(messages)

def combine_results(question: str, primary: dict, secondary: dict) -> dict:
    user = json.dumps({"question": question, "primary": primary, "secondary": secondary}, default=str)
    raw  = _call(COMBINE_PROMPT, user)
    parsed = _parse_json(raw, {"rows": [], "reasoning": "Combiner returned invalid JSON."})
    rows = parsed.get("rows", [])
    if not isinstance(rows, list):
        rows = []
    return {"rows": rows, "reasoning": parsed.get("reasoning", "")}

def verify_result(question: str, retrieval: dict, rows: list) -> dict:
    user = json.dumps({
        "question": question, "retrieval": retrieval,
        "combined_row_count": len(rows), "combined_results": rows[:10]
    }, default=str)
    raw = _call(VERIFY_PROMPT, user)
    return _parse_json(raw, {"valid": True})

def generate_viz(question: str, rows: list) -> dict | None:
    if not rows or len(rows) < 2:
        return None
    user = f"Question: {question}\nColumns: {list(rows[0].keys())}\nRow count: {len(rows)}\nSample rows: {rows[:3]}"
    raw  = _call(VIZ_PROMPT, user, fast=True)
    return _parse_json(raw, None)