# 배포 구조와 실행 기록

현재 구조(2026-10-15 이관 이후)를 먼저 적고, 2026-09-20 첫 배포 때 실제로 실행한 것과 겪은 함정은 뒤에 기록으로 남깁니다. 서버 주소·계정·경로는
`<서버>`·`<데이터 폴더>`로 적고, compose·systemd·이미지 빌드 정의는 비공개 인프라 저장소에서 관리합니다. 백엔드 공개 주소는 Vercel 환경변수
`HEUNGMAP_BACKEND_URL`에만 둡니다.

## 현재 구조 (2026-10-15 이후)

```text
브라우저
   │ https://heungmap.vercel.app
   ▼
Vercel (Next.js, GitHub main 연동 자동 배포)   ← next.config.ts의 rewrites가 /api/v1/* 를
   │ /api/v1/*                                    백엔드로 서버측 프록시한다(브라우저에는 같은 origin).
   ▼
Caddy (단일 ARM64 VM의 진입점, Let's Encrypt 자동 인증서)   ← https://heungmap.ssumcp.duckdns.org
   ▼
Docker Compose 프로젝트 heungmap
   ├─ api      FastAPI(uvicorn worker 1), 이미지 heungmap:<커밋 12자리>, 메모리 상한 512MB, healthcheck /api/v1/health
   └─ refresh  같은 이미지, 매일 04:30 KST systemd 타이머가 한 번 실행(상세: ORACLE_MODEL_REFRESH.md)
          │
          └─ <데이터 폴더> = 컨테이너 /app/data  (raw/ 원본, processed/ 모델·기록, db/ SQLite)
```

- 서버는 1 vCPU·약 6GB RAM의 ARM64 VM 한 대이고, 다른 개인 프로젝트들과 Caddy 하나를 공유합니다. 이 저장소에서 알아야 하는 것은 컨테이너 안이
  저장소 구조 그대로(`/app/backend`, `/app/contracts`, `/app/data`)라는 점과, 모델·원본·DB가 이미지 밖 폴더에 있다는 점입니다.
- **백엔드를 Vercel에 올릴 수 없는 이유**: pandas·LightGBM·scikit-learn 의존성이 Vercel 파이썬 함수의 압축 해제 250MB 한도를 넘고, 24MB 모델 artifact를
  동봉할 수 없으며, SQLite 쓰기가 필요하고, 매일 재학습한 새 모델을 읽어야 합니다.
- CI(`.github/workflows/ci.yml`)는 테스트·타입검사·빌드만 하고 이미지를 만들거나 서버에 접속하지 않습니다. 백엔드 반영은 아래 수동 절차입니다.

### 백엔드 반영 절차

1. **빌드(맥, ARM64)**: 비공개 인프라 저장소의 빌드 스크립트가 이 공개 저장소를 임시 폴더에 clone해 **지정한 커밋**을 detached checkout하고(작업 트리가
   깨끗한지 검사), `docker buildx build --platform linux/arm64`로 `heungmap:<커밋 12자리>` 이미지를 만든 뒤 `docker save`로 tar를 남깁니다. 이미지 라벨
   `org.opencontainers.image.revision`에 전체 커밋 해시가 들어갑니다. 의존성은 `backend/requirements-model.txt`를 전이 의존성까지 고정한 제약 파일로 설치하므로
   `requirements*.txt`가 바뀐 커밋은 제약 파일도 같이 갱신해야 빌드됩니다.
2. **전송·적재**: tar를 `<서버>`로 복사해 `docker load`. 이전 태그 이미지는 롤백용으로 서버에 남겨 둡니다.
3. **태그 변경**: compose 파일의 `api`·`refresh` 두 서비스 `image:` 태그를 새 커밋으로 바꿉니다(바꾸기 전 파일 백업). 이 변경은 비공개 인프라 저장소에
   커밋합니다.
4. **재시작**: `docker compose up -d api`. `refresh`는 다음 타이머 실행부터 새 이미지를 씁니다. 재학습 코드가 바뀐 날은
   `sudo systemctl start heungmap-refresh.service`로 한 번 바로 돌려 기록을 확인합니다.
5. **확인**(모두 공개 주소로):

   ```bash
   curl -s https://heungmap.ssumcp.duckdns.org/api/v1/health                 # 200 {"status":"ok","service":"heungmap-api",...}
   curl -s https://heungmap.ssumcp.duckdns.org/api/v1/system/model-status    # status ready, adopted true, adoption_mode, last_predictable_target_date
   curl -s https://heungmap.vercel.app/api/v1/health                          # Vercel rewrite가 백엔드에 닿는지
   python3 scripts/deploy-smoke.py https://heungmap.vercel.app                # 예측 가능 시군구·로그인 리다이렉트·TourAPI·모델 버전 일치
   ```

6. **롤백**: compose의 태그를 이전 커밋으로 되돌리고 `up -d api`. 데이터 폴더는 이미지와 분리돼 있어 롤백해도 모델·DB는 그대로입니다.

### 운영 중 확인

```bash
ssh <서버> 'sudo docker compose -f <compose 파일> ps'                          # api healthy
ssh <서버> 'sudo docker logs --tail 50 heungmap-api-1'                           # API 로그(json-file 10MB×3 회전)
ssh <서버> 'sudo journalctl -u heungmap-refresh -n 40 --no-pager'                # 재학습 실행 출력·종료 코드
ssh <서버> 'tail -1 <데이터 폴더>/processed/model-refresh-log.jsonl'               # 그날의 재학습 판단
```

재학습 기록을 읽는 법과 종료 코드의 뜻은 [ORACLE_MODEL_REFRESH.md](ORACLE_MODEL_REFRESH.md)에 있습니다. 실패 알림은 따로 없고 `systemctl --failed`와
`model-status`로 확인합니다.

## 프론트 배포 (Vercel)

Vercel 프로젝트가 GitHub `ghdtjdwn/heungmap`의 `main`에 연결돼 있어 PR이 `main`에 머지되면 자동으로 production 배포됩니다(Root Directory `frontend`).
프리뷰 빌드는 Ignored Build Step으로 건너뛰므로 PR마다 빌드가 돌지 않습니다. 다시 올려야 하면 Vercel 대시보드의 Redeploy를 씁니다.

- 환경변수 `KAKAO_JAVASCRIPT_KEY`, `HEUNGMAP_BACKEND_URL`은 Production에 둡니다. `next.config.ts`가 `KAKAO_JAVASCRIPT_KEY`를 환경변수에서 먼저 읽고
  없을 때만 `../.env`를 보기 때문에 저장소 루트 `.env`가 없는 Vercel에서도 빌드됩니다.
- `rewrites()`는 **빌드 시점**에 값이 박힙니다. `HEUNGMAP_BACKEND_URL`이 없으면 빌드가 바로 실패하게 했고, 빈 문자열은 `||`로 걸러 냅니다(아래 함정 참고).
- Google 로그인: Google Cloud Console의 승인된 리디렉션 URI `https://heungmap.vercel.app/api/v1/auth/google/callback`, JavaScript 원본
  `https://heungmap.vercel.app`. `redirect_uri`는 백엔드의 `HEUNGMAP_PUBLIC_ORIGIN`에서 만들어지고 토큰 교환 때도 같은 값을 보내므로 등록값과 정확히
  일치해야 합니다. google 모드에서는 모의 로그인(`/auth/mock`)이 404로 막힙니다.

## 2026-09-20 첫 배포 기록

이관 전 구조는 서버에 직접 만든 Python 가상환경 + systemd 서비스 + 사용자 crontab이었고, 공개 통로는 Tailscale Funnel이었습니다. 지금은 쓰지 않지만
검증 방법과 함정은 그대로 유효해서 남깁니다.

### 끝난 것

1. **재학습 cron 고장 수리**: 9/18·9/19 이틀 연속 `Permission denied`. crontab이 스크립트를 실행 파일로 직접 불렀는데 `scripts/model-refresh.sh`에
   실행 권한(`+x`)이 없었습니다. 9/18 설치 검증은 `sh 스크립트` 형태로 돌려 이 경로를 지나쳤습니다. cron 줄을 `/bin/sh <스크립트>`로 등록하도록 고치고,
   저장소의 `.sh`에 실행 권한을 부여(`git update-index --chmod=+x`)한 뒤 cron과 같은 최소 환경(`env -i`)에서 종료 코드 0을 확인했습니다.
2. **백엔드 배포**: `scripts/oracle/deploy-web.sh`로 폴더 하나에 전용 Python 3.12 가상환경을 만들고 systemd 서비스(`127.0.0.1:8000`, `Nice=5`,
   uvicorn worker 1개)로 올렸습니다. **worker 1개 고정** 이유: `app.main`이 분석 결과를 프로세스 메모리(`analysis_cache`)에 들고 있어 worker를 늘리면
   "분석 → 공개" 흐름이 로컬과 달라집니다(지금의 컨테이너도 같은 이유로 worker 1개). 서비스의 `data/processed`는 재학습 폴더를 심볼릭 링크로 공유해 새 채택본이
   자동 반영되게 했습니다(지금은 같은 데이터 폴더를 두 컨테이너가 마운트).
3. **로컬과의 동작 일치**: 서버에서 `pytest backend/tests` 172 passed(당시), `verify_daily_model.py` 출처 checksum 4건·홀드아웃 재계산 300행·261개
   시군구 전부 예측 가능·온라인 예측 평균 0.026초.
4. **프론트 배포**: 당시에는 `vercel --prod`로 CLI 배포했고, 2026-11-09부터 GitHub 연동 자동 배포로 바꿨습니다(위 "프론트 배포").
5. **실사용 흐름 검증 15/15**: 공개 통로가 생기기 전에 사설망으로 포트를 당겨 와 Vercel이 보낼 것과 같은 요청(같은 `Origin`)으로 `scripts/deploy-smoke.py`를
   돌렸습니다. 예측 가능 시군구 261, 잘못된 출처 403, 모의 로그인·세션·역할 선택 통과, 기획자 분석 `method=machine_learning`·`is_mock=false`,
   강남구 3일 p10 2,817,563 / p50 3,021,623 / p90 3,240,463(방문자-일), TreeSHAP 요인 5개, TourAPI 목록·상세 정상, 분석↔상태카드 모델 버전 일치
   (`regional-daily-1.0-ab975d661247`).
6. **공개 통로**: 당시 서버에 공인 IP가 없어 Caddy + Let's Encrypt가 실패했고(검증 요청이 도착하지 않음) 아웃바운드만 쓰는 Tailscale Funnel로 열었습니다.
   공개 DNS 레코드가 35분이 지나도 생기지 않아 권위 서버에 NODATA를 확인한 뒤 tailscaled를 재시작하니 바로 등록됐습니다. 이관 뒤에는 공인 IP가 있는 서버의
   Caddy가 TLS를 종료합니다.
7. **Google 로그인 연결과 최종 검증 11/11**: `scripts/deploy-smoke.py https://heungmap.vercel.app` — 예측 가능 시군구 261, 실제 Google 로그인
   리다이렉트 307(클라이언트 ID·콜백·PKCE·state·nonce 포함), 콜백 주소 일치, TourAPI 목록·상세 정상, 모델 상태 261개 지역.

### 겪은 함정

- **systemd**: `enable --now`는 이미 돌고 있는 서비스를 재시작하지 않아 `.env` 변경이 반영되지 않습니다. 배포 스크립트에 `restart`를 명시했습니다.
- **리라이트 목적지**: `next.config.ts`의 `rewrites()`는 빌드 시점에 값이 박힙니다. 환경변수가 빈 문자열이면 `??`가 걸러 내지 못해 호스트가 사라지고 Vercel이
  `DNS_HOSTNAME_EMPTY`를 냅니다. `||`로 바꿔 빈 값을 걸러 내고, Vercel 빌드에서 `HEUNGMAP_BACKEND_URL`이 없으면 바로 실패하게 했습니다.
- **배포 직후**: 엣지 전파가 끝나기 전 몇 분은 이전 빌드가 섞여 502가 간헐적으로 납니다. `deploy-smoke.py`가 5xx를 재시도합니다.
- **원격 데몬 재시작**: 유일한 접속 경로인 데몬을 재시작하면 SSH도 끊깁니다. `systemd-run --on-active=<초>`로 분리 실행하고 복귀를 확인합니다.
