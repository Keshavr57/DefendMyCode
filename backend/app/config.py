"""
All app settings live here, in ONE place.

Values come from environment variables. load_dotenv() first copies every line
of our .env file into the environment, then os.getenv() reads them.
Every other file does `from app import config` and uses e.g. config.LLM_MODEL,
so nothing else in the app ever reads .env directly.
"""

import os

from dotenv import load_dotenv

# Find the .env file (it searches upward from this file, so backend/.env is found)
# and load its values. A variable that is ALREADY set in the environment wins
# over .env, which is how tests and the deploy server can override settings.
load_dotenv()

# Secret key for Groq. Defaults to "" instead of crashing, so the server and the
# tests can still start without a key. Only an actual LLM call needs it, and that
# call gives a clear error (see app/llm/groq_client.py).
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")

# Which LLM answers our prompts.
LLM_MODEL = os.getenv("LLM_MODEL", "openai/gpt-oss-120b")

# Which speech-to-text model we use. Stored now, but not used until Phase 8.
WHISPER_MODEL = os.getenv("WHISPER_MODEL", "whisper-large-v3-turbo")

# Where the database lives. "./repoviva.db" means a file in the folder you run
# the server from (backend/).
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./repoviva.db")

# How much detail the logs show: DEBUG, INFO, WARNING or ERROR.
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
