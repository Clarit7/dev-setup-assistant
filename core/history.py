"""
F. 설치 이력 저장

설치 결과를 history.json에 기록하고, 다음 실행 시 LLM에게 컨텍스트로 제공합니다.
"""

import json
from datetime import datetime
from pathlib import Path
from typing import List, Optional


_HISTORY_FILE = Path(__file__).parent.parent / "history.json"
_MAX_ENTRIES = 50


class HistoryManager:
    def __init__(self, path: Optional[Path] = None):
        self._path = path or _HISTORY_FILE
        self._entries: List[dict] = self._load()

    def _load(self) -> List[dict]:
        try:
            if self._path.exists():
                with open(self._path, encoding="utf-8") as f:
                    data = json.load(f)
                    return data if isinstance(data, list) else []
        except Exception:
            pass
        return []

    def _save(self):
        try:
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump(self._entries, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def record(self, packages: List[str], success: bool):
        """설치 결과를 기록합니다."""
        entry = {
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "packages": packages,
            "success": success,
        }
        self._entries.append(entry)
        if len(self._entries) > _MAX_ENTRIES:
            self._entries = self._entries[-_MAX_ENTRIES:]
        self._save()

    def get_recent(self, n: int = 5) -> List[dict]:
        return self._entries[-n:]

    def format_for_llm(self) -> str:
        """최근 이력을 LLM 시스템 프롬프트용 텍스트로 변환합니다."""
        recent = self.get_recent(5)
        if not recent:
            return ""
        lines = ["## 최근 설치 이력"]
        for e in reversed(recent):
            status = "✓ 성공" if e["success"] else "✗ 실패"
            pkgs = ", ".join(e.get("packages") or [])
            ts = e.get("timestamp", "")[:10]
            lines.append(f"  {ts} {status}: {pkgs}")
        return "\n".join(lines)
