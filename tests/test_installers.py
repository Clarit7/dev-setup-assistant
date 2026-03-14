"""
installers/ 테스트

인스톨러 명령어 생성 및 가용성 확인 로직을 검증합니다.
"""
import unittest
from unittest.mock import patch
from installers.winget import WingetInstaller


class TestWingetInstaller(unittest.TestCase):
    def setUp(self):
        self.installer = WingetInstaller()

    def test_installer_type(self):
        self.assertEqual(self.installer.installer_type, "winget")

    def test_build_command_contains_winget(self):
        cmd = self.installer.build_install_command("OpenJS.NodeJS")
        self.assertEqual(cmd[0], "winget")

    def test_build_command_contains_package_id(self):
        cmd = self.installer.build_install_command("OpenJS.NodeJS")
        self.assertIn("OpenJS.NodeJS", cmd)

    def test_build_command_has_accept_flags(self):
        cmd = self.installer.build_install_command("OpenJS.NodeJS")
        self.assertIn("--accept-package-agreements", cmd)
        self.assertIn("--accept-source-agreements", cmd)

    def test_build_command_is_list(self):
        cmd = self.installer.build_install_command("Microsoft.VisualStudioCode")
        self.assertIsInstance(cmd, list)
        self.assertTrue(all(isinstance(s, str) for s in cmd))

    def test_is_available_when_winget_exists(self):
        with patch("shutil.which", return_value="C:\\winget.exe"):
            self.assertTrue(self.installer.is_available())

    def test_is_not_available_when_winget_missing(self):
        with patch("shutil.which", return_value=None):
            self.assertFalse(self.installer.is_available())


if __name__ == "__main__":
    unittest.main()
