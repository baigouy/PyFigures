"""Port the MCP partner prototype into ``pyfigures/assistant``.

The prototype (``chatGPT_validation/live_mcp_gui``, outside the repository)
is where the live-session server is developed against a local model. This
script copies its server modules into the package so the real application can
use them:

* flat imports become relative ones; ``live_gui.py`` becomes ``session.py``;
* the prototype's process-wide redirection (TEMP, APPDATA, QSettings,
  ``sys.path``, faulthandler log) and its ``main()`` are dropped: state lives
  in ``pyfigures.assistant.runtime_dir()``;
* help supplements are authored guides in ``pyfigures.guides`` (the
  prototype's ``source_help`` is not copied);
* the legacy chat files (chat_sidecar, local_runtime, qwen_protocol, ...) are
  not copied: the chat is the separate ``qtpy_ai_sidecar`` package.

Hand-written package files (``__init__.py``, ``launch.py``) are never touched.
Re-run after the prototype changes, then run ``tests/test_assistant_*.py``::

    python packaging/port_assistant.py [PROTOTYPE_DIR]
"""
from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DEFAULT_SRC = REPO / "chatGPT_validation" / "live_mcp_gui"
DST = REPO / "pyfigures" / "assistant"

MODULES = ["categorized_mcp", "existing_tools", "original_registry", "partner_gui", "figure_state",
           "gui_selection", "letter_sequence", "live_structure", "plot_lifecycle", "pointer_context",
           "readability", "recovery", "submission_review", "manual_help", "native_gui",
           "assistant_actions", "advanced_annotations", "live_mcp", "live_gui"]
RENAMED = {"live_gui": "session"}
DATA = ["manual_help_verified.json"]
HEADER = '''"""Live session of the open figure editor: requests from the local HTTP
bridge run on the Qt thread, with revisions, recovery copies and one undo
step per edit. State lives in ``pyfigures.assistant.runtime_dir()``.
Ported from the MCP partner prototype by packaging/port_assistant.py."""
import os
import sys
from pathlib import Path
import argparse
import hashlib
import html
import json
import queue
import secrets
import tempfile
import threading
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from pyfigures.assistant import runtime_dir
from pyfigures.gui.pfgui import EZFIG_GUI, QApplication, QTimer, object_to_xml, TAText2D, Image2D
from qtpy.QtCore import QSettings
from .partner_gui import PartnerGUI
EZFIG_GUI = PartnerGUI

STATE = runtime_dir()
'''


def _replace(text, old, new, name, count=1):
    if text.count(old) != count:
        raise SystemExit(f"{name}: expected {count} x {old[:60]!r}, found {text.count(old)}: update the port")
    return text.replace(old, new)


def relativise(text):
    def sub(m):
        name = RENAMED.get(m.group(2), m.group(2))
        if m.group(2) in MODULES:
            return f"{m.group(1)}from .{name} import "
        return m.group(0)
    return re.sub(r"^(\s*)from (\w+) import ", sub, text, flags=re.M)


def port_session(text):
    head_end = text.index("EZFIG_GUI = PartnerGUI\n") + len("EZFIG_GUI = PartnerGUI\n")
    text = HEADER + text[head_end:]
    text = _replace(text, "ROOT / 'saved_figures'", "STATE / 'saved_figures'", "session")
    text = re.sub(r"        if not destination\.is_relative_to\(ROOT\.resolve\(\)\) or destination\.suffix\.lower\(\) != '\.pyf':\n"
                  r"            raise ValueError\('[^']*'\)\n",
                  "        if destination.suffix.lower() != '.pyf':\n"
                  "            raise ValueError('Save paths must be .pyf files')\n", text)
    text = text[:text.index("\ndef main():")].rstrip() + "\n"
    if "ROOT" in text:
        raise SystemExit("session: ROOT still used: update the port")
    return text


def port_live_mcp(text):
    text = _replace(text, "os.environ['PYTHONDONTWRITEBYTECODE'] = '1'\n", "", "live_mcp")
    text = re.sub(r"ROOT = Path\(__file__\)\.resolve\(\)\.parent\nif ROOT\.parent\.name == 'chatGPT_validation':\n"
                  r"    sys\.path\.insert\(0, str\(ROOT\.parent\.parent\)\)\n",
                  "from pyfigures.assistant import runtime_dir\n", text)
    text = re.sub(r"ROOT / os\.environ\.get\('PYFIGURES_LIVE_RUNTIME', 'runtime'\)", "runtime_dir()", text)
    text = text.replace("FastMCP('PyFigures live prototype'", "FastMCP('PyFigures live'")
    text = text.replace(" inside the prototype folder", "")
    text = text.replace("The prototype window is closed or starting. Reopen it",
                        "The PyFigures window is closed or not sharing its figure "
                        "(Tools > Share the open figure with the MCP server). Start it")
    text = text.replace("Reinspect the active prototype", "Reinspect the live figure")
    text = text.replace("The prototype is not responding. Reopen its window",
                        "PyFigures is not responding. Reopen its window")
    text = text.replace("earlier prototype sessions", "earlier live sessions")
    if "ROOT" in text:
        raise SystemExit("live_mcp: ROOT still used: update the port")
    return text


def port_manual_help(text):
    text = re.sub(r"    from \.?source_help import explain_feature\n    supplement=explain_feature\(topic\)\n"
                  r"    if supplement is not None:return supplement\n", "", text)
    text = _replace(text, "(ROOT.parent.parent/'pyfigures/gui/ezfig.py')", "(ROOT.parent/'gui'/'ezfig.py')",
                    "manual_help")
    return text


def port_categorized_mcp(text):
    # supplements are authored guides now: manual_help.explain finds them
    return _replace(text, "        from source_help import explain_feature\n"
                          "        manual_guides=explain_feature(query)\n",
                    "        manual_guides=None\n", "categorized_mcp")


SPECIAL = {"live_gui": port_session, "live_mcp": port_live_mcp, "manual_help": port_manual_help,
           "categorized_mcp": port_categorized_mcp}


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    src = Path(argv[0]) if argv else DEFAULT_SRC
    for name in MODULES:
        text = relativise((src / (name + ".py")).read_text(encoding="utf-8"))
        if name in SPECIAL:
            text = SPECIAL[name](text)
        (DST / (RENAMED.get(name, name) + ".py")).write_text(text, encoding="utf-8", newline="\n")
    for name in DATA:
        shutil.copy2(src / name, DST / name)
    problems = []
    for p in sorted(DST.glob("*.py")):
        for i, line in enumerate(p.read_text(encoding="utf-8").splitlines(), 1):
            if re.match(r"\s*(from|import) (" + "|".join(MODULES + ["source_help", "chat_sidecar", "test_live"]) + r")\b", line):
                problems.append(f"{p.name}:{i}: {line.strip()}")
            if "chatGPT_validation" in line or "sys.path.insert" in line:
                problems.append(f"{p.name}:{i}: {line.strip()}")
    print("\n".join(problems) or f"ported {len(MODULES)} modules from {src}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
