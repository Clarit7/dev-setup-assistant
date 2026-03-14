"""
core/runner.py 테스트

안전 검사 통과 여부와 subprocess 오류 처리를 검증합니다.
실제 외부 명령어는 실행하지 않고 mock을 사용합니다.
"""
import unittest
from unittest.mock import patch, MagicMock
from core.runner import run_command


class TestRunnerSafetyBlock(unittest.TestCase):
    """안전하지 않은 명령어는 subprocess 호출 없이 차단되어야 합니다."""

    def test_unsafe_command_blocked_without_subprocess(self):
        errors = []
        with patch("subprocess.Popen") as mock_popen:
            result = run_command(["rm", "-rf", "/"], on_output=lambda _: None, on_error=errors.append)
        mock_popen.assert_not_called()
        self.assertFalse(result)
        self.assertTrue(any("보안 차단" in e for e in errors))

    def test_unknown_executable_blocked(self):
        errors = []
        with patch("subprocess.Popen") as mock_popen:
            result = run_command(["evil.exe", "--run"], on_output=lambda _: None, on_error=errors.append)
        mock_popen.assert_not_called()
        self.assertFalse(result)


class TestRunnerExecution(unittest.TestCase):
    """허용된 명령어는 subprocess로 실행되어야 합니다."""

    def _make_mock_process(self, output_lines: list, returncode: int = 0):
        mock_process = MagicMock()
        mock_process.stdout = [line.encode() for line in output_lines]
        mock_process.returncode = returncode
        mock_process.wait.return_value = None
        return mock_process

    def test_safe_command_runs(self):
        outputs = []
        mock_proc = self._make_mock_process(["설치 중...\n", "완료\n"], returncode=0)

        with patch("subprocess.Popen", return_value=mock_proc):
            result = run_command(
                ["winget", "install", "--id", "OpenJS.NodeJS",
                 "--accept-package-agreements", "--accept-source-agreements"],
                on_output=outputs.append,
                on_error=lambda _: None,
            )
        self.assertTrue(result)
        self.assertIn("설치 중...\n", outputs)
        self.assertIn("완료\n", outputs)

    def test_nonzero_returncode_returns_false(self):
        mock_proc = self._make_mock_process(["오류 발생\n"], returncode=1)

        with patch("subprocess.Popen", return_value=mock_proc):
            result = run_command(
                ["winget", "install", "--id", "OpenJS.NodeJS",
                 "--accept-package-agreements", "--accept-source-agreements"],
                on_output=lambda _: None,
                on_error=lambda _: None,
            )
        self.assertFalse(result)

    def test_file_not_found_handled(self):
        errors = []
        with patch("subprocess.Popen", side_effect=FileNotFoundError):
            result = run_command(
                ["winget", "install", "--id", "OpenJS.NodeJS"],
                on_output=lambda _: None,
                on_error=errors.append,
            )
        self.assertFalse(result)
        self.assertTrue(any("찾을 수 없습니다" in e for e in errors))

    def test_unexpected_exception_handled(self):
        errors = []
        with patch("subprocess.Popen", side_effect=OSError("permission denied")):
            result = run_command(
                ["winget", "install", "--id", "OpenJS.NodeJS"],
                on_output=lambda _: None,
                on_error=errors.append,
            )
        self.assertFalse(result)
        self.assertTrue(any("오류" in e for e in errors))


if __name__ == "__main__":
    unittest.main()
