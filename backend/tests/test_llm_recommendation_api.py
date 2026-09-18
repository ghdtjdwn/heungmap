import asyncio
import json
from copy import deepcopy
from types import SimpleNamespace

import httpx
import pytest
from fastapi.testclient import TestClient

from app import main as main_module
from app.main import app, recommendation_cache
from app.schemas import (
    LlmResponseMeta,
    PlannerRecommendationContent,
    PlannerRecommendationResponse,
    StructuredPlanningRecommendation,
)
from app.services.llm import LlmNotConfigured, LlmUpstreamUnavailable, PlannerLlmClient


client = TestClient(app)


def valid_request() -> dict:
    return {
        "contract_version": "0.1.0",
        "client_request_id": "a6a641a1-7234-4ef6-b0e5-dbf857bc4df6",
        "analysis_id": "ana_test_001",
        "planning_context": {
            "context_version": "1.0",
            "event_brief": {"working_title": {"value": "가상 축제", "value_type": "user_input"}},
            "tourism_and_local_evidence": {
                "evidence": {"value": [{"evidence_id": "ev_planner_target", "display_value": "500명"}]}
            },
            "generation": {"model_mock": True},
        },
        "rule_recommendations": [
            {
                "recommendation_id": "rec_capacity",
                "category": "venue",
                "priority": "high",
                "title": "공식 수용인원 확인",
                "action": "장소 운영자에게 확인합니다.",
                "reason": "목표 인원 근거가 필요합니다.",
                "evidence_refs": ["ev_planner_target"],
                "requires_human_review": True,
            }
        ],
        "requested_alternatives": 1,
    }


def generated_content(evidence_ref: str = "ev_planner_target") -> dict:
    return {
        "executive_summary": "입력 근거를 바탕으로 장소 확인을 먼저 진행합니다.",
        "priorities": [
            {
                "id": "priority_1",
                "priority": "high",
                "category": "venue",
                "title": "공식 수용인원 확인",
                "action": "장소 운영자에게 수용인원을 확인합니다.",
                "reason": "목표 인원과 장소 조건을 비교해야 합니다.",
                "evidence_refs": [evidence_ref],
                "assumptions": [],
                "predicted_impact": "장소 선택의 불확실성을 줄입니다.",
                "confidence": "medium",
                "cost_level": "unknown",
                "difficulty": "needs_review",
                "deadline": None,
                "dependencies": [],
                "risks": ["운영자 확인 전에는 확정할 수 없습니다."],
                "requires_human_review": True,
            }
        ],
        "alternatives": [
            {
                "id": "alternative_1",
                "title": "장소 후보 비교",
                "changes": ["장소 후보를 비교합니다."],
                "verify": ["공식 수용인원을 확인합니다."],
            }
        ],
        "roadmap": [{"phase": "지금", "actions": ["장소 운영자에게 문의합니다."]}],
        "missing_information": ["공식 수용인원"],
        "limitations": ["자체 수요점수는 학습 모델 연결 전 mock입니다."],
    }


def generated_response() -> PlannerRecommendationResponse:
    return PlannerRecommendationResponse(
        recommendation=StructuredPlanningRecommendation(
            **generated_content(),
            schema_version="1.0",
            prompt_version="planner-recommendation-1.0",
            generation_mode="llm",
            generated_at="2026-09-06T12:00:00+09:00",
        ),
        meta=LlmResponseMeta(
            contract_version="0.1.0",
            generated_at="2026-09-06T12:00:00+09:00",
            request_id="llm_test_001",
            provider="openai",
            model="test-model",
            prompt_version="planner-recommendation-1.0",
        ),
    )


def setup_function() -> None:
    recommendation_cache.clear()


def test_recommendation_returns_structured_llm_result(monkeypatch) -> None:
    class FakeLlm:
        async def generate(self, _payload):
            return generated_response()

    monkeypatch.setattr(main_module, "llm", FakeLlm())
    response = client.post("/api/v1/planner/recommendations", json=valid_request())
    assert response.status_code == 200
    assert response.json()["recommendation"]["generation_mode"] == "llm"
    assert response.json()["recommendation"]["priorities"][0]["requires_human_review"] is True


def test_unconfigured_llm_returns_problem_json(monkeypatch) -> None:
    class MissingLlm:
        async def generate(self, _payload):
            raise LlmNotConfigured("LLM 설정이 없습니다.")

    monkeypatch.setattr(main_module, "llm", MissingLlm())
    response = client.post("/api/v1/planner/recommendations", json=valid_request())
    assert response.status_code == 503
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["code"] == "LLM_NOT_CONFIGURED"
    assert response.json()["retryable"] is False


def test_recommendation_is_idempotent_and_rejects_conflict(monkeypatch) -> None:
    class CountingLlm:
        calls = 0

        async def generate(self, _payload):
            self.calls += 1
            return generated_response()

    fake = CountingLlm()
    monkeypatch.setattr(main_module, "llm", fake)
    payload = valid_request()
    first = client.post("/api/v1/planner/recommendations", json=payload)
    second = client.post("/api/v1/planner/recommendations", json=payload)
    changed = deepcopy(payload)
    changed["analysis_id"] = "ana_test_002"
    conflict = client.post("/api/v1/planner/recommendations", json=changed)
    assert first.status_code == second.status_code == 200
    assert fake.calls == 1
    assert conflict.status_code == 409


def test_openai_adapter_uses_structured_output_and_disables_storage(monkeypatch) -> None:
    captured: dict = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(
            200,
            json={"output": [{"type": "message", "content": [{"type": "output_text", "text": json.dumps(generated_content(), ensure_ascii=False)}]}]},
        )

    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("LLM_API_KEY", "local-test-key")
    monkeypatch.setenv("LLM_MODEL", "test-model")
    llm = PlannerLlmClient(transport=httpx.MockTransport(handler))
    from app.schemas import PlannerRecommendationRequest

    result = asyncio.run(llm.generate(PlannerRecommendationRequest.model_validate(valid_request())))
    assert result.recommendation.generation_mode == "llm"
    assert captured["store"] is False
    assert captured["text"]["format"]["type"] == "json_schema"


def test_openai_adapter_rejects_unknown_evidence_reference(monkeypatch) -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={"output_text": json.dumps(generated_content("ev_fabricated"), ensure_ascii=False)},
        )

    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("LLM_API_KEY", "local-test-key")
    monkeypatch.setenv("LLM_MODEL", "test-model")
    llm = PlannerLlmClient(transport=httpx.MockTransport(handler))
    from app.schemas import PlannerRecommendationRequest
    from app.services.llm import LlmInvalidResponse

    try:
        asyncio.run(llm.generate(PlannerRecommendationRequest.model_validate(valid_request())))
    except LlmInvalidResponse:
        pass
    else:
        raise AssertionError("unknown evidence reference must be rejected")


def test_openai_adapter_rejects_new_numeric_claim(monkeypatch) -> None:
    content = generated_content()
    content["priorities"][0]["action"] = "근거에 없는 999명 수용안을 확정합니다."

    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"output_text": json.dumps(content, ensure_ascii=False)})

    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("LLM_API_KEY", "local-test-key")
    monkeypatch.setenv("LLM_MODEL", "test-model")
    llm = PlannerLlmClient(transport=httpx.MockTransport(handler))
    from app.schemas import PlannerRecommendationRequest
    from app.services.llm import LlmInvalidResponse

    try:
        asyncio.run(llm.generate(PlannerRecommendationRequest.model_validate(valid_request())))
    except LlmInvalidResponse:
        pass
    else:
        raise AssertionError("new numeric claim must be rejected")


def test_adapter_rejects_fixed_constraint_violation(monkeypatch) -> None:
    content = generated_content()
    content["alternatives"][0]["changes"] = ["행사 날짜를 변경합니다."]
    payload = valid_request()
    payload["planning_context"]["fixed_constraints"] = ["날짜 변경 불가"]

    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"output_text": json.dumps(content, ensure_ascii=False)})

    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("LLM_API_KEY", "local-test-key")
    monkeypatch.setenv("LLM_MODEL", "test-model")
    llm = PlannerLlmClient(transport=httpx.MockTransport(handler))
    from app.schemas import PlannerRecommendationRequest
    from app.services.llm import LlmInvalidResponse

    with pytest.raises(LlmInvalidResponse, match="고정 제약"):
        asyncio.run(llm.generate(PlannerRecommendationRequest.model_validate(payload)))


def test_adapter_rejects_misleading_attendance_claim(monkeypatch) -> None:
    content = generated_content()
    content["executive_summary"] = "예상 관람객 수는 입력 목표와 같습니다."

    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"output_text": json.dumps(content, ensure_ascii=False)})

    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("LLM_API_KEY", "local-test-key")
    monkeypatch.setenv("LLM_MODEL", "test-model")
    llm = PlannerLlmClient(transport=httpx.MockTransport(handler))
    from app.schemas import PlannerRecommendationRequest
    from app.services.llm import LlmInvalidResponse

    with pytest.raises(LlmInvalidResponse, match="관람객 수"):
        asyncio.run(llm.generate(PlannerRecommendationRequest.model_validate(valid_request())))


def test_openai_adapter_allows_opaque_id_numbers(monkeypatch) -> None:
    content = generated_content()
    content["priorities"][0]["id"] = "priority_999"

    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"output_text": json.dumps(content, ensure_ascii=False)})

    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("LLM_API_KEY", "local-test-key")
    monkeypatch.setenv("LLM_MODEL", "test-model")
    llm = PlannerLlmClient(transport=httpx.MockTransport(handler))
    from app.schemas import PlannerRecommendationRequest

    result = asyncio.run(llm.generate(PlannerRecommendationRequest.model_validate(valid_request())))
    assert result.recommendation.priorities[0].id == "priority_999"


def test_adapter_allows_structural_ordinal_numbers(monkeypatch) -> None:
    content = generated_content()
    content["alternatives"][0]["title"] = "대안 1"
    content["roadmap"][0]["phase"] = "1단계, 2차 검토"
    content["roadmap"][0]["actions"] = ["1) 장소 운영자에게 문의합니다."]

    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"output_text": json.dumps(content, ensure_ascii=False)})

    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("LLM_API_KEY", "local-test-key")
    monkeypatch.setenv("LLM_MODEL", "test-model")
    llm = PlannerLlmClient(transport=httpx.MockTransport(handler))
    from app.schemas import PlannerRecommendationRequest

    result = asyncio.run(llm.generate(PlannerRecommendationRequest.model_validate(valid_request())))
    assert result.recommendation.alternatives[0].title == "대안 1"


def test_adapter_allows_fixed_constraint_preservation_statement(monkeypatch) -> None:
    content = generated_content()
    content["alternatives"][0]["changes"] = ["날짜와 장소를 변경하지 않고 검토합니다."]
    content["alternatives"][0]["verify"] = ["규모를 줄이는 방안은 고정 제약과 충돌하므로 제외합니다."]
    payload = valid_request()
    payload["planning_context"]["fixed_constraints"] = ["날짜 변경 불가", "장소 변경 불가", "규모 축소 불가"]

    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"output_text": json.dumps(content, ensure_ascii=False)})

    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("LLM_API_KEY", "local-test-key")
    monkeypatch.setenv("LLM_MODEL", "test-model")
    llm = PlannerLlmClient(transport=httpx.MockTransport(handler))
    from app.schemas import PlannerRecommendationRequest

    result = asyncio.run(llm.generate(PlannerRecommendationRequest.model_validate(payload)))
    assert result.recommendation.generation_mode == "llm"


def test_openai_adapter_maps_exhausted_credit_without_exposing_provider_body(monkeypatch) -> None:
    async def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            429,
            json={"error": {"type": "insufficient_quota", "code": "credit_balance_exhausted", "message": "private provider detail"}},
        )

    monkeypatch.setenv("LLM_PROVIDER", "openai")
    monkeypatch.setenv("LLM_API_KEY", "local-test-key")
    monkeypatch.setenv("LLM_MODEL", "gpt-5-nano")
    llm = PlannerLlmClient(transport=httpx.MockTransport(handler))
    from app.schemas import PlannerRecommendationRequest

    try:
        asyncio.run(llm.generate(PlannerRecommendationRequest.model_validate(valid_request())))
    except LlmUpstreamUnavailable as exc:
        assert "credit" in str(exc)
        assert "private provider detail" not in str(exc)
    else:
        raise AssertionError("credit exhaustion must be mapped")


def test_ollama_adapter_uses_local_structured_output(monkeypatch) -> None:
    captured: dict = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(
            200,
            json={"message": {"role": "assistant", "content": json.dumps(generated_content(), ensure_ascii=False)}},
        )

    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("LLM_API_BASE_URL", "http://127.0.0.1:11434")
    monkeypatch.setenv("LLM_MODEL", "qwen3.5:9b")
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    llm = PlannerLlmClient(transport=httpx.MockTransport(handler))
    from app.schemas import PlannerRecommendationRequest

    result = asyncio.run(llm.generate(PlannerRecommendationRequest.model_validate(valid_request())))
    assert result.recommendation.generation_mode == "llm"
    assert result.meta.provider == "ollama"
    assert captured["stream"] is False
    assert captured["think"] is False
    assert captured["options"]["temperature"] == 0
    assert captured["format"]["type"] == "object"
    assert "title" in captured["format"]["$defs"]["PlannerRecommendationPriority"]["properties"]
    assert captured["format"]["properties"]["alternatives"]["minItems"] == 1
    assert captured["format"]["properties"]["alternatives"]["maxItems"] == 1
    assert captured["format"]["$defs"]["PlannerRecommendationRoadmapItem"]["properties"]["phase"]["enum"] == [
        "지금",
        "준비 중",
        "행사 전",
    ]
    schema_text = json.dumps(captured["format"])
    assert "minLength" not in schema_text
    assert "anyOf" not in schema_text
    assert "const" not in schema_text
    assert '"enum": [true]' in schema_text


class FakeClaude:
    """anthropic.AsyncAnthropic 대역. 네트워크 없이 요청 인자를 기록한다."""

    def __init__(self, text=None, stop_reason="end_turn", blocks=None):
        self.calls = []
        response = SimpleNamespace(stop_reason=stop_reason, content=blocks if blocks is not None else [
            SimpleNamespace(type="thinking", thinking=""), SimpleNamespace(type="text", text=text)])

        async def create(**kwargs):
            self.calls.append(kwargs)
            return response

        self.beta = SimpleNamespace(messages=SimpleNamespace(create=create))


def claude_llm(monkeypatch, fake, model="claude-sonnet-5"):
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.setenv("LLM_MODEL", model)
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    return PlannerLlmClient(anthropic_client=fake)


def test_claude_adapter_uses_structured_output_and_shared_validation(monkeypatch) -> None:
    from app.schemas import PlannerRecommendationRequest

    fake = FakeClaude(json.dumps(generated_content(), ensure_ascii=False))
    result = asyncio.run(claude_llm(monkeypatch, fake).generate(PlannerRecommendationRequest.model_validate(valid_request())))
    call = fake.calls[0]
    assert result.recommendation.generation_mode == "llm" and result.meta.provider == "anthropic"
    assert call["model"] == "claude-sonnet-5" and call["output_config"]["format"]["type"] == "json_schema"
    assert call["output_config"]["effort"] == "high" and "fallbacks" not in call
    assert "temperature" not in call and "thinking" not in call


def test_claude_schema_drops_unsupported_constraints_but_keeps_field_names() -> None:
    from app.services.llm_anthropic import planner_schema

    serialized = json.dumps(planner_schema())
    assert "minLength" not in serialized and "maxItems" not in serialized
    priority = planner_schema()["$defs"]["PlannerRecommendationPriority"]
    assert "title" in priority["properties"] and priority["additionalProperties"] is False


def test_claude_top_models_opt_into_default_fallbacks(monkeypatch) -> None:
    from app.schemas import PlannerRecommendationRequest

    fake = FakeClaude(json.dumps(generated_content(), ensure_ascii=False))
    asyncio.run(claude_llm(monkeypatch, fake, "claude-fable-5-1").generate(PlannerRecommendationRequest.model_validate(valid_request())))
    assert fake.calls[0]["fallbacks"] == "default" and fake.calls[0]["betas"] == ["server-side-fallback-2026-07-01"]


def test_claude_refusal_truncation_and_fabricated_evidence_fall_back(monkeypatch) -> None:
    from app.schemas import PlannerRecommendationRequest
    from app.services.llm import LlmInvalidResponse

    request = PlannerRecommendationRequest.model_validate(valid_request())
    cases = [
        (FakeClaude(stop_reason="refusal", blocks=[]), LlmUpstreamUnavailable),
        (FakeClaude("{", stop_reason="max_tokens"), LlmInvalidResponse),
        (FakeClaude(json.dumps(generated_content("ev_fabricated"), ensure_ascii=False)), LlmInvalidResponse),
        (FakeClaude(blocks=[SimpleNamespace(type="thinking", thinking="")]), LlmInvalidResponse),
    ]
    for fake, error in cases:
        try:
            asyncio.run(claude_llm(monkeypatch, fake).generate(request))
        except error:
            continue
        raise AssertionError(f"{error.__name__} expected")


def test_claude_is_not_configured_without_any_credential(monkeypatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    monkeypatch.delenv("LLM_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert PlannerLlmClient().configured is False
    monkeypatch.setenv("LLM_API_KEY", "sk-ant-test")
    assert PlannerLlmClient().configured is True and PlannerLlmClient().model == "claude-fable-5-1"
