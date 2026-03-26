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
from typing import Optional


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
    """PIL Image → CTkImage 썸네일. 실패 시 None 반환."""
    try:
        import customtkinter as ctk
        thumb = img.copy()
        thumb.thumbnail(size)
        return ctk.CTkImage(light_image=thumb, dark_image=thumb, size=size)
    except Exception:
        return None


def is_available() -> bool:
    """Pillow 설치 여부를 확인합니다."""
    try:
        import PIL  # noqa: F401
        return True
    except ImportError:
        return False


def grab_clipboard_image() -> Optional[ImageAttachment]:
    """
    클립보드에서 이미지를 가져옵니다 (Windows/macOS).
    이미지가 없으면 None을 반환합니다.
    """
    try:
        from PIL import ImageGrab
        data = ImageGrab.grabclipboard()
        if data is None:
            return None

        # 파일 경로 리스트인 경우 (파일을 복사했을 때)
        if isinstance(data, list):
            for path in data:
                if Path(path).suffix.lower() in (
                    ".png", ".jpg", ".jpeg", ".bmp", ".gif", ".webp"
                ):
                    return load_image_from_file(path)
            return None

        # PIL Image 객체인 경우 (스크린샷 캡처 후 붙여넣기)
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
