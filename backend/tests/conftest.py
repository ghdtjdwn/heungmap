import pytest


@pytest.fixture(autouse=True)
def isolated_accounts(tmp_path, monkeypatch):
    from app import main as main_module

    monkeypatch.setenv("HEUNGMAP_DB_PATH", str(tmp_path / "test.sqlite3"))
    monkeypatch.setenv("HEUNGMAP_AUTH_MODE", "mock")
    monkeypatch.setenv("HEUNGMAP_ENV", "development")
    monkeypatch.setenv("HEUNGMAP_PUBLIC_ORIGIN", "http://localhost:3000")
    monkeypatch.setenv("HEUNGMAP_DEMAND_MODE", "mock")
    monkeypatch.setenv("HEUNGMAP_MCST_LOOKUP_PATH", str(tmp_path / "no-mcst-lookup.csv"))
    monkeypatch.setattr(main_module.kakao_places, "rest_api_key", "")
    monkeypatch.setattr(main_module.tourapi, "service_key", "")  # .env의 실제 TourAPI 키로 외부 호출하지 않는다.
    # main.py가 import 시 .env를 읽으므로 실제 LLM 키로 외부 호출하지 않게 끊는다. 필요한 테스트는 가짜 client를 주입한다.
    from app.services.llm import PlannerLlmClient

    monkeypatch.setenv("LLM_PROVIDER", "disabled")
    monkeypatch.setenv("LLM_API_KEY", "")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("LLM_MODEL", raising=False)
    monkeypatch.delenv("LLM_EFFORT", raising=False)
    monkeypatch.setattr(main_module, "llm", PlannerLlmClient())


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
