# 배포 실행 기록 (2026-09-20)

[DEPLOYMENT.md](DEPLOYMENT.md)는 계획 문서이고, 이 문서는 **실제로 실행한 것과 남은 것**입니다.

## 구조

```text
브라우저
   │ https://heungmap.vercel.app
   ▼
Vercel (Next.js)              ← 프론트. next.config.ts의 rewrites가
   │ /api/v1/*                  /api/v1/* 를 백엔드로 서버측 프록시한다.
   │                            (브라우저에는 같은 origin으로 보여 CORS·쿠키 문제가 없다)
   ▼
https://ssumcp.tail5e04bc.ts.net   ← Tailscale Funnel. 서버에 공인 IP가 없어
   │                                 아웃바운드 연결만으로 공개 HTTPS를 받는다.
   ▼
오라클 서버 ssumcp (FastAPI 127.0.0.1:8000)
   ├─ 모델: ~/heungmap-model/data/processed (재학습 폴더를 심볼릭 링크로 공유)
   └─ SQLite: ~/heungmap-web/data/heungmap.sqlite3
```

**백엔드를 Vercel에 올릴 수 없는 이유**: pandas·LightGBM·scikit-learn 의존성이 Vercel 파이썬 함수의
압축 해제 250MB 한도를 넘고, 24MB 모델 artifact를 동봉할 수 없으며, SQLite 쓰기가 필요하고,
매일 재학습한 새 모델을 읽어야 합니다.

## 끝난 것

### 1. 재학습 cron 고장 수리

`~/heungmap-model`의 cron이 9/18·9/19 이틀 연속 `Permission denied`로 실패하고 있었습니다.
crontab이 스크립트를 실행 파일로 직접 불렀는데 `scripts/model-refresh.sh`에 실행 권한(`+x`)이 없었습니다.
9/18 설치 검증은 `sh 스크립트` 형태로 돌려서 이 경로를 지나치지 않았습니다.

- `scripts/install-model-refresh.sh`가 cron 줄을 `/bin/sh <스크립트>`로 등록하도록 수정
- 저장소의 `.sh` 파일에 실행 권한 부여(`git update-index --chmod=+x`)
- cron과 동일한 최소 환경(`env -i`)에서 그대로 실행해 **종료 코드 0** 확인

### 2. 백엔드 배포 (오라클 서버)

```bash
scripts/oracle/deploy-web.sh ubuntu@100.97.34.28 https://heungmap.vercel.app
```

- 폴더 `~/heungmap-web` 하나. 전용 Python 3.12 가상환경(재학습 폴더의 uv·libgomp 공유)
- systemd `heungmap-api` — `127.0.0.1:8000`, 재부팅 후 자동 시작, `Nice=5`
- **uvicorn worker 1개 고정**: `app.main`이 분석 결과를 프로세스 메모리(`analysis_cache`)에 들고 있어
  worker를 늘리면 "분석 → 공개" 흐름이 로컬과 달라집니다.
- `data/processed` → `~/heungmap-model/data/processed` 심볼릭 링크.
  백엔드가 번호가 가장 큰 채택본을 고르므로 **매일 새벽 재학습 결과가 자동 반영**됩니다.
- `.env`는 로컬 것을 기준으로 `HEUNGMAP_PUBLIC_ORIGIN`·`HEUNGMAP_ENV`·`HEUNGMAP_AUTH_MODE`만 덮어씁니다.
  실제 Google 로그인은 범위 밖이므로 `HEUNGMAP_AUTH_MODE=mock`, 이는 `HEUNGMAP_ENV=development`에서만 허용됩니다(`auth.py`).

서버에서 확인한 동작: `/api/v1/health` ok, `/api/v1/system/model-status` ready
(`regional-daily-1.0-ab975d661247`, 예측 가능 ~2026-10-18), `/api/v1/events` TourAPI 실응답,
`/api/v1/prediction/regions` 261개 시군구.

### 3. 로컬과의 동작 일치 검증

서버에서 로컬과 **같은 결과**가 나오는 것을 확인했습니다.

| 검증 | 로컬(맥) | 서버(오라클) |
| --- | --- | --- |
| `pytest backend/tests` | 172 passed | **172 passed** |
| `verify_daily_model.py` | — | 출처 checksum 4건, 홀드아웃 재계산 300행, 261개 시군구 전부 예측 가능(불가 0건), 온라인 예측 평균 0.026초 |

계약 검증 테스트가 `contracts/openapi.yaml`을, 모델 검증이 `data/raw`를 읽으므로 둘 다 서버에 두도록
`deploy-web.sh`에 추가했습니다(`data/raw`는 재학습 폴더를 심볼릭 링크로 공유).

### 4. 프론트 배포 (Vercel) — 완료

```bash
cd frontend
vercel link --yes --project heungmap --scope akftjdwn-9388s-projects
vercel env add KAKAO_JAVASCRIPT_KEY production
vercel --prod --yes
```

- 공개 주소 **https://heungmap.vercel.app** (HTTP 200, 제목 `흥할지도 · 만드는 즐거움, 찾아가는 설렘`)
- 리포 루트 `.env`가 없는 Vercel 환경에서 빌드됩니다. `next.config.ts`가 `KAKAO_JAVASCRIPT_KEY`를
  환경변수에서 먼저 읽고 없을 때만 `../.env`를 보기 때문입니다.
- 백엔드 주소(`HEUNGMAP_BACKEND_URL`)는 아직 미설정이라 `/api/v1/*`가 404입니다. 아래가 마지막 단계입니다.

### 5. 배포된 백엔드 실사용 흐름 검증 — 15/15 통과

공개 통로가 아직 없어도 Tailscale 사설망으로 포트를 당겨 오면 **Vercel이 보낼 것과 똑같은 요청**
(같은 `Origin` 헤더)으로 검증할 수 있습니다. `scripts/deploy-smoke.py`가 그 점검입니다.

```bash
ssh -f -N -L 18000:127.0.0.1:8000 ubuntu@100.97.34.28
.venv/bin/python scripts/deploy-smoke.py http://127.0.0.1:18000 --origin https://heungmap.vercel.app
```

| 점검 | 결과 |
| --- | --- |
| 예측 가능 시군구 | 261개 |
| 잘못된 출처 차단(`same_origin`) | HTTP 403 |
| 모의 로그인·세션 쿠키·역할 선택 | 통과 |
| 기획자 분석 | `method=machine_learning`, `is_mock=false` — **규칙이 아니라 실제 모델** |
| 예측 범위 | 강남구 3일 p10 2,817,563 / p50 3,021,623 / p90 3,240,463 (방문자-일) |
| TreeSHAP 기여 요인 | 5개 |
| 규칙 권고 | 4건 |
| TourAPI 축제 목록·상세 | 20건 조회, 상세 정상 |
| 모델 버전 일치(분석 ↔ 상태카드) | `regional-daily-1.0-ab975d661247` |

공개 주소가 생긴 뒤에는 같은 스크립트를 프론트 주소로 돌려 프록시까지 한 번에 확인합니다.

```bash
python3 scripts/deploy-smoke.py https://heungmap.vercel.app
```

## 5. 공개 통로 — Tailscale Funnel

오라클 VNIC에 **공인 IP가 없습니다**(사설 `10.0.0.9`만). `168.110.104.199`는 아웃바운드 NAT 주소라
외부에서 들어올 수 없습니다. Caddy로 `sslip.io` 자동 HTTPS를 시도했으나 Let's Encrypt 검증 요청이
Caddy에 **한 번도 도착하지 않아** 실패했고, 확인 후 Caddy는 제거했습니다(80/443 반환).

그래서 아웃바운드 연결만 쓰는 **Tailscale Funnel**로 열었습니다.

```bash
# 관리 콘솔: DNS → HTTPS Certificates 켜기, ACL → JSON editor 우측 "Add Funnel to policy" → Save
sudo tailscale funnel --bg 8000
```

공개 DNS 레코드가 문서상 10분 안에 올라와야 하는데 35분이 지나도 생기지 않았습니다.
권위 서버(DNSimple)에 직접 질의해 NODATA를 확인한 뒤 **tailscaled를 재시작**하니 바로 등록됐습니다
(`103.84.155.217`, Funnel 릴레이). 같은 증상이면 재등록이 해법입니다.

```bash
ssh <서버> 'sudo systemd-run --no-block --on-active=2 --unit=ts-restart systemctl restart tailscaled'
```

> tailscaled를 재시작하면 SSH도 끊깁니다. 이 서버는 Tailscale이 유일한 접속 경로이므로
> 반드시 위처럼 **분리 실행**하고 복귀를 확인하세요.

## 6. Google 로그인 연결

```bash
# .env 에 GOOGLE_CLIENT_ID·GOOGLE_CLIENT_SECRET 을 넣고
scripts/oracle/deploy-web.sh ubuntu@100.97.34.28 https://heungmap.vercel.app
```

`deploy-web.sh`가 두 값이 있으면 `HEUNGMAP_AUTH_MODE=google`·`HEUNGMAP_ENV=production`으로 올립니다.

| Google Cloud Console 등록값 | |
| --- | --- |
| 승인된 리디렉션 URI | `https://heungmap.vercel.app/api/v1/auth/google/callback` |
| 승인된 JavaScript 원본 | `https://heungmap.vercel.app` |

`redirect_uri`는 `HEUNGMAP_PUBLIC_ORIGIN`에서 만들어지고 토큰 교환 때도 같은 값을 보내므로
등록값과 **정확히 일치**해야 합니다. google 모드에서는 모의 로그인(`/auth/mock`)이 404로 막힙니다.

## 7. 최종 검증 — 11/11 통과

```bash
python3 scripts/deploy-smoke.py https://heungmap.vercel.app
```

| 점검 | 결과 |
| --- | --- |
| 예측 가능 시군구 | 261개 |
| 인증 모드 | 실제 Google 로그인 |
| 구글 리다이렉트 | 307, 클라이언트 ID·콜백·PKCE·state·nonce 모두 포함 |
| 콜백 주소 일치 | `https://heungmap.vercel.app/api/v1/auth/google/callback` |
| TourAPI 축제 목록·상세 | 20건 조회, 상세 정상 |
| 모델 상태 | `regional-daily-1.0-ab975d661247`, 261개 지역 |

로그인이 필요한 기능(기획자 분석·보고서·공개)은 실계정 로그인 뒤 화면에서 확인합니다.
서버 안에서 모의 로그인으로 돌렸을 때는 `method=machine_learning`·`is_mock=false`로
실제 모델 예측(강남구 3일 p50 약 302만 방문자-일)과 TreeSHAP 요인 5개를 확인했습니다.

### 겪은 함정

- **systemd**: `enable --now`는 이미 돌고 있는 서비스를 재시작하지 않아 `.env` 변경이 반영되지 않습니다.
  `setup-web.sh`에 `restart`를 명시했습니다.
- **리라이트 목적지**: `next.config.ts`의 `rewrites()`는 **빌드 시점**에 값이 박힙니다.
  환경변수가 빈 문자열이면 `??`가 걸러 내지 못해 호스트가 사라지고 Vercel이 `DNS_HOSTNAME_EMPTY`를 냅니다.
  `||`로 바꾸고 배포 환경 기본값을 둬서 환경변수가 없어도 동작하게 했습니다.
- **배포 직후**: 엣지 전파가 끝나기 전 몇 분은 이전 빌드가 섞여 502가 간헐적으로 납니다.
  `deploy-smoke.py`가 5xx를 재시도합니다.

## 운영 명령

```bash
ssh ubuntu@100.97.34.28 'systemctl is-active heungmap-api'
ssh ubuntu@100.97.34.28 'sudo journalctl -u heungmap-api -n 50 --no-pager'
ssh ubuntu@100.97.34.28 'sudo systemctl restart heungmap-api'
ssh ubuntu@100.97.34.28 'tail -1 ~/heungmap-model/data/processed/model-refresh-log.jsonl'
```
