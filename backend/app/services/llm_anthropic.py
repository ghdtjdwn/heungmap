"""Claude(Anthropic Messages API)로 기획 추천 JSON을 생성한다. 다른 LLM 공급자 코드와 분리한 adapter다."""
from __future__ import annotations

from typing import Any

import anthropic

from app.schemas import PlannerRecommendationContent
from app.services.llm import LlmInvalidResponse, LlmTimeout, LlmUpstreamUnavailable


DEFAULT_MODEL = "claude-fable-5-1"
DEFAULT_EFFORT = "high"
EFFORTS = {"low", "medium", "high", "xhigh", "max"}
MAX_TOKENS = 16000
# 안전 분류기가 거절하면 Anthropic 권장 모델로 서버에서 다시 실행한다(거절 범주별 자동 선택).
FALLBACK_BETA = "server-side-fallback-2026-07-01"
FALLBACK_MODELS = {"claude-fable-5-1", "claude-fable-5", "claude-opus-5"}
# structured outputs가 지원하지 않는 제약. 길이·개수 검사는 응답을 받은 뒤 Pydantic이 다시 한다.
UNSUPPORTED_SCHEMA_KEYS = {"minLength", "maxLength", "minItems", "maxItems", "minimum", "maximum",
                           "exclusiveMinimum", "exclusiveMaximum", "multipleOf", "pattern"}


def claude_schema(value: Any, *, property_map: bool = False) -> Any:
    """Pydantic JSON Schema를 Claude structured outputs가 받는 형태로 줄인다."""
    if isinstance(value, list):
        return [claude_schema(item) for item in value]
    if not isinstance(value, dict):
        return value
    result: dict[str, Any] = {}
    for key, item in value.items():
        if key in UNSUPPORTED_SCHEMA_KEYS or (key == "title" and not property_map):
            continue
        result[key] = claude_schema(item, property_map=key == "properties")
    if result.get("type") == "object" and not property_map:
        result["additionalProperties"] = False
    return result


def planner_schema() -> dict[str, Any]:
    return claude_schema(PlannerRecommendationContent.model_json_schema())


async def generate_planner_json(*, instructions: str, user_content: str, model: str, effort: str,
                                timeout_seconds: float, api_key: str | None = None, client: Any = None) -> str:
    """Claude 응답의 JSON 문자열을 돌려준다. 검증은 호출하는 쪽(PlannerLlmClient)이 공통으로 한다."""
    client = client or anthropic.AsyncAnthropic(api_key=api_key or None, timeout=timeout_seconds, max_retries=2)
    arguments: dict[str, Any] = {
        "model": model, "max_tokens": MAX_TOKENS, "system": instructions,
        "messages": [{"role": "user", "content": user_content}],
        "output_config": {"effort": effort, "format": {"type": "json_schema", "schema": planner_schema()}},
    }
    if model in FALLBACK_MODELS:
        arguments.update(betas=[FALLBACK_BETA], fallbacks="default")
    try:
        response = await client.beta.messages.create(**arguments)
    except anthropic.APITimeoutError as exc:
        raise LlmTimeout("Claude 응답 시간이 초과됐습니다.") from exc
    except (anthropic.AuthenticationError, anthropic.PermissionDeniedError) as exc:
        raise LlmUpstreamUnavailable("Claude API key 또는 권한을 확인해 주세요.") from exc
    except anthropic.RateLimitError as exc:
        raise LlmUpstreamUnavailable("Claude API 요청 한도에 도달했습니다.") from exc
    except anthropic.BadRequestError as exc:
        raise LlmUpstreamUnavailable("Claude API가 요청을 받지 않았습니다. model·credit 설정을 확인해 주세요.") from exc
    except anthropic.APIStatusError as exc:
        raise LlmUpstreamUnavailable(f"Claude API가 HTTP {exc.status_code}을 반환했습니다.") from exc
    except anthropic.APIConnectionError as exc:
        raise LlmUpstreamUnavailable("Claude API에 연결하지 못했습니다.") from exc
    if response.stop_reason == "refusal":
        raise LlmUpstreamUnavailable("Claude가 이 요청을 처리하지 않아 규칙 보고서로 전환합니다.")
    if response.stop_reason == "max_tokens":
        raise LlmInvalidResponse("Claude 응답이 길이 제한에서 끊겼습니다.")
    # 대체 모델이 이어 답했다면 마지막 text block이 실제 응답이다. thinking·fallback block은 건너뛴다.
    texts = [block.text for block in response.content if getattr(block, "type", None) == "text"]
    if not texts:
        raise LlmInvalidResponse("Claude 응답에 JSON 본문이 없습니다.")
    return texts[-1]
