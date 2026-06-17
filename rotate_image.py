"""画像を手動で回転するスクリプト。"""

import sys
from pathlib import Path
from typing import Optional

from PIL import Image

SUPPORTED = {".jpg", ".jpeg", ".png", ".webp"}
ROTATE_MAP = {
    "90": Image.Transpose.ROTATE_270,   # 時計回り90度
    "180": Image.Transpose.ROTATE_180,
    "270": Image.Transpose.ROTATE_90,   # 反時計回り90度 = 時計回り270度
    "-90": Image.Transpose.ROTATE_90,   # 反時計回り90度
    "cw": Image.Transpose.ROTATE_270,   # clockwise
    "ccw": Image.Transpose.ROTATE_90,   # counter-clockwise
}


def rotate_file(path: Path, angle: str, output: Optional[Path] = None) -> Path:
    ext = path.suffix.lower()
    if ext not in SUPPORTED:
        raise ValueError(f"対応していない形式です: {ext}")

    if angle not in ROTATE_MAP:
        raise ValueError("角度は 90 / 180 / 270 / -90 / cw / ccw のいずれかを指定してください")

    img = Image.open(path)
    rotated = img.transpose(ROTATE_MAP[angle])

    save_path = output or path
    save_format = {".jpg": "JPEG", ".jpeg": "JPEG", ".png": "PNG", ".webp": "WEBP"}[ext]
    save_kwargs = {"quality": 95} if save_format == "JPEG" else {}
    rotated.save(save_path, format=save_format, **save_kwargs)
    return save_path


def print_usage() -> None:
    print("使い方:")
    print("  python rotate_image.py <画像ファイル> <角度>")
    print("  python rotate_image.py <画像ファイル> <角度> <保存先>")
    print()
    print("角度:")
    print("  90   ... 時計回りに90度")
    print("  180  ... 180度回転")
    print("  270  ... 時計回りに270度（反時計回り90度）")
    print("  -90  ... 反時計回りに90度")
    print("  cw   ... 時計回りに90度")
    print("  ccw  ... 反時計回りに90度")
    print()
    print("例:")
    print("  python rotate_image.py images\\photo.jpg 90")
    print("  python rotate_image.py images\\photo.jpg ccw images\\photo_fixed.jpg")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print_usage()
        raise SystemExit(1)

    src = Path(sys.argv[1])
    angle = sys.argv[2].lower()
    dst = Path(sys.argv[3]) if len(sys.argv) > 3 else None

    if not src.is_file():
        raise SystemExit(f"ファイルが見つかりません: {src}")

    saved = rotate_file(src, angle, dst)
    print(f"保存しました: {saved}")
