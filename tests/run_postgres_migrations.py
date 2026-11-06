"""Run inside a throw-away PostgreSQL cluster: pg_virtualenv -t -v 16 .venv/bin/python tests/run_postgres_migrations.py"""
import os
import sys
from pathlib import Path
import pytest
from sqlalchemy.engine import URL

root=Path(__file__).resolve().parent.parent
os.chdir(root)
sys.path.insert(0,str(root))
os.environ['AMANDA_TEST_POSTGRES_URL']=URL.create(
    'postgresql+psycopg',username=os.environ.get('PGUSER'),password=os.environ.get('PGPASSWORD'),
    host=os.environ.get('PGHOST'),port=int(os.environ.get('PGPORT','5432')),
    database=os.environ.get('PGDATABASE','postgres')).render_as_string(hide_password=False)
raise SystemExit(pytest.main(['-q','tests/test_migrations.py::test_postgres_initial_revision_with_real_foreign_keys_and_data']))
