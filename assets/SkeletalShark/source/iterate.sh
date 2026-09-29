#!/bin/bash
# usage: iterate.sh <round-name>   (rebuild -> render -> compare -> fit report)
set -e
SP=${SP:?set SP to a scratch dir containing bvenv/ and ../images/1.webp}
cd "$(dirname "$0")"
$SP/bvenv/bin/python build_blend.py $SP/out 2>&1 | grep -E "^TRIS|Error|Traceback" || true
SAMPLES=${SAMPLES:-24} $SP/bvenv/bin/python render_views.py $SP/out/SkeletalShark.blend $SP/$1 2>&1 | grep -E "Error|Traceback" || true
$SP/bvenv/bin/python compare_sheet.py $SP/../images/1.webp $SP/$1 $SP/$1
$SP/bvenv/bin/python fit_report.py $SP/../images/1.webp $SP/$1 | tr -d '\n '; echo
