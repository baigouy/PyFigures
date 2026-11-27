"""Fiji starts in the background at every launch (user 2026-11-23: keep it). A cached Fiji
downloads nothing, but its start still printed ~6000 debug lines (jgo / scyjava / imagej,
each twice through the app's log handler) while the user dropped images: the window lagged.
The debug log now goes to the console only for a real download. No JVM is started here."""
import logging
import sys
import types

import pytest

R = pytest.importorskip("batoolset.IJ.ij_reader", exc_type=ImportError)
# the real start-up (conftest swaps it for one that refuses); imagej.init is faked below
_REAL_INIT = R._init_ij_unlocked


@pytest.fixture
def fake_init(monkeypatch):
    seen = {}

    def init(*a, **k):
        lg = logging.getLogger("jgo")
        seen["level"] = lg.level
        seen["handlers"] = list(lg.handlers)
        lg.debug("Resolving RELEASE for sc.fiji:fiji")
        return "gateway"
    monkeypatch.setitem(sys.modules, "imagej", types.SimpleNamespace(init=init))
    for name in ("_cleanup_duplicate_jgo_fiji_envs", "_use_conda_java", "silence_java_logging",
                 "_remove_incomplete_fiji_envs"):
        monkeypatch.setattr(R, name, lambda: None)
    monkeypatch.setattr(R, "_on_fiji_init_callback", None)
    return seen


def test_a_cached_fiji_starts_without_its_debug_log(fake_init, monkeypatch, capsys):
    monkeypatch.setattr(R, "_is_fiji_cached", lambda: True)
    before = list(logging.getLogger("jgo").handlers)
    assert _REAL_INIT() == "gateway"
    assert fake_init["handlers"] == before and fake_init["level"] != logging.DEBUG
    assert "Resolving RELEASE" not in capsys.readouterr().out


def test_a_download_still_shows_its_progress(fake_init, monkeypatch, capsys):
    monkeypatch.setattr(R, "_is_fiji_cached", lambda: False)
    monkeypatch.setattr(R, "_progress_sink", None)
    before = list(logging.getLogger("jgo").handlers)
    _REAL_INIT()
    assert fake_init["level"] == logging.DEBUG
    out = capsys.readouterr().out
    assert "First Fiji start" in out
    assert "Resolving RELEASE" not in out          # bookkeeping, not progress
    assert logging.getLogger("jgo").handlers == before   # detached afterwards


# what a real first run logs (C:\pyf_fresh_test, 2026-11-27): ~10 000 debug lines, of
# which only the Java fetch, the Fiji version and one line per downloaded file mean progress
_FIRST_RUN = [
    ("scyjava._jdk_fetch", logging.DEBUG, "Fetching zulu-jre:11..."),
    ("jgo.util.java", logging.DEBUG, "Using Java 11.0.33 (zulu-jre) via cjdk at C:\\x\\bin\\java.exe"),
    ("jgo.maven._core", logging.DEBUG, "Resolving RELEASE for sc.fiji:fiji"),
    ("jgo.maven._core", logging.DEBUG, "Resolved RELEASE -> '2.18.0' for sc.fiji:fiji"),
    ("jgo.maven._model", logging.DEBUG, "sc.fiji:fiji:2.18.0: dependency management injection"),
    ("jgo.maven._resolver", logging.DEBUG, "Trying https://repo.maven.apache.org/maven2/a.pom"),
    ("jgo.maven._resolver", logging.DEBUG, "Downloaded sc.fiji:fiji:pom:2.18.0 to C:\\m2\\fiji.pom"),
    ("jgo.maven._resolver", logging.DEBUG, "Downloaded net.imagej:ij:jar:1.54p to C:\\m2\\ij.jar"),
    ("jgo.maven._resolver", logging.WARNING, "Could not reach a mirror"),
]


def _replay(handler):
    for name, level, msg in _FIRST_RUN:
        handler.handle(logging.LogRecord(name, level, __file__, 1, msg, None, None))


def test_the_progress_keeps_milestones_and_counts_files():
    seen = []
    h = R._FijiProgress(lambda text, transient: seen.append((text, transient)))
    _replay(h)
    lasting = [t for t, transient in seen if not transient]
    assert lasting == [
        "Checking Java (zulu-jre:11 needed; downloaded once if missing)...",
        "Java ready: Java 11.0.33 (zulu-jre)",
        "Downloading Fiji 2.18.0 and its components (first run only)...",
        "jgo: Could not reach a mirror",
    ]
    counts = [t for t, transient in seen if transient]
    assert counts == ["Fiji: 1 files downloaded (sc.fiji:fiji:pom:2.18.0)",
                      "Fiji: 2 files downloaded (net.imagej:ij:jar:1.54p)"]
    assert not any("Trying" in t or "dependency management" in t for t, _ in seen)


def test_a_log_file_gets_one_count_line_every_25_files(monkeypatch, capsys):
    monkeypatch.setattr(sys.stdout, "isatty", lambda: False, raising=False)
    h = R._FijiProgress()
    for i in range(60):
        h.handle(logging.LogRecord("jgo.maven._resolver", logging.DEBUG, __file__, 1,
                                   f"Downloaded g:a{i}:jar:1 to x", None, None))
    lines = capsys.readouterr().out.splitlines()
    assert [ln.split(" (")[0] for ln in lines] == [
        f"Downloading Fiji {R._FIJI_VERSION} and its components",   # (pinned version)
        "Fiji: 25 files downloaded", "Fiji: 50 files downloaded"]


def test_a_broken_sink_never_stops_the_fiji_start():
    def sink(text, transient):
        raise RuntimeError("dialog gone")
    _replay(R._FijiProgress(sink))   # no exception


# ---- a first download that dies half-way (fresh install 2026-11-27) ----

def _env(home, name, complete):
    d = home / ".jgo" / "envs" / "sc" / "fiji" / "fiji" / name
    (d / "jars").mkdir(parents=True)
    (d / "jars" / "ij-1.54p.jar").write_bytes(b"x")
    if complete:
        (d / "jgo.lock.toml").write_text("[environment]\n")
    return d


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    # the jgo cache comes from scyjava (Path.home() read at import): never the real one
    monkeypatch.setattr(R.sj.config, "get_cache_dir", lambda: tmp_path / ".jgo")
    return tmp_path


def _started(env, monkeypatch):
    # what a successful start leaves: the JVM class path holds the env's jars
    monkeypatch.setattr(R.jpype, "getClassPath", lambda: str(env / "modules" / "*"))
    R._record_fiji_env()


def test_half_a_download_is_not_a_downloaded_fiji(home, monkeypatch):
    assert not R._is_fiji_cached()
    half = _env(home, "aaa", complete=False)   # jars but no lock file: jgo died mid-way
    _started(half, monkeypatch)
    assert not R._is_fiji_cached()
    done = _env(home, "bbb", complete=True)
    _started(done, monkeypatch)
    assert R._is_fiji_cached()


def test_an_older_unpinned_fiji_is_not_the_pinned_one(home, monkeypatch):
    # a user upgrading: a finished env from the unpinned "sc.fiji:fiji" and no marker
    # -> the pinned env is built with its progress shown, not silently
    _env(home, "unpinned", complete=True)
    assert not R._is_fiji_cached()
    old = _env(home, "other", complete=True)
    _started(old, monkeypatch)
    import json
    marker = R._fiji_marker_path()
    info = json.load(open(marker, encoding="utf-8"))
    json.dump(dict(info, endpoint="sc.fiji:fiji:2.17.0"), open(marker, "w", encoding="utf-8"))
    assert not R._is_fiji_cached()             # recorded for another Fiji version


def test_the_unfinished_env_is_removed_and_the_finished_one_kept(home):
    half = _env(home, "aaa", complete=False)
    done = _env(home, "bbb", complete=True)
    R._remove_incomplete_fiji_envs()
    assert not half.exists() and done.exists()


def _requests_timeout():
    try:
        try:
            raise TimeoutError("_ssl.c:1001: The handshake operation timed out")
        except TimeoutError as e:
            raise OSError("Read timed out. (read timeout=10)") from e
    except OSError as e:
        return e


def test_network_errors_are_told_from_other_errors():
    assert R._is_network_error(_requests_timeout())
    assert R._is_network_error(ConnectionResetError())
    assert not R._is_network_error(ValueError("bad pom"))
    assert not R._is_network_error(RuntimeError("Fiji init previously failed"))


def test_a_network_error_is_retried_and_resumes(fake_init, monkeypatch, capsys):
    calls = []

    def init(*a, **k):
        calls.append(1)
        if len(calls) == 1:
            raise _requests_timeout()
        return "gateway"
    monkeypatch.setitem(sys.modules, "imagej", types.SimpleNamespace(init=init))
    monkeypatch.setattr(R, "_is_fiji_cached", lambda: False)
    monkeypatch.setattr(R, "_progress_sink", None)
    monkeypatch.setattr(R, "_NETWORK_RETRY_WAIT", 0)
    monkeypatch.setattr(R, "_jvm_started", lambda: False)
    assert _REAL_INIT() == "gateway" and len(calls) == 2
    assert f"trying again (2/{R._NETWORK_TRIES})" in capsys.readouterr().out


def test_fiji_is_pinned_to_a_tested_version():
    # "sc.fiji:fiji" alone = the latest Fiji: a new Fiji release would change what new
    # users download without any test (first official release, user 2026-11-27)
    assert R._FIJI_ENDPOINT == "sc.fiji:fiji:" + R._FIJI_VERSION
    assert R._FIJI_VERSION.count(".") == 2 and R._FIJI_JAVA >= 21


def test_two_finished_fiji_envs_are_both_kept(home):
    # the pinned Fiji next to an older unpinned one: deleting "the smaller" made the
    # pinned env be rebuilt at every start
    a = _env(home, "unpinned", complete=True)
    b = _env(home, "pinned", complete=True)
    half = _env(home, "broken", complete=False)
    R._cleanup_duplicate_jgo_fiji_envs()
    assert a.exists() and b.exists() and not half.exists()


def test_retries_stop_after_three_and_other_errors_are_not_retried(fake_init, monkeypatch):
    calls = []

    def init(*a, **k):
        calls.append(1)
        raise _requests_timeout()
    monkeypatch.setitem(sys.modules, "imagej", types.SimpleNamespace(init=init))
    monkeypatch.setattr(R, "_is_fiji_cached", lambda: False)
    monkeypatch.setattr(R, "_NETWORK_RETRY_WAIT", 0)
    monkeypatch.setattr(R, "_jvm_started", lambda: False)
    with pytest.raises(OSError):
        _REAL_INIT()
    assert len(calls) == R._NETWORK_TRIES

    calls.clear()

    def bad(*a, **k):
        calls.append(1)
        raise ValueError("bad pom")
    monkeypatch.setitem(sys.modules, "imagej", types.SimpleNamespace(init=bad))
    with pytest.raises(ValueError):
        _REAL_INIT()
    assert len(calls) == 1


def test_the_macos_java_stub_is_not_a_java(monkeypatch):
    # /usr/bin/java exists on every Mac, Java installed or not
    import shutil
    import subprocess
    monkeypatch.setattr(R.sys, "platform", "darwin")
    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/java")
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(
        a, 1, "", "Unable to locate a Java Runtime."))
    assert R._system_java_home() is None


def test_a_real_macos_java_is_found_through_java_home(monkeypatch, tmp_path):
    import shutil
    import subprocess
    jdk = tmp_path / "zulu-21.jdk" / "Contents" / "Home"
    (jdk / "bin").mkdir(parents=True)
    (jdk / "bin" / "java").write_text("")
    monkeypatch.setattr(R.sys, "platform", "darwin")
    monkeypatch.setattr(shutil, "which", lambda name: "/usr/bin/java")
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: subprocess.CompletedProcess(
        a, 0, str(jdk) + "\n", ""))
    assert R._system_java_home() == str(jdk)


def test_an_old_or_unreadable_system_java_gets_java_21_downloaded(monkeypatch, tmp_path):
    seen = {}
    monkeypatch.setattr(R.sj.config, "set_java_constraints",
                        lambda **k: seen.update(k))
    monkeypatch.setattr(R, "_system_java_home", lambda: str(tmp_path))
    monkeypatch.setattr(R.sys, "prefix", str(tmp_path / "no_conda_java"))
    monkeypatch.delenv("JAVA_HOME", raising=False)
    for major in (8, 11, None):
        seen.clear()
        monkeypatch.setattr(R, "_java_major", lambda exe, m=major: m)
        R._use_conda_java()
        assert seen == {"fetch": "always", "version": str(R._FIJI_JAVA)}
        assert R.os.environ.get("JAVA_HOME") != str(tmp_path)   # the old one is not used


def test_java_versions_are_read_old_and_new_style():
    import subprocess

    def fake_run(out):
        return lambda *a, **k: subprocess.CompletedProcess(a, 0, "", out)
    for text, major in (('java version "1.8.0_402"', 8),
                        ('openjdk version "11.0.33" 2026-10-20', 11),
                        ('openjdk version "21.0.6" 2025-01-21', 21)):
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr(subprocess, "run", fake_run(text))
            assert R._java_major("java") == major
