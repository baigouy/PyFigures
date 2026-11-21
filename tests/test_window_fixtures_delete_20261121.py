"""Every function-scoped test fixture that makes a main window and closes it in teardown
also deletes it (deleteLater). A closed window is only hidden: hundreds of them ran the
Windows CI out of handles, an access violation in initUI (v0.2.9 on 2026-11-12, and again
v0.2.22 on 2026-11-21 because 15 per-file fixtures still only closed). User, 2026-11-21:
"we already had and fixed these errors ... memorize this one for good"."""
import pathlib
import re

HERE = pathlib.Path(__file__).parent
# its tutorial objects outlive the window: deleted with them at the end of the test instead
ALLOWED = {"test_tutorial_controller.py"}


def _fixtures_that_only_close(path):
    lines = path.read_text(encoding="utf-8").splitlines()
    found = []
    i = 0
    while i < len(lines):
        if re.fullmatch(r"@pytest\.fixture\s*(\(\s*\))?", lines[i].strip()) and i + 1 < len(lines) \
                and lines[i + 1].lstrip().startswith("def "):
            k, var, yielded, closed, deleted = i + 2, None, False, None, False
            while k < len(lines) and (not lines[k].strip() or lines[k].startswith((" ", "\t"))):
                s = lines[k]
                made = re.search(r"(\w+)\s*=\s*(?:EZFIG_GUI|PartnerGUI)\(\)", s)
                if made:
                    var = made.group(1)
                yielded = yielded or s.strip().startswith("yield")
                if var and yielded and re.fullmatch(rf"\s+{var}\.close\(\)\s*", s):
                    closed = k + 1
                deleted = deleted or "deleteLater" in s
                k += 1
            if closed and not deleted:
                found.append(f"{path.name}:{closed}")
            i = k
            continue
        i += 1
    return found


def test_window_fixtures_delete_the_window_they_close():
    bad = [hit for p in sorted(HERE.glob("test_*.py")) if p.name not in ALLOWED
           for hit in _fixtures_that_only_close(p)]
    assert not bad, ("these fixtures close a main window without deleting it; add "
                     "`<window>.deleteLater()` after the close (see test_assistant_live.py's gui): " + ", ".join(bad))
