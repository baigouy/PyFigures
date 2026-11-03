#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
export PYTHONPATH="$SCRIPT_DIR:$SCRIPT_DIR/../BAtools_pkg${PYTHONPATH:+:$PYTHONPATH}"
export QT_QPA_PLATFORM=offscreen
PYTHON=/home/aigouy/miniconda3/envs/FISH_Dist/bin/python3
$PYTHON -m pip install --quiet pytest pytest-qt pytest-timeout
$PYTHON -m pytest "$@"
