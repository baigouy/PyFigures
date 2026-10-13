"""Licence notices and corresponding source for the standalone PyFigures apps.

PyFigures' own code is BSD-2-Clause, but the standalone executables bundle
copyleft code: PyQt6, read-lif and pyqt6-plugins (GPLv3), Qt (LGPLv3),
PyAV's FFmpeg, built with --enable-version3 and x264/x265 (GPLv3 as a whole),
and PyMuPDF with MuPDF (AGPLv3; its PyPI source archive contains MuPDF's).
Each executable is therefore distributed under the GNU GPL version 3, and must
come with (1) the licence texts and notices of everything inside it and (2)
access to the complete corresponding source, offered from the same place as
the executable (GPLv3 section 6(d)).

Used by .github/workflows/build.yml:

  python packaging/collect_licenses.py notices third_party
      third_party/THIRD_PARTY_LICENSES.txt  bundled into the app (Help > About)
      third_party/SOURCES.md                where each component's source is
      third_party/sources.json              manifest for the step below

  python packaging/collect_licenses.py sources OUT_DIR manifest.json [...]
      downloads every source archive the manifests list (deduplicated) and packs
      them into a few .tar files that are attached to the GitHub release, next
      to the executables.

Needs network access (PyPI, gnu.org, GitHub); standard library only.
"""
import importlib.metadata as md
import json
import os
import re
import ssl
import sys
import tarfile
import time
import urllib.request

PYPI_JSON = "https://pypi.org/pypi/{name}/{version}/json"
GNU_TEXTS = {
    "GNU GENERAL PUBLIC LICENSE, Version 3": "https://www.gnu.org/licenses/gpl-3.0.txt",
    # PyMuPDF / MuPDF (PDF files as vector panels)
    "GNU AFFERO GENERAL PUBLIC LICENSE, Version 3": "https://www.gnu.org/licenses/agpl-3.0.txt",
    "GNU LESSER GENERAL PUBLIC LICENSE, Version 3": "https://www.gnu.org/licenses/lgpl-3.0.txt",
    "GNU GENERAL PUBLIC LICENSE, Version 2": "https://www.gnu.org/licenses/old-licenses/gpl-2.0.txt",
    "GNU LESSER GENERAL PUBLIC LICENSE, Version 2.1": "https://www.gnu.org/licenses/old-licenses/lgpl-2.1.txt",
}
# PyQt6-Qt6 is a binary-only wheel of Qt: its source is the Qt release itself
QT_SOURCE = "https://download.qt.io/archive/qt/{mm}/{v}/single/qt-everywhere-src-{v}.tar.xz"
# PyAV's FFmpeg: PyAV names the pyav-ffmpeg release it links against, and
# pyav-ffmpeg's pkg.py names the source archive of every library in it
PYAV_FFMPEG_JSON = "https://raw.githubusercontent.com/PyAV-Org/PyAV/v{av}/scripts/ffmpeg-{mm}.json"
PYAV_FFMPEG_PKG = "https://raw.githubusercontent.com/PyAV-Org/pyav-ffmpeg/{tag}/scripts/pkg.py"
PYAV_FFMPEG_SCRIPTS = "https://github.com/PyAV-Org/pyav-ffmpeg/archive/refs/tags/{tag}.tar.gz"
NATIVE_LICENSES = {
    "ffmpeg": "GPL-3.0-or-later (this build: --enable-version3 with libx264/libx265)",
    "x264": "GPL-2.0-or-later", "x265": "GPL-2.0-or-later",
    "lame": "LGPL-2.0-or-later", "opus": "BSD-3-Clause", "dav1d": "BSD-2-Clause",
    "libsvtav1": "BSD-3-Clause-Clear", "vpx": "BSD-3-Clause", "png": "libpng-2.0",
    "webp": "BSD-3-Clause", "opencore-amr": "Apache-2.0",
    "gmp": "LGPL-3.0-or-later OR GPL-2.0-or-later", "unistring": "LGPL-3.0-or-later",
    "nettle": "LGPL-3.0-or-later", "gnutls": "LGPL-2.1-or-later",
    "alsa-lib": "LGPL-2.1-or-later", "nv-codec-headers": "MIT", "amf-headers": "MIT",
    "libvpl": "MIT", "nasm": "BSD-2-Clause (build tool)",
}
# packages whose metadata does not state their licence
KNOWN_LICENSES = {"read-lif": "GPL v3 (GPL-3.0-or-later)"}
LICENSE_FILE = re.compile(r"(^|/)(licen[cs]e|copying|notice)[^/]*$", re.I)


def _ssl_context():
    """certifi's CA bundle when available (some Windows certificate stores
    cannot be loaded by Python's ssl), else the system default."""
    try:
        import certifi
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return None


def _get(url, tries=3):
    ctx = _ssl_context() if url.startswith("https:") else None
    for i in range(tries):
        try:
            with urllib.request.urlopen(url, timeout=120, context=ctx) as r:
                return r.read()
        except Exception:
            if i == tries - 1:
                raise
            time.sleep(5 * (i + 1))


def _license_of(dist):
    m = dist.metadata
    known = KNOWN_LICENSES.get((m["Name"] or "").lower().replace("_", "-"))
    if known:
        return known
    lic = m.get("License-Expression") or ""
    if not lic:
        raw = (m.get("License") or "").strip()
        if raw and "\n" not in raw and len(raw) < 80:
            lic = raw
    if not lic:
        classes = [c.split("::")[-1].strip() for c in (m.get_all("Classifier") or [])
                   if c.startswith("License ::")]
        lic = ", ".join(classes)
    return lic or "see the licence text below"


def _license_texts(dist):
    out = []
    for f in dist.files or []:
        p = str(f).replace("\\", "/")
        if ".dist-info/" in p and LICENSE_FILE.search(p) and not p.endswith((".py", ".pyc")):
            try:
                with open(f.locate(), encoding="utf-8", errors="replace") as fh:
                    out.append((p.split("/")[-1], fh.read()))
            except OSError:
                pass
    return out


def _installed_from_local(dist):
    try:
        info = json.loads(dist.read_text("direct_url.json") or "null")
    except Exception:
        info = None
    return bool(info) and "url" in info


def _pypi_sdist(name, version):
    try:
        data = json.loads(_get(PYPI_JSON.format(name=name, version=version)))
    except Exception:
        return None
    for u in data.get("urls", []):
        if u.get("packagetype") == "sdist":
            return u["url"]
    return None


def _python_components():
    comps = []
    seen = set()
    for dist in sorted(md.distributions(), key=lambda d: (d.metadata["Name"] or "").lower()):
        name = dist.metadata["Name"]
        if not name or name.lower() in seen:
            continue
        seen.add(name.lower())
        version = dist.version
        if name.lower() == "pyqt6-qt6":
            parts = version.split(".")
            v = ".".join(parts[:3])
            url = QT_SOURCE.format(mm=".".join(parts[:2]), v=v)
            group = "qt"
        elif _installed_from_local(dist):
            url = None                     # built from a repository checkout
            group = "python"
        else:
            url = _pypi_sdist(name, version)
            group = "python"
        comps.append({"name": name, "version": version, "license": _license_of(dist),
                      "source": url, "group": group, "texts": _license_texts(dist)})
    return comps


def _ffmpeg_components():
    try:
        import av
    except Exception:
        return []
    ff = av.ffmpeg_version_info
    mm = ".".join(ff.split(".")[:2])
    cfg = json.loads(_get(PYAV_FFMPEG_JSON.format(av=av.__version__, mm=mm)))
    tag = cfg["url"].split("/releases/download/")[1].split("/")[0]
    if not tag.startswith(ff):
        raise SystemExit(f"PyAV {av.__version__}: FFmpeg {ff} but pyav-ffmpeg tag {tag}")
    pkg = _get(PYAV_FFMPEG_PKG.format(tag=tag)).decode("utf-8")
    comps = [{"name": "pyav-ffmpeg build scripts", "version": tag,
              "license": "BSD-3-Clause (scripts used to build the libraries below)",
              "source": PYAV_FFMPEG_SCRIPTS.format(tag=tag), "group": "ffmpeg", "texts": []}]
    for name, url in re.findall(r'name="([^"]+)",\s*source_url="([^"]+)"', pkg):
        comps.append({"name": name, "version": "", "license": NATIVE_LICENSES.get(name, "see source"),
                      "source": url, "group": "ffmpeg", "texts": []})
    return comps


def _release_page():
    server = os.environ.get("GITHUB_SERVER_URL", "https://github.com")
    repo = os.environ.get("GITHUB_REPOSITORY")
    ref = os.environ.get("GITHUB_REF_NAME")
    if repo and ref:
        return f"{server}/{repo}/releases/tag/{ref}"
    return "the release page this application was downloaded from"


def notices(out_dir):
    os.makedirs(out_dir, exist_ok=True)
    py = _python_components()
    ff = _ffmpeg_components()
    agpl = sorted(c["name"] for c in py if "AFFERO" in c["license"].upper() or "AGPL" in c["license"].upper())
    gpl = sorted(c["name"] for c in py if "GPL" in c["license"] and "LGPL" not in c["license"]
                 and c["name"] not in agpl)
    release = _release_page()
    head = [
        "PyFigures standalone application - licence information",
        "=" * 60,
        "",
        "PyFigures' own source code is licensed under the BSD 2-Clause licence",
        "(https://github.com/baigouy/pyfigures).",
        "",
        "This application bundle also contains third-party software. Because it",
        "includes components licensed under the GNU General Public License",
        f"version 3 ({', '.join(gpl) or 'PyQt6'}" + (", and FFmpeg built with x264/x265)" if ff else ")"),
        "the application AS A WHOLE is distributed under the terms of the GNU",
        "General Public License version 3 (full text below). Qt is used under the",
        "GNU LGPL version 3 and is dynamically linked: you may replace the Qt",
        "libraries inside this bundle with your own (modified) build.",
        "",
    ] + ([
        f"{', '.join(agpl)} (PDF files as vector panels, with the MuPDF library) is",
        "licensed under the GNU Affero General Public License version 3 (full text",
        "below), which section 13 of the GPL v3 allows to be combined with it; those",
        "components keep the AGPL terms.",
        "",
    ] if agpl else []) + [
        "THERE IS NO WARRANTY FOR THE PROGRAM, TO THE EXTENT PERMITTED BY",
        "APPLICABLE LAW (see sections 15-16 of the GPL below).",
        "",
        "Complete corresponding source code of every component (source archives,",
        "including the scripts used to build FFmpeg and its libraries) is",
        f"available, at no charge, from the same place as this application: {release}",
        "See also SOURCES.md next to this file.",
        "",
        "Qt's own third-party components (FreeType, HarfBuzz, libpng, zlib, PCRE2,",
        "...) are listed with their licences in the Qt source archive",
        "(qt_attribution.json files).",
        "",
    ]
    body = []
    for c in py:
        body += ["", "-" * 72, f"{c['name']} {c['version']}  -  {c['license']}", "-" * 72]
        for fname, text in c["texts"]:
            body += [f"[{fname}]", text.rstrip(), ""]
    if ff:
        body += ["", "=" * 72, "FFmpeg and the libraries linked into it (inside PyAV, the 'av' package)",
                 "=" * 72]
        for c in ff:
            body.append(f"{c['name']} {c['version']}".strip() + f"  -  {c['license']}  -  {c['source']}")
    texts = []
    for title, url in GNU_TEXTS.items():
        texts += ["", "=" * 72, title, "=" * 72, _get(url).decode("utf-8")]
    with open(os.path.join(out_dir, "THIRD_PARTY_LICENSES.txt"), "w", encoding="utf-8") as f:
        f.write("\n".join(head + body + texts) + "\n")

    rows = ["# Corresponding source of the PyFigures standalone application", "",
            f"Every archive below is attached to the release: {release}", "",
            "| Component | Version | Licence | Original source |", "|---|---|---|---|"]
    for c in py + ff:
        src = c["source"] or "this repository / its GitHub repository at the release tag"
        rows.append(f"| {c['name']} | {c['version']} | {c['license'].replace('|', '/')} | {src} |")
    with open(os.path.join(out_dir, "SOURCES.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(rows) + "\n")
    manifest = [{k: c[k] for k in ("name", "version", "license", "source", "group")} for c in py + ff]
    with open(os.path.join(out_dir, "sources.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=1)
    missing = [c["name"] for c in py if not c["source"]]
    print(f"{len(py)} Python packages, {len(ff)} FFmpeg components; GPL: {gpl}; AGPL: {agpl}")
    if missing:
        print("no source archive found (must come from their repositories):", ", ".join(missing))


def sources(out_dir, manifests):
    os.makedirs(out_dir, exist_ok=True)
    work = os.path.join(out_dir, "_download")
    os.makedirs(work, exist_ok=True)
    by_group = {}
    seen = set()
    for m in manifests:
        with open(m, encoding="utf-8") as f:
            for c in json.load(f):
                if c["source"] and c["source"] not in seen:
                    seen.add(c["source"])
                    by_group.setdefault(c["group"], []).append(c)
    failed = []
    for group, comps in sorted(by_group.items()):
        tar_path = os.path.join(out_dir, f"corresponding-source-{group}.tar")
        with tarfile.open(tar_path, "w") as tar:
            for c in comps:
                fname = re.sub(r"[^A-Za-z0-9._+-]", "_", c["source"].rstrip("/").split("/")[-1])
                if group == "ffmpeg" and c["name"] == "pyav-ffmpeg build scripts":
                    fname = f"pyav-ffmpeg-{c['version']}.tar.gz"
                path = os.path.join(work, fname)
                try:
                    data = _get(c["source"])
                except Exception as e:
                    failed.append(f"{c['name']}: {c['source']} ({e})")
                    continue
                with open(path, "wb") as f:
                    f.write(data)
                tar.add(path, arcname=f"{group}/{fname}")
                os.remove(path)
        print(tar_path, os.path.getsize(tar_path) // 1_000_000, "MB")
    os.rmdir(work)
    if failed:
        print("FAILED downloads:\n  " + "\n  ".join(failed))
        sys.exit(1)


if __name__ == "__main__":
    if len(sys.argv) >= 3 and sys.argv[1] == "notices":
        notices(sys.argv[2])
    elif len(sys.argv) >= 4 and sys.argv[1] == "sources":
        sources(sys.argv[2], sys.argv[3:])
    else:
        print(__doc__)
        sys.exit(2)
