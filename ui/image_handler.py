"""
이미지 첨부/붙여넣기 처리 모듈

클립보드 이미지 감지 또는 파일 선택으로 이미지를 로드하고
LLM 비전 API에 전달할 수 있는 형식(base64)으로 변환합니다.

Pillow(PIL)가 설치되지 않은 경우 이미지 기능은 자동으로 비활성화됩니다.
"""

import base64
import io
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, List


@dataclass
class ImageAttachment:
    base64_data: str          # base64 인코딩된 이미지 데이터
    media_type: str           # "image/png", "image/jpeg" 등
    thumbnail: object         # CTkImage 썸네일 (GUI 표시용), None 가능
    source_path: Optional[str] = None  # 파일에서 로드된 경우 원본 경로


def _pil_to_base64(img, fmt: str = "PNG"):
    """PIL Image → (base64_string, media_type)"""
    buf = io.BytesIO()
    # RGBA → RGB 변환 (JPEG 저장 시 필요)
    if fmt == "JPEG" and img.mode in ("RGBA", "P"):
        img = img.convert("RGB")
    img.save(buf, format=fmt)
    b64 = base64.b64encode(buf.getvalue()).decode("utf-8")
    media_type = f"image/{fmt.lower().replace('jpeg', 'jpeg')}"
    return b64, media_type


def _make_thumbnail(img, size=(80, 60)):
    """PIL Image → CTkImage 썸네일 (letterbox로 원본 비율 유지). 실패 시 None 반환."""
    try:
        from PIL import Image as PILImage
        import customtkinter as ctk

        thumb = img.copy()
        thumb.thumbnail(size, PILImage.LANCZOS)  # 비율 유지 축소

        # size 박스에 검정 배경 letterbox 합성
        canvas = PILImage.new("RGBA", size, (0, 0, 0, 0))
        x = (size[0] - thumb.width)  // 2
        y = (size[1] - thumb.height) // 2
        if thumb.mode != "RGBA":
            thumb = thumb.convert("RGBA")
        canvas.paste(thumb, (x, y))

        return ctk.CTkImage(light_image=canvas, dark_image=canvas, size=size)
    except Exception:
        return None


def is_available() -> bool:
    """Pillow 설치 여부를 확인합니다."""
    try:
        import PIL  # noqa: F401
        return True
    except ImportError:
        return False


_IMAGE_EXTS = frozenset((".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp"))

# Windows 클립보드 형식 ID
_CF_HDROP = 15   # 파일 드롭 (탐색기 Ctrl+C)
_CF_DIB   = 8    # DIB 비트맵 (스크린샷)
_CF_DIBV5 = 17   # DIB v5 비트맵


def _clipboard_has_format(fmt_id: int) -> bool:
    """클립보드를 열지 않고 특정 형식의 존재 여부를 확인합니다."""
    try:
        import ctypes
        return bool(ctypes.windll.user32.IsClipboardFormatAvailable(fmt_id))
    except Exception:
        return False


def _get_clipboard_files_win32() -> Optional[List[str]]:
    """Windows 클립보드에서 CF_HDROP 파일 경로 목록을 ctypes로 직접 가져옵니다."""
    try:
        import ctypes
        import ctypes.wintypes
        user32  = ctypes.windll.user32
        shell32 = ctypes.windll.shell32
        kernel32 = ctypes.windll.kernel32

        # 64비트 Windows에서 HANDLE은 64비트 — 기본 c_int로는 잘림
        user32.GetClipboardData.restype = ctypes.c_void_p
        user32.GetClipboardData.argtypes = [ctypes.c_uint]
        shell32.DragQueryFileW.restype  = ctypes.c_uint
        shell32.DragQueryFileW.argtypes = [
            ctypes.c_void_p,  # hDrop
            ctypes.c_uint,    # iFile
            ctypes.c_wchar_p, # lpszFile
            ctypes.c_uint,    # cch
        ]

        if not user32.OpenClipboard(None):
            return None
        try:
            h_drop = user32.GetClipboardData(_CF_HDROP)
            if not h_drop:
                return None
            count = shell32.DragQueryFileW(h_drop, 0xFFFFFFFF, None, 0)
            files = []
            for i in range(count):
                buf = ctypes.create_unicode_buffer(260)
                shell32.DragQueryFileW(h_drop, i, buf, 260)
                files.append(buf.value)
            return files if files else None
        finally:
            user32.CloseClipboard()
    except Exception:
        return None


def grab_clipboard_image() -> Optional[ImageAttachment]:
    """
    클립보드에서 이미지를 가져옵니다 (Windows/macOS).
    이미지가 없으면 None을 반환합니다.
    """
    try:
        # ── Windows 파일 복사(CF_HDROP) 감지 ──────────────────────────────────
        # IsClipboardFormatAvailable은 클립보드를 열지 않아도 호출 가능.
        # CF_HDROP가 있으면 PIL을 절대 호출하지 않음 — PIL은 Windows에서
        # 클립보드 DIB(파일 미리보기 포함)를 tkinter PhotoImage로 변환하려
        # 시도하므로 "pyimage1 doesn't exist" TclError가 발생할 수 있음.
        if _clipboard_has_format(_CF_HDROP):
            files = _get_clipboard_files_win32()
            if files:
                for path in files:
                    if Path(path).suffix.lower() in _IMAGE_EXTS:
                        return load_image_from_file(path)
            # CF_HDROP 있으면 PIL 폴백 없이 바로 None 반환
            return None

        # ── 실제 이미지 데이터(스크린샷 등) — PIL로 처리 ─────────────────────
        # CF_DIB/CF_DIBV5 도 없으면 굳이 PIL을 호출할 필요 없음
        if not (_clipboard_has_format(_CF_DIB) or _clipboard_has_format(_CF_DIBV5)):
            return None

        from PIL import ImageGrab
        data = ImageGrab.grabclipboard()
        if data is None:
            return None

        # PIL이 혹시 리스트를 반환하는 경우 (폴백)
        if isinstance(data, list):
            for path in data:
                if Path(path).suffix.lower() in _IMAGE_EXTS:
                    return load_image_from_file(path)
            return None

        # PIL Image 객체 (스크린샷)
        b64, media_type = _pil_to_base64(data)
        thumbnail = _make_thumbnail(data)
        return ImageAttachment(
            base64_data=b64,
            media_type=media_type,
            thumbnail=thumbnail,
        )
    except Exception:
        return None


def load_image_from_file(path: str) -> Optional[ImageAttachment]:
    """파일 경로에서 이미지를 로드합니다."""
    try:
        from PIL import Image
        img = Image.open(path)
        suffix = Path(path).suffix.lower()
        fmt = "JPEG" if suffix in (".jpg", ".jpeg") else "PNG"
        b64, media_type = _pil_to_base64(img, fmt)
        thumbnail = _make_thumbnail(img)
        return ImageAttachment(
            base64_data=b64,
            media_type=media_type,
            thumbnail=thumbnail,
            source_path=path,
        )
    except Exception:
        return None
