"""User 2026-11-23: while Hermes Agent edited the figure through the live MCP server, the chat
panel kept saying "Mistral". A live request now says whether it comes from the chat panel's own
server (run with the sidecar's vision setting) or from another AI app; the session keeps the
time of the last outside one for the panel."""
import io
import json

from pyfigures.assistant import live_mcp


def _capture(monkeypatch, tmp_path):
    (tmp_path / 'connection.json').write_text(json.dumps({'url': 'http://127.0.0.1:9/', 'token': 't'}))
    monkeypatch.setattr(live_mcp, 'descriptor_path', lambda: tmp_path / 'connection.json')
    sent = []

    class Reply(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def urlopen(req, timeout=None):
        sent.append(json.loads(req.data))
        return Reply(json.dumps({'result': {'ok': True}}).encode())
    monkeypatch.setattr(live_mcp.urllib.request, 'urlopen', urlopen)
    return sent


def test_an_outside_app_is_marked_external(monkeypatch, tmp_path):
    sent = _capture(monkeypatch, tmp_path)
    monkeypatch.delenv('QTPY_AI_SIDECAR_VISION', raising=False)
    live_mcp.request('inspect')
    assert sent[-1]['origin'] == 'external'
    monkeypatch.setenv('QTPY_AI_SIDECAR_VISION', 'images')        # the chat panel's own server
    live_mcp.request('inspect')
    assert sent[-1]['origin'] == 'chat'
