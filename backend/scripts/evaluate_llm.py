from __future__ import annotations

import argparse
import asyncio
import json
import time
from datetime import datetime
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from app.schemas import PlannerRecommendationRequest, Recommendation
from app.services.llm import LlmInvalidResponse, PlannerLlmClient


SCENARIOS = [
    {
        "name": "large_festival",
        "context": {"event_brief": {"scale": {"value": "large", "value_type": "user_input"}}, "fixed_constraints": ["개최 지역 변경 불가"], "generation": {"model_mock": True}},
        "alternatives": 3,
    },
    {
        "name": "independent_small",
        "context": {"event_brief": {"scale": {"value": "small", "value_type": "user_input"}}, "fixed_constraints": ["행사 날짜 변경 불가"], "generation": {"model_mock": True}},
        "alternatives": 2,
    },
    {
        "name": "mostly_empty",
        "context": {"event_brief": {"known": {"value": "festival", "value_type": "user_input"}}, "missing_information": ["지역", "일정", "장소", "예산"], "fixed_constraints": [], "generation": {"model_mock": True}},
        "alternatives": 1,
    },
    {
        "name": "contradictory_capacity",
        "context": {"event_brief": {"constraint_state": {"value": "목표 인원이 장소 수용인원보다 큼", "value_type": "derived_value"}}, "fixed_constraints": ["규모 축소 불가"], "generation": {"model_mock": True}},
        "alternatives": 2,
    },
    {
        "name": "strong_fixed_constraints",
        "context": {"event_brief": {"priority": {"value": "safety", "value_type": "user_input"}}, "fixed_constraints": ["날짜 변경 불가", "장소 변경 불가", "예산 증액 불가"], "generation": {"model_mock": True}},
        "alternatives": 2,
    },
]


def request_for(scenario: dict) -> PlannerRecommendationRequest:
    evidence_id = f"ev_{scenario['name']}"
    context = {
        **scenario["context"],
        "tourism_and_local_evidence": {"evidence": {"value": [{"evidence_id": evidence_id, "display_value": "synthetic scenario evidence"}]}},
    }
    recommendation = Recommendation(
        recommendation_id=f"rec_{scenario['name']}",
        category="risk",
        priority="high",
        title="확인되지 않은 조건을 먼저 검토하세요",
        action="입력 근거와 공식 정보를 담당자가 확인하세요.",
        reason="현재 정보만으로 확정할 수 없습니다.",
        evidence_refs=[evidence_id],
        requires_human_review=True,
    )
    return PlannerRecommendationRequest(
        contract_version="0.1.0",
        client_request_id=uuid5(NAMESPACE_URL, scenario["name"]),
        analysis_id=f"ana_eval_{scenario['name']}",
        planning_context=context,
        rule_recommendations=[recommendation],
        requested_alternatives=scenario["alternatives"],
    )


async def run(output: Path) -> dict:
    client = PlannerLlmClient()
    results = []
    for scenario in SCENARIOS:
        started = time.perf_counter()
        try:
            response = await client.generate(request_for(scenario))
            recommendation = response.recommendation
            result = {
                "scenario": scenario["name"],
                "status": "pass",
                "latency_seconds": round(time.perf_counter() - started, 3),
                "alternatives": len(recommendation.alternatives),
                "priorities": len(recommendation.priorities),
                "human_review_all": all(item.requires_human_review for item in recommendation.priorities),
                "provider": response.meta.provider,
                "model": response.meta.model,
            }
        except Exception as exc:
            result = {
                "scenario": scenario["name"],
                "status": "fail",
                "latency_seconds": round(time.perf_counter() - started, 3),
                "error_type": type(exc).__name__,
                "error": str(exc),
            }
            diagnostics = getattr(exc, "diagnostics", None)
            if diagnostics:
                result["diagnostics"] = diagnostics
        results.append(result)
        print(json.dumps(result, ensure_ascii=False), flush=True)
    latencies = [item["latency_seconds"] for item in results]
    report = {
        "report_version": "1.0",
        "generated_at": datetime.now().astimezone().isoformat(),
        "scenarios": results,
        "passed": sum(item["status"] == "pass" for item in results),
        "failed": sum(item["status"] != "pass" for item in results),
        "cold_latency_seconds": latencies[0] if latencies else None,
        "warm_latency_seconds": latencies[1:] if len(latencies) > 1 else [],
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("data/processed/llm-eval.json"))
    parser.add_argument("--scenario", action="append", choices=[item["name"] for item in SCENARIOS])
    args = parser.parse_args()
    if args.scenario:
        selected = set(args.scenario)
        SCENARIOS[:] = [item for item in SCENARIOS if item["name"] in selected]
    report = asyncio.run(run(args.output))
    return 0 if report["failed"] == 0 else 2


if __name__ == "__main__":
    raise SystemExit(main())
