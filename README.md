# 개발환경 세팅 도우미 (DevSetupAssistant)

채팅형 GUI에서 LLM과 대화하며 개발환경을 자동으로 구성하는 Windows 데스크톱 앱입니다.
무엇을 만들고 싶은지 자유롭게 입력하면, 필요한 도구를 설치하고 Docker 컨테이너까지 세팅합니다.

---

## 주요 기능

| 기능 | 설명 |
|------|------|
| **A. 환경 자동 감지** | 앱 시작 시 설치된 도구(Node.js, Python, Git, Docker 등)와 실행 중인 컨테이너를 자동 감지하여 LLM에 컨텍스트로 제공 |
| **B. 스트리밍 응답** | LLM 응답을 글자 단위로 실시간 표시 |
| **C. LLM 설정 UI** | ⚙ 버튼으로 프로바이더(Claude / GPT / Gemini / Ollama)와 API 키를 GUI에서 변경 |
| **D. 컨테이너 연동** | Docker 이미지 pull·컨테이너 생성, `.devcontainer/devcontainer.json` 자동 생성, 진입 스크립트(`enter-dev.bat` / `enter-dev.sh`), Windows Terminal 프로파일 자동 등록, VS Code·Cursor 워크스페이스 자동 열기 |
| **E. 이미지 첨부** | 스크린샷을 `Ctrl+V`로 붙여넣거나 📎 버튼으로 파일 선택 → LLM 비전 API로 문제 분석 |
| **F. 설치 이력** | 설치 결과를 `history.json`에 기록하여 LLM이 중복 설치를 피할 수 있도록 컨텍스트 제공 |
| **주제 가드** | 개발환경 세팅 외 질문은 LLM이 `topic_valid=false`로 표시 → 앱이 응답을 교체하여 오남용 방지 |
| **보안 검사** | 모든 명령어를 화이트리스트 + 블랙리스트 이중 검사 후 실행 |

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

### 환경 변수 설정

프로젝트 루트에 `.env` 파일을 생성하거나 앱 내 ⚙ 버튼으로 설정합니다.

```env
# 사용할 LLM 프로바이더 선택 (기본: anthropic)
LLM_PROVIDER=anthropic

# 선택한 프로바이더의 API 키만 입력
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
GEMINI_API_KEY=AIza...

# Ollama 사용 시 (로컬, API 키 불필요)
# LLM_PROVIDER=ollama
# OLLAMA_BASE_URL=http://localhost:11434
# LLM_MODEL=mistral
```

### 실행

```bash
python app.py
```

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

### 스크린샷으로 문제 해결

안내대로 했는데 오류가 발생하는 경우:
1. 오류 화면을 캡처합니다.
2. 채팅창에 **`Ctrl+V`** 로 붙여넣거나 **📎** 버튼으로 파일을 선택합니다.
3. AI가 스크린샷을 분석하여 구체적인 해결 방법을 안내합니다.

---

## 프로젝트 구조

```
dev-setup-assistant/
├── app.py                       # 메인 GUI (customtkinter, 상태머신)
├── DevSetupAssistant.spec       # PyInstaller 빌드 설정
│
├── core/
│   ├── llm.py                   # 멀티 프로바이더 LLM 클라이언트 (스트리밍, 비전)
│   ├── actions.py               # 액션 정의 (Install / Run / Launch / ContainerSetup)
│   ├── runner.py                # 명령어 실행기 (실시간 stdout 스트리밍)
│   ├── safety.py                # 명령어 안전 검사 (화이트리스트 + 블랙리스트)
│   ├── env_detector.py          # 설치된 개발 도구 자동 감지
│   ├── history.py               # 설치 이력 관리 (history.json)
│   ├── container.py             # Docker 감지, devcontainer 설정·스크립트 생성
│   └── ide_connector.py         # IDE 감지, 워크스페이스 열기, 연결 안내
│
├── ui/
│   ├── settings_dialog.py       # LLM 설정 다이얼로그
│   └── image_handler.py         # 이미지 첨부 처리 (클립보드, 파일, base64)
│
├── installers/
│   ├── base.py                  # BaseInstaller 추상 클래스
│   └── winget.py                # Windows winget 구현체
│
├── scenarios/
│   ├── base.py                  # Scenario / PackageSpec / LaunchSpec
│   ├── registry.py              # 시나리오 등록 및 OS별 매칭
│   └── windows/
│       ├── js_timer.py          # JS 타이머 앱 시나리오
│       └── web_dev.py           # 웹 개발환경 시나리오 (스택·에디터 선택)
│
└── tests/
    ├── test_safety.py           # 안전 검사 테스트
    ├── test_runner.py           # 실행기 테스트
    ├── test_scenarios.py        # 시나리오 테스트
    ├── test_installers.py       # 인스톨러 테스트
    ├── test_web_dev_scenario.py # 웹 개발 시나리오 테스트
    ├── test_container.py        # 컨테이너 기능 테스트
    └── test_topic_guard.py      # 주제 가드 테스트
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
| **Anthropic Claude** | claude-haiku-4-5 | 추천, 비전 지원 |
| **OpenAI GPT** | gpt-4o-mini | 비전 지원 |
| **Google Gemini** | gemini-2.5-flash | 무료 티어 있음, 비전 지원 |
| **Ollama** | mistral | 로컬 실행, API 키 불필요 |

`LLM_MODEL` 환경 변수로 모델을 오버라이드할 수 있습니다.

---

## 보안

`core/safety.py`는 LLM이 제안한 모든 명령어를 실행 전 이중 검사합니다.

**화이트리스트** — 허용된 실행 파일만 통과
```
winget, npm, node, pip, python, git, code, cursor,
docker, docker-compose, podman, wsl, cargo, go, dotnet, ...
```

**블랙리스트** — 아래 패턴은 허용된 실행 파일에서도 차단
- Windows 시스템 경로 접근 (`System32`, `SysWOW64`, `%windir%`)
- 디스크·파티션 조작 (`format`, `diskpart`, `fdisk`, `dd`)
- 강제 삭제 (`rm -rf`, `del /f`)
- 레지스트리·부트 조작 (`reg delete`, `bcdedit`)
- 셸 인젝션 (`| bash`, `| cmd`, `-EncodedCommand`)
- 시스템 종료·재시작

**주제 가드** — 개발환경 외 질문은 LLM이 `topic_valid=false`로 마킹
앱이 이를 감지하면 스트리밍된 응답을 삭제하고 고정 거부 메시지로 교체합니다.

---

## 테스트

```bash
python -m pytest tests/ -v
```

159개 테스트 통과 (3개 skip — Pillow 미설치 환경)

---

## 알려진 이슈 및 패치

| 상태 | 설명 | 해결 |
|:---:|------|------|
| 해결됨 | customtkinter 5.2.2 + Windows 11 타이틀바 버그 | `app.py` 상단 no-op 람다 패치 |
| 부분 대응 | winget 출력 인코딩 (UTF-16LE / UTF-8 혼용) | `mbcs` fallback 적용 |

---

## 로드맵

- [ ] macOS (brew) 인스톨러 구현
- [ ] Linux (apt) 인스톨러 구현
- [ ] 추가 시나리오: Java Spring, Rust, Go 등
- [ ] 앱 아이콘 적용
- [ ] README 스크린샷 추가

---

## 라이선스

MIT
