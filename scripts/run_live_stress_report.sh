#!/usr/bin/env bash
set -euo pipefail

API_BASE="${1:-${API_BASE:-}}"

if [[ -z "$API_BASE" ]]; then
  echo "Usage:"
  echo "  bash scripts/run_live_stress_report.sh https://your-live-domain.com/api"
  echo
  echo "Optional env vars:"
  echo "  REQUESTS=1000 CONCURRENCY=25 USERS=100 TIER=both PREFIX=stress OUTPUT=/tmp/dashboard_stress_report.json"
  echo "  ALL=1  # dashboard + workout + nutrition + microhabit in parallel"
  exit 1
fi

REQUESTS="${REQUESTS:-100}"
CONCURRENCY="${CONCURRENCY:-5}"
USERS="${USERS:-100}"
TIER="${TIER:-both}"
PREFIX="${PREFIX:-stress}"
DOMAIN="${DOMAIN:-stress.local}"
OUTPUT="${OUTPUT:-/tmp/dashboard_stress_report.json}"
ENDPOINT="${ENDPOINT:-/dashboard-new}"
ALL="${ALL:-0}"

cd "$(dirname "$0")/.."

ALL_ARGS=()
if [[ "$ALL" == "1" || "$ALL" == "true" || "$ALL" == "yes" ]]; then
  ALL_ARGS=(--all)
fi

python manage.py run_api_stress_report \
  --api-base "$API_BASE" \
  --endpoint "$ENDPOINT" \
  "${ALL_ARGS[@]}" \
  --users "$USERS" \
  --tier "$TIER" \
  --prefix "$PREFIX" \
  --domain "$DOMAIN" \
  -n "$REQUESTS" \
  -c "$CONCURRENCY" \
  --output "$OUTPUT"

echo
echo "Report saved at: $OUTPUT"
echo "HTML report saved at: ${OUTPUT%.*}.html"
echo
echo "View summary:"
echo "python3 - <<'PY'"
echo "import json"
echo "r=json.load(open('$OUTPUT'))"
echo "print('Requests/sec:', r['results']['requests_per_second'])"
echo "print('Status:', r['results']['status_codes'])"
echo "print('Endpoint counts:', r['results'].get('endpoint_counts'))"
echo "print('Endpoint status:', r['results'].get('endpoint_status_codes'))"
echo "print('Latency avg/p95/max:', r['latency_ms']['avg'], r['latency_ms']['p95'], r['latency_ms']['max'])"
echo "print('CPU avg/max:', r['system']['during_summary']['cpu_percent']['avg'], r['system']['during_summary']['cpu_percent']['max'])"
echo "print('RAM avg/max:', r['system']['during_summary']['memory_used_percent']['avg'], r['system']['during_summary']['memory_used_percent']['max'])"
echo "PY"
