"""A Python file dropped on the window, to become a script panel (user, 2026-11-18: "can
the user also drop a .py file, to be used as a script for the panel, just make sure it's
done safely").

Running a script runs code with the user's rights: nothing here makes an unknown script
safe. What is done instead: the file is only READ when dropped (never imported, never
run), its syntax is checked, and the user sees the code with the lines that touch the
computer (files deleted or written, programs started, network, code built at run time)
called out, and runs it only by choosing to. The same rule as opening a .pyf with
scripts (a security warning first).
"""
from __future__ import annotations

import ast
import os

MAX_BYTES = 512 * 1024          # a panel script, not a program

# calls whose name (or dotted name) is worth a look before running
_RISKY_CALLS = {
    "os.system": "runs a shell command", "os.popen": "runs a shell command",
    "os.remove": "deletes a file", "os.unlink": "deletes a file", "os.rmdir": "deletes a folder",
    "os.removedirs": "deletes folders", "os.rename": "renames a file", "os.replace": "replaces a file",
    "os.chmod": "changes file permissions", "os.kill": "stops a program",
    "shutil.rmtree": "deletes a folder and everything in it", "shutil.move": "moves files",
    "shutil.copy": "copies files", "shutil.copyfile": "copies files", "shutil.copytree": "copies folders",
    "subprocess.run": "starts a program", "subprocess.call": "starts a program",
    "subprocess.Popen": "starts a program", "subprocess.check_call": "starts a program",
    "subprocess.check_output": "starts a program",
    "eval": "runs code built at run time", "exec": "runs code built at run time",
    "compile": "builds code at run time", "__import__": "imports a module by name",
    "urllib.request.urlopen": "reads from the internet", "requests.get": "reads from the internet",
    "requests.post": "sends data over the internet", "socket.socket": "opens a network connection",
    "ctypes.CDLL": "loads a native library", "ctypes.windll": "calls Windows directly",
}
_RISKY_MODULES = {"subprocess": "starts programs", "socket": "network", "ctypes": "native code",
                  "requests": "internet", "urllib": "internet", "http": "internet", "ftplib": "internet",
                  "smtplib": "sends e-mail", "winreg": "the Windows registry", "pickle": "can run code when loading"}


def _dotted(node) -> str:
    parts = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return ".".join(reversed(parts))


def read_script(path: str) -> tuple[str | None, str | None]:
    """(code, None), or (None, why it cannot be a panel script). Only reads the file."""
    try:
        size = os.path.getsize(path)
    except OSError as e:
        return None, f"cannot read {os.path.basename(path)}: {e}"
    if size > MAX_BYTES:
        return None, f"{os.path.basename(path)} is {size // 1024} KB: too big for a panel script"
    try:
        with open(path, encoding="utf-8-sig") as f:
            code = f.read()
    except (OSError, UnicodeDecodeError) as e:
        return None, f"cannot read {os.path.basename(path)} as text: {e}"
    if not code.strip():
        return None, f"{os.path.basename(path)} is empty"
    try:
        ast.parse(code)
    except SyntaxError as e:
        return None, f"{os.path.basename(path)} is not valid Python (line {e.lineno}: {e.msg})"
    return code, None


def review(code: str) -> dict:
    """What the user should know before running *code* (from its syntax tree; nothing is
    run): 'risky' = [(line, what it does, the line's text)], 'sets_image' = whether it
    gives the panel its picture (self.img = ...)."""
    tree = ast.parse(code)
    lines = code.splitlines()
    risky = []

    def note(node, what):
        text = lines[node.lineno - 1].strip() if 0 < node.lineno <= len(lines) else ""
        risky.append((node.lineno, what, text[:120]))

    sets_image = False
    for node in ast.walk(tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""]
            for name in names:
                top = name.split(".")[0]
                if top in _RISKY_MODULES:
                    note(node, f"imports {top} ({_RISKY_MODULES[top]})")
        elif isinstance(node, ast.Call):
            name = _dotted(node.func)
            if name in _RISKY_CALLS:
                note(node, _RISKY_CALLS[name])
            elif name == "open" and _opens_for_writing(node):
                note(node, "writes a file")
            elif name.split(".")[-1] in ("write_text", "write_bytes", "unlink", "rmdir") and "." in name:
                note(node, "writes or deletes a file")         # pathlib.Path methods
        elif isinstance(node, ast.Assign):
            for t in node.targets:
                if isinstance(t, ast.Attribute) and t.attr == "img" and _dotted(t.value) == "self":
                    sets_image = True
    risky.sort()
    return {"risky": risky, "sets_image": sets_image}


def _opens_for_writing(call: ast.Call) -> bool:
    mode = None
    if len(call.args) > 1 and isinstance(call.args[1], ast.Constant):
        mode = call.args[1].value
    for kw in call.keywords:
        if kw.arg == "mode" and isinstance(kw.value, ast.Constant):
            mode = kw.value.value
    return isinstance(mode, str) and any(c in mode for c in "wax+")


def warning_text(path: str, info: dict) -> str:
    """The message shown with the code."""
    out = [f"{os.path.basename(path)} is Python code. Running it as a panel runs it on this "
           "computer, with your rights, now and each time the figure is opened. Only run scripts "
           "you wrote or trust."]
    if info["risky"]:
        out.append("It does things beyond drawing:")
        out += [f"  line {n}: {what}  ({text})" for n, what, text in info["risky"][:12]]
        if len(info["risky"]) > 12:
            out.append(f"  ... and {len(info['risky']) - 12} more")
    if not info["sets_image"]:
        out.append("It never sets self.img (the panel's picture: self.img = fig): the panel "
                   "would stay empty.")
    return "\n".join(out)
