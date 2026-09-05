# 확정 기술 스택과 폴더 구조

EVENT-US 수준의 캘린더·지도 상호작용, Python 예측 pipeline과 개인 Ubuntu 서버 배포를 함께 고려해 첫
application 스택을 확정합니다. 학습 model과 LLM은 데이터·품질 gate를 통과한 경우에만 활성화합니다.

## 선택한 기술

| 영역 | 선택 | 사용 범위 |
| --- | --- | --- |
| 데이터·모델·API 언어 | Python 3.11+ | 수집, 학습과 serving을 같은 생태계에서 유지 |
| 데이터 처리 | pandas, requests | 표 형식 조립과 HTTP 수집 |
| 예측 모델 | 규칙 baseline, 이후 LightGBM·scikit-learn | 시간·group 검증에서 baseline보다 나을 때만 학습 model 채택 |
| 모델 설명 | 규칙 근거, 이후 SHAP | 검증된 model의 개별 영향 요인만 표시 |
| backend API | FastAPI·Pydantic | Python 추론 통합과 OpenAPI 3.1 contract 생성 |
| frontend | Next.js App Router·TypeScript | 캘린더·지도·URL 상태와 반응형 UI 구현 |
| 지도 | Kakao Map JavaScript SDK | 국내 위치·주차·숙소 표현 |
| 설명 생성 | 공급자 중립 내부 계약 + Ollama `qwen3.5:9b` 기본 adapter | 로컬 structured output, timeout·idempotency·검증·fallback 제공; OpenAI는 선택 adapter |
| 공통 계약 | OpenAPI 3.1.0·JSON Schema 2020-12 | Python·TypeScript 사이 단일 API schema |
| 초기 저장 | SQLite 또는 저장 없음 | cache·draft가 필요할 때만 SQLite 추가 |
| 서버 | Ubuntu·Nginx·systemd | 단일 개인 서버, 같은 origin으로 frontend·API 제공 |
| 협업 | GitHub | branch와 pull request 기반 검토 |

### Next.js를 선택한 이유

- 캘린더·지도 marker·filter·URL 상태를 EVENT-US 공개 동작에 가깝게 구현하기 쉽습니다.
- 기획자 form과 사용자 탐색을 같은 design system과 routing에서 유지할 수 있습니다.
- TypeScript client를 OpenAPI에서 생성해 두 담당자의 response type 중복을 줄일 수 있습니다.
- Streamlit은 data spike와 내부 model demo에는 빠르지만 목표 UI·반응형·상태 동기화의 제약이 커서 제품
  frontend에서는 제외합니다.

공통 schema는 [`SHARED_SPEC.md`](SHARED_SPEC.md), 개인 서버 배포 조건은
[`DEPLOYMENT.md`](DEPLOYMENT.md)를 따릅니다.

## 목표 폴더 구조

```text
heungmap/
├─ README.md, .gitignore, .env.example
├─ docs/                # 제품·데이터·기술 명세
├─ contracts/           # OpenAPI와 mock fixture
├─ data/
│  ├─ raw/              # API 원본, Git 제외
│  └─ processed/        # 학습표, Git 제외
├─ scripts/             # 데이터 수집·조립
├─ model/               # 학습·평가·추론
├─ backend/             # FastAPI
└─ frontend/            # Next.js App Router·TypeScript
```

코드 디렉터리는 해당 단계가 시작될 때 생성합니다. 현재 저장소에는 문서·공통 계약과 데이터 경로만
있습니다.

## 로컬 환경 기준

- Python 3.11 이상과 가상 환경
- 데이터 단계: pandas, requests, python-dotenv
- 모델 단계: lightgbm, scikit-learn, shap
- API 단계: fastapi, uvicorn
- 선택한 Next.js version이 요구하는 Node.js version. scaffolding 때 exact version을 lockfile과 README에 기록

실제 의존성은 사용하는 단계에 맞춰 lockfile에 고정하고, 설치와 검증 명령을 README에 추가합니다.
