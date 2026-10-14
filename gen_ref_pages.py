"""Pages generated when the documentation is built (mkdocs-gen-files).

Run by MkDocs itself (mkdocs.yml, plugin ``gen-files``), locally or on Read
the Docs; nothing here is written into the repository:

- ``index.md``: README.md, with its links made relative to the site;
- ``user_guide.md``: the body of docs/pyfigures_user_guide.html (the guide
  the application opens from Help → User Guide), so there is one source;
- ``api/*.md``: the API reference pages (mkdocstrings), from the docstrings.

Build locally:  pip install -r docs/requirements.txt  then  mkdocs serve
"""
import os
import re

import mkdocs_gen_files

ROOT = os.path.dirname(os.path.abspath(__file__))
REPO = "https://github.com/baigouy/PyFigures"

# ---------------------------------------------------------------------------
# Home: README.md
# ---------------------------------------------------------------------------
with open(os.path.join(ROOT, "README.md"), encoding="utf-8") as f:
    readme = f.read()
# docs/X.md -> X.md (the site's own pages); other repository files -> GitHub
readme = re.sub(r"\]\(docs/([^)#\s]+\.md)(#[^)]*)?\)", lambda m: f"]({m.group(1)}{m.group(2) or ''})", readme)
readme = re.sub(r"\]\(docs/pyfigures_user_guide\.html(#[^)]*)?\)",
                lambda m: f"](user_guide.md{m.group(1) or ''})", readme)


def _to_github(m):
    target = m.group(1)
    if re.match(r"(https?:|mailto:|#)", target) or target.endswith(".md"):
        return m.group(0)
    if re.search(r"\.(png|jpe?g|gif|svg)$", target, re.I):
        return m.group(0)                      # images are copied next to the page below
    return f"]({REPO}/blob/main/{target.lstrip('./')})"


readme = re.sub(r"\]\(([^)\s]+)\)", _to_github, readme)
with mkdocs_gen_files.open("index.md", "w") as f:
    f.write(readme)
mkdocs_gen_files.set_edit_path("index.md", "README.md")

# images the README shows (e.g. ./images/PyFigures.png)
for rel in sorted(set(re.findall(r"\]\(\.?/?([^)\s]+\.(?:png|jpe?g|gif|svg))\)", readme, re.I))):
    src = os.path.join(ROOT, rel)
    if os.path.isfile(src) and not rel.startswith("http"):
        with open(src, "rb") as fi, mkdocs_gen_files.open(rel, "wb") as fo:
            fo.write(fi.read())

# ---------------------------------------------------------------------------
# User guide: the HTML guide's body
# ---------------------------------------------------------------------------
with open(os.path.join(ROOT, "docs", "pyfigures_user_guide.html"), encoding="utf-8") as f:
    html = f.read()
body = re.search(r"<body[^>]*>(.*)</body>", html, re.S | re.I)
body = body.group(1) if body else html
body = re.sub(r"<script\b.*?</script>", "", body, flags=re.S | re.I)
# the guide's own sidebar: the site's navigation replaces it
body = re.sub(r'<nav id="sidebar".*?</nav>', "", body, flags=re.S | re.I)
# the guide's own stylesheet, limited to the guide (the site theme keeps the rest)
style = re.search(r"<style[^>]*>(.*?)</style>", html, re.S | re.I)
css = ""
if style:
    rules = re.sub(r"(^|})\s*(body|html)\s*\{[^}]*\}", r"\1", style.group(1))
    css = "<style>\n" + re.sub(r"(^|})\s*([^{}@]+)\{",
                               lambda m: m.group(1) + " " + ", ".join(
                                   ".pyf-guide " + s.strip() for s in m.group(2).split(",")) + " {",
                               rules)
    # inside the site page: no page padding or width of its own
    css += ("\n.pyf-guide .page-wrapper { display: block; min-height: 0; }"
            "\n.pyf-guide main { padding: 0; max-width: none; flex: none; display: block; }"
            "\n.pyf-guide { overflow-x: hidden; }"
            "\n.pyf-guide *, .pyf-guide *::before, .pyf-guide *::after { box-sizing: border-box; max-width: 100%; }"
            "\n.pyf-guide img { height: auto; }"
            "\n.pyf-guide table { table-layout: auto; width: 100%; }"
            "\n.pyf-guide td, .pyf-guide th { white-space: normal; }\n</style>\n")
with mkdocs_gen_files.open("user_guide.md", "w") as f:
    f.write("# User guide\n\n" + css + '<div class="pyf-guide" markdown="0">\n' + body + "\n</div>\n")
mkdocs_gen_files.set_edit_path("user_guide.md", "docs/pyfigures_user_guide.html")

# ---------------------------------------------------------------------------
# API reference (Google-style docstrings, mkdocstrings)
# ---------------------------------------------------------------------------
API = [
    ("Recipes", "pyfigures.recipe", "Build figures from YAML / JSON recipes."),
    ("Equations", "pyfigures.equations", "LaTeX equations as vector panels."),
    ("Headless rendering", "pyfigures.gui.render_headless", "Render a .pyf without a window."),
]
# (batoolset, the image and drawing library underneath, is a separate
# package and repository: its modules are not documented here)
lines = ["# API reference\n",
         "PyFigures is used through its window, recipes and MCP server. These modules are the",
         "ones scripts call directly.\n"]
for title, module, what in API:
    page = f"api/{module}.md"
    with mkdocs_gen_files.open(page, "w") as f:
        f.write(f"# {title}\n\n::: {module}\n")
    lines.append(f"- [{title}]({module}.md): {what}")
with mkdocs_gen_files.open("api/index.md", "w") as f:
    f.write("\n".join(lines) + "\n")
