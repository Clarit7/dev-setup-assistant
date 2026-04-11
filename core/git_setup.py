"""Git 초기 설정 자동화 — 사용자 정보, SSH 키, 원격 연결 테스트"""
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

_CF = 0x08000000


def _git(*args, timeout: int = 5):
    try:
        r = subprocess.run(
            ["git"] + list(args),
            capture_output=True, text=True, timeout=timeout,
            creationflags=_CF,
        )
        return r.returncode == 0, (r.stdout + r.stderr).strip()
    except Exception as e:
        return False, str(e)


@dataclass
class GitConfig:
    user_name: str = ""
    user_email: str = ""
    default_branch: str = ""
    credential_helper: str = ""


@dataclass
class SSHKeyInfo:
    exists: bool = False
    key_type: str = ""      # ed25519, rsa
    public_key: str = ""
    key_path: str = ""


def is_git_installed() -> bool:
    return shutil.which("git") is not None


def get_git_config() -> GitConfig:
    cfg = GitConfig()
    _, cfg.user_name         = _git("config", "--global", "user.name")
    _, cfg.user_email        = _git("config", "--global", "user.email")
    _, cfg.default_branch    = _git("config", "--global", "init.defaultBranch")
    _, cfg.credential_helper = _git("config", "--global", "credential.helper")
    return cfg


def set_git_config(key: str, value: str) -> bool:
    ok, _ = _git("config", "--global", key, value)
    return ok


def detect_ssh_key() -> SSHKeyInfo:
    ssh_dir = Path.home() / ".ssh"
    for key_type, filename in [("ed25519", "id_ed25519"), ("rsa", "id_rsa")]:
        priv = ssh_dir / filename
        pub  = ssh_dir / f"{filename}.pub"
        if priv.exists() and pub.exists():
            try:
                public_key = pub.read_text(encoding="utf-8").strip()
            except Exception:
                public_key = ""
            return SSHKeyInfo(
                exists=True, key_type=key_type,
                public_key=public_key, key_path=str(priv),
            )
    return SSHKeyInfo(exists=False)


def generate_ssh_key(email: str, key_type: str = "ed25519"):
    """SSH 키를 생성합니다. (success: bool, message: str) 반환."""
    ssh_dir = Path.home() / ".ssh"
    ssh_dir.mkdir(exist_ok=True)
    key_path = str(ssh_dir / f"id_{key_type}")
    priv = Path(key_path)
    if priv.exists():
        return False, f"키가 이미 존재합니다: {key_path}"
    try:
        r = subprocess.run(
            ["ssh-keygen", "-t", key_type, "-C", email, "-f", key_path, "-N", ""],
            capture_output=True, text=True, timeout=30,
            creationflags=_CF,
        )
        if r.returncode == 0:
            return True, key_path
        return False, r.stderr.strip()
    except Exception as e:
        return False, str(e)


def test_remote_connection(host: str) -> str:
    """SSH로 원격 Git 서버 인증을 테스트합니다.
    반환값: 'success' | 'permission_denied' | 'no_ssh' | 'failed'
    """
    if not shutil.which("ssh"):
        return "no_ssh"
    try:
        r = subprocess.run(
            ["ssh", "-T",
             "-o", "StrictHostKeyChecking=no",
             "-o", "ConnectTimeout=8",
             f"git@{host}"],
            capture_output=True, text=True, timeout=12,
            creationflags=_CF,
        )
        out = (r.stdout + r.stderr).lower()
        if "successfully" in out or "you've successfully" in out:
            return "success"
        if "permission denied" in out:
            return "permission_denied"
        return "failed"
    except subprocess.TimeoutExpired:
        return "failed"
    except Exception:
        return "failed"
