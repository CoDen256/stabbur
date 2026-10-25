"""
scripts/bootstrap.py — the Docker image's entrypoint: runs migrations, then
starts the Flask app. No data import step (stabbur has no provider data to
seed, unlike smia) — just migrate and run.
"""

from __future__ import annotations

import os
import subprocess


def main() -> None:
    subprocess.run(["alembic", "upgrade", "head"], check=True)

    # exec, not subprocess.run: replaces this process (PID 1 in the
    # container) so signals (SIGTERM on `docker stop`) reach the Flask
    # process directly, and the full inherited environment (DATABASE_URL,
    # STABBUR_AUTH_TOKEN, ...) carries over automatically.
    os.execvp("python", ["python", "app.py"])


if __name__ == "__main__":
    main()
