"""
명령어 안전 검사 모듈

모든 외부 명령어는 실행 전 이 모듈을 통해 검사됩니다.
화이트리스트 방식(허용 목록) + 위험 패턴 블랙리스트를 함께 사용합니다.
"""
import re
from typing import List, Tuple

# ── 허용된 실행 파일 목록 (이 외의 실행 파일은 모두 차단) ──────────────────
ALLOWED_EXECUTABLES = {
    # 패키지 관리자
    "winget", "choco", "brew",
    "apt", "apt-get", "snap", "dnf", "yum", "pacman", "zypper",
    # JS 생태계
    "npm", "npx", "node", "yarn", "pnpm", "deno", "bun",
    # Python 생태계
    "pip", "pip3", "python", "python3",
    # 기타 런타임 / 도구
    "git", "code", "cargo", "rustup", "go", "dotnet",
    "mvn", "gradle", "java", "javac",
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


def is_safe_command(cmd: List[str]) -> Tuple[bool, str]:
    """
    명령어 리스트를 검사합니다.
    Returns:
        (True, "")           — 안전
        (False, "사유")      — 차단
    """
    if not cmd:
        return False, "빈 명령어입니다."

    # 실행 파일명 추출 (전체 경로 및 .exe 확장자 제거)
    exe_raw = cmd[0].replace("\\", "/").split("/")[-1].lower()
    exe_name = exe_raw[:-4] if exe_raw.endswith(".exe") else exe_raw

    if exe_name not in ALLOWED_EXECUTABLES:
        return False, f"허용되지 않은 실행 파일: '{cmd[0]}'"

    full_str = " ".join(cmd)
    for pattern, reason in DANGEROUS_PATTERNS:
        if re.search(pattern, full_str, re.IGNORECASE):
            return False, reason

    return True, ""
