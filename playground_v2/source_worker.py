"""Isolate document parsing from credentials and enforce its deadline in the parent."""
import json
from pathlib import Path
import sys


def main():
    from .source import prepare_source
    job = json.load(sys.stdin)
    try:
        context, source = prepare_source(job["case"], Path(job["output"]), **job["limits"])
        result = {"context": context, "source": source}
    except Exception as error:
        result = {"error": type(error).__name__, "message": str(error)[:1500]}
    print(json.dumps(result, ensure_ascii=True, allow_nan=False))


if __name__ == "__main__":
    main()
