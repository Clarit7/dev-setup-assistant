"""
core/safety.py 테스트

명령어 화이트리스트 및 위험 패턴 블랙리스트 검사 로직을 검증합니다.
"""
import unittest
from core.safety import is_safe_command


class TestAllowedExecutables(unittest.TestCase):
    """허용된 실행 파일 테스트"""

    def test_winget_allowed(self):
        ok, _ = is_safe_command(["winget", "install", "--id", "OpenJS.NodeJS"])
        self.assertTrue(ok)

    def test_npm_allowed(self):
        ok, _ = is_safe_command(["npm", "install"])
        self.assertTrue(ok)

    def test_code_allowed(self):
        ok, _ = is_safe_command(["code"])
        self.assertTrue(ok)

    def test_pip_allowed(self):
        ok, _ = is_safe_command(["pip", "install", "requests"])
        self.assertTrue(ok)

    def test_git_allowed(self):
        ok, _ = is_safe_command(["git", "clone", "https://github.com/example/repo"])
        self.assertTrue(ok)

    def test_node_allowed(self):
        ok, _ = is_safe_command(["node", "index.js"])
        self.assertTrue(ok)


class TestBlockedExecutables(unittest.TestCase):
    """차단된 실행 파일 테스트"""

    def test_cmd_blocked(self):
        ok, reason = is_safe_command(["cmd", "/c", "del", "file.txt"])
        self.assertFalse(ok)
        self.assertIn("허용되지 않은", reason)

    def test_powershell_blocked(self):
        ok, _ = is_safe_command(["powershell", "-Command", "Get-Process"])
        self.assertFalse(ok)

    def test_rm_blocked(self):
        ok, _ = is_safe_command(["rm", "-rf", "/"])
        self.assertFalse(ok)

    def test_del_blocked(self):
        ok, _ = is_safe_command(["del", "/f", "file.txt"])
        self.assertFalse(ok)

    def test_unknown_exe_blocked(self):
        ok, _ = is_safe_command(["malware.exe", "--silent"])
        self.assertFalse(ok)

    def test_empty_command_blocked(self):
        ok, reason = is_safe_command([])
        self.assertFalse(ok)
        self.assertIn("빈", reason)


class TestDangerousPatterns(unittest.TestCase):
    """허용된 실행 파일이지만 위험한 인자 패턴 차단 테스트"""

    def test_winget_system32_blocked(self):
        ok, reason = is_safe_command(["winget", "install", "C:\\Windows\\System32\\hack"])
        self.assertFalse(ok)
        self.assertIn("시스템", reason)

    def test_pip_shell_pipe_blocked(self):
        ok, _ = is_safe_command(["pip", "install", "pkg", "|", "bash"])
        self.assertFalse(ok)

    def test_npm_encoded_command_blocked(self):
        ok, _ = is_safe_command(["npm", "run", "-EncodedCommand", "aGFjaw=="])
        self.assertFalse(ok)

    def test_winget_with_shutdown_blocked(self):
        ok, _ = is_safe_command(["winget", "install", "shutdown"])
        self.assertFalse(ok)

    def test_git_chain_delete_blocked(self):
        ok, _ = is_safe_command(["git", "clone", "repo", "&&", "del", "file"])
        self.assertFalse(ok)


class TestPathHandling(unittest.TestCase):
    """경로 및 확장자 처리 테스트"""

    def test_full_path_winget_allowed(self):
        ok, _ = is_safe_command(
            ["C:\\Users\\Jay\\AppData\\Local\\Microsoft\\WindowsApps\\winget.exe",
             "install", "--id", "OpenJS.NodeJS"]
        )
        self.assertTrue(ok)

    def test_exe_extension_stripped(self):
        ok, _ = is_safe_command(["code.exe"])
        self.assertTrue(ok)

    def test_full_path_unknown_blocked(self):
        ok, _ = is_safe_command(["C:\\malware\\bad.exe"])
        self.assertFalse(ok)


if __name__ == "__main__":
    unittest.main()
