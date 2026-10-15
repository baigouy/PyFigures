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

LaTeX *code panels* (``latex_code_pdf``): a panel whose script is LaTeX code
(a TikZ picture, a table, a whole document…) instead of Python, or a Python
script calling ``latex(code)``; compiled the same way.
"""
from __future__ import annotations

import hashlib
import json
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


def candidate_parts(body: str):
    """The parts of a document body that can be a panel, in order: its figure
    and table environments (without \\caption / \\label), else its
    tikzpictures. [(short description, LaTeX)]; empty if it has none."""
    parts = []
    counts = {}
    for m in re.finditer(r"\\begin\{(figure|table)\*?\}(\[[^\]]*\])?(.*?)\\end\{\1\*?\}", body, re.S):
        kind = m.group(1).capitalize()
        counts[kind] = counts.get(kind, 0) + 1
        inner = m.group(3)
        cap = re.search(r"\\caption\*?\s*(\[[^\]]*\])?\s*\{", inner)
        caption = ""
        if cap:
            caption = inner[cap.end():_balanced(inner, cap.end() - 1) - 1]
            caption = " ".join(re.sub(r"\\[A-Za-z]+\*?|[{}$]", " ", caption).split())[:60]
        content = _drop_command(_drop_command(inner, "caption"), "label").strip()
        parts.append((f"{kind} {counts[kind]}" + (f": {caption}" if caption else ""), content))
    if not parts:
        for i, m in enumerate(re.finditer(r"\\begin\{tikzpicture\}.*?\\end\{tikzpicture\}", body, re.S)):
            parts.append((f"TikZ picture {i + 1}", m.group(0)))
    return parts


def panel_content(body: str, part: int | None = None) -> str:
    """The part of a document body shown as a panel (see module docstring):
    candidate *part* (1-based; default the first), or the whole body if the
    document has no figure, table or tikzpicture."""
    parts = candidate_parts(body)
    if not parts:
        return body.strip()
    index = 1 if part is None else int(part)
    if not 1 <= index <= len(parts):
        raise ValueError(f"part must be between 1 and {len(parts)} (the document has "
                         f"{len(parts)} figure/table/picture(s))")
    return parts[index - 1][1]


def parts_of(tex_path):
    """[(description, LaTeX)] of the panel candidates of a .tex document."""
    with open(tex_path, encoding="utf-8", errors="replace") as f:
        _, body = split_document(f.read())
    return candidate_parts(body)


def split_document(text: str):
    """(preamble up to \\begin{document}, body) of a LaTeX document."""
    m = re.search(r"\\begin\{document\}(.*?)\\end\{document\}", text, re.S)
    if not m:
        raise ValueError("not a LaTeX document (no \\begin{document} … \\end{document})")
    return text[:m.start()], m.group(1)


def document_pdf_path(pyf_path, tex_path, part=None) -> str:
    from pyfigures.equations import equation_dir
    with open(tex_path, "rb") as f:
        key = f.read() + os.path.abspath(tex_path).encode("utf-8") + str(part or 1).encode()
    digest = hashlib.sha1(key).hexdigest()[:12]
    base = os.path.splitext(os.path.basename(tex_path))[0]
    folder = os.path.join(os.path.dirname(equation_dir(pyf_path)), "latex")
    return os.path.join(folder, f"{re.sub(r'[^A-Za-z0-9_-]+', '_', base)}_{digest}.pdf")


def compile_document(tex_path: str, out_pdf: str, part: int | None = None) -> str:
    """Compile the panel part (*part*, 1-based; default the first) of the
    document *tex_path* to *out_pdf* (cropped). Raises ValueError with
    LaTeX's message on failure."""
    with open(tex_path, encoding="utf-8", errors="replace") as f:
        text = f.read()
    compile_text(text, out_pdf, os.path.dirname(os.path.abspath(tex_path)),
                 os.path.basename(tex_path), part)
    _mark_source(out_pdf, tex_path, part)
    return out_pdf


def compile_text(text: str, out_pdf: str, src_dir: str, name: str = "the LaTeX code",
                 part: int | None = None, whole_body: bool = False) -> str:
    """Compile the LaTeX document *text* (its panel part, or its whole body
    with *whole_body*) to *out_pdf*, cropped, running in *src_dir* (relative
    paths resolve there). Raises ValueError with LaTeX's message on failure."""
    from pyfigures.equations import find_tex_tool
    pdflatex = find_tex_tool("pdflatex")
    if pdflatex is None:
        from batoolset.tex_install import INSTALL_HINT
        raise ValueError("LaTeX code needs a LaTeX installation (pdflatex from TeX Live, "
                         f"MiKTeX or MacTeX). {INSTALL_HINT}")
    preamble, body = split_document(text)
    content = body.strip() if whole_body else panel_content(body, part)
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
    work = tempfile.mkdtemp(prefix="pyf_texdoc_")
    try:
        job = os.path.join(work, "panel.tex")
        with open(job, "w", encoding="utf-8") as f:
            f.write(doc)
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        pdf = os.path.join(work, "panel.pdf")
        rounds = 6                     # LaTeX stops at the first missing package
        for attempt in range(rounds):
            # run in the document's folder: its relative paths (images, \input) resolve there
            r = subprocess.run([pdflatex, "-interaction=nonstopmode", "-halt-on-error",
                                f"-output-directory={work}", job],
                               cwd=src_dir, capture_output=True, text=True, timeout=600,
                               creationflags=flags)
            log = ""
            if os.path.isfile(os.path.join(work, "panel.log")):
                with open(os.path.join(work, "panel.log"), encoding="utf-8", errors="replace") as f:
                    log = f.read()
            if r.returncode == 0 and os.path.isfile(pdf):
                break
            # a package the document uses is missing: TeX Live can add it
            from batoolset.tex_install import install_missing
            if attempt == rounds - 1 or not install_missing(log):
                break
        if r.returncode != 0 or not os.path.isfile(pdf):
            errors = [ln[1:].strip() for ln in log.splitlines() if ln.startswith("!")]
            detail = "; ".join(errors[:3]) or (r.stdout or r.stderr or "").strip()[-300:]
            raise ValueError(f"LaTeX could not compile {name}: {detail}")
        os.makedirs(os.path.dirname(os.path.abspath(out_pdf)) or ".", exist_ok=True)
        shutil.copyfile(pdf, out_pdf)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    return out_pdf


# ---------------------------------------------------------------------------
# LaTeX code panels: a panel whose script is LaTeX code (or a Python script
# calling latex(...)); compiled to a PDF kept with the figure's typeset maths
# (batoolset.latex_tools caches), so it opens on computers without TeX
# ---------------------------------------------------------------------------
CODE_PREAMBLE = "\n".join([
    r"\documentclass{article}",
    r"\usepackage{amsmath,amssymb,bm,siunitx,graphicx,booktabs,xcolor}",
    r"\usepackage{tikz}",
    r"\usepackage{pgfplots}",
    r"\pgfplotsset{compat=1.18}",
])
CODE_VERSION = 1             # bumped if CODE_PREAMBLE / the wrapping changes


def is_latex_code(script) -> bool:
    """True if a panel script is LaTeX rather than Python (Python code never
    starts with a backslash or a % comment)."""
    return isinstance(script, str) and script.lstrip().startswith(("\\", "%"))


def code_document(code: str, preamble: str | None = None):
    """(full document text, whole_body) for LaTeX *code*: a whole document is
    used as it is (its panel part); a snippet (TikZ, pgfplots, a table,
    maths…) is wrapped in CODE_PREAMBLE (+ *preamble*) and shown whole."""
    if is_full_document(code):
        return code, False
    head = CODE_PREAMBLE + ("\n" + preamble if preamble else "")
    return head + "\n\\begin{document}\n" + code.strip() + "\n\\end{document}\n", True


def _code_key(code, preamble):
    raw = json.dumps([CODE_VERSION, code.strip(), preamble or ""])
    return "code_" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:16]


def latex_code_pdf(code: str, preamble: str | None = None, cache_dirs=None, cwd=None) -> str:
    """The PDF of LaTeX *code* (see code_document): from the caches (the
    figure's ``equations/labels`` folder, then the user's), else compiled —
    in *cwd* (default: the figure's folder) so relative \\includegraphics
    paths work. Raises ValueError (LaTeX's message, or how to install LaTeX)."""
    from batoolset import latex_tools as LT
    key = _code_key(code, preamble)
    dirs = list(LT.CACHE_DIRS if cache_dirs is None else cache_dirs) + [LT.user_cache_dir()]
    for d in dirs:
        pdf = os.path.join(d, key + ".pdf")
        if os.path.isfile(pdf):
            LT.USED.add(key)
            if dirs[0] != d and cache_dirs is None and LT.CACHE_DIRS:
                _store_code(pdf, key, code, preamble, [LT.CACHE_DIRS[0]])
            return pdf
    text, whole = code_document(code, preamble)
    if cwd is None:
        cwd = LT.FIGURE_DIR[0] if LT.FIGURE_DIR else os.getcwd()
    tmp = tempfile.mkdtemp(prefix="pyf_code_")
    try:
        out = compile_text(text, os.path.join(tmp, key + ".pdf"), cwd, "the LaTeX code",
                           whole_body=whole)
        stored = _store_code(out, key, code, preamble, dirs)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    LT.USED.add(key)
    if stored is None:
        raise ValueError("could not store the compiled LaTeX code")
    return stored


def _store_code(pdf, key, code, preamble, dirs):
    """Copy *pdf* (+ a .json with its code) into the first writable of *dirs*
    and the user cache; returns the first copy."""
    from batoolset import latex_tools as LT
    first = None
    for d in list(dirs[:1]) + [LT.user_cache_dir()]:
        try:
            os.makedirs(d, exist_ok=True)
            dest = os.path.join(d, key + ".pdf")
            if os.path.abspath(dest) != os.path.abspath(pdf):
                shutil.copyfile(pdf, dest)
            with open(os.path.join(d, key + ".json"), "w", encoding="utf-8") as f:
                json.dump({"code": code, "preamble": preamble}, f)
            if first is None:
                first = dest
        except OSError:
            continue
    return first


def _mark_source(pdf_path, tex_path, part=None):
    """Record the source .tex (and part) next to the PDF (<pdf>.source), so
    the panel can be recompiled from it later."""
    import json
    try:
        with open(pdf_path + ".source", "w", encoding="utf-8") as f:
            json.dump({"tex": os.path.abspath(tex_path), "part": part}, f)
    except OSError:
        pass


def _source_record(pdf_path):
    import json
    try:
        with open(pdf_path + ".source", encoding="utf-8") as f:
            text = f.read().strip()
    except OSError:
        return None
    try:
        rec = json.loads(text)
        return rec if isinstance(rec, dict) else None
    except ValueError:
        return {"tex": text, "part": None} if text else None


def source_of(pdf_path):
    """The .tex a compiled document panel came from, or None."""
    rec = _source_record(pdf_path)
    return rec.get("tex") if rec else None


def part_of(pdf_path):
    """Which part of its .tex a compiled document panel shows (1-based), or None."""
    rec = _source_record(pdf_path)
    return rec.get("part") if rec else None


def is_stale(pdf_path) -> bool:
    """True if the .tex a document panel came from changed after it was compiled."""
    src = source_of(pdf_path)
    try:
        return bool(src) and os.path.getmtime(src) > os.path.getmtime(pdf_path)
    except OSError:
        return False


def make_document_panel(pyf_path, tex_path, part=None) -> str:
    """Compile *tex_path* (its *part*; if not already) and return the PDF
    panel's path."""
    out = document_pdf_path(pyf_path, tex_path, part)
    if not os.path.isfile(out):
        compile_document(tex_path, out, part)
    return out
