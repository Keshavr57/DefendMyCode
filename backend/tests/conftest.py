"""
pytest loads conftest.py automatically BEFORE the test files.

We point DATABASE_URL at a throwaway database in a temp folder, so tests never
touch your real repoviva.db. This must happen before `app` is imported, because
app/db.py creates the engine at import time. (load_dotenv won't overwrite it,
since a variable that is already set wins over .env.)
"""

import os
import tempfile

test_db_path = os.path.join(tempfile.mkdtemp(), "test_repoviva.db")
os.environ["DATABASE_URL"] = f"sqlite:///{test_db_path}"
