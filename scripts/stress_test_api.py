#!/usr/bin/env python3
"""
Simple API stress tester using only Python standard library.

Examples:
  python3 scripts/stress_test_api.py --url "https://example.com/api/dashboard-new" --token "JWT" -n 200 -c 10
  python3 scripts/stress_test_api.py --url "https://example.com/api/workout-logs" --token "JWT" --method POST -n 50 -c 2 --json '{"user_routine":1,"exercise_id":1,"points":5}'
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed


def request_once(method: str, url: str, token: str, body, timeout: int):
    headers = {
        "User-Agent": "fitness-api-stress-test/1.0",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode("utf-8")

    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    started = time.perf_counter()

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            resp.read()
            status_code = int(resp.status)
            error = ""
    except urllib.error.HTTPError as exc:
        status_code = int(exc.code)
        try:
            error = exc.read(300).decode("utf-8", errors="replace")
        except Exception:
            error = str(exc)
    except Exception as exc:
        status_code = 0
        error = str(exc)

    elapsed_ms = (time.perf_counter() - started) * 1000.0
    return status_code, elapsed_ms, error


def percentile(sorted_values: list[float], pct: int) -> float:
    if not sorted_values:
        return 0.0
    index = round((pct / 100.0) * (len(sorted_values) - 1))
    return float(sorted_values[index])


def main() -> int:
    parser = argparse.ArgumentParser(description="Stress test one API endpoint.")
    parser.add_argument("--url", required=True, help="Full endpoint URL.")
    parser.add_argument("--token", default="", help="JWT access token.")
    parser.add_argument("--method", default="GET", choices=["GET", "POST", "PUT", "PATCH", "DELETE"])
    parser.add_argument("-n", "--requests", type=int, default=100, help="Total requests.")
    parser.add_argument("-c", "--concurrency", type=int, default=10, help="Concurrent workers.")
    parser.add_argument("--json", default="", help="JSON body for POST/PUT/PATCH.")
    parser.add_argument("--timeout", type=int, default=30, help="Per-request timeout seconds.")
    args = parser.parse_args()

    if args.requests <= 0:
        raise SystemExit("--requests must be > 0")
    if args.concurrency <= 0:
        raise SystemExit("--concurrency must be > 0")

    body = None
    if args.json:
        try:
            body = json.loads(args.json)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"Invalid --json body: {exc}") from exc

    print("API stress test")
    print("---------------")
    print(f"URL:         {args.url}")
    print(f"Method:      {args.method}")
    print(f"Requests:    {args.requests}")
    print(f"Concurrency: {args.concurrency}")
    print(f"Timeout:     {args.timeout}s")
    print()

    started = time.perf_counter()
    results = []

    with ThreadPoolExecutor(max_workers=args.concurrency) as executor:
        futures = [
            executor.submit(request_once, args.method, args.url, args.token, body, args.timeout)
            for _ in range(args.requests)
        ]
        for future in as_completed(futures):
            results.append(future.result())

    total_seconds = max(time.perf_counter() - started, 0.000001)
    status_counts: dict[int, int] = {}
    timings = []
    sample_errors = []

    for status_code, elapsed_ms, error in results:
        status_counts[status_code] = status_counts.get(status_code, 0) + 1
        timings.append(elapsed_ms)
        if error and len(sample_errors) < 5:
            sample_errors.append((status_code, error.replace("\n", " ")[:300]))

    timings_sorted = sorted(timings)
    success_count = sum(count for code, count in status_counts.items() if 200 <= code < 300)
    error_count = len(results) - success_count

    print("Results")
    print("-------")
    print(f"Completed:    {len(results)}")
    print(f"Total time:   {total_seconds:.2f}s")
    print(f"Requests/sec: {len(results) / total_seconds:.2f}")
    print(f"2xx success:  {success_count}")
    print(f"Errors:       {error_count}")
    print(f"Status codes: {dict(sorted(status_counts.items()))}")
    print()
    print("Latency")
    print("-------")
    print(f"Min:    {min(timings):.2f} ms")
    print(f"Avg:    {statistics.mean(timings):.2f} ms")
    print(f"Median: {statistics.median(timings):.2f} ms")
    print(f"P90:    {percentile(timings_sorted, 90):.2f} ms")
    print(f"P95:    {percentile(timings_sorted, 95):.2f} ms")
    print(f"P99:    {percentile(timings_sorted, 99):.2f} ms")
    print(f"Max:    {max(timings):.2f} ms")

    if sample_errors:
        print()
        print("Sample errors")
        print("-------------")
        for status_code, error in sample_errors:
            print(f"{status_code}: {error}")

    return 0 if error_count == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
