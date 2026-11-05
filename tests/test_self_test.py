"""`PyFigures --self-test report.json` (run by the CI on each built app).

Run with PYTEST_QT_API=pyqt6.
"""
import json
import os
import subprocess
import sys

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
os.environ.setdefault("QT_API", "pyqt6")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _child_env(**extra):
    # subprocesses must run this checkout's pyfigures, not an installed copy
    # (a relative PYTHONPATH breaks once an earlier test changed directory)
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen", QT_API="pyqt6", **extra)
    env["PYTHONPATH"] = os.pathsep.join([ROOT] + [p for p in env.get("PYTHONPATH", "").split(os.pathsep) if p])
    return env


def test_self_test_passes_without_pymupdf(qapp, tmp_path, monkeypatch):
    pytest.importorskip("pypdfium2")
    pytest.importorskip("av")
    pytest.importorskip("zarr")
    from pyfigures import self_test
    monkeypatch.setitem(sys.modules, "fitz", None)          # as in the apps
    out = tmp_path / "r.json"
    status = self_test.run(str(out))
    report = json.loads(out.read_text(encoding="utf-8"))
    assert status == 0, report
    assert report["ok"] and set(report["checks"]) == {"qt_svg", "pdf_panels", "video", "zarr", "chat"}
    assert "pypdfium2" in report["checks"]["pdf_panels"]


def test_self_test_fails_if_pymupdf_is_bundled(qapp, tmp_path, monkeypatch):
    pytest.importorskip("fitz")
    from pyfigures import self_test
    monkeypatch.setattr(sys, "frozen", True, raising=False)   # a standalone app
    out = tmp_path / "r.json"
    assert self_test.run(str(out)) == 1
    report = json.loads(out.read_text(encoding="utf-8"))
    assert "PyMuPDF (AGPL) is bundled" in report["checks"]["pdf_panels"]


def test_pymupdf_is_fine_in_a_pip_install(qapp, tmp_path, monkeypatch):
    # pip install pyfigures[all] brings PyMuPDF on purpose: no false failure
    pytest.importorskip("fitz")
    pytest.importorskip("pypdfium2")
    from pyfigures import self_test
    monkeypatch.delattr(sys, "frozen", raising=False)
    assert self_test._check_pdf_panels(str(tmp_path)) == "ok (PyMuPDF vector panels)"


def test_no_key_store_fails_only_the_apps(tmp_path, monkeypatch):
    # headless Linux (CI, servers) has no key store: fine for a pip install,
    # a build error for the apps (which must bundle the OS backends)
    pytest.importorskip("qtpy_ai_sidecar")
    import keyring
    from keyring.backends import fail
    from pyfigures import self_test
    monkeypatch.setattr(keyring, "get_keyring", lambda: fail.Keyring())
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    with pytest.raises(AssertionError, match="no key store"):
        self_test._check_chat(str(tmp_path))
    monkeypatch.delattr(sys, "frozen")
    assert self_test._check_chat(str(tmp_path)).startswith("ok (qtpy-ai-sidecar")


def test_linux_apps_need_the_secret_service_backend_not_a_running_store(tmp_path, monkeypatch):
    # the Linux build machine is headless: the key store check is that the
    # backend is bundled; on a desktop it then finds GNOME Keyring / KWallet
    pytest.importorskip("qtpy_ai_sidecar")
    import keyring
    from keyring.backends import fail
    from pyfigures import self_test
    monkeypatch.setattr(keyring, "get_keyring", lambda: fail.Keyring())
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "platform", "linux")
    real_import = __import__

    def no_secretstorage(name, *args, **kwargs):
        if name == "secretstorage":
            raise ImportError("not bundled")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", no_secretstorage)
    with pytest.raises(ImportError, match="not bundled"):
        self_test._check_chat(str(tmp_path))


def test_linux_packages():
    with open(os.path.join(ROOT, ".github", "workflows", "build.yml"), encoding="utf-8") as f:
        wf = f.read()
    assert "os: ubuntu-22.04" in wf and "PyFigures-Linux-x86_64.*" in wf
    assert "appimagetool/releases/download/1.9.1/" in wf                # pinned, not "continuous"
    assert "bash packaging/make_linux_packages.sh dist ./appimagetool" in wf
    assert "PyFigures-Linux-x86_64.AppImage --self-test" in wf          # the AppImage itself is tested
    with open(os.path.join(ROOT, "packaging", "make_linux_packages.sh"), encoding="utf-8") as f:
        script = f.read()
    with open(os.path.join(ROOT, "packaging", "linux", "AppRun"), encoding="utf-8") as f:
        apprun = f.read()
    assert '"$APPDIR/usr/lib/PyFigures"' in script and '"$HERE/usr/lib/PyFigures/PyFigures"' in apprun
    for text in (script, apprun):
        assert "\r" not in text                                         # LF only: run by sh/bash
    with open(os.path.join(ROOT, "packaging", "linux", "pyfigures.desktop"), encoding="utf-8") as f:
        desktop = f.read()
    assert "Icon=pyfigures\n" in desktop and os.path.isfile(os.path.join(ROOT, "pyfigures", "icons", "pyfigures.png"))
    assert "Exec=PyFigures --album" in desktop and "Exec=PyFigures --poster" in desktop
    with open(os.path.join(ROOT, "pyfigures.spec"), encoding="utf-8") as f:
        spec = f.read()
    assert "collect_submodules('secretstorage')" in spec and "collect_submodules('jeepney')" in spec


def test_command_line_flag(tmp_path):
    out = tmp_path / "r.json"
    p = subprocess.run([sys.executable, "-m", "pyfigures", "--self-test", str(out)],
                       env=_child_env(), cwd=ROOT, capture_output=True, text=True, timeout=300)
    report = json.loads(out.read_text(encoding="utf-8"))
    assert p.returncode == (0 if report["ok"] else 1), (p.returncode, report, p.stderr[-3000:])
    assert set(report["checks"]) == {"qt_svg", "pdf_panels", "video", "zarr", "chat"}, report


def test_live_mcp_flag_serves_the_tools(tmp_path):
    # `PyFigures --live-mcp` is how the apps start the chat's MCP server
    # (sys.executable -m … would open a second PyFigures window there)
    pytest.importorskip("mcp")
    import anyio
    from mcp import ClientSession, StdioServerParameters
    from mcp.client.stdio import stdio_client
    env = _child_env(PYFIGURES_MCP_SURFACE="categories", PYFIGURES_LIVE_RUNTIME=str(tmp_path))

    async def tools():
        params = StdioServerParameters(command=sys.executable, args=["-m", "pyfigures", "--live-mcp"],
                                       env=env, cwd=ROOT)
        with anyio.fail_after(240):
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    return [t.name for t in (await session.list_tools()).tools]

    names = anyio.run(tools)
    assert len(names) >= 5, names


def test_frozen_apps_start_the_mcp_server_with_the_flag(tmp_path, monkeypatch):
    from pyfigures.assistant import launch
    exe = tmp_path / "PyFigures.exe"
    exe.write_bytes(b"")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(exe))
    monkeypatch.setattr(sys, "platform", "darwin")
    assert launch.mcp_server_command() == (str(exe), ["--live-mcp"])
    monkeypatch.setattr(sys, "platform", "win32")
    assert launch.mcp_server_command() == (str(exe), ["--live-mcp"])    # no twin yet
    twin = tmp_path / "PyFigures MCP.exe"                               # console twin (stdio)
    twin.write_bytes(b"")
    assert launch.mcp_server_command() == (str(twin), ["--live-mcp"])
    assert launch.mcp_server_entry()["args"] == ["--live-mcp"]
    monkeypatch.delattr(sys, "frozen")
    command, args = launch.mcp_server_command()
    assert args == ["-m", "pyfigures.assistant.live_mcp"]


def test_the_spec_bundles_the_chat_sidebar():
    root = ROOT
    with open(os.path.join(root, "pyfigures.spec"), encoding="utf-8") as f:
        spec = f.read()
    for needed in ("collect_submodules('qtpy_ai_sidecar')", "collect_data_files('qtpy_ai_sidecar')",
                   "collect_submodules('keyring')", "collect_submodules('mcp', filter=",
                   "not name.startswith('mcp.cli')",          # mcp.cli exits without typer
                   "name='PyFigures MCP'", "console=True"):
        assert needed in spec, needed
    assert "'0.1.11'" not in spec            # the macOS version comes from version.py
    with open(os.path.join(root, "setup.py"), encoding="utf-8") as f:
        setup = f.read()
    core = setup[setup.index("install_requires"):setup.index("extras_require")]
    assert '"qtpy-ai-sidecar' in core and '"mcp' in core            # installed by default
