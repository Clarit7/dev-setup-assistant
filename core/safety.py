"""
명령어 안전 검사 모듈

모든 외부 명령어는 실행 전 이 모듈을 통해 검사됩니다.
화이트리스트 방식(허용 목록) + 위험 패턴 블랙리스트를 함께 사용합니다.
"""
import re
from typing import List, Tuple

# ── 세션 동적 화이트리스트 (앱 종료 시 소멸) ─────────────────────────────────
_DYNAMIC_WHITELIST: set = set()

# ── 허용된 실행 파일 목록 (이 외의 실행 파일은 모두 차단) ──────────────────
ALLOWED_EXECUTABLES = {
    # 패키지 관리자
    "winget", "choco", "brew", "scoop",
    "apt", "apt-get", "snap", "dnf", "yum", "pacman", "zypper",
    # 다운로드 도구 (curl | bash 패턴은 블랙리스트가 별도 차단)
    "curl", "wget",
    # JS 생태계
    "npm", "npx", "node", "yarn", "pnpm", "deno", "bun",
    # Node.js 버전 관리자
    "nvm", "volta", "fnm",
    # Python 생태계
    "pip", "pip3", "python", "python3",
    "pyenv",                             # Python 버전 관리자
    "uv",                                # 고속 Python 패키지 관리자
    # Ruby 생태계
    "ruby", "gem", "bundle", "rbenv", "rvm",
    # PHP
    "php", "composer",
    # 기타 런타임 / 도구
    "git", "code", "cargo", "rustup", "go", "dotnet",
    "mvn", "gradle", "java", "javac",
    # Kotlin
    "kotlin", "kotlinc",
    # Flutter / Dart
    "flutter", "dart",
    # Swift
    "swift", "swiftc",
    # Elixir / Erlang
    "elixir", "mix", "erlang", "rebar3",
    # Haskell
    "stack", "cabal", "ghc",
    # Lua
    "lua", "luarocks",
    # Julia
    "julia",
    # 컨테이너
    "docker", "docker-compose", "podman", "wsl",
    # 쿠버네티스 / 클라우드 인프라
    "kubectl", "helm", "minikube", "k9s", "kind", "k3s",
    "terraform", "tofu",
    # 클라우드 CLI
    "az",                                # Azure CLI
    "aws",                               # AWS CLI
    "gcloud", "gsutil", "bq",           # Google Cloud SDK
    # 배포 CLI
    "vercel", "netlify",
    # AI 코드 에이전트
    "claude",   # Claude Code (Anthropic)
    "codex",    # OpenAI Codex CLI
    "gemini",   # Gemini CLI (Google)
    "aider",    # Aider
    "gh",       # GitHub CLI (gh extension install github/gh-copilot)
    "cursor",   # Cursor IDE 런처
    # C / C++ 빌드 도구
    "gcc", "g++", "cc", "c++",          # GCC / MinGW
    "clang", "clang++",                  # LLVM Clang
    "cmake", "ctest", "cpack",           # CMake
    "make", "nmake", "mingw32-make",     # Make
    "meson", "ninja",                    # Meson + Ninja
    "gdb", "lldb",                       # 디버거
    # 데이터베이스 CLI
    "psql", "pg_ctl", "createdb", "dropdb", "initdb",   # PostgreSQL
    "mysql", "mysqladmin", "mysqldump",                  # MySQL / MariaDB
    "mongod", "mongosh", "mongo",                        # MongoDB
    "redis-cli", "redis-server",                         # Redis
    "sqlite3",                                           # SQLite
    # SSH
    "ssh", "ssh-keygen", "ssh-add", "ssh-copy-id",
}

# ── 위험한 인자 패턴 (허용된 실행 파일 내에서도 차단) ─────────────────────
DANGEROUS_PATTERNS: List[Tuple[str, str]] = [
    # 시스템 경로 접근
    (r"[Ss]ystem32",            "Windows 시스템 디렉토리 접근 금지"),
    (r"[Ss]ys[Ww][Oo][Ww]64",  "Windows 시스템 디렉토리 접근 금지"),
    (r"%[Ww][Ii][Nn][Dd][Ii][Rr]%", "Windows 디렉토리 접근 금지"),
    # 디스크 / 파티션 조작
    (r"\bformat\b",             "디스크 포맷 명령어 차단"),
    (r"\bdiskpart\b",           "디스크 파티션 명령어 차단"),
    (r"\bfdisk\b",              "디스크 파티션 명령어 차단"),
    (r"\bdd\b.*\bof=",          "디스크 덮어쓰기 명령어 차단"),
    # 강제 삭제
    (r"\brm\s+-[Rrf]*f[Rrf]*\b", "강제 재귀 삭제 차단"),
    (r"del\s+/[sfqSFQ].*\\",    "강제 삭제 차단"),
    # 레지스트리 / 부트 조작
    (r"\breg\s+delete\b",       "레지스트리 삭제 차단"),
    (r"\bbcdedit\b",            "부트 설정 변경 차단"),
    # 셸 난독화 / 인젝션
    (r"-[Ee]ncodedCommand",     "PowerShell 난독화 차단"),
    (r"\|\s*(bash|sh|cmd|powershell|pwsh)\b", "셸 파이프 인젝션 차단"),
    # 명령어 체이닝을 이용한 삭제
    (r"&&\s*(del|rm)\b",        "체이닝 삭제 명령어 차단"),
    (r";\s*(del|rm)\b",         "체이닝 삭제 명령어 차단"),
    # 시스템 종료 / 재시작
    (r"\bshutdown\b",           "시스템 종료 명령어 차단"),
    (r"\brestart\b",            "시스템 재시작 명령어 차단"),
    # 서비스 / 프로세스 강제 조작
    (r"\bsc\s+(delete|stop)\b", "서비스 강제 조작 차단"),
    (r"\btaskkill\b.*\s/[Ff]\b.*\b(lsass|svchost|winlogon|csrss)", "시스템 프로세스 강제 종료 차단"),
]


def get_exe_name(cmd: List[str]) -> str:
    """명령어 리스트에서 실행 파일명을 추출합니다 (경로·.exe 제거, 소문자)."""
    if not cmd:
        return ""
    exe_raw = cmd[0].replace("\\", "/").split("/")[-1].lower()
    return exe_raw[:-4] if exe_raw.endswith(".exe") else exe_raw


def is_in_dynamic_whitelist(exe: str) -> bool:
    """세션 동적 화이트리스트에 해당 실행 파일이 있는지 확인합니다."""
    return exe.lower() in _DYNAMIC_WHITELIST


def add_to_dynamic_whitelist(exe: str) -> None:
    """세션 동적 화이트리스트에 실행 파일을 추가합니다."""
    _DYNAMIC_WHITELIST.add(exe.lower())


def is_in_blacklist(cmd: List[str]) -> Tuple[bool, str]:
    """
    블랙리스트 패턴만 검사합니다 (화이트리스트 무관).
    Returns:
        (True,  "사유") — 블랙리스트 매칭
        (False, "")     — 이상 없음
    """
    full_str = " ".join(cmd)
    for pattern, reason in DANGEROUS_PATTERNS:
        if re.search(pattern, full_str, re.IGNORECASE):
            return True, reason
    return False, ""


def is_safe_command(cmd: List[str]) -> Tuple[bool, str]:
    """
    명령어 리스트를 검사합니다.
    화이트리스트(정적 + 동적) 확인 → 블랙리스트 패턴 확인 순서입니다.
    Returns:
        (True, "")           — 안전
        (False, "사유")      — 차단
    """
    if not cmd:
        return False, "빈 명령어입니다."

    exe_name = get_exe_name(cmd)

    if exe_name not in ALLOWED_EXECUTABLES and not is_in_dynamic_whitelist(exe_name):
        return False, f"허용되지 않은 실행 파일: '{cmd[0]}'"

    in_bl, reason = is_in_blacklist(cmd)
    if in_bl:
        return False, reason

    return True, ""
