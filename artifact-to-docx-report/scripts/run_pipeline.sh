#!/usr/bin/env bash
# End to end: saved artifact HTML -> data.json -> charts -> docx -> render check.
# Usage: run_pipeline.sh <artifact_index.html> <example_dir> <out.docx> [workdir]
# Example: run_pipeline.sh index.html examples/property_financials ./2026-10-05_Property-Financials-Review_Report_v01.docx
set -e
HERE="$(cd "$(dirname "$0")/.." && pwd)"
HTML="$1"; EX="$2"; OUT="$3"; WD="${4:-$(mktemp -d)}"
mkdir -p "$WD/charts"
python3 -I "$HERE/scripts/extract_artifact_data.py" "$HTML" "$WD/data.json"
python3 -I "$EX/charts.py" "$WD/data.json" "$WD/charts"
node "$EX/make.js" "$WD/data.json" "$WD/charts" "$OUT"
bash "$HERE/scripts/render_check.sh" "$OUT" "$WD/render"
echo "workdir: $WD"
