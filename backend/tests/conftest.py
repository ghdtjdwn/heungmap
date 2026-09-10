import pytest


@pytest.fixture(autouse=True)
def isolated_accounts(tmp_path, monkeypatch):
    monkeypatch.setenv("HEUNGMAP_DB_PATH", str(tmp_path / "test.sqlite3"))
    monkeypatch.setenv("HEUNGMAP_AUTH_MODE", "mock")
    monkeypatch.setenv("HEUNGMAP_ENV", "development")
    monkeypatch.setenv("HEUNGMAP_PUBLIC_ORIGIN", "http://localhost:3000")


@pytest.fixture(autouse=True)
def authenticated_planner_client(request, isolated_accounts):
    if request.module.__name__ in {"test_planner_api", "test_llm_recommendation_api"}:
        client = request.module.client
        client.cookies.clear()
        client.headers["Origin"] = "http://localhost:3000"
        assert client.post("/api/v1/auth/mock").status_code == 200
        yield
        client.cookies.clear()
    else:
        yield
