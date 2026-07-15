"""Shared pytest fixtures and path setup for the job_bot test suite."""
import os
import sys

# Ensure the job_bot package root is importable so that modules using
# top-level imports (e.g. ``from db_manager import ...``) resolve correctly.
JOB_BOT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if JOB_BOT_ROOT not in sys.path:
    sys.path.insert(0, JOB_BOT_ROOT)
