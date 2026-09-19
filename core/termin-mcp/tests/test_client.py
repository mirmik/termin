import io
import json
import urllib.error

import pytest

from termin.mcp import client


def test_session_loading_rejects_missing_credentials(tmp_path):
    path = tmp_path / "session.json"
    path.write_text(json.dumps({"url": "http://localhost/mcp"}))
    with pytest.raises(client.McpClientError, match="missing bearer token"):
        client.load_session(path)
    path.write_text(json.dumps({"url": "http://localhost/mcp", "token": "secret"}))
    assert client.load_session(path)["session_file"] == str(path)


def test_call_sends_authenticated_json_rpc(monkeypatch):
    class Response(io.BytesIO):
        status = 200

    requests = []

    def urlopen(request, timeout):
        requests.append((request, timeout))
        return Response(b'{"jsonrpc":"2.0","id":1,"result":{}}')

    monkeypatch.setattr(client.urllib.request, "urlopen", urlopen)
    response = client.call({"url": "http://localhost/mcp", "token": "secret"}, "ping")
    request, timeout = requests[0]
    assert request.get_method() == "POST"
    assert request.get_header("Authorization") == "Bearer secret"
    assert json.loads(request.data) == {"jsonrpc": "2.0", "id": 1, "method": "ping"}
    assert timeout == 35
    assert response["result"] == {}


def test_http_error_does_not_expose_response_credentials(monkeypatch):
    def urlopen(request, timeout):
        raise urllib.error.HTTPError(
            request.full_url, 403, "Forbidden", {}, io.BytesIO(b"Bearer secret")
        )

    monkeypatch.setattr(client.urllib.request, "urlopen", urlopen)
    with pytest.raises(client.McpClientError, match="HTTP 403") as error:
        client.call({"url": "http://localhost/mcp", "token": "secret"}, "ping")
    assert "secret" not in str(error.value)


def test_empty_response_is_not_a_call_result(monkeypatch):
    monkeypatch.setattr(client, "post_rpc", lambda session, payload: None)
    with pytest.raises(client.McpClientError, match="no JSON-RPC response"):
        client.call({}, "ping")
