"""Bounded private-stdin HTTP worker transport."""
import json
import os
import subprocess
import sys
from pathlib import Path

ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"

def run_worker(kind, data, timeout):
    environment = os.environ.copy()
    # Validators/source never inherit API credentials; HTTP receives only its key
    # through a private stdin pipe, not argv or a logged file.
    environment.pop("OPENROUTER_API_KEY", None)
    environment["PYTHONIOENCODING"] = "utf-8"
    root = str(Path(__file__).resolve().parent.parent)
    process = subprocess.Popen([sys.executable, "-m", "playground_v2.http_worker", kind],
                               stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                               text=True, encoding="utf-8", cwd=root, env=environment,
                               creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    try:
        stdout, stderr = process.communicate(json.dumps(data, allow_nan=False), timeout=max(0.1, timeout))
    except subprocess.TimeoutExpired:
        process.kill()
        process.communicate(timeout=3)
        raise TimeoutError(f"{kind} worker exceeded its time allowance") from None
    if process.returncode:
        raise RuntimeError(f"{kind} worker failed with exit code {process.returncode}")
    return json.loads(stdout)
