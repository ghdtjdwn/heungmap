# 다음 세션 인계

## 2026-09-15 종료 시점

- 현재 서비스 기본 예측은 `regional-daily-1.0-3e0451e58b0c` D-30 지역 방문자-일 모델입니다.
- 원본·학습표·모델 artifact는 Git 제외 경로에 있으며, 소스·계약·평가 문서·테스트만 GitHub로 전달합니다.
- GitHub 전달 PR 번호와 병합 결과는 이번 종료 작업에서 확인해 아래 전달 상태에 기록합니다.
- 기존 로컬 `frontend/next-env.d.ts`의 `.next/dev/types` 변경은 생성 파일이므로 이번 전달에서 제외해 보존합니다.

## 구현·데이터 범위

- 한국관광공사 지역별 방문자 원본 471,355행을 검증해 완전한 지역·일 157,110행을 만들었습니다.
- 목표일 60일 전까지의 이력, 전년도 같은 요일과 최근 연간 성장률 기준선, 최대40% LightGBM 잔차 보정으로
  행사기간 시군구 방문자-일 합계와 p10/p50/p90 범위를 제공합니다.
- 2026-08-01~15 시간 홀드아웃 3,510행에서 WAPE3.809%, 중앙 절대비율오차3.351%, ±20% 이내97.81%,
  80% 구간 포함률78.21%를 관측해5개 채택 조건을 모두 통과했습니다.
- 문체부 공식 지역축제 ZIP 2017~2026년10개·10,198행을 직접 수집했습니다. 축제별 관람객 후보 모델은
  중앙 절대비율오차가 전년도 기준보다 나빠 미채택으로 봉인했고 제품에 연결하지 않았습니다.
- 기획 분석·공개·방문객 상세는 같은 모델 버전·prediction ID·방문자-일 범위를 공유합니다. LLM은 모델
  수치를 바꾸거나 지역 방문자-일을 축제 관람객으로 환산하지 않습니다.

## 실제 검증

- backend 전체: `118 passed`(기존 deprecation 경고3건).
- frontend: TypeScript 검사, ESLint, Next.js production build 통과.
- Playwright desktop·mobile: `23 passed`.
- 실제 채택 artifact와 격리 SQLite에서 체험 로그인 → 기획 분석200 → 공개200 → 방문객 예측 조회를 확인했습니다.
- 문체부 수집 스크립트로 2026 ZIP을 재수집해 SHA-256이 기존 원본과 일치함을 확인했습니다.
- 실제 Google 계정, Windows, 원격 CI와 운영 배포는 검증하지 않았습니다.

## 다음 세션 시작

1. `AGENTS.md`, `docs/00_START_HERE.md`, 이 문서와 `docs/MODEL_EVALUATION.md`를 읽습니다.
2. `git status --short --branch`, GitHub PR·Actions 상태와 병합된 commit을 다시 확인합니다.
3. Git에서 제외된 `data/processed/daily-forecast-production-v3/`가 로컬에 있는지 확인합니다.
4. 로컬 실행은 저장소 루트에서 backend, `frontend/`에서 frontend를 각각 시작합니다.

```bash
PYTHONPATH=backend .venv/bin/uvicorn app.main:app --reload --port 8000
cd frontend && npm run dev
```

## 제출·운영 전 남은 일

- 발표에서는 `축제 관람객 정확도`가 아니라 `D-30 시군구 방문자-일 최근 시간 홀드아웃`으로 설명합니다.
- 실제 서버에는 Git에서 제외된 23MB 모델 artifact를 별도 복사하고 `HEUNGMAP_DAILY_MODEL_DIR`을 설정합니다.
- 두 팀원의 공통 계약·표현 검토, Windows 재현, 새 날짜 전향 평가, 실제 Google 설정과 배포 smoke가 남았습니다.
- 현재 원본으로 마지막 계산 가능한 목표일은 2026-10-14입니다. 새 방문자 자료가 공개되면 append-only 원본으로
  수집하고 기존 결과 폴더를 덮어쓰지 않은 채 재학습합니다.
- 비밀값·원본/가공 데이터·SQLite·모델·가상환경·캐시·빌드 결과는 계속 Git과 개인 작업 로그에서 제외합니다.

## GitHub 전달 상태

- 이번 모델 변경 PR: 종료 작업에서 생성 후 번호와 병합 commit을 기록할 예정입니다.
