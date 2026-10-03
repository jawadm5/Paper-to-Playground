"""Bounded subprocess entry points. Outputs exclude hidden model reasoning."""
import json
import sys


def main():
    job = json.load(sys.stdin)
    if sys.argv[1] == "http":
        import requests
        try:
            response = requests.post(job["endpoint"], headers={
                "Authorization": "Bearer " + job["key"], "Content-Type": "application/json",
                "X-Title": "Paper to Playground"}, json=job["payload"],
                timeout=(10, job["timeout"]))
            try:
                body = response.json()
            except ValueError:
                body = {}
            choices = body.get("choices") or []
            first = choices[0] if choices else {}
            error_text = json.dumps(body.get("error") or {}).lower()
            # Never return reasoning/reasoning_details or the raw provider error.
            result = {"status": response.status_code, "id": body.get("id"),
                      "content": (first.get("message") or {}).get("content"),
                      "usage": body.get("usage"), "finish_reason": first.get("finish_reason"),
                      "retry_after": response.headers.get("Retry-After"),
                      "error_code": str((body.get("error") or {}).get("code", ""))[:80],
                      "format_unsupported": any(term in error_text for term in
                                                ("response_format", "json_schema", "structured output", "reasoning"))}
        except requests.RequestException as error:
            result = {"status": 0, "error_code": type(error).__name__, "usage": None}
    else:
        raise ValueError("Unknown worker")
    print(json.dumps(result, ensure_ascii=True, allow_nan=False))


if __name__ == "__main__":
    main()
