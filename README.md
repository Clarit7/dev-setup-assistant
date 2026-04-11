# 개발환경 세팅 도우미 (DevSetupAssistant)

채팅형 GUI에서 LLM과 대화하며 개발환경을 자동으로 구성하는 데스크톱 앱입니다.
무엇을 만들고 싶은지 자유롭게 입력하면, 필요한 도구를 설치하고 Docker 컨테이너까지 세팅합니다.
AI 코드 에이전트(Claude Code, Codex CLI, Gemini CLI, Aider 등)와 데이터베이스(PostgreSQL, MySQL, MongoDB, Redis)도 지원합니다.

---

## 주요 기능

| 기능 | 설명 |
|------|------|
| **A. 환경 자동 감지** | 앱 시작 시 설치된 도구(Node.js, Python, Git, Docker 등)와 실행 중인 컨테이너를 자동 감지하여 LLM에 컨텍스트로 제공 |
| **B. 스트리밍 응답** | LLM 응답을 글자 단위로 실시간 표시 |
| **C. LLM 설정 UI** | ⚙ 버튼으로 프로바이더·API 키·모델을 GUI에서 변경. 프로바이더 선택 시 사용 가능한 모델 목록을 API에서 자동으로 불러와 드롭다운으로 선택 |
| **D. 컨테이너 연동** | Docker 이미지 pull·컨테이너 생성, `.devcontainer/devcontainer.json` 자동 생성, 진입 스크립트(`enter-dev.bat` / `enter-dev.sh`), Windows Terminal 프로파일 자동 등록, VS Code·Cursor 워크스페이스 자동 열기 |
| **E. 이미지 첨부** | 스크린샷을 `Ctrl+V`로 붙여넣거나 📎 버튼으로 파일 선택, 파일을 드래그앤드롭 → LLM 비전 API로 문제 분석 |
| **F. 설치 이력** | 설치 결과를 `history.json`에 기록하여 LLM이 중복 설치를 피할 수 있도록 컨텍스트 제공 |
| **G. AI 에이전트 설치** | Claude Code / OpenAI Codex CLI / Gemini CLI / Aider / GitHub Copilot CLI 설치 + API 키를 마스킹 다이얼로그로 수집하여 시스템 환경변수에 영속 등록 |
| **H. DB 지원** | PostgreSQL / MySQL / MongoDB / Redis / SQLite CLI 허용, DB 연결 환경변수(`DATABASE_URL` 등) `SetEnvAction`으로 등록 가능, Docker 컨테이너 방식 완전 지원 |
| **I. 관리자 권한 자동 실행** | 앱 시작 시 UAC 프롬프트를 자동으로 표시하고 관리자 권한으로 재실행. winget 등 시스템 설치 도구가 권한 문제 없이 동작 |
| **J. 패키지 자동 설치** | LLM 프로바이더 패키지(anthropic, openai, google-genai, groq 등)가 없으면 첫 사용 시 pip으로 자동 설치 |
| **설치 실패 자동 분석** | 설치 실패 시 stdout/stderr 로그를 LLM에 전달하여 원인을 자동 분석하고 대안을 제시 |
| **차단 명령어 대안 요청** | 블랙리스트나 보안 검사로 차단된 명령어가 있으면 LLM에 재질의하여 안전한 대안 명령어를 자동 제안 |
| **주제 가드** | 개발환경 세팅 외 질문은 LLM이 `topic_valid=false`로 표시 → 앱이 응답을 교체하여 오남용 방지 |
| **보안 검사** | 모든 명령어를 화이트리스트 + 블랙리스트 이중 검사 후 실행, 화이트리스트에 없는 명령어는 LLM 동적 안전성 검사 수행 |

---

## 스크린샷

> 추가 예정

---

## 시작하기

### 요구사항

- Windows 10 1709 이상 (winget 기본 포함)
- Python 3.10+
- 아래 LLM 프로바이더 중 하나의 API 키 (또는 로컬 Ollama)

### 설치

```bash
git clone https://github.com/Clarit7/dev-setup-assistant.git
cd dev-setup-assistant

pip install -r requirements.txt
```

> **참고**: 프로바이더별 패키지(`anthropic`, `openai`, `google-genai`, `groq`)는 해당 프로바이더를 처음 사용할 때 자동으로 설치됩니다. `requirements.txt`에 모두 포함되어 있지만, 미설치 상태에서도 앱이 자동으로 처리합니다.

### 환경 변수 설정

프로젝트 루트에 `.env` 파일을 생성하거나 앱 내 ⚙ 버튼으로 설정합니다.

```env
# 사용할 LLM 프로바이더 선택 (기본: anthropic)
LLM_PROVIDER=anthropic

# 선택한 프로바이더의 API 키만 입력
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
GEMINI_API_KEY=AIza...
GROQ_API_KEY=gsk_...

# 프로바이더별 모델 오버라이드 (선택 — 기본값 사용 시 생략)
# ANTHROPIC_MODEL=claude-opus-4-6
# OPENAI_MODEL=gpt-4o
# GEMINI_MODEL=gemini-2.5-pro
# GROQ_MODEL=llama-3.3-70b-versatile

# Ollama 사용 시 (로컬, API 키 불필요)
# LLM_PROVIDER=ollama
# OLLAMA_BASE_URL=http://localhost:11434
# OLLAMA_MODEL=mistral
```

### 실행

```bash
python app.py
```

앱 시작 시 관리자 권한이 없으면 UAC 프롬프트가 자동으로 표시됩니다. 승인하면 관리자 권한으로 재실행됩니다.

### 실행파일(.exe) 빌드

```bash
pip install pyinstaller
pyinstaller DevSetupAssistant.spec
# dist/DevSetupAssistant.exe 생성됨
```

---

## 사용 방법

### 기본 도구 설치

1. 앱을 실행합니다.
2. 원하는 개발환경을 채팅창에 입력합니다.
   - 예: `Node.js랑 VS Code 설치해줘`, `Python 웹 개발환경 세팅해줘`
3. AI가 설치 계획을 제안하면 `Y`를 입력해 확인합니다.
4. 설치 로그가 실시간으로 표시됩니다.

### Docker 컨테이너 개발환경

1. 컨테이너 기반으로 개발하고 싶다고 입력합니다.
   - 예: `Docker로 Node.js 개발환경 만들어줘`
2. 스택과 포트를 확인 후 `Y`를 입력하면 자동으로:
   - Docker 이미지를 pull하고 컨테이너를 생성합니다.
   - `.devcontainer/devcontainer.json`을 생성합니다.
   - `enter-dev.bat` (Windows) / `enter-dev.sh` (WSL) 진입 스크립트를 생성합니다.
   - Windows Terminal에 컨테이너 진입 프로파일을 등록합니다.
   - VS Code 또는 Cursor에서 워크스페이스를 자동으로 엽니다.
3. VS Code가 열리면 우측 하단의 **Reopen in Container** 버튼을 클릭합니다.
   - 버튼이 보이지 않으면 `Ctrl+Shift+P` → `Dev Containers: Reopen in Container`

### AI 코드 에이전트 설치

1. 원하는 에이전트를 채팅창에 입력합니다.
   - 예: `Claude Code 설치해줘`, `Aider 써보고 싶어`
2. AI가 설치 계획을 제안하면 `Y`를 입력합니다.
3. 설치가 끝나면 API 키 입력 다이얼로그가 나타납니다 (마스킹 처리).
4. 입력된 키는 시스템 환경변수에 영속 저장됩니다.
   - Windows: `HKCU\Environment` 레지스트리
   - macOS/Linux: `~/.zshrc` 또는 `~/.bashrc`

지원 에이전트:

| 에이전트 | 설치 방법 | 인증 |
|---------|---------|------|
| **Claude Code** | npm | `ANTHROPIC_API_KEY` |
| **OpenAI Codex CLI** | npm | `OPENAI_API_KEY` |
| **Gemini CLI** | npm | `GEMINI_API_KEY` |
| **Aider** | pip | `ANTHROPIC_API_KEY` 등 |
| **GitHub Copilot CLI** | gh extension | `gh auth login` |

### 데이터베이스 설치

Docker 방식 (권장):
- 예: `Docker로 PostgreSQL 개발 DB 만들어줘`
- 컨테이너 자동 생성 + `.devcontainer/devcontainer.json` 포함

로컬 설치:
- 예: `PostgreSQL 로컬 설치해줘`
- 설치 후 `POSTGRES_PASSWORD` 등 연결 환경변수를 마스킹 다이얼로그로 설정

### 스크린샷으로 문제 해결

안내대로 했는데 오류가 발생하는 경우:
1. 오류 화면을 캡처합니다.
2. 채팅창에 **`Ctrl+V`** 로 붙여넣거나, **📎** 버튼으로 파일을 선택하거나, 이미지 파일을 **드래그앤드롭**합니다.
3. AI가 스크린샷을 분석하여 구체적인 해결 방법을 안내합니다.

### LLM 모델 변경

⚙ 버튼 → 설정 다이얼로그:
- 프로바이더 선택 → API 키 입력 → **↻ 목록 새로고침** 클릭
- 해당 프로바이더에서 사용 가능한 모델이 드롭다운으로 표시됩니다.
- 직접 모델 이름을 입력하는 것도 가능합니다.
- 프로바이더마다 모델 설정이 독립적으로 저장됩니다.

---

## 프로젝트 구조

```
dev-setup-assistant/
├── app.py                       # 메인 GUI (customtkinter, 상태머신)
├── DevSetupAssistant.spec       # PyInstaller 빌드 설정
│
├── core/
│   ├── llm.py                   # 멀티 프로바이더 LLM 클라이언트 (스트리밍, 비전)
│   ├── llm_safety.py            # LLM 기반 동적 명령어 안전성 검사
│   ├── actions.py               # 액션 정의 (Install / Run / Launch / ContainerSetup / SetEnv)
│   ├── runner.py                # 명령어 실행기 (실시간 stdout 스트리밍)
│   ├── safety.py                # 명령어 안전 검사 (화이트리스트 + 블랙리스트)
│   ├── admin.py                 # Windows UAC 권한 상승 유틸리티
│   ├── auto_install.py          # 프로바이더 패키지 자동 설치 유틸리티
│   ├── model_list.py            # 프로바이더별 사용 가능한 모델 목록 조회
│   ├── env_detector.py          # 설치된 개발 도구 자동 감지
│   ├── history.py               # 설치 이력 관리 (history.json)
│   ├── container.py             # Docker 감지, devcontainer 설정·스크립트 생성
│   ├── container_manager.py     # 컨테이너 생성·삭제·상태 조회
│   ├── git_setup.py             # Git 초기 설정 (사용자명·이메일·SSH 키)
│   ├── wsl.py                   # WSL 배포판 목록·설치·실행
│   └── ide_connector.py         # IDE 감지, 워크스페이스 열기, 연결 안내
│
├── ui/
│   ├── settings_dialog.py       # LLM 설정 다이얼로그 (모델 드롭다운 포함)
│   ├── container_dashboard.py   # 컨테이너 탭 대시보드
│   ├── git_tab.py               # Git 설정 탭
│   ├── wsl_tab.py               # WSL 관리 탭
│   └── image_handler.py         # 이미지 첨부 처리 (클립보드, 드래그앤드롭, 파일, base64)
│
├── installers/
│   ├── base.py                  # BaseInstaller 추상 클래스
│   └── winget.py                # Windows winget 구현체
│
├── scenarios/
│   ├── base.py                  # Scenario / PackageSpec / LaunchSpec
│   ├── registry.py              # 시나리오 등록 및 OS별 매칭
│   ├── ai_agents.py             # AI 코드 에이전트 시나리오 (크로스 플랫폼)
│   └── windows/
│       ├── js_timer.py          # JS 타이머 앱 시나리오
│       ├── web_dev.py           # 웹 개발환경 시나리오 (스택·에디터 선택)
│       ├── cpp_dev.py           # C/C++ 개발환경 시나리오
│       ├── java_dev.py          # Java 개발환경 시나리오
│       ├── rust_dev.py          # Rust 개발환경 시나리오
│       ├── go_dev.py            # Go 개발환경 시나리오
│       ├── dotnet_dev.py        # .NET 개발환경 시나리오
│       └── game_dev.py          # 게임 개발 시나리오 (Unity / Unreal)
│
└── tests/
    ├── test_safety.py           # 안전 검사 테스트
    ├── test_runner.py           # 실행기 테스트
    ├── test_scenarios.py        # 시나리오 테스트
    ├── test_installers.py       # 인스톨러 테스트
    ├── test_web_dev_scenario.py # 웹 개발 시나리오 테스트
    ├── test_container.py        # 컨테이너 기능 테스트
    ├── test_topic_guard.py      # 주제 가드 테스트
    ├── test_ai_agents.py        # AI 에이전트 + DB 지원 테스트
    ├── test_new_scenarios.py    # C/C++·Java·Rust·Go·.NET·게임 시나리오 테스트
    └── test_llm_safety.py       # LLM 동적 안전성 검사 테스트
```

---

## 앱 상태머신

```
CHATTING
  │  (LLM: ready_to_install=true)
  ▼
AWAITING_CONFIRM ──(Y 외 입력)──► CHATTING
  │  (Y)
  ▼
INSTALLING
  │  (완료)
  ▼
CHATTING  (다음 단계 안내 계속)
```

---

## 지원 LLM 프로바이더

| 프로바이더 | 기본 모델 | 비고 |
|-----------|----------|------|
| **Anthropic Claude** | claude-haiku-4-5-20251001 | 추천, 비전 지원 |
| **OpenAI GPT** | gpt-4o-mini | 비전 지원 |
| **Google Gemini** | gemini-2.5-flash-preview-04-17 | 무료 티어 있음, 비전 지원, `google-genai` SDK 사용 |
| **Groq** | llama-3.3-70b-versatile | 무료 티어 있음, 초고속 추론 |
| **Ollama** | mistral | 로컬 실행, API 키 불필요 |

프로바이더별 모델은 설정 다이얼로그에서 API를 통해 동적으로 조회하거나 환경 변수로 오버라이드할 수 있습니다.

---

## 보안

`core/safety.py`는 LLM이 제안한 모든 명령어를 실행 전 이중 검사합니다.

**화이트리스트** — 허용된 실행 파일만 통과
```
# 패키지 관리자
winget, choco, brew, scoop, apt, apt-get, snap, dnf, yum, pacman

# JS 생태계 + 버전 관리자
npm, npx, node, yarn, pnpm, deno, bun, nvm, volta, fnm

# Python 생태계 + 버전 관리자
pip, pip3, python, python3, pyenv, uv

# Ruby / PHP / 기타 런타임
ruby, gem, bundle, rbenv, rvm, php, composer
kotlin, kotlinc, flutter, dart, swift, swiftc
elixir, mix, erlang, rebar3, stack, cabal, ghc, lua, luarocks, julia

# C/C++ 빌드 도구
gcc, g++, clang, clang++, cmake, make, nmake, meson, ninja, gdb, lldb

# VCS / 에디터 / 빌드
git, code, cursor, cargo, rustup, go, dotnet, mvn, gradle, java

# 컨테이너 / 쿠버네티스 / 클라우드
docker, docker-compose, podman, wsl
kubectl, helm, minikube, k9s, kind, k3s, terraform, tofu
az, aws, gcloud, gsutil, bq, vercel, netlify

# AI 코드 에이전트
claude, codex, gemini, aider, gh

# 다운로드
curl, wget

# 데이터베이스 CLI
psql, pg_ctl, createdb, dropdb, initdb
mysql, mysqladmin, mysqldump
mongod, mongosh, mongo
redis-cli, redis-server, sqlite3

# SSH
ssh, ssh-keygen, ssh-add, ssh-copy-id
```

**LLM 동적 안전성 검사** — 화이트리스트에 없는 명령어는 LLM에 안전성을 추가로 질의
- `SAFE`: 동적 화이트리스트에 추가 후 자동 실행
- `CAUTION`: 사용자 확인 다이얼로그 표시 (허용 시 세션 화이트리스트 추가)
- `DANGEROUS`: 무조건 차단, LLM에 대안 명령어 재요청

**블랙리스트** — 아래 패턴은 허용된 실행 파일에서도 차단
- Windows 시스템 경로 접근 (`System32`, `SysWOW64`, `%windir%`)
- 디스크·파티션 조작 (`format`, `diskpart`, `fdisk`, `dd`)
- 강제 삭제 (`rm -rf`, `del /f`)
- 레지스트리·부트 조작 (`reg delete`, `bcdedit`)
- 셸 인젝션 (`| bash`, `| cmd`, `-EncodedCommand`)
- 시스템 종료·재시작

**SetEnvAction 허용 키** — API 키·DB 비밀번호는 별도 화이트리스트로 추가 검증
```
ANTHROPIC_API_KEY, OPENAI_API_KEY, GEMINI_API_KEY, OPENROUTER_API_KEY, GITHUB_TOKEN
DATABASE_URL, POSTGRES_URL, POSTGRES_PASSWORD
MYSQL_URL, MYSQL_ROOT_PASSWORD, MYSQL_PASSWORD
MONGODB_URL, MONGO_INITDB_ROOT_PASSWORD
REDIS_URL, REDIS_PASSWORD
```

**주제 가드** — 개발환경 외 질문은 LLM이 `topic_valid=false`로 마킹
앱이 이를 감지하면 스트리밍된 응답을 삭제하고 고정 거부 메시지로 교체합니다.

---

## 테스트

```bash
python -m pytest tests/ -v
```

213개 테스트 통과 (3개 skip — Pillow 미설치 환경)

---

## 알려진 이슈 및 패치

| 상태 | 설명 | 해결 |
|:---:|------|------|
| 해결됨 | customtkinter 5.2.2 + Windows 11 타이틀바 버그 | `app.py` 상단 no-op 람다 패치 |
| 해결됨 | 이미지 첨부 후 드래그앤드롭 2번째 시도 실패 | CTkLabel 내부 image 참조 선제 정리 |
| 해결됨 | 탐색기 파일 복사 후 Ctrl+V 시 오류 | CF_HDROP 감지 후 PIL 우회, 10ms 지연 처리 |
| 해결됨 | `python app.py` 실행 시 VS Code 창 자동 열림 | `code --version` 실행 없이 `which`만 확인 |
| 해결됨 | Groq 스트리밍 후 응답 내용 전체 삭제 | `_spinner_present` 플래그로 이중 삭제 방지 |
| 해결됨 | 설정 창에서 프로바이더 변경 시 모델이 다른 프로바이더 값으로 표시 | 프로바이더별 독립 모델 환경 변수 분리 |
| 해결됨 | Docker Desktop 설치가 보안 검사에서 차단됨 | LLM이 winget 우선 사용하도록 시스템 프롬프트 개선 |
| 해결됨 | 설치 실패 시 AI가 사용자에게 원인 선택을 요구 | stdout/stderr 로그를 LLM에 전달하여 자동 분석 |
| 해결됨 | `python.exe`로 관리자 재실행 시 빈 CMD 창 표시 | `pythonw.exe`로 전환하여 콘솔 없이 재실행 |
| 해결됨 | `google.generativeai` FutureWarning | `google-genai` 신규 SDK로 마이그레이션 |
| 부분 대응 | winget 출력 인코딩 (UTF-16LE / UTF-8 혼용) | `mbcs` fallback 적용 |

---

## 로드맵

- [ ] macOS (brew) 인스톨러 구현
- [ ] Linux (apt) 인스톨러 구현
- [ ] 앱 아이콘 적용
- [ ] README 스크린샷 추가

---

## 라이선스

MIT
