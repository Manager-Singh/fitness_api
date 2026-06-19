from __future__ import annotations

import json
import statistics
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import date, datetime, timedelta
from html import escape
from pathlib import Path
from urllib.parse import urljoin

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken

from payment_packages.models import PaymentPackage
from user_profile.models import Payment, UserProfile


def _read_meminfo() -> dict:
    out = {}
    try:
        with open("/proc/meminfo", "r", encoding="utf-8") as fh:
            for line in fh:
                key, raw = line.split(":", 1)
                value = raw.strip().split()[0]
                out[key] = int(value)
    except Exception:
        return {}
    total_kb = out.get("MemTotal", 0)
    available_kb = out.get("MemAvailable", 0)
    used_kb = max(0, total_kb - available_kb)
    return {
        "total_mb": round(total_kb / 1024, 2),
        "available_mb": round(available_kb / 1024, 2),
        "used_mb": round(used_kb / 1024, 2),
        "used_percent": round((used_kb / total_kb) * 100, 2) if total_kb else None,
    }


def _read_cpu_totals():
    try:
        with open("/proc/stat", "r", encoding="utf-8") as fh:
            parts = fh.readline().strip().split()[1:]
        values = [int(v) for v in parts]
        idle = values[3] + (values[4] if len(values) > 4 else 0)
        total = sum(values)
        return total, idle
    except Exception:
        return None


def _cpu_percent(prev, current):
    if not prev or not current:
        return None
    prev_total, prev_idle = prev
    total, idle = current
    total_delta = total - prev_total
    idle_delta = idle - prev_idle
    if total_delta <= 0:
        return None
    return round((1.0 - (idle_delta / total_delta)) * 100, 2)


def _read_loadavg() -> dict:
    try:
        with open("/proc/loadavg", "r", encoding="utf-8") as fh:
            one, five, fifteen, *_ = fh.read().strip().split()
        return {"1m": float(one), "5m": float(five), "15m": float(fifteen)}
    except Exception:
        return {}


class SystemSampler:
    def __init__(self, interval_seconds: float = 1.0):
        self.interval_seconds = interval_seconds
        self.samples = []
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def start(self):
        self._thread.start()

    def stop(self):
        self._stop.set()
        self._thread.join(timeout=5)

    def _run(self):
        previous_cpu = _read_cpu_totals()
        while not self._stop.is_set():
            time.sleep(self.interval_seconds)
            current_cpu = _read_cpu_totals()
            self.samples.append(
                {
                    "ts": datetime.utcnow().isoformat() + "Z",
                    "cpu_percent": _cpu_percent(previous_cpu, current_cpu),
                    "memory": _read_meminfo(),
                    "loadavg": _read_loadavg(),
                }
            )
            previous_cpu = current_cpu

    def summary(self):
        cpu_values = [s["cpu_percent"] for s in self.samples if s.get("cpu_percent") is not None]
        mem_values = [
            (s.get("memory") or {}).get("used_percent")
            for s in self.samples
            if (s.get("memory") or {}).get("used_percent") is not None
        ]
        load_1m = [
            (s.get("loadavg") or {}).get("1m")
            for s in self.samples
            if (s.get("loadavg") or {}).get("1m") is not None
        ]
        return {
            "samples": len(self.samples),
            "cpu_percent": {
                "avg": round(statistics.mean(cpu_values), 2) if cpu_values else None,
                "max": round(max(cpu_values), 2) if cpu_values else None,
            },
            "memory_used_percent": {
                "avg": round(statistics.mean(mem_values), 2) if mem_values else None,
                "max": round(max(mem_values), 2) if mem_values else None,
            },
            "loadavg_1m": {
                "avg": round(statistics.mean(load_1m), 2) if load_1m else None,
                "max": round(max(load_1m), 2) if load_1m else None,
            },
        }


def _percentile(sorted_values: list[float], pct: int) -> float:
    if not sorted_values:
        return 0.0
    index = round((pct / 100.0) * (len(sorted_values) - 1))
    return float(sorted_values[index])


def _request_once(method: str, url: str, token: str, body, timeout: int, label: str = "request"):
    headers = {"User-Agent": "fitness-api-live-stress-report/1.0"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode("utf-8")

    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            response.read()
            status_code = int(response.status)
            error = ""
    except urllib.error.HTTPError as exc:
        status_code = int(exc.code)
        try:
            error = exc.read(500).decode("utf-8", errors="replace")
        except Exception:
            error = str(exc)
    except Exception as exc:
        status_code = 0
        error = str(exc)
    elapsed_ms = (time.perf_counter() - started) * 1000.0
    return label, status_code, elapsed_ms, error


def _html_value(value):
    if value is None:
        return "—"
    return escape(str(value))


def _render_table(title: str, rows: list[tuple[str, object]]) -> str:
    body = "\n".join(
        f"<tr><th>{escape(str(key))}</th><td>{_html_value(value)}</td></tr>"
        for key, value in rows
    )
    return f"<section><h2>{escape(title)}</h2><table>{body}</table></section>"


def _write_html_report(report: dict, html_path: Path) -> None:
    results = report.get("results") or {}
    latency = report.get("latency_ms") or {}
    system = ((report.get("system") or {}).get("during_summary") or {})
    cpu = system.get("cpu_percent") or {}
    ram = system.get("memory_used_percent") or {}
    load = system.get("loadavg_1m") or {}
    target = report.get("target") or {}
    load_cfg = report.get("load") or {}
    users = report.get("stress_users") or {}
    endpoint_status = results.get("endpoint_status_codes") or {}
    sample_errors = report.get("sample_errors") or []

    endpoint_rows = []
    for endpoint, statuses in endpoint_status.items():
        endpoint_rows.append(
            f"<tr><td>{escape(str(endpoint))}</td><td>{escape(json.dumps(statuses))}</td></tr>"
        )
    endpoint_table = (
        "<section><h2>Endpoint Status</h2><table><tr><th>Endpoint</th><th>Status Codes</th></tr>"
        + "\n".join(endpoint_rows)
        + "</table></section>"
        if endpoint_rows
        else ""
    )

    error_rows = []
    for err in sample_errors:
        error_rows.append(
            "<tr>"
            f"<td>{escape(str(err.get('endpoint', '')))}</td>"
            f"<td>{escape(str(err.get('status', '')))}</td>"
            f"<td><code>{escape(str(err.get('error', '')))}</code></td>"
            "</tr>"
        )
    errors_table = (
        "<section><h2>Sample Errors</h2><table><tr><th>Endpoint</th><th>Status</th><th>Error</th></tr>"
        + "\n".join(error_rows)
        + "</table></section>"
        if error_rows
        else "<section><h2>Sample Errors</h2><p>No sample errors captured.</p></section>"
    )

    html = f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>Fitness API Stress Test Report</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 24px; color: #111827; background: #f9fafb; }}
    h1 {{ margin-bottom: 4px; }}
    h2 {{ margin-top: 24px; border-bottom: 1px solid #d1d5db; padding-bottom: 6px; }}
    table {{ border-collapse: collapse; width: 100%; background: white; margin-top: 8px; }}
    th, td {{ text-align: left; border: 1px solid #e5e7eb; padding: 8px; vertical-align: top; }}
    th {{ width: 260px; background: #f3f4f6; }}
    code, pre {{ white-space: pre-wrap; word-break: break-word; }}
    .cards {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin-top: 16px; }}
    .card {{ background: white; border: 1px solid #e5e7eb; border-radius: 8px; padding: 14px; }}
    .card strong {{ display: block; font-size: 24px; margin-top: 4px; }}
    .ok {{ color: #166534; }}
    .bad {{ color: #991b1b; }}
  </style>
</head>
<body>
  <h1>Fitness API Stress Test Report</h1>
  <p>Generated at: <strong>{escape(str(report.get("generated_at", "")))}</strong></p>
  <div class="cards">
    <div class="card">Requests/sec<strong>{_html_value(results.get("requests_per_second"))}</strong></div>
    <div class="card">Completed<strong>{_html_value(results.get("completed"))}</strong></div>
    <div class="card">Errors<strong class="{'bad' if results.get('errors') else 'ok'}">{_html_value(results.get("errors"))}</strong></div>
    <div class="card">P95 latency<strong>{_html_value(latency.get("p95"))} ms</strong></div>
    <div class="card">CPU max<strong>{_html_value(cpu.get("max"))}%</strong></div>
    <div class="card">RAM max<strong>{_html_value(ram.get("max"))}%</strong></div>
  </div>
  {_render_table("Target", [
      ("API base", target.get("api_base")),
      ("Endpoint", target.get("endpoint")),
      ("URL", target.get("url")),
      ("Method", target.get("method")),
      ("All mode", target.get("all_mode")),
  ])}
  {_render_table("Load", [
      ("Users", load_cfg.get("users")),
      ("Total requests", load_cfg.get("requests")),
      ("Concurrency", load_cfg.get("concurrency")),
      ("Timeout seconds", load_cfg.get("timeout_seconds")),
  ])}
  {_render_table("Results", [
      ("Total seconds", results.get("total_seconds")),
      ("Requests/sec", results.get("requests_per_second")),
      ("Success 2xx", results.get("success_2xx")),
      ("Errors", results.get("errors")),
      ("Status codes", json.dumps(results.get("status_codes") or {})),
      ("Endpoint counts", json.dumps(results.get("endpoint_counts") or {})),
  ])}
  {endpoint_table}
  {_render_table("Latency (ms)", [
      ("Min", latency.get("min")),
      ("Avg", latency.get("avg")),
      ("Median", latency.get("median")),
      ("P90", latency.get("p90")),
      ("P95", latency.get("p95")),
      ("P99", latency.get("p99")),
      ("Max", latency.get("max")),
  ])}
  {_render_table("System During Test", [
      ("CPU avg %", cpu.get("avg")),
      ("CPU max %", cpu.get("max")),
      ("RAM avg %", ram.get("avg")),
      ("RAM max %", ram.get("max")),
      ("Load avg 1m", load.get("avg")),
      ("Load max 1m", load.get("max")),
      ("Samples", system.get("samples")),
  ])}
  {_render_table("Stress Users", [
      ("Prefix", users.get("prefix")),
      ("Domain", users.get("domain")),
      ("Tier", users.get("tier")),
      ("Paid", users.get("paid")),
      ("Count", users.get("count")),
      ("First email", users.get("first_email")),
      ("Last email", users.get("last_email")),
  ])}
  {errors_table}
</body>
</html>
"""
    html_path.write_text(html, encoding="utf-8")


class Command(BaseCommand):
    help = "Create stress-test users, run API load, sample CPU/RAM/load, and write one report."

    def add_arguments(self, parser):
        parser.add_argument("--api-base", required=True, help="Live API base URL, e.g. https://domain.com/api")
        parser.add_argument("--endpoint", default="/dashboard-new", help="Endpoint path under --api-base.")
        parser.add_argument("--method", default="GET", choices=["GET", "POST", "PUT", "PATCH", "DELETE"])
        parser.add_argument("--json", default="", help="JSON body for POST/PUT/PATCH.")
        parser.add_argument(
            "--all",
            action="store_true",
            help="Run mixed dashboard + workout + nutrition + habit requests in parallel.",
        )
        parser.add_argument("--users", type=int, default=100, help="Dummy users to create/reuse.")
        parser.add_argument("-n", "--requests", type=int, default=500, help="Total API requests.")
        parser.add_argument("-c", "--concurrency", type=int, default=20, help="Concurrent request workers.")
        parser.add_argument("--tier", choices=["teen", "adult", "both"], default="teen")
        parser.add_argument("--prefix", default="stress")
        parser.add_argument("--domain", default="stress.local")
        parser.add_argument("--password", default="StressTest@12345")
        parser.add_argument("--timeout", type=int, default=30)
        parser.add_argument("--sample-interval", type=float, default=1.0)
        parser.add_argument("--output", default="", help="Report JSON path. Defaults to /tmp/fitness_api_stress_report_<ts>.json")
        parser.add_argument("--reset-password", action="store_true")
        parser.add_argument("--free", action="store_true", help="Do not create paid subscription rows for stress users.")

    def handle(self, *args, **options):
        user_count = int(options["users"])
        request_count = int(options["requests"])
        concurrency = int(options["concurrency"])
        if user_count <= 0:
            raise CommandError("--users must be > 0")
        if request_count <= 0:
            raise CommandError("--requests must be > 0")
        if concurrency <= 0:
            raise CommandError("--concurrency must be > 0")

        body = None
        if options["json"]:
            try:
                body = json.loads(options["json"])
            except json.JSONDecodeError as exc:
                raise CommandError(f"Invalid --json body: {exc}") from exc

        api_base = str(options["api_base"]).rstrip("/") + "/"
        endpoint = str(options["endpoint"]).lstrip("/")
        url = urljoin(api_base, endpoint)
        output = options["output"] or f"/tmp/fitness_api_stress_report_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
        output_path = Path(output)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        users = self._create_users(options)
        auth_preflight = self._filter_api_valid_users(
            api_base,
            users,
            int(options["timeout"]),
            max_workers=min(max(concurrency, 1), 20),
        )
        self.stdout.write(
            "Auth preflight: "
            f"valid={auth_preflight['valid_count']} "
            f"invalid={auth_preflight['invalid_count']} "
            f"url={auth_preflight['profile_url']}"
        )
        if auth_preflight["invalid_samples"]:
            self.stdout.write(
                "Auth preflight invalid samples: "
                + json.dumps(auth_preflight["invalid_samples"][:5], separators=(",", ":"))
            )
        users = auth_preflight["valid_users"]
        tokens = [row["access"] for row in users]
        if not users:
            raise CommandError(
                "No stress users passed API auth preflight. "
                "Check that Api base points to the same server/DB as this admin."
            )
        stress_fixtures = self._ensure_stress_fixtures(users) if self._needs_stress_fixtures(options, body) else {}
        tasks = self._build_tasks(api_base, url, options, users, stress_fixtures)

        self.stdout.write(self.style.WARNING("Starting live stress test. Use QA/test users only."))
        self.stdout.write(f"URL: {url if not options['all'] else 'mixed endpoints'}")
        self.stdout.write(f"Users: {len(tokens)} | Requests: {request_count} | Concurrency: {concurrency}")

        sampler = SystemSampler(interval_seconds=float(options["sample_interval"]))
        sampler.start()
        started = time.perf_counter()
        results = []
        try:
            with ThreadPoolExecutor(max_workers=concurrency) as executor:
                futures = [
                    executor.submit(
                        _request_once,
                        task["method"],
                        task["url"],
                        task["token"],
                        task["body"],
                        int(options["timeout"]),
                        task["label"],
                    )
                    for task in tasks
                ]
                for future in as_completed(futures):
                    results.append(future.result())
        finally:
            total_seconds = time.perf_counter() - started
            sampler.stop()

        status_counts: dict[int, int] = {}
        endpoint_counts: dict[str, int] = {}
        endpoint_status_counts: dict[str, dict[int, int]] = {}
        timings = []
        sample_errors = []
        for label, status_code, elapsed_ms, error in results:
            status_counts[status_code] = status_counts.get(status_code, 0) + 1
            endpoint_counts[label] = endpoint_counts.get(label, 0) + 1
            endpoint_status_counts.setdefault(label, {})
            endpoint_status_counts[label][status_code] = endpoint_status_counts[label].get(status_code, 0) + 1
            timings.append(elapsed_ms)
            if error and len(sample_errors) < 10:
                sample_errors.append({"endpoint": label, "status": status_code, "error": error.replace("\n", " ")[:500]})

        timings_sorted = sorted(timings)
        success_count = sum(count for code, count in status_counts.items() if 200 <= code < 300)
        error_count = len(results) - success_count
        report = {
            "generated_at": datetime.utcnow().isoformat() + "Z",
            "target": {
                "api_base": api_base.rstrip("/"),
                "endpoint": "mixed" if options["all"] else "/" + endpoint,
                "url": "mixed" if options["all"] else url,
                "method": "mixed" if options["all"] else options["method"],
                "all_mode": bool(options["all"]),
            },
            "load": {
                "users": len(tokens),
                "created_or_loaded_users": auth_preflight["total_users"],
                "auth_valid_users": auth_preflight["valid_count"],
                "auth_invalid_users": auth_preflight["invalid_count"],
                "requests": request_count,
                "concurrency": concurrency,
                "timeout_seconds": int(options["timeout"]),
            },
            "results": {
                "completed": len(results),
                "total_seconds": round(total_seconds, 3),
                "requests_per_second": round(len(results) / max(total_seconds, 0.000001), 2),
                "success_2xx": success_count,
                "errors": error_count,
                "status_codes": dict(sorted(status_counts.items())),
                "endpoint_counts": endpoint_counts,
                "endpoint_status_codes": {
                    key: dict(sorted(value.items()))
                    for key, value in sorted(endpoint_status_counts.items())
                },
            },
            "latency_ms": {
                "min": round(min(timings), 2) if timings else None,
                "avg": round(statistics.mean(timings), 2) if timings else None,
                "median": round(statistics.median(timings), 2) if timings else None,
                "p90": round(_percentile(timings_sorted, 90), 2) if timings else None,
                "p95": round(_percentile(timings_sorted, 95), 2) if timings else None,
                "p99": round(_percentile(timings_sorted, 99), 2) if timings else None,
                "max": round(max(timings), 2) if timings else None,
            },
            "system": {
                "before": {
                    "memory": _read_meminfo(),
                    "loadavg": _read_loadavg(),
                },
                "during_summary": sampler.summary(),
                "after": {
                    "memory": _read_meminfo(),
                    "loadavg": _read_loadavg(),
                },
            },
            "sample_errors": sample_errors,
            "auth_preflight": {
                "profile_url": auth_preflight["profile_url"],
                "valid_count": auth_preflight["valid_count"],
                "invalid_count": auth_preflight["invalid_count"],
                "invalid_samples": auth_preflight["invalid_samples"],
            },
            "stress_users": {
                "prefix": options["prefix"],
                "domain": options["domain"],
                "tier": options["tier"],
                "paid": not bool(options["free"]),
                "password": options["password"],
                "count": len(users),
                "first_email": users[0]["email"] if users else None,
                "last_email": users[-1]["email"] if users else None,
            },
        }

        with output_path.open("w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2)
        html_output_path = output_path.with_suffix(".html")
        _write_html_report(report, html_output_path)

        self.stdout.write("")
        self.stdout.write(self.style.SUCCESS("Stress test complete"))
        self.stdout.write(f"Report: {output_path}")
        self.stdout.write(f"HTML report: {html_output_path}")
        self.stdout.write(f"Requests/sec: {report['results']['requests_per_second']}")
        self.stdout.write(f"Status codes: {report['results']['status_codes']}")
        if auth_preflight["invalid_count"]:
            self.stdout.write(
                self.style.WARNING(
                    f"Skipped {auth_preflight['invalid_count']} users that failed API auth preflight. "
                    "Check auth_preflight.invalid_samples in report."
                )
            )
        if options["all"]:
            self.stdout.write(f"Endpoint counts: {report['results']['endpoint_counts']}")
            self.stdout.write(f"Endpoint status: {report['results']['endpoint_status_codes']}")
        self.stdout.write(f"Latency avg/p95/max ms: {report['latency_ms']['avg']} / {report['latency_ms']['p95']} / {report['latency_ms']['max']}")
        self.stdout.write(f"CPU avg/max %: {report['system']['during_summary']['cpu_percent']['avg']} / {report['system']['during_summary']['cpu_percent']['max']}")
        self.stdout.write(f"RAM avg/max %: {report['system']['during_summary']['memory_used_percent']['avg']} / {report['system']['during_summary']['memory_used_percent']['max']}")
        if error_count:
            self.stdout.write(self.style.WARNING(f"Errors found: {error_count}. See report sample_errors."))

    def _filter_api_valid_users(self, api_base: str, users: list[dict], timeout: int, max_workers: int = 10) -> dict:
        profile_url = urljoin(api_base, "auth/profile")
        valid_users = []
        invalid_samples = []

        def check_user(row):
            return row, _request_once(
                "GET",
                profile_url,
                row["access"],
                None,
                timeout,
                "auth-profile",
            )

        worker_count = min(max(int(max_workers or 1), 1), max(len(users), 1))
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures = [executor.submit(check_user, row) for row in users]
            for future in as_completed(futures):
                row, (_label, status_code, _elapsed_ms, error) = future.result()
                if 200 <= status_code < 300:
                    valid_users.append(row)
                elif len(invalid_samples) < 20:
                    invalid_samples.append(
                        {
                            "id": row.get("id"),
                            "email": row.get("email"),
                            "tier": row.get("tier"),
                            "status": status_code,
                            "error": error,
                        }
                    )
        return {
            "profile_url": profile_url,
            "total_users": len(users),
            "valid_users": valid_users,
            "valid_count": len(valid_users),
            "invalid_count": len(users) - len(valid_users),
            "invalid_samples": invalid_samples,
        }

    def _build_tasks(self, api_base, single_url, options, users, fixtures):
        request_count = int(options["requests"])
        body = json.loads(options["json"]) if options["json"] else None

        if not options["all"]:
            label = str(options["endpoint"]).lstrip("/") or "request"
            method = options["method"]
            endpoint = str(options["endpoint"]).lstrip("/")
            return [
                {
                    "label": label,
                    "method": method,
                    "url": single_url,
                    "token": users[index % len(users)]["access"],
                    "body": self._auto_body_for_endpoint(endpoint, method, body, users[index % len(users)], fixtures, index),
                }
                for index in range(request_count)
            ]

        endpoint_cycle = ["dashboard", "workout", "nutrition", "habit"]
        tasks = []
        for index in range(request_count):
            user_row = users[index % len(users)]
            label = endpoint_cycle[index % len(endpoint_cycle)]
            if label == "dashboard":
                tasks.append(
                    {
                        "label": "dashboard-new",
                        "method": "GET",
                        "url": urljoin(api_base, "dashboard-new"),
                        "token": user_row["access"],
                        "body": None,
                    }
                )
            elif label == "workout":
                tasks.append(
                    {
                        "label": "workout-logs",
                        "method": "POST",
                        "url": urljoin(api_base, "workout-logs"),
                        "token": user_row["access"],
                        "body": self._workout_body_for_user(user_row),
                    }
                )
            elif label == "nutrition":
                tasks.append(
                    {
                        "label": "nutra-logs",
                        "method": "POST",
                        "url": urljoin(api_base, "nutra-logs"),
                        "token": user_row["access"],
                        "body": self._nutrition_body(),
                    }
                )
            else:
                tasks.append(
                    {
                        "label": "habit-logs",
                        "method": "POST",
                        "url": urljoin(api_base, "habit-logs"),
                        "token": user_row["access"],
                        "body": self._habit_body(index),
                    }
                )
        return tasks

    def _needs_stress_fixtures(self, options, body) -> bool:
        if options["all"]:
            return True
        method = str(options["method"]).upper()
        if method not in {"POST", "PUT", "PATCH"}:
            return False
        endpoint = str(options["endpoint"]).strip().lower()
        body_is_empty = body in (None, {})
        return body_is_empty and any(
            key in endpoint
            for key in ("workout-logs", "nutra-logs", "habit-logs")
        )

    def _auto_body_for_endpoint(self, endpoint, method, body, user_row, fixtures, index):
        if body not in (None, {}):
            return body
        if str(method).upper() not in {"POST", "PUT", "PATCH"}:
            return body
        endpoint = str(endpoint).strip().lower()
        if "workout-logs" in endpoint and fixtures:
            return self._workout_body_for_user(user_row)
        if "nutra-logs" in endpoint and fixtures:
            return self._nutrition_body()
        if "habit-logs" in endpoint and fixtures:
            return self._habit_body(index)
        return body

    def _workout_body_for_user(self, user_row):
        from workouts.models import UserRoutineExercise

        row = (
            UserRoutineExercise.objects.filter(
                routine__user_id=user_row["id"],
                routine__is_active=True,
            )
            .select_related("routine", "exercise")
            .order_by("routine_id", "order", "id")
            .first()
        )
        if not row:
            raise CommandError(f"No active routine exercise found for stress user id={user_row['id']}")
        return {
            "user_routine": row.routine_id,
            "exercise_id": row.exercise_id,
            "points": int(getattr(row.exercise, "points", 0) or 5),
            "sets_done": int(row.sets or 1),
            "reps_done": int(row.qty_min or 10) if row.unit == "reps" else 0,
            "duration_s": int(row.qty_min or 40) if row.unit == "secs" else 40,
        }

    def _nutrition_body(self):
        from nutration.models import Module, ModuleFood

        rel = (
            ModuleFood.objects.select_related("module", "food")
            .filter(module__type=Module.NUTRITION)
            .order_by("module__age_group__min_age", "module__sort_order", "id")
            .first()
        )
        if not rel:
            raise CommandError("No nutrition ModuleFood row found for stress request body.")
        return {
            "module_id": rel.module_id,
            "food_id": rel.food_id,
            "servings": 1,
            "score": int(rel.score or 1),
        }

    def _habit_body(self, index):
        from habits.models import MicroHabit, MicroHabitLog

        habit = MicroHabit.objects.filter(is_active=True).order_by("sort_order", "id").first()
        if not habit:
            raise CommandError("No active MicroHabit found for stress request body.")
        if habit.logging_mode == MicroHabit.AM_PM:
            slot = MicroHabitLog.SLOT_AM if index % 2 == 0 else MicroHabitLog.SLOT_PM
        else:
            slot = MicroHabitLog.SLOT_ONCE
        return {
            "habit_code": habit.code,
            "slot": slot,
        }

    def _ensure_stress_fixtures(self, users):
        from habits.models import MicroHabit
        from nutration.models import AgeGroup, Food, Module, ModuleFood
        from workouts.models import (
            Exercise,
            ExerciseCategory,
            RoutineType,
            Tier,
            UserRoutine,
            UserRoutineExercise,
        )

        exercise, _ = Exercise.objects.get_or_create(
            name="Stress Test Wall Angels",
            defaults={
                "short_name": "Stress Angels",
                "points": 5,
                "category": ExerciseCategory.POSTURE,
                "age_group": "both",
            },
        )
        age_group, _ = AgeGroup.objects.get_or_create(
            name="Stress Test All Ages",
            defaults={"min_age": 0, "max_age": None},
        )
        module, _ = Module.objects.get_or_create(
            name="Stress Test Nutrition",
            age_group=age_group,
            defaults={
                "type": Module.NUTRITION,
                "short_name": "Stress Nutra",
                "nutrition_category": Module.NUTRITION_CATEGORY_TEEN,
                "action_btn": "Log",
                "tag_line": "Stress test fixture",
            },
        )
        food, _ = Food.objects.get_or_create(
            name="Stress Test Food",
            defaults={"short_name": "Stress Food"},
        )
        ModuleFood.objects.get_or_create(
            module=module,
            food=food,
            defaults={"score": 5, "adult_score": 1},
        )
        habit, _ = MicroHabit.objects.get_or_create(
            code="stress-test-breathing",
            defaults={
                "name": "Stress Test Breathing",
                "ui_prompt": "Stress test micro habit",
                "daily_max_points": 2,
                "logging_mode": MicroHabit.AM_PM,
                "points_per_log": 1,
                "sort_order": 999,
                "is_active": True,
            },
        )

        routine_ids = {}
        User = get_user_model()
        for user_row in users:
            user = User.objects.get(pk=user_row["id"])
            routine, _ = UserRoutine.objects.get_or_create(
                user=user,
                routine_type=RoutineType.POSTURE,
                is_active=True,
                defaults={
                    "optimization_breakdown": {
                        "spinal_compression": {"current_loss_cm": 1.0, "max_loss_cm": 2.0},
                        "posture_collapse": {"current_loss_cm": 1.0, "max_loss_cm": 2.0},
                    }
                },
            )
            UserRoutineExercise.objects.get_or_create(
                routine=routine,
                exercise=exercise,
                defaults={
                    "tier": Tier.CORE,
                    "order": 1,
                    "sets": 1,
                    "qty_min": 10,
                    "qty_max": 10,
                    "unit": "reps",
                },
            )
            routine_ids[user.id] = routine.id

        return {
            "exercise_id": exercise.id,
            "module_id": module.id,
            "food_id": food.id,
            "habit_code": habit.code,
            "routines": routine_ids,
        }

    def _create_users(self, options):
        User = get_user_model()
        prefix = str(options["prefix"]).strip()
        domain = str(options["domain"]).strip()
        password = str(options["password"])
        tier = str(options["tier"])
        reset_password = bool(options["reset_password"])
        make_paid = not bool(options["free"])
        count = int(options["users"])

        if not prefix:
            raise CommandError("--prefix cannot be empty")
        if not domain or "@" in domain:
            raise CommandError("--domain must be a plain domain, e.g. stress.local")

        exported = []
        created = 0
        existing = 0
        rows_to_create = []
        if tier == "both":
            teen_count = count // 2
            adult_count = count - teen_count
            rows_to_create.extend(("teen", i) for i in range(1, teen_count + 1))
            rows_to_create.extend(("adult", i) for i in range(1, adult_count + 1))
        else:
            rows_to_create.extend((tier, i) for i in range(1, count + 1))

        for row_tier, index in rows_to_create:
            tier_prefix = f"{prefix}_{row_tier}" if tier == "both" else prefix
            username = f"{tier_prefix}_{index:04d}"
            email = f"{username}@{domain}"
            user, was_created = User.objects.get_or_create(
                email=email,
                defaults={
                    "username": username,
                    "name": f"Stress User {index:04d}",
                    "display_name": f"Stress User {index:04d}",
                    "profile_step": "completed",
                    "account_tier": row_tier,
                    "verified": timezone.now(),
                    "timezone": "UTC",
                    "country_code": "US",
                },
            )
            if was_created:
                user.set_password(password)
                user.save()
                created += 1
            else:
                existing += 1
                update_fields = []
                if reset_password:
                    user.set_password(password)
                    update_fields.append("password")
                if user.account_tier != row_tier:
                    user.account_tier = row_tier
                    update_fields.append("account_tier")
                if user.profile_step != "completed":
                    user.profile_step = "completed"
                    update_fields.append("profile_step")
                if user.verified is None:
                    user.verified = timezone.now()
                    update_fields.append("verified")
                if update_fields:
                    user.save(update_fields=update_fields)

            profile, _ = UserProfile.objects.get_or_create(user=user)
            if row_tier == "adult":
                birth_date = date.today() - timedelta(days=int(365.2425 * 25))
                profile.age = "25"
                profile.current_height_cm = "175"
            else:
                birth_date = date.today() - timedelta(days=int(365.2425 * 15))
                profile.age = "15"
                profile.current_height_cm = "165"
            profile.gender = "male"
            profile.birth_date = birth_date
            profile.base_height_cm = profile.base_height_cm or profile.current_height_cm
            profile.current_height_type = "cm"
            profile.father_height_cm = "178"
            profile.father_height_type = "cm"
            profile.mother_height_cm = "165"
            profile.mother_height_type = "cm"
            profile.save()

            if make_paid:
                self._ensure_paid_subscription(user)

            refresh = RefreshToken.for_user(user)
            exported.append(
                {
                    "id": user.id,
                    "email": email,
                    "tier": row_tier,
                    "access": str(refresh.access_token),
                    "refresh": str(refresh),
                }
            )

        self.stdout.write(f"Stress users: created={created}, existing={existing}, total={len(exported)}")
        return exported

    def _ensure_paid_subscription(self, user):
        package, _ = PaymentPackage.objects.get_or_create(
            name="Stress Test Paid",
            defaults={
                "amount": 1,
                "is_free": False,
                "duration": "1m",
                "description": "Internal stress-test paid package.",
                "features": ["stress-test"],
            },
        )
        Payment.objects.get_or_create(
            user=user,
            payment_id=f"stress-paid-{user.id}",
            defaults={
                "package": package,
                "payment_status": "succeeded",
                "payment_method": "stress_test",
                "amount": package.amount,
                "currency": "usd",
                "complete_response": "{}",
            },
        )
