"""
scenarios/ 테스트

시나리오 매칭, 패키지 명세, 레지스트리 라우팅을 검증합니다.
"""
import unittest
from unittest.mock import patch
from scenarios.base import PackageSpec, LaunchSpec
from scenarios.windows.js_timer import JSTimerScenario
from scenarios.registry import match_scenario, list_supported_scenarios


class TestJSTimerScenario(unittest.TestCase):
    def setUp(self):
        self.scenario = JSTimerScenario()

    # ── 매칭 ─────────────────────────────────────────────────────────────────

    def test_matches_korean_timer(self):
        self.assertTrue(self.scenario.matches("윈도우에서 타이머 앱 만들고 싶어"))

    def test_matches_english_timer(self):
        self.assertTrue(self.scenario.matches("I want to make a timer app"))

    def test_not_matches_unrelated(self):
        self.assertFalse(self.scenario.matches("로그인 페이지 만들어줘"))

    def test_not_matches_empty(self):
        self.assertFalse(self.scenario.matches(""))

    # ── 패키지 명세 ──────────────────────────────────────────────────────────

    def test_returns_two_packages(self):
        self.assertEqual(len(self.scenario.get_packages()), 2)

    def test_nodejs_package_spec(self):
        node = self.scenario.get_packages()[0]
        self.assertIsInstance(node, PackageSpec)
        self.assertEqual(node.check_command, "node")
        self.assertIn("winget", node.package_ids)
        self.assertEqual(node.package_ids["winget"], "OpenJS.NodeJS")

    def test_vscode_package_spec(self):
        vscode = self.scenario.get_packages()[1]
        self.assertIsInstance(vscode, PackageSpec)
        self.assertEqual(vscode.check_command, "code")
        self.assertIn("winget", vscode.package_ids)
        self.assertEqual(vscode.package_ids["winget"], "Microsoft.VisualStudioCode")

    # ── 실행 명세 ─────────────────────────────────────────────────────────────

    def test_launch_spec_exists(self):
        launch = self.scenario.get_launch()
        self.assertIsInstance(launch, LaunchSpec)

    def test_launch_command_is_code(self):
        launch = self.scenario.get_launch()
        self.assertEqual(launch.command, ["code"])

    # ── 메시지 ───────────────────────────────────────────────────────────────

    def test_proposal_message_not_empty(self):
        msg = self.scenario.get_proposal_message()
        self.assertGreater(len(msg), 0)

    def test_proposal_message_mentions_nodejs(self):
        msg = self.scenario.get_proposal_message()
        self.assertIn("Node.js", msg)

    def test_proposal_message_mentions_vscode(self):
        msg = self.scenario.get_proposal_message()
        self.assertIn("Visual Studio Code", msg)

    # ── OS 지원 ──────────────────────────────────────────────────────────────

    def test_supports_windows(self):
        self.assertIn("windows", self.scenario.supported_os)

    def test_does_not_support_linux_yet(self):
        self.assertNotIn("linux", self.scenario.supported_os)


class TestRegistry(unittest.TestCase):
    """시나리오 레지스트리 라우팅 테스트"""

    def test_match_timer_on_windows(self):
        with patch("scenarios.registry.get_current_os", return_value="windows"):
            result = match_scenario("타이머 앱 만들고 싶어")
        self.assertIsNotNone(result)
        self.assertIsInstance(result, JSTimerScenario)

    def test_no_match_on_linux(self):
        with patch("scenarios.registry.get_current_os", return_value="linux"):
            result = match_scenario("타이머 앱 만들고 싶어")
        self.assertIsNone(result)  # JS 타이머 시나리오는 아직 linux 미지원

    def test_no_match_for_unknown_request(self):
        with patch("scenarios.registry.get_current_os", return_value="windows"):
            result = match_scenario("블록체인 NFT 민팅 서버 만들어줘")
        self.assertIsNone(result)

    def test_list_supported_on_windows(self):
        with patch("scenarios.registry.get_current_os", return_value="windows"):
            supported = list_supported_scenarios()
        self.assertGreater(len(supported), 0)

    def test_list_supported_on_linux_has_ai_agents(self):
        from scenarios.ai_agents import AIAgentsScenario
        with patch("scenarios.registry.get_current_os", return_value="linux"):
            supported = list_supported_scenarios()
        # AIAgentsScenario는 linux도 지원
        self.assertGreater(len(supported), 0)
        self.assertTrue(any(isinstance(s, AIAgentsScenario) for s in supported))


if __name__ == "__main__":
    unittest.main()
