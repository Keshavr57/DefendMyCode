# RepoViva — What I Learned

One section per phase: what we built, why, how it works, and interview questions I could be asked.

---

## Phase 1 — Backend setup

### What we built
- A **FastAPI** backend with a `GET /health` endpoint.
- **Config** in one file (`app/config.py`), loaded from `.env`.
- **5 SQLite tables** (`app/db.py`): repos, chunks, sessions, questions, answers.
- **One Groq client** (`app/llm/groq_client.py`): every LLM call goes through `chat()`, which times and logs it.
- A manual LLM test script (`scripts/try_llm.py`) and automated tests (`tests/test_health.py`).

### Why
Every later phase needs these foundations: a place for settings, a database to store interviews, and a safe, measured way to call the LLM. The `/health` endpoint lets me (and the deploy server) check that the app is alive.

### How it works (simple English)
- **Config:** `load_dotenv()` copies `.env` into environment variables; `config.py` reads them once with `os.getenv()` and sensible defaults. The rest of the app only does `from app import config`.
  I chose plain `os.getenv` over `pydantic-settings`: it has fewer moving parts and is easy to explain. The trade-off is that `pydantic-settings` would also check types (for example, catching a typo in a number), which matters more as the number of settings grows.
- **Database:** `create_engine` makes the connection factory. `SessionLocal()` gives one session per request. A `connect` event listener turns on `PRAGMA foreign_keys=ON`, because SQLite ignores foreign keys by default. Tables are Python classes (`Mapped` / `mapped_column`).
  - `check_same_thread=False` is needed because FastAPI runs routes in worker threads.
  - `ondelete="CASCADE"`: deleting a parent row also deletes its children (for example, a session's questions).
  - `questions.parent_question_id` points to another question in the same table, which is how a follow-up links to its main question.
  - The session table's class is called `InterviewSession` because SQLAlchemy already has a `Session` class.
  - We skipped `relationship()` for now. Plain foreign-key ids are enough, and the code is simpler to read. We can add it once we need to load related rows together (for example, a session with all its questions).
- **Schema changes:** `create_all` only creates **missing** tables and never changes existing ones. During development I delete `repoviva.db` after a schema change. Real projects use **Alembic**, a tool that writes "migration" scripts to change existing tables without losing data.
- **LLM client:** `get_client()` creates the Groq client only on first use, so the app starts even without a key. `chat()` times the call with `time.perf_counter()` (a stopwatch made for measuring durations, unlike the wall clock in `time.time()`). On success, it logs purpose, model, milliseconds and token counts. On failure, it logs the error with the elapsed time and re-raises it.
- **Startup:** `lifespan` runs `init_db()` once when the server starts. `GET /health` gets a DB session through `Depends(get_db)`, runs `SELECT 1`, and returns status, model and whether a key is set (never the key itself). If the DB fails, it returns **503** (Service Unavailable).
- **Tests:** `TestClient` used inside a `with` block runs the startup code. Tests use a temporary database and never call the LLM.
- **Model choice:** the brief said a LLaMA 70B model. Groq shut down `llama-3.3-70b-versatile` on the free tier in August 2026, so the default is now `openai/gpt-oss-120b` (Groq's recommended replacement). It can be changed with `LLM_MODEL` in `.env`.

### Interview questions

**1. Why do all LLM calls go through one file?**
Every call is timed and logged the same way. This gives me one place to debug, to watch token cost, and to get my latency numbers for evaluation. It also means switching provider (say Groq to OpenAI) changes one file, not every feature. And features like retries can be added once for the whole app.

**2. What does /health check, and why?**
It checks that the server is running **and** that it can actually reach the database, by running `SELECT 1`. It also reports which model is configured and whether a key is set (True/False only, never the key). Deploy platforms like Render call this URL to decide if the app is healthy. If the DB is down, it returns 503 so the problem is visible instead of hidden.

**3. You use a sync Groq client. Won't it block the server?**
Not the whole server. My routes are normal `def` functions, and FastAPI runs those in a pool of worker threads, so a slow LLM call blocks one thread while other requests continue. For a student project with few users, that's fine and simpler. At scale I'd switch to the async client (`AsyncGroq`) with `async def` routes, and move slow jobs like repo indexing to a background queue with worker processes.
