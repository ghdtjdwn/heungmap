"""배포한 서비스를 실제 사용자 흐름대로 점검한다.

프론트 공개 주소로 그대로 돌리거나(권장), 백엔드만 따로 볼 때는 ssh 포트포워딩 주소를 준다.

    python3 scripts/deploy-smoke.py https://heungmap.vercel.app
    ssh -f -N -L 18000:127.0.0.1:8000 <서버>
    python3 scripts/deploy-smoke.py http://127.0.0.1:18000 --origin https://heungmap.vercel.app

Origin은 백엔드의 HEUNGMAP_PUBLIC_ORIGIN과 정확히 같아야 한다(auth.py의 same_origin).
기본값은 base와 같게 둔다. 외부 API를 실제로 호출하므로 조회 수가 늘어난다.
"""

import argparse
import json
import time
import urllib.request
import urllib.error
from urllib.parse import quote, unquote

parser = argparse.ArgumentParser()
parser.add_argument("base", help="예: https://heungmap.vercel.app")
parser.add_argument("--origin", help="기본값은 base와 동일")
args = parser.parse_args()

BASE = args.base.rstrip("/") + "/api/v1"
ORIGIN = (args.origin or args.base).rstrip("/")
cookies: dict[str, str] = {}


def call(method: str, path: str, body=None, origin=True):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method)
    req.add_header("Accept", "application/json")
    if data:
        req.add_header("Content-Type", "application/json")
    if origin:
        req.add_header("Origin", ORIGIN)
    if cookies:
        req.add_header("Cookie", "; ".join(f"{k}={v}" for k, v in cookies.items()))
    # 배포 직후에는 엣지 전파가 끝나지 않아 502가 섞일 수 있다. 몇 번 다시 시도한다.
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=180) as resp:
                for raw in resp.headers.get_all("Set-Cookie") or []:
                    name, _, rest = raw.partition("=")
                    cookies[name] = rest.split(";")[0]
                body = resp.read().decode()
                try:
                    return resp.status, json.loads(body or "{}")
                except ValueError:
                    return resp.status, {"_raw": body[:200]}
        except urllib.error.HTTPError as err:
            body = err.read().decode()
            if err.code in (502, 503, 504) and attempt < 4:
                time.sleep(3)
                continue
            try:
                return err.code, json.loads(body or "{}")
            except ValueError:
                return err.code, {"_raw": body[:200]}
        except urllib.error.URLError:
            if attempt < 4:
                time.sleep(3)
                continue
            raise
    return 0, {}


def redirect_target(path: str):
    """리다이렉트를 따라가지 않고 Location 헤더만 본다."""
    class Keep(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *_args, **_kw):
            return None
    opener = urllib.request.build_opener(Keep)
    req = urllib.request.Request(BASE + path)
    req.add_header("Origin", ORIGIN)
    for attempt in range(5):
        try:
            with opener.open(req, timeout=60) as resp:
                return resp.status, resp.headers.get("Location", "")
        except urllib.error.HTTPError as err:
            if err.code in (502, 503, 504) and attempt < 4:
                time.sleep(3)
                continue
            return err.code, err.headers.get("Location", "")
    return 0, ""


def show(label, ok, detail=""):
    print(f"  {'PASS' if ok else 'FAIL'}  {label}{(' — ' + detail) if detail else ''}")
    return ok


results = []

print("\n[1] 예측 가능 시군구 조회")
status, regions = call("GET", "/prediction/regions")
if not isinstance(regions, list) or not regions or not isinstance(regions[0], dict):
    print("  FAIL  지역 목록 — 예상과 다른 응답:", str(regions)[:200])
    raise SystemExit(1)
region = next(r for r in regions if r.get("legal_dong_code"))
results.append(show("지역 목록", status == 200 and len(regions) > 200, f"{len(regions)}개, 예: {region['display_name']}"))

print("\n[2] 인증 모드 확인")
mock_status, _ = call("POST", "/auth/mock", {})
google_mode = mock_status == 404
print(f"      · {'실제 Google 로그인(google)' if google_mode else '체험용 모의 로그인(mock)'}")

if google_mode:
    print("\n[3] Google 로그인 시작점")
    status, location = redirect_target("/auth/google")
    results.append(show("구글로 리다이렉트", status in (302, 303, 307) and "accounts.google.com" in location,
                        f"HTTP {status}"))
    for name, label in (("client_id", "클라이언트 ID"), ("redirect_uri", "콜백 주소"),
                        ("code_challenge", "PKCE"), ("state", "state"), ("nonce", "nonce")):
        results.append(show(label + " 포함", name + "=" in location))
    want = quote(ORIGIN + "/api/v1/auth/google/callback", safe="")
    results.append(show("콜백 주소가 공개 origin과 일치", want in location, unquote(want)))
    print("\n[4] 로그인 필요한 기능은 실계정이 있어야 해 건너뜁니다")
else:
    results.append(show("Origin 없는 로그인 차단",
                        call("POST", "/auth/mock", {}, origin=False)[0] == 403))
    print("\n[3] 모의 로그인 (Vercel과 동일한 Origin)")
    status, session = call("POST", "/auth/mock", {})
    results.append(show("로그인", status == 200, f"사용자 {session.get('user', {}).get('name')}"))
    results.append(show("세션 쿠키 발급", "heungmap_session" in cookies))

    print("\n[4] 역할 선택 — 기획자")
    status, session = call("POST", "/auth/role", {"role": "planner"})
    results.append(show("역할 설정", status == 200 and session.get("user", {}).get("role") == "planner"))

print("\n[5] 기획자 분석 (실제 모델 예측)")
payload = {
    "contract_version": "0.1.0",
    "client_request_id": "c0ffee00-1111-4222-8333-444455556666",
    "event_draft": {
        "event_id": "evt_planner_deploy_check_001",
        "working_title": "배포 점검용 가상 축제",
        "planner_type": "independent_planner",
        "planning_stage": "idea",
        "event_type": "festival",
        "purpose": "community",
        "theme_keywords": ["청년", "음악"],
        "schedule_selection_mode": "fixed",
        "start_date": "2026-10-10",
        "end_date": "2026-10-12",
        "region_selection_mode": "fixed",
        "region": {
            "area_code": region["area_code"],
            "legal_dong_code": region["legal_dong_code"],
            "display_name": region["display_name"],
        },
        "indoor_outdoor": "outdoor",
        "target_audience": ["young_adult", "local_resident"],
        "target_attendance": 500,
        "ticket_type": "free",
        "budget_max_krw": 10000000,
        "fixed_constraints": ["개최일 변경 불가"],
    },
    "requested_outputs": ["prediction", "nearby_places", "rule_recommendations"],
}
if google_mode:
    print("      · 로그인 필요 — 건너뜁니다(실계정 로그인 뒤 화면에서 확인)")
    status, analysis, prediction = 200, {}, {}
else:
    status, analysis = call("POST", "/planner/analyses", payload)
    prediction = analysis.get("prediction", {})
if not google_mode:
    results.append(show("분석 응답", status == 200, f"HTTP {status}"))
(None if google_mode else results.append(show("예측 사용 가능", prediction.get("status") == "available",
                    f"{prediction.get('prediction_type')} / method={prediction.get('method')}")))
(None if google_mode else results.append(show("실제 모델 사용(규칙 아님)", prediction.get("is_mock") is False,
                    f"is_mock={prediction.get('is_mock')}")))
rng = prediction.get("primary_metric") or {}
(None if google_mode else results.append(show("p10·p50·p90 범위", all(rng.get(k) is not None for k in ("p10", "p50", "p90")),
                    f"p10={rng.get('p10'):,} p50={rng.get('p50'):,} p90={rng.get('p90'):,} ({rng.get('unit') or ''})"
                    if rng.get("p50") is not None else f"키: {list(rng.keys())}")))
factors = prediction.get("factors") or []
(None if google_mode else results.append(show("SHAP 기여 요인", len(factors) > 0, f"{len(factors)}개")))
(None if google_mode else results.append(show("규칙 권고", len(analysis.get("rule_recommendations") or []) > 0,
                    f"{len(analysis.get('rule_recommendations') or [])}건")))

print("\n[6] 방문객 — TourAPI 축제 목록")
status, events = call("GET", "/events?page=1&size=5")
items = events.get("items") or []
results.append(show("축제 목록", status == 200 and len(items) > 0, f"{len(items)}건, 예: {items[0]['title'] if items else '-'}"))

print("\n[7] 방문객 — 축제 상세")
if items:
    status, detail = call("GET", f"/events/{items[0]['event_id']}")
    results.append(show("축제 상세", status == 200, detail.get("title", "")))

print("\n[8] 모델 상태 카드")
status, model = call("GET", "/system/model-status")
results.append(show("모델 상태", status == 200 and model.get("status") == "ready",
                    f"{model.get('model_version')} / {model.get('regions')}개 지역"))
(None if google_mode else results.append(show("모델 버전 일치(분석 응답 ↔ 상태카드)",
                    prediction.get("model_version") == model.get("model_version"),
                    str(prediction.get("model_version")))))

print(f"\n{'=' * 60}")
print(f"결과: {sum(results)}/{len(results)} 통과  ({BASE})")
print("=" * 60)
raise SystemExit(0 if all(results) else 1)
