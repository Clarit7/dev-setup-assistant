# 개발환경 세팅 도우미 (DevSetupAssistant)

대화형 GUI로 개발환경을 자동으로 구성해주는 Windows 데스크톱 앱입니다.
무엇을 만들고 싶은지 채팅창에 입력하면, 필요한 도구를 자동으로 설치하고 실행합니다.

---

## 주요 기능

- **자연어 인식** — "타이머 앱 만들고 싶어" 같은 자유로운 입력으로 시나리오 매칭
- **자동 설치** — winget을 통해 필요한 패키지를 자동 설치 (이미 설치된 항목은 건너뜀)
- **보안 검사** — 화이트리스트 + 블랙리스트 이중 검사로 위험한 명령어 차단
- **실시간 출력** — 설치 로그를 GUI에 실시간으로 표시
- **시나리오 확장** — 새 시나리오를 파일 하나로 간단히 추가 가능

---

## 스크린샷

> 추가 예정

---

## 시작하기

### 요구사항

- Windows 10 1709 이상 (winget 기본 포함)
- Python 3.10+
- [customtkinter](https://github.com/TomSchimansky/CustomTkinter) 5.2.2

### 설치 및 실행

```bash
# 저장소 클론
git clone https://github.com/your-username/start_dev_setup.git
cd start_dev_setup

# 의존성 설치
pip install customtkinter

# 실행
python app.py
```

### 실행파일 (.exe) 빌드

```bash
pip install pyinstaller
pyinstaller DevSetupAssistant.spec
# dist/DevSetupAssistant.exe 생성됨
```

---

## 사용 방법

1. 앱을 실행합니다.
2. 채팅창에 만들고 싶은 것을 입력합니다.
   - 예: `타이머 앱 만들고 싶어`, `timer app`
3. AI가 필요한 도구 목록을 제안하면 `y`로 확인합니다.
4. 자동 설치가 진행됩니다. 완료 후 앱 실행 여부를 선택합니다.

---

## 프로젝트 구조

```
start_dev_setup/
├── app.py                      # 메인 GUI (customtkinter, 상태머신)
├── DevSetupAssistant.spec      # PyInstaller 빌드 설정
│
├── core/
│   ├── safety.py               # 명령어 안전 검사 (화이트리스트 + 블랙리스트)
│   └── runner.py               # 명령어 실행기 (실시간 stdout 스트리밍)
│
├── installers/
│   ├── base.py                 # BaseInstaller 추상 클래스
│   └── winget.py               # Windows winget 구현체
│
├── scenarios/
│   ├── base.py                 # Scenario / PackageSpec / LaunchSpec 데이터 클래스
│   ├── registry.py             # 시나리오 등록 및 매칭
│   └── windows/
│       └── js_timer.py         # JS 타이머 앱 시나리오 (Node.js + VSCode)
│
└── tests/
    ├── test_safety.py          # safety 모듈 테스트
    ├── test_runner.py          # runner 모듈 테스트
    ├── test_scenarios.py       # 시나리오 테스트
    └── test_installers.py      # 인스톨러 테스트
```

---

## GUI 상태머신

```
INIT
 │ (시나리오 매칭 성공)
 ▼
AWAITING_CONFIRM ──(N)──► INIT
 │ (y)
 ▼
INSTALLING
 │ (완료)
 ▼
AWAITING_LAUNCH ──(N)──► DONE
 │ (y)
 ▼
DONE
```

---

## 새 시나리오 추가하기

`scenarios/windows/` 아래에 새 파일을 만들고 `Scenario`를 상속합니다.

```python
# scenarios/windows/my_scenario.py
from ..base import Scenario, PackageSpec, LaunchSpec

class MyScenario(Scenario):
    name = "내 시나리오"
    description = "무언가를 개발하는 환경"
    supported_os = ["windows"]

    def get_packages(self):
        return [
            PackageSpec(
                display_name="My Tool",
                check_command="mytool",
                package_ids={"winget": "Publisher.MyTool"},
            ),
        ]

    def get_launch(self):
        return LaunchSpec(display_name="My Tool", command=["mytool"])

    def get_proposal_message(self):
        return "My Tool을 설치할까요? (y/N)"

    def matches(self, user_input: str) -> bool:
        return "mytool" in user_input.lower()
```

그런 다음 `scenarios/registry.py`의 `_ALL_SCENARIOS` 리스트에 추가합니다.

```python
from .windows.my_scenario import MyScenario

_ALL_SCENARIOS = [
    JSTimerScenario(),
    MyScenario(),   # 추가
]
```

---

## 보안

`core/safety.py`는 모든 외부 명령어 실행 전에 두 단계로 검사합니다.

1. **화이트리스트** — `winget`, `npm`, `pip`, `git`, `code` 등 허용된 실행 파일만 통과
2. **블랙리스트** — 시스템 경로 접근, 강제 삭제, 셸 인젝션, 시스템 종료 등 위험 패턴 차단

---

## 테스트

```bash
python -m pytest tests/ -v
```

총 52개 테스트 (safety, runner, scenarios, installers 전 모듈 커버)

---

## 알려진 이슈 및 패치

- **customtkinter 5.2.2 + Windows 11 버그** — `_windows_set_titlebar_color`가 내부적으로 `str`을 callable로 잘못 호출하는 문제. `app.py` 상단에서 해당 메서드를 no-op 람다로 패치해 해결.

---

## 로드맵

- [ ] macOS (brew) 인스톨러 구현
- [ ] Linux (apt) 인스톨러 구현
- [ ] 추가 시나리오: Python Flask, React, Java Spring 등
- [ ] 앱 아이콘 적용
- [ ] README 스크린샷 추가

---

## 라이선스

MIT
