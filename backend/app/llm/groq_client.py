"""
The ONLY place in the app that talks to Groq.

Every LLM call goes through chat(), so:
- every call is timed and logged in the same way (Phase 9 latency numbers come from these logs),
- switching to another provider later means changing just this one file.
"""

import logging
import time
from dataclasses import dataclass

from groq import Groq

from app import config

logger = logging.getLogger(__name__)

# The Groq client is created the first time we need it, not when the app starts.
# This way the server and tests still start even when no API key is set.
_client: Groq | None = None


def get_client() -> Groq:
    """Return the shared Groq client, creating it on first use."""
    global _client  # we want to change the module-level _client, not make a local one
    if _client is None:
        if not config.GROQ_API_KEY:
            raise RuntimeError(
                "GROQ_API_KEY is not set. Copy backend/.env.example to backend/.env "
                "and put your Groq key in it."
            )
        _client = Groq(api_key=config.GROQ_API_KEY)
    return _client


@dataclass
class LLMResult:
    """What chat() returns. @dataclass writes __init__ for us, so this is just a
    simple box with named fields."""
    text: str
    latency_ms: int
    input_tokens: int
    output_tokens: int


def chat(
    messages: list[dict],
    temperature: float = 0.2,
    json_mode: bool = False,
    max_tokens: int = 1024,
    purpose: str = "chat",
) -> LLMResult:
    """Send messages to the LLM and return its reply with timing and token counts.

    messages: e.g. [{"role": "system", "content": "..."}, {"role": "user", "content": "..."}]
    temperature: 0 = most consistent, higher = more varied.
    json_mode: force the reply to be valid JSON. Groq requires the word "JSON"
               to appear somewhere in the messages when this is on.
    purpose: a label for the logs, e.g. "question_gen" or "scoring".
    """
    client = get_client()

    # Build the request settings. response_format is only added in JSON mode.
    request = {
        "model": config.LLM_MODEL,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    if json_mode:
        request["response_format"] = {"type": "json_object"}

    # perf_counter() is a stopwatch made for measuring durations. time.time() is
    # the wall clock, which can jump (e.g. when the system syncs its clock).
    start = time.perf_counter()
    try:
        response = client.chat.completions.create(**request)  # ** spreads the dict into named arguments
    except Exception:
        elapsed_ms = int((time.perf_counter() - start) * 1000)
        # logger.exception logs the message AND the full error traceback.
        logger.exception("LLM call failed | purpose=%s model=%s after_ms=%d", purpose, config.LLM_MODEL, elapsed_ms)
        raise  # let the caller decide what to do with the error
    latency_ms = int((time.perf_counter() - start) * 1000)

    text = response.choices[0].message.content or ""
    usage = response.usage
    input_tokens = usage.prompt_tokens if usage else 0
    output_tokens = usage.completion_tokens if usage else 0

    logger.info(
        "LLM call ok | purpose=%s model=%s ms=%d tokens_in=%d tokens_out=%d",
        purpose, config.LLM_MODEL, latency_ms, input_tokens, output_tokens,
    )
    return LLMResult(text=text, latency_ms=latency_ms, input_tokens=input_tokens, output_tokens=output_tokens)
