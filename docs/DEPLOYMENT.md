# 개인 서버 배포 계획

## 판단

팀이 보유한 서버는 흥할지도 demo 배포 후보로 사용할 수 있다. 비공개로 전달된 기록에서 Ubuntu 계열
서버 접근 정보와 domain·HTTPS 설정 절차는 확인했지만, CPU·RAM·저장공간, 현재 설치 package와 실제
접속 상태는 확인되지 않았다. 따라서 최종 판단은 아래 사전점검을 통과하는 조건부 `go`다.

서버 주소, domain, 계정, 비밀번호와 key는 저장소·issue·PR·log에 기록하지 않는다. 이 문서에도 실제 값을
남기지 않는다.

## 권장 배포 구조

```text
Internet
   │ 80·443
   ▼
Nginx
   ├─ `/`      → Next.js on 127.0.0.1:3000
   └─ `/api/`  → FastAPI on 127.0.0.1:8000
                         ├─ TourAPI·관광 데이터랩
                         ├─ 규칙 baseline·검증된 model
                         └─ 선택적 외부 LLM API
```

- Nginx가 TLS, request size, timeout과 기본 rate limit을 담당한다.
- frontend와 API를 같은 origin으로 제공해 CORS와 cookie 설정을 단순화한다.
- Next.js와 FastAPI는 별도 systemd service로 실행하고 재부팅 후 자동 시작한다.
- application port 3000·8000은 외부에 공개하지 않고 loopback에서만 listen한다.
- 첫 배포에서는 단일 instance를 사용한다. load balancer, Redis와 Kubernetes는 넣지 않는다.
- LLM은 서버에서 직접 구동하지 않고 외부 API를 선택적으로 호출하므로 GPU는 필요하지 않다.

Next.js 공식 self-hosting 안내도 application server 앞의 reverse proxy 사용을 권장한다. 참고:
[Next.js self-hosting](https://nextjs.org/docs/app/guides/self-hosting),
[Next.js deployment](https://nextjs.org/docs/app/getting-started/deploying).

## 선택한 운영 방식

| 영역 | 첫 배포 | 나중에 검토할 조건 |
| --- | --- | --- |
| frontend | Next.js Node.js server | 완전 정적 UI로 확정될 때 static export |
| backend | FastAPI·Uvicorn | 실제 부하 측정 후 worker 수 조정 |
| process | systemd | 컨테이너 운영 필요와 팀 학습비용이 정당화될 때 Docker Compose |
| proxy·TLS | Nginx | 기존 server 운영 표준이 다를 때 대체 |
| 저장 | 필요 시 SQLite | 동시 쓰기·다중 instance·운영 데이터가 늘 때 PostgreSQL |
| model | CPU 규칙 baseline, 검증된 소형 LightGBM | 지표와 자원 측정 없이 복잡한 model 추가 금지 |
| LLM | 외부 API, timeout·fallback | provider와 비용을 검증한 뒤 활성화 |

SQLite에는 cache·draft·분석 metadata처럼 다시 만들거나 backup할 수 있는 최소 데이터만 둔다. 원본 API
응답, 학습 dataset와 model artifact는 Git에 넣지 않으며 server에서도 보관 위치·권한·삭제 정책을 정한다.

## 서버 사전점검

접속 정보가 있는 것과 application을 안정적으로 구동할 수 있는 것은 다르다. 배포 전에 server 안에서
다음을 확인하고 실제 결과를 비공개 운영 기록에 남긴다.

```bash
cat /etc/os-release
nproc
free -h
df -h
python3 --version
node --version
nginx -v
systemctl --failed
ss -lntup
```

팀의 작은 단일-instance demo 기준 권장 여유치는 2 CPU core, RAM 4 GB, application·build·log용 여유
storage 20 GB다. 이는 서버의 확인된 사양이 아니라 초기 운영 판단 기준이다. RAM이 부족하면 Next.js build는
로컬 또는 CI에서 수행하고 server에는 build artifact만 전달하는 방식을 검토한다.

### go 조건

- 지원 중인 Ubuntu release와 보안 update를 적용할 수 있다.
- Node.js가 선택한 Next.js version의 최소 요구사항을 충족한다.
- Python 3.11 virtual environment와 service account를 만들 수 있다.
- Nginx가 80·443을 사용하고 application port는 외부에서 차단된다.
- domain DNS와 TLS certificate 갱신 경로를 확인한다.
- RAM·disk가 build와 두 process를 동시에 감당한다.
- outbound HTTPS로 TourAPI·관광 데이터랩·선택적 LLM API를 호출할 수 있다.
- `.env`를 repository 밖에 두고 service만 읽도록 권한을 제한할 수 있다.
- log rotation, SQLite 또는 필요한 운영 데이터 backup·복구 방법이 있다.

하나라도 충족하지 못하면 즉시 cloud로 옮기기보다 부족 항목, 해결 비용과 대체 hosting을 비교해 별도
결정으로 기록한다.

## 배포 전후 확인

### 배포 전

- [ ] server 사양·OS·설치 service 확인
- [ ] domain·DNS·TLS 갱신 확인
- [ ] production 환경 변수 이름만 목록화하고 값은 안전하게 저장
- [ ] frontend build, backend test와 OpenAPI contract 검증 통과
- [ ] database migration·backup이 필요하면 rollback 절차 준비
- [ ] Nginx와 systemd 설정 review

### 배포 후

- [ ] `/api/v1/health` 200 확인
- [ ] 실제 TourAPI 행사 목록과 한국관광공사 출처 표시 확인
- [ ] 기획자 입력→규칙 결과와 사용자 캘린더→지도→상세 smoke test
- [ ] prediction unavailable·외부 API 오류 fallback 확인
- [ ] HTTPS, mobile 화면, log와 재부팅 후 자동 시작 확인

실제 서버 접속, 방화벽·Nginx·systemd 변경, 재시작과 첫 production 배포는 별도 실행 작업이다. 실행 직전에
대상과 rollback을 확인하고 명시적인 승인을 받은 뒤 진행한다.
