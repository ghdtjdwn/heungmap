from pathlib import Path

import yaml

from app.main import app


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def test_implemented_paths_exist_in_approved_contract() -> None:
    approved = yaml.safe_load((REPOSITORY_ROOT / "contracts/openapi.yaml").read_text(encoding="utf-8"))
    generated = app.openapi()
    base_path = approved["servers"][0]["url"].rstrip("/")
    approved_http_paths = {f"{base_path}{path}" for path in approved["paths"]}
    for path in generated["paths"]:
        assert path in approved_http_paths


def test_planner_schema_top_level_fields_match_approved_contract() -> None:
    approved = yaml.safe_load((REPOSITORY_ROOT / "contracts/openapi.yaml").read_text(encoding="utf-8"))
    generated = app.openapi()
    for name in (
        "EventDraft",
        "PlannerAnalysisRequest",
        "PlannerAnalysisResponse",
        "HealthResponse",
        "VenueSearchItem",
        "VenueSearchResponse",
        "AddressSearchItem",
        "AddressSearchResponse",
        "EventSummary",
        "EventListResponse",
        "SearchFilter",
        "NearbyPlaceListResponse",
        "AvailablePredictionSummary",
        "UnavailablePredictionSummary",
        "PlannerRecommendationRequest",
        "PlannerRecommendationPriority",
        "PlannerRecommendationAlternative",
        "PlannerRecommendationRoadmapItem",
        "StructuredPlanningRecommendation",
        "LlmResponseMeta",
        "PlannerRecommendationResponse",
    ):
        approved_schema = approved["components"]["schemas"][name]
        generated_schema = generated["components"]["schemas"][name]
        assert set(generated_schema.get("properties", {})) == set(approved_schema.get("properties", {}))
        assert set(generated_schema.get("required", [])) == set(approved_schema.get("required", []))


def test_planner_operation_and_problem_media_type_match_contract() -> None:
    approved = yaml.safe_load((REPOSITORY_ROOT / "contracts/openapi.yaml").read_text(encoding="utf-8"))
    generated = app.openapi()
    approved_operation = approved["paths"]["/planner/analyses"]["post"]
    generated_operation = generated["paths"]["/api/v1/planner/analyses"]["post"]
    assert generated_operation["operationId"] == approved_operation["operationId"]
    for status in ("409", "422"):
        assert "application/problem+json" in generated_operation["responses"][status]["content"]


def test_location_search_operations_and_problem_media_types_match_contract() -> None:
    approved = yaml.safe_load((REPOSITORY_ROOT / "contracts/openapi.yaml").read_text(encoding="utf-8"))
    generated = app.openapi()
    for path in ("/venues/search", "/addresses/search"):
        approved_operation = approved["paths"][path]["get"]
        generated_operation = generated["paths"][f"/api/v1{path}"]["get"]
        assert generated_operation["operationId"] == approved_operation["operationId"]
        for status in ("422", "503"):
            assert "application/problem+json" in generated_operation["responses"][status]["content"]


def test_llm_recommendation_operation_and_problem_media_types_match_contract() -> None:
    approved = yaml.safe_load((REPOSITORY_ROOT / "contracts/openapi.yaml").read_text(encoding="utf-8"))
    generated = app.openapi()
    approved_operation = approved["paths"]["/planner/recommendations"]["post"]
    generated_operation = generated["paths"]["/api/v1/planner/recommendations"]["post"]
    assert generated_operation["operationId"] == approved_operation["operationId"]
    for status in ("409", "422", "502", "503", "504"):
        assert "application/problem+json" in generated_operation["responses"][status]["content"]


def test_protected_operations_and_google_redirects_are_documented() -> None:
    approved = yaml.safe_load((REPOSITORY_ROOT / "contracts/openapi.yaml").read_text(encoding="utf-8"))
    protected_operations = (
        ("/auth/role", "post"),
        ("/planner/publications", "get"),
        ("/planner/publications", "post"),
        ("/planner/publications/{event_id}", "delete"),
        ("/planner/analyses", "post"),
        ("/planner/recommendations", "post"),
    )
    assert approved["components"]["securitySchemes"]["sessionCookie"] == {
        "type": "apiKey",
        "in": "cookie",
        "name": "heungmap_session",
        "description": "로그인 후 발급되는 HttpOnly 세션 쿠키",
    }
    for path, method in protected_operations:
        assert approved["paths"][path][method]["security"] == [{"sessionCookie": []}]
    assert set(approved["paths"]["/auth/google"]["get"]["responses"]) >= {"307"}
    assert set(approved["paths"]["/auth/google/callback"]["get"]["responses"]) >= {"303"}


def test_event_search_contract_only_advertises_supported_mvp_filters() -> None:
    approved = yaml.safe_load((REPOSITORY_ROOT / "contracts/openapi.yaml").read_text(encoding="utf-8"))
    assert approved["components"]["schemas"]["EventSort"]["enum"] == ["start_date"]
    parameter_names = {
        parameter["name"] for parameter in approved["paths"]["/events"]["get"]["parameters"]
    }
    assert not parameter_names.intersection({"latitude", "longitude", "south", "west", "north", "east"})
