"""
Manual check that our Groq setup works. This makes REAL API calls (uses your key).

Run from the backend/ folder:  python -m scripts.try_llm
(-m runs it as a module, so Python adds backend/ to its import path and
`from app...` works. `python scripts/try_llm.py` would fail to find `app`.)
"""

import json
import logging

from app import config
from app.llm.groq_client import chat


def main() -> None:
    # Scripts set up their own logging, so we can see groq_client's timing log line.
    logging.basicConfig(level=config.LOG_LEVEL, format="%(asctime)s | %(levelname)s | %(module)s | %(message)s")
    print(f"Model: {config.LLM_MODEL}\n")

    # Test 1: a normal text reply.
    result = chat(
        messages=[{"role": "user", "content": "In one sentence, what is FastAPI?"}],
        purpose="try_text",
    )
    print("Test 1 (text)")
    print(f"  reply:  {result.text}")
    print(f"  time:   {result.latency_ms} ms")
    print(f"  tokens: {result.input_tokens} in / {result.output_tokens} out\n")

    # Test 2: JSON mode. Note the word "JSON" in the message, which Groq requires.
    result = chat(
        messages=[
            {"role": "system", "content": "You reply only with a JSON object."},
            {
                "role": "user",
                "content": 'Give JSON with keys "language" (string) and "uses" (list of 3 short strings) for Python.',
            },
        ],
        temperature=0,
        json_mode=True,
        purpose="try_json",
    )
    parsed = json.loads(result.text)  # turns the JSON text into a Python dict (crashes if invalid)
    print("Test 2 (json)")
    print(f"  parsed: {parsed}")
    print(f"  time:   {result.latency_ms} ms")


if __name__ == "__main__":
    main()
