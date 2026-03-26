# 개발 진행상황

> 최종 업데이트: 2026-03-26 (v0.9)

---

## 완료된 작업

### v0.1 — 초기 구현 (`83519d1`)
- [x] customtkinter 기반 채팅형 GUI 구현
- [x] 상태머신 (`INIT → AWAITING_CONFIRM → INSTALLING → DONE`)
- [x] JS 타이머 앱 시나리오 (Node.js + VSCode) 첫 구현
- [x] winget을 통한 자동 설치 및 앱 실행 기능

### v0.2 — 모듈화 리팩터링 (`4144fae`)
- [x] `core/safety.py` — 화이트리스트 + 블랙리스트 이중 명령어 검사
- [x] `core/runner.py` — subprocess 실행 + 실시간 stdout 스트리밍
- [x] `installers/base.py` / `winget.py` — OS별 패키지 관리자 추상화
- [x] `scenarios/` — Scenario / PackageSpec / LaunchSpec 데이터 클래스 + 레지스트리

### v0.3 — 테스트 스위트 (`6470c9f`)
- [x] safety / runner / scenarios / installers 모듈 단위 테스트
- [x] 총 52개 테스트 전 통과

### v0.4 — 빌드 및 버그 수정 (`6db8ed3`)
- [x] `DevSetupAssistant.spec` — PyInstaller 빌드 설정
- [x] customtkinter 5.2.2 + Windows 11 타이틀바 색상 버그 패치

### v0.5 — LLM 연동 + A/B/C/F 기능 (`af2e382`)
- [x] **A. 환경 자동 감지** — `core/env_detector.py`, 14개 도구 감지 후 LLM 컨텍스트 제공
- [x] **B. 스트리밍 응답** — `core/llm.py`, JSON `message` 필드를 글자 단위 실시간 emit
- [x] **C. LLM 설정 UI** — `ui/settings_dialog.py`, ⚙ 버튼으로 프로바이더·API 키 변경
- [x] **F. 설치 이력** — `core/history.py`, `history.json` 기록 + LLM 컨텍스트 갱신
- [x] 멀티 프로바이더 지원: Anthropic Claude / OpenAI GPT / Google Gemini / Ollama
- [x] 웹 개발환경 시나리오 추가 (`scenarios/windows/web_dev.py`, 스택·에디터 2단계 선택)
- [x] 전체 90개 테스트 통과

### v0.6 — 컨테이너 연동(D) + 이미지 첨부(E) (`424042c`)
- [x] **D. 컨테이너 연동**
  - `core/container.py`: Docker 설치·실행 감지, 컨테이너 목록 조회
  - `.devcontainer/devcontainer.json` 자동 생성 (VS Code / Cursor 자동 인식)
  - `enter-dev.bat` / `enter-dev.sh` 진입 스크립트 자동 생성
  - Windows Terminal 프로파일 자동 등록
  - `core/ide_connector.py`: VS Code / Cursor 감지 + 워크스페이스 자동 열기
  - 수동 조작 필요 시 단계별 안내 메시지 제공
  - `core/actions.py`: `ContainerSetupAction` 추가
  - `core/safety.py`: `docker`, `docker-compose`, `podman`, `wsl` 허용
- [x] **E. 이미지 첨부 (스크린샷 LLM Q&A)**
  - `ui/image_handler.py`: `Ctrl+V` 클립보드 이미지 감지, 파일 선택 로드, base64 인코딩
  - `core/llm.py`: Anthropic / OpenAI / Gemini / Ollama 4개 프로바이더 비전 지원
  - `app.py`: 📎 버튼, 이미지 미리보기 프레임 (숨김/표시 토글)
  - Pillow 미설치 시 자동 비활성화
- [x] `requirements.txt`: Pillow >= 10.0.0 추가
- [x] `tests/test_container.py`: 55개 테스트 추가 → 전체 **145개 통과**

### v0.7 — 주제 가드 (`732efe5`)
- [x] **방법 1**: 시스템 프롬프트에 TOPIC GUARD 섹션 추가
  - `topic_valid` 필드를 JSON 응답 스키마에 포함
  - 개발환경 외 질문은 `topic_valid=false` + 거부 문장만 반환하도록 지시
- [x] **방법 4**: 스트리밍 후 응답 교체
  - 스트리밍 시작 직전 텍스트박스 인덱스 저장
  - `topic_valid=false` 감지 시 해당 범위 삭제 → 고정 거부 메시지 표시
  - LLM이 이미 스트리밍한 내용도 사용자에게 노출되지 않음
- [x] `core/llm.py`: `LLMResponse.topic_valid` 필드 추가, `_parse_response` 반영
- [x] `tests/test_topic_guard.py`: 14개 테스트 추가 → 전체 **159개 통과**

### v0.8 — AI 코드 에이전트 설치 지원 (`a97d55e`)
- [x] **G. AI 코드 에이전트 설치**
  - 지원 에이전트: Claude Code / OpenAI Codex CLI / Gemini CLI / Aider / GitHub Copilot CLI
  - `core/safety.py`: `claude`, `codex`, `gemini`, `aider`, `gh`, `cursor` 화이트리스트 추가
  - `core/actions.py`: `SetEnvAction` 추가 — LLM이 API 키 등록 액션 제안 가능
  - `app.py`: `_SecureInputDialog` (마스킹 입력), `_set_system_env` (레지스트리/셸 프로파일 영속 저장), `_validate_set_env` (환경변수명 화이트리스트 검증), `_prompt_env_key` (백그라운드-메인스레드 이벤트 동기화)
  - `app.py`: `_start_installation` — `InstallAction` 없이 `RunAction`만 있어도 설치 진행 가능
  - `scenarios/ai_agents.py`: `AIAgentsScenario` — Windows / macOS / Linux 크로스 플랫폼
  - `scenarios/registry.py`: `AIAgentsScenario` 등록
  - `tests/test_ai_agents.py`: 40개 테스트 추가 → 전체 **199개 통과**

### v0.9 — 데이터베이스 CLI + 환경변수 지원 (`8c8468f`)
- [x] **H. 데이터베이스 지원**
  - `core/safety.py`: DB CLI 실행 파일 화이트리스트 추가
    - PostgreSQL: `psql`, `pg_ctl`, `createdb`, `dropdb`, `initdb`
    - MySQL: `mysql`, `mysqladmin`, `mysqldump`
    - MongoDB: `mongod`, `mongosh`, `mongo`
    - Redis: `redis-cli`, `redis-server`
    - SQLite: `sqlite3`
  - `app.py`: `_ALLOWED_ENV_KEYS`에 DB 연결 환경변수 추가
    - `DATABASE_URL`, `POSTGRES_URL`, `POSTGRES_PASSWORD`
    - `MYSQL_URL`, `MYSQL_ROOT_PASSWORD`, `MYSQL_PASSWORD`
    - `MONGODB_URL`, `MONGO_INITDB_ROOT_PASSWORD`
    - `REDIS_URL`, `REDIS_PASSWORD`
  - Docker 방식은 기존 `ContainerSetupAction`으로 완전 지원 (변경 없음)
  - `tests/test_ai_agents.py`: DB 테스트 14개 추가 → 전체 **213개 통과**

---

## 아키텍처 요약

```
사용자 입력 (텍스트 / 이미지)
    │
    ▼
app.py  ── 상태머신 (CHATTING / AWAITING_CONFIRM / INSTALLING)
    │
    ├─► core/llm.py          멀티 프로바이더 LLM 클라이언트 (스트리밍, 비전)
    │       └── TOPIC GUARD  topic_valid=false → 앱이 응답 교체
    │
    ├─► core/actions.py      Install / Run / Launch / ContainerSetup / SetEnv 액션
    │
    ├─► core/safety.py       화이트리스트 + 블랙리스트 이중 검사 (AI 에이전트·DB CLI 포함)
    │
    ├─► core/runner.py       subprocess 실행 + stdout 스트리밍
    │
    ├─► core/container.py    Docker 감지 / devcontainer.json / 진입 스크립트
    │
    ├─► core/ide_connector.py  IDE 감지 / 워크스페이스 열기 / 안내 메시지
    │
    ├─► core/env_detector.py   설치 도구 자동 감지 → LLM 컨텍스트
    │
    ├─► core/history.py        설치 이력 → LLM 컨텍스트
    │
    ├─► installers/winget.py   winget 명령어 생성
    │
    ├─► scenarios/ai_agents.py  AI 코드 에이전트 시나리오 (크로스 플랫폼)
    │
    └─► ui/
            settings_dialog.py   LLM 설정 다이얼로그
            image_handler.py     클립보드·파일 이미지 → base64
            (_SecureInputDialog)  API 키·DB 비밀번호 마스킹 입력 (app.py 내)
```

---

## 알려진 이슈

| 상태 | 설명 | 해결 |
|:---:|------|------|
| 해결됨 | customtkinter 5.2.2 + Windows 11 타이틀바 색상 버그 | `app.py` 런타임 패치 |
| 부분 대응 | winget 출력 인코딩 (UTF-16LE / UTF-8 혼용) | `mbcs` fallback 적용 |
| 한계 | 주제 가드 — 적극적 프롬프트 조작은 방어 불가 | 방법 3(가드 LLM) 추가 시 개선 가능 |

---

## 로드맵

| 우선순위 | 항목 |
|:---:|------|
| 높음 | macOS (brew) 인스톨러 구현 |
| 높음 | Linux (apt) 인스톨러 구현 |
| 중간 | 추가 시나리오: Java Spring, Rust, Go 등 |
| 중간 | 주제 가드 방법 3 (가드 LLM 호출) 추가 |
| 중간 | DB 서비스 기동/중지 지원 (Windows 서비스 관리) |
| 낮음 | 앱 아이콘 (.ico) 적용 |
| 낮음 | README 스크린샷 추가 |
