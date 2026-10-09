"""The built frontend served by the API server, and security headers."""

import pytest
from fastapi.testclient import TestClient

from core.config import Settings
from core.context import RunContext
from server.app import create_app, default_manager
from server.runs import RunManager
from server.store import Store
from fakes import FakeLLM, happy_script


@pytest.fixture
def dist(tmp_path):
    root = tmp_path / "dist"
    (root / "assets").mkdir(parents=True)
    (root / "index.html").write_text("<!doctype html><title>AI SDR</title>", encoding="utf-8")
    (root / "theme.js").write_text("// theme", encoding="utf-8")
    (root / "assets" / "index-abc123.js").write_text("// app", encoding="utf-8")
    return root


@pytest.fixture
def client(tmp_path, dist, search):
    def make_manager() -> RunManager:
        def make_context(brief, cancel) -> RunContext:
            return RunContext(settings=Settings(), llm=FakeLLM(happy_script()), search_client=search, cancel=cancel)

        return RunManager(Store(tmp_path / "sdr.sqlite3"), make_context)

    with TestClient(create_app(make_manager, static_dir=str(dist))) as client:
        yield client


def test_index_is_served_at_root_and_revalidated(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "AI SDR" in response.text
    assert response.headers["cache-control"] == "no-cache"


def test_hashed_assets_are_cached_for_good(client):
    response = client.get("/assets/index-abc123.js")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "public, max-age=31536000, immutable"
    assert client.get("/theme.js").headers["cache-control"] == "no-cache"


def test_api_routes_win_over_the_frontend(client):
    assert client.get("/api/health").json() == {"status": "ok"}
    unknown = client.get("/api/nope")
    assert unknown.status_code == 404
    assert "AI SDR" not in unknown.text


def test_every_response_carries_security_headers(client):
    for path in ("/", "/api/health", "/api/nope"):
        headers = client.get(path).headers
        assert "script-src 'self'" in headers["content-security-policy"]
        assert "frame-ancestors 'none'" in headers["content-security-policy"]
        assert headers["x-content-type-options"] == "nosniff"
        assert "strict-transport-security" not in headers  # plain HTTP


def test_hsts_only_over_https(dist, tmp_path):
    app = create_app(lambda: RunManager(Store(tmp_path / "s.sqlite3"), lambda b, c: None), static_dir=str(dist))
    with TestClient(app, base_url="https://testserver") as client:
        assert client.get("/").headers["strict-transport-security"] == "max-age=31536000"


def test_without_static_dir_root_is_404(tmp_path):
    app = create_app(lambda: RunManager(Store(tmp_path / "s.sqlite3"), lambda b, c: None))
    with TestClient(app) as client:
        assert client.get("/").status_code == 404


@pytest.mark.parametrize("missing", ["OPENAI_API_KEY", "TAVILY_API_KEY", "SDR_CLIENT_SALT"])
def test_production_wiring_requires_keys_and_salt(monkeypatch, missing):
    monkeypatch.setattr("server.app.load_dotenv", lambda: None)
    for key in ("OPENAI_API_KEY", "TAVILY_API_KEY", "SDR_CLIENT_SALT"):
        monkeypatch.setenv(key, "x")
    monkeypatch.delenv(missing)
    with pytest.raises(RuntimeError, match=missing):
        default_manager()
