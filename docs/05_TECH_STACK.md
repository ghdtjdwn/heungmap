# 05. 기술 스택 & 폴더 구조 (제안 — 다음 세션에서 최종 확정)

> 팀이 초심자이므로 **러닝커브가 낮고 자료 많은 스택** 우선. 아래는 제안이며, 첫 세션에서 팀 상황(특히 프론트 경험/시간) 보고 확정.

## 추천 스택
| 영역 | 추천 | 이유 / 대안 |
|---|---|---|
| 언어(데이터/모델/백엔드) | **Python** | 데이터·ML·백엔드를 한 언어로 |
| 데이터 처리 | pandas, requests | 표 다루기·API 호출 |
| 예측 모델(Tier1) | **LightGBM**(or XGBoost), scikit-learn | 표 데이터에 강함·튜토리얼 풍부 |
| 설명가능성(Tier2) | **SHAP** | 예측 근거 시각화 |
| 백엔드 API | **FastAPI** | 파이썬이라 러닝커브 최소 |
| 프론트엔드 | **Next.js(React)** *또는* **Streamlit** | Next.js=제품 UI·확장성 / Streamlit=빠른 MVP·단일 Python 스택 |
| 지도 | **Kakao Map JS SDK** | 국내 주차/장소 표시에 적합(한국어) |
| LLM(Tier2 리포트) | **Claude API** (`claude-sonnet` 등) | 보완 피드백 생성 |
| 협업 | GitHub | 공개 저장소에서 branch와 pull request로 검토 |

### 프론트 선택 가이드
- **제품 UI와 확장성 우선** → Next.js + FastAPI 분리형. 빠른 검증이 더 중요하면 Streamlit 단일 앱으로 시작한다.
- **검증 속도 우선** → Streamlit로 Tier 0를 검증하고, 제품 UI 요구가 확정된 뒤 Next.js로 이관.
- 2인·8주 일정에서는 데이터 파이프라인과 예측 정확도를 먼저 검증한다.

## 제안 폴더 구조 (모노레포)
```
heungmap/
├─ README.md, .gitignore, .env.example
├─ docs/                # 기획·규정·로드맵 (현재 폴더)
├─ data/
│  ├─ raw/              # API 원본 (gitignore)
│  └─ processed/        # train.csv 등 (gitignore)
├─ scripts/             # 데이터 수집·조립 스크립트 (스파이크/파이프라인)
├─ model/               # 학습·평가·추론 (Tier1~2)
├─ backend/             # FastAPI (예측 API 서빙)
└─ frontend/            # Next.js 또는 streamlit_app/
```
> 위 코드 디렉터리는 구현 단계에서 생성한다. 현재는 docs/data만 존재한다.

## 환경 셋업 메모 (첫 세션에서)
- Python 3.11+ 설치 확인 → `python -m venv .venv` → 활성화 → `pip install pandas requests lightgbm scikit-learn shap fastapi uvicorn python-dotenv`
- Node 20+ (Next.js 쓸 경우)
- Python 없거나 설치 번거로우면 **데이터 스파이크는 Google Colab**으로 먼저 시작 가능.
