# 개발 진행상황

> 최종 업데이트: 2026-03-15

---

## 완료된 작업

### v0.1 — 초기 구현 (`83519d1`)
- [x] customtkinter 기반 채팅형 GUI 구현
- [x] 상태머신 (`INIT → AWAITING_CONFIRM → INSTALLING → AWAITING_LAUNCH → DONE`)
- [x] JS 타이머 앱 시나리오 (Node.js + VSCode) 첫 구현
- [x] winget을 통한 자동 설치 및 앱 실행 기능

### v0.2 — 모듈화 리팩터링 (`4144fae`)
- [x] `core/safety.py` — 명령어 안전 검사 모듈 분리
  - 화이트리스트: `winget`, `npm`, `pip`, `git`, `code` 등 허용 실행 파일 목록
  - 블랙리스트: 시스템 경로 접근, 강제 삭제, 셸 인젝션, 시스템 종료 등 16개 위험 패턴
- [x] `core/runner.py` — 안전 검사 통과 후 subprocess 실행 + 실시간 stdout 스트리밍
- [x] `installers/base.py` — `BaseInstaller` 추상 클래스 (멀티 OS 확장 인터페이스)
- [x] `installers/winget.py` — Windows winget 구현체
- [x] `scenarios/base.py` — `Scenario` / `PackageSpec` / `LaunchSpec` 데이터 클래스
- [x] `scenarios/registry.py` — 시나리오 등록 및 OS별 매칭 로직
- [x] `scenarios/windows/js_timer.py` — JS 타이머 시나리오 모듈로 분리

### v0.3 — 테스트 스위트 추가 (`6470c9f`)
- [x] `tests/test_safety.py` — 화이트리스트/블랙리스트/경로 처리 검증 (22개)
- [x] `tests/test_runner.py` — 실행기 동작 검증
- [x] `tests/test_scenarios.py` — 시나리오 매칭/패키지/실행 정보 검증
- [x] `tests/test_installers.py` — 인스톨러 구현 검증
- [x] 총 **52개 테스트** 전 통과

### v0.4 — 빌드 및 버그 수정 (`783441e`, `6db8ed3`)
- [x] `DevSetupAssistant.spec` — PyInstaller 빌드 설정 추가
- [x] `dist/DevSetupAssistant.exe` 빌드 성공
- [x] customtkinter 5.2.2 + Windows 11 타이틀바 색상 버그 패치
  - 원인: `_windows_set_titlebar_color` 내부에서 `str`을 callable로 잘못 호출
  - 해결: `app.py` 상단에서 해당 메서드를 no-op 람다로 런타임 패치

### v0.5 — 문서화 (`현재`)
- [x] `README.md` 작성
- [x] `PROGRESS.md` 작성 (이 파일)

---

## 진행 중

없음 (현재 안정 버전)

---

## 로드맵 (예정)

| 우선순위 | 항목 | 비고 |
|:---:|---|---|
| 높음 | macOS brew 인스톨러 구현 | `installers/brew.py` |
| 높음 | Linux apt 인스톨러 구현 | `installers/apt.py` |
| 중간 | 추가 시나리오: Python Flask | `scenarios/windows/python_flask.py` |
| 중간 | 추가 시나리오: React 앱 | `scenarios/windows/react_app.py` |
| 중간 | 추가 시나리오: Java Spring | `scenarios/windows/java_spring.py` |
| 낮음 | 앱 아이콘 (.ico) 적용 | PyInstaller spec 연동 |
| 낮음 | README 스크린샷 추가 | |
| 낮음 | 다크/라이트 모드 토글 UI | |

---

## 아키텍처 요약

```
사용자 입력
    │
    ▼
scenarios/registry.py  ──  OS 감지 + 시나리오 매칭
    │
    ▼
scenarios/*/           ──  PackageSpec 목록 반환
    │
    ▼
core/safety.py         ──  명령어 화이트리스트/블랙리스트 검사
    │
    ▼
core/runner.py         ──  subprocess 실행 + stdout 스트리밍
    │
    ▼
installers/*.py        ──  OS별 install 명령어 생성
```

---

## 알려진 이슈

| 상태 | 설명 | 해결 |
|:---:|---|---|
| 해결됨 | customtkinter 5.2.2 Windows 11 타이틀바 색상 버그 | `app.py` 런타임 패치 |
| 미해결 | winget 출력 인코딩이 환경에 따라 UTF-16LE/UTF-8 혼용 | `mbcs` fallback으로 부분 대응 중 |
