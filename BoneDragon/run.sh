#!/bin/bash
# rebuild + render comparison. usage: ./run.sh [views]
cd "$(dirname "$0")"; python3 build.py 2>&1 | grep -E "tris|Error|error|Traceback|assert" ; V=${1:-front,left,back,top,right,persp34}
VIEWS=$V RES=900 SAMPLES=20 python3 tools/render_ref.py BoneDragon.blend renders 2>&1 | tail -1
