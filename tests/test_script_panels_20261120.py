"""User, 2026-11-20: "is the model able to guide an LLM to design a script that could be used
within pyfigures, e.g. tell what the script should return and the type ... something not
supported such as some phylogenetic tree". The contract is in pyfigures.script_panels (and
docs/SCRIPT_PANELS.md); a script is checked as PyFigures runs it; a function the script
defines (a recursive tree drawer) now sees its imports and itself."""
import json
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# a tree drawn by a recursive function using the script's own import: the kind of script
# an LLM writes for a plot PyFigures has no tool for
TREE = '''
import math
tree = ("root", [("A", []), ("n1", [("B", []), ("C", [])])])

def leaves(node):
    name, kids = node
    return 1 if not kids else sum(leaves(k) for k in kids)

def draw(ax, node, x, y0):
    name, kids = node
    if not kids:
        ax.text(x + 0.05, y0 + 0.5, name, va="center")
        return y0 + 0.5
    ys, y = [], y0
    for k in kids:
        ys.append(draw(ax, k, x + 1, y))
        y += leaves(k)
    ax.plot([x, x], [min(ys), max(ys)], "k-")
    for yy in ys:
        ax.plot([x, x + 1], [yy, yy], "k-")
    return float(np.mean(ys)) + 0 * math.pi

fig, ax = plt.subplots(figsize=(3, 2))
draw(ax, tree, 0, 0)
ax.axis("off")
self.img = fig
'''


def test_a_script_with_its_own_recursive_function_draws():
    from pyfigures.script_panels import check_script
    report = check_script(TREE)
    assert report["ok"], report
    assert report["kind"] == "figure" and report["size"] == "3.00 x 2.00 in"


def test_a_broken_script_says_why():
    from pyfigures.script_panels import check_script
    r = check_script("fig, ax = plt.subplots()\nax.plot(undefined_name)\nself.img = fig")
    assert not r["ok"] and "undefined_name" in (r["error"] + r["log"])
    r = check_script("x = 1")
    assert not r["ok"] and "self.img" in r["error"]
    r = check_script("def (:")
    assert not r["ok"] and "syntax" in r["error"]
    r = check_script("self.img = np.zeros((20, 30, 3), np.uint8)")
    assert r["ok"] and r["kind"] == "image" and r["size"] == "30 x 20 px"


def test_add_scripted_image_refuses_a_script_that_fails(tmp_path):
    from pyfigures.mcp_server import create_figure, add_scripted_image
    pyf = str(tmp_path / "f.pyf")
    create_figure(pyf)
    out = add_scripted_image(pyf, [], "fig, ax = plt.subplots()\nax.plot(nope)\nself.img = fig")
    assert out.startswith("ERROR") and "nope" in out and "Nothing was added" in out
    out = add_scripted_image(pyf, [], TREE, label="A")
    assert not out.startswith("ERROR"), out


def test_the_command_line_check(tmp_path, capsys):
    from pyfigures.script_panels import main
    p = tmp_path / "tree.py"
    p.write_text(TREE, encoding="utf-8")
    assert main([str(p)]) == 0 and "OK: the panel is figure" in capsys.readouterr().out
    p.write_text("x = 1", encoding="utf-8")
    assert main([str(p)]) == 1 and "self.img" in capsys.readouterr().out
    assert json  # noqa
