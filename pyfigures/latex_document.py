"""A LaTeX document (.tex with \\documentclass) as a figure panel.

Dropping a full document — a TikZ / pgfplots picture, a figure environment
with \\includegraphics, a table — compiles it with the computer's LaTeX
installation and adds the result as a (vector) PDF panel:

- the document's own preamble is kept, so its packages and macros work;
- only the part that makes sense as a panel is kept: the first figure or
  table environment (without its \\caption and \\label: captions belong in the
  paper), else the first tikzpicture, else the whole body;
- it is compiled in the document's own folder (relative \\includegraphics /
  \\input paths work) with pdflatex, cropped to its content by the preview
  package;
- the PDF goes to a ``latex`` folder next to the figure, named from a hash of
  the source, so the same document is compiled only once. Its source path is
  recorded beside it (``<pdf>.source``), so the panel can be recompiled later.

A .tex file without \\documentclass is an equation (pyfigures.equations).
"""
from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import tempfile

_MARKER = "pyfigures-latex-document:"


def is_full_document(text: str) -> bool:
    """True for a .tex file that should become a compiled document panel: a
    whole document (\\documentclass…) whose body is more than an equation
    (a document holding only maths stays an editable equation panel)."""
    clean = _strip_comments(text)
    if re.search(r"^\s*\\documentclass", clean, re.M) is None:
        return False
    m = re.search(r"\\begin\{document\}(.*?)\\end\{document\}", clean, re.S)
    return not (m and is_math_only(m.group(1)))


_MATH_BLOCK = re.compile(
    r"\$\$.*?\$\$|\\\[.*?\\\]|\$.*?\$|\\begin\{(equation|align|gather|multline|flalign|alignat|"
    r"displaymath|math|eqnarray)\*?\}.*?\\end\{\1\*?\}", re.S)


def is_math_only(body: str) -> bool:
    """True if a document body holds nothing but mathematics."""
    rest = _MATH_BLOCK.sub("", _strip_comments(body))
    return bool(_MATH_BLOCK.search(body)) and not rest.strip()


def _strip_comments(text):
    return re.sub(r"(?<!\\)%.*", "", text)


def _balanced(text, start):
    """End index (exclusive) of the {...} group opening at text[start] == '{'."""
    depth = 0
    for i in range(start, len(text)):
        c = text[i]
        if c == "\\":
            continue
        if c == "{" and (i == 0 or text[i - 1] != "\\"):
            depth += 1
        elif c == "}" and (i == 0 or text[i - 1] != "\\"):
            depth -= 1
            if depth == 0:
                return i + 1
    return len(text)


def _drop_command(text, name):
    """Remove every \\name[...]{...} (balanced braces)."""
    out = []
    i = 0
    pat = re.compile(r"\\" + name + r"\*?\s*(\[[^\]]*\])?\s*\{")
    while True:
        m = pat.search(text, i)
        if not m:
            out.append(text[i:])
            return "".join(out)
        out.append(text[i:m.start()])
        i = _balanced(text, m.end() - 1)


def panel_content(body: str) -> str:
    """The part of a document body shown as a panel (see module docstring)."""
    m = re.search(r"\\begin\{(figure|table)\*?\}(\[[^\]]*\])?(.*?)\\end\{\1\*?\}", body, re.S)
    if m:
        inner = _drop_command(_drop_command(m.group(3), "caption"), "label")
        return inner.strip()
    m = re.search(r"\\begin\{tikzpicture\}.*?\\end\{tikzpicture\}", body, re.S)
    if m:
        return m.group(0)
    return body.strip()


def split_document(text: str):
    """(preamble up to \\begin{document}, body) of a LaTeX document."""
    m = re.search(r"\\begin\{document\}(.*?)\\end\{document\}", text, re.S)
    if not m:
        raise ValueError("not a LaTeX document (no \\begin{document} … \\end{document})")
    return text[:m.start()], m.group(1)


def document_pdf_path(pyf_path, tex_path) -> str:
    from pyfigures.equations import equation_dir
    with open(tex_path, "rb") as f:
        digest = hashlib.sha1(f.read() + os.path.abspath(tex_path).encode("utf-8")).hexdigest()[:12]
    base = os.path.splitext(os.path.basename(tex_path))[0]
    folder = os.path.join(os.path.dirname(equation_dir(pyf_path)), "latex")
    return os.path.join(folder, f"{re.sub(r'[^A-Za-z0-9_-]+', '_', base)}_{digest}.pdf")


def compile_document(tex_path: str, out_pdf: str) -> str:
    """Compile the panel part of the document *tex_path* to *out_pdf*
    (cropped). Raises ValueError with LaTeX's message on failure."""
    from pyfigures.equations import find_tex_tool
    pdflatex = find_tex_tool("pdflatex")
    if pdflatex is None:
        raise ValueError("a .tex document needs a LaTeX installation (pdflatex from TeX Live, "
                         "MiKTeX or MacTeX)")
    with open(tex_path, encoding="utf-8", errors="replace") as f:
        text = f.read()
    preamble, body = split_document(text)
    content = panel_content(body)
    doc = "\n".join([
        preamble.rstrip(),
        r"\usepackage{varwidth}",
        r"\usepackage[active,tightpage]{preview}",
        r"\setlength\PreviewBorder{1pt}",
        r"\pagestyle{empty}",
        r"\begin{document}",
        r"\begin{preview}\begin{varwidth}{\linewidth}\centering",
        content,
        r"\end{varwidth}\end{preview}",
        r"\end{document}",
        ""])
    src_dir = os.path.dirname(os.path.abspath(tex_path))
    work = tempfile.mkdtemp(prefix="pyf_texdoc_")
    try:
        job = os.path.join(work, "panel.tex")
        with open(job, "w", encoding="utf-8") as f:
            f.write(doc)
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        # run in the document's folder: its relative paths (images, \input) resolve there
        r = subprocess.run([pdflatex, "-interaction=nonstopmode", "-halt-on-error",
                            f"-output-directory={work}", job],
                           cwd=src_dir, capture_output=True, text=True, timeout=600,
                           creationflags=flags)
        pdf = os.path.join(work, "panel.pdf")
        if r.returncode != 0 or not os.path.isfile(pdf):
            log = ""
            if os.path.isfile(os.path.join(work, "panel.log")):
                with open(os.path.join(work, "panel.log"), encoding="utf-8", errors="replace") as f:
                    log = f.read()
            errors = [ln[1:].strip() for ln in log.splitlines() if ln.startswith("!")]
            detail = "; ".join(errors[:3]) or (r.stdout or r.stderr or "").strip()[-300:]
            raise ValueError(f"LaTeX could not compile {os.path.basename(tex_path)}: {detail}")
        os.makedirs(os.path.dirname(os.path.abspath(out_pdf)) or ".", exist_ok=True)
        shutil.copyfile(pdf, out_pdf)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    _mark_source(out_pdf, tex_path)
    return out_pdf


def _mark_source(pdf_path, tex_path):
    """Record the source .tex next to the PDF (<pdf>.source), so the panel can
    be recompiled from it later."""
    try:
        with open(pdf_path + ".source", "w", encoding="utf-8") as f:
            f.write(os.path.abspath(tex_path))
    except OSError:
        pass


def source_of(pdf_path):
    """The .tex a compiled document panel came from, or None."""
    try:
        with open(pdf_path + ".source", encoding="utf-8") as f:
            return f.read().strip() or None
    except OSError:
        return None


def make_document_panel(pyf_path, tex_path) -> str:
    """Compile *tex_path* (if not already) and return the PDF panel's path."""
    out = document_pdf_path(pyf_path, tex_path)
    if not os.path.isfile(out):
        compile_document(tex_path, out)
    return out
