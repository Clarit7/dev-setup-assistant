"""
WebDevScenario 테스트

- 키워드 매칭
- 스택/에디터 조합별 패키지/실행 정보
- 선택 안내 메시지 존재 여부
- 설치 제안 메시지 조합별 내용 검증
"""
import pytest
from scenarios.windows.web_dev import WebDevScenario


# ── 픽스처 ──────────────────────────────────────────────────────────────────

@pytest.fixture
def scenario():
    return WebDevScenario()


def make_scenario(stack: int, editor: int) -> WebDevScenario:
    s = WebDevScenario()
    s.set_stack(stack)
    s.set_editor(editor)
    return s


# ── 매칭 테스트 ──────────────────────────────────────────────────────────────

class TestMatches:
    def test_웹_키워드(self, scenario):
        assert scenario.matches("웹 개발 하고 싶어")

    def test_web_영문(self, scenario):
        assert scenario.matches("web development setup")

    def test_개발환경_키워드(self, scenario):
        assert scenario.matches("개발환경 만들어줘")

    def test_개발_환경_띄어쓰기(self, scenario):
        assert scenario.matches("개발 환경 구성해줘")

    def test_무관한_입력(self, scenario):
        assert not scenario.matches("타이머 앱 만들고 싶어")

    def test_빈_문자열(self, scenario):
        assert not scenario.matches("")

    def test_대소문자_무관(self, scenario):
        assert scenario.matches("WEB 개발")


# ── 선택 안내 메시지 테스트 ─────────────────────────────────────────────────

class TestChoiceMessages:
    def test_스택_메시지_비어있지_않음(self, scenario):
        msg = scenario.get_stack_choice_message()
        assert len(msg) > 0

    def test_스택_메시지_선택지_포함(self, scenario):
        msg = scenario.get_stack_choice_message()
        assert "1" in msg and "2" in msg
        assert "React" in msg
        assert "Flask" in msg

    def test_에디터_메시지_비어있지_않음(self, scenario):
        msg = scenario.get_editor_choice_message()
        assert len(msg) > 0

    def test_에디터_메시지_선택지_포함(self, scenario):
        msg = scenario.get_editor_choice_message()
        assert "1" in msg and "2" in msg
        assert "Visual Studio Code" in msg
        assert "Cursor" in msg


# ── 패키지 구성 테스트 (4가지 조합) ─────────────────────────────────────────

class TestGetPackages:
    @pytest.mark.parametrize("stack,editor,expected_pkg,expected_editor", [
        (1, 1, "Node.js",  "Visual Studio Code"),
        (1, 2, "Node.js",  "Cursor"),
        (2, 1, "Python",   "Visual Studio Code"),
        (2, 2, "Python",   "Cursor"),
    ])
    def test_패키지_조합(self, stack, editor, expected_pkg, expected_editor):
        s = make_scenario(stack, editor)
        pkgs = s.get_packages()
        assert len(pkgs) == 2
        names = [p.display_name for p in pkgs]
        assert expected_pkg in names
        assert expected_editor in names

    @pytest.mark.parametrize("stack,editor,winget_key", [
        (1, 1, "OpenJS.NodeJS"),
        (2, 1, "Python.Python.3"),
        (1, 2, "Anysphere.Cursor"),
        (2, 2, "Anysphere.Cursor"),
    ])
    def test_winget_id(self, stack, editor, winget_key):
        s = make_scenario(stack, editor)
        all_ids = [p.package_ids.get("winget") for p in s.get_packages()]
        assert winget_key in all_ids

    @pytest.mark.parametrize("stack,editor", [(1,1),(1,2),(2,1),(2,2)])
    def test_모든_패키지에_check_command_존재(self, stack, editor):
        s = make_scenario(stack, editor)
        for pkg in s.get_packages():
            assert pkg.check_command


# ── 실행 정보 테스트 ─────────────────────────────────────────────────────────

class TestGetLaunch:
    def test_vscode_실행(self):
        s = make_scenario(1, 1)
        launch = s.get_launch()
        assert launch.display_name == "Visual Studio Code"
        assert launch.command == ["code"]

    def test_cursor_실행(self):
        s = make_scenario(1, 2)
        launch = s.get_launch()
        assert launch.display_name == "Cursor"
        assert launch.command == ["cursor"]

    @pytest.mark.parametrize("stack", [1, 2])
    def test_스택_무관하게_에디터로_실행(self, stack):
        s1 = make_scenario(stack, 1)
        s2 = make_scenario(stack, 2)
        assert s1.get_launch().command == ["code"]
        assert s2.get_launch().command == ["cursor"]


# ── 설치 제안 메시지 테스트 ──────────────────────────────────────────────────

class TestProposalMessage:
    @pytest.mark.parametrize("stack,editor,stack_kw,editor_kw", [
        (1, 1, "React",  "Visual Studio Code"),
        (1, 2, "React",  "Cursor"),
        (2, 1, "Flask",  "Visual Studio Code"),
        (2, 2, "Flask",  "Cursor"),
    ])
    def test_메시지_내용_검증(self, stack, editor, stack_kw, editor_kw):
        s = make_scenario(stack, editor)
        msg = s.get_proposal_message()
        assert stack_kw in msg
        assert editor_kw in msg

    @pytest.mark.parametrize("stack,editor", [(1,1),(1,2),(2,1),(2,2)])
    def test_yn_안내_포함(self, stack, editor):
        s = make_scenario(stack, editor)
        msg = s.get_proposal_message()
        assert "y/N" in msg or "Y/N" in msg


# ── OS 지원 테스트 ───────────────────────────────────────────────────────────

class TestOsSupport:
    def test_windows_지원(self, scenario):
        assert "windows" in scenario.supported_os

    def test_name_비어있지_않음(self, scenario):
        assert scenario.name

    def test_description_비어있지_않음(self, scenario):
        assert scenario.description
