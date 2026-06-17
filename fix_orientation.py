"""既に保存済みの画像の向きを一括で修正するスクリプト。"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from PIL import Image, ImageOps

load_dotenv()

SAVE_DIR = Path(__file__).parent / Path(os.getenv("IMAGE_SAVE_DIR", "images"))
SUPPORTED = {".jpg", ".jpeg", ".png", ".webp"}


def fix_file(path: Path) -> bool:
    ext = path.suffix.lower()

    if ext not in SUPPORTED:

        return False



    img = Image.open(path)

    fixed = ImageOps.exif_transpose(img)

    if fixed is img:

        return False



    save_format = {".jpg": "JPEG", ".jpeg": "JPEG", ".png": "PNG", ".webp": "WEBP"}[ext]

    save_kwargs = {"quality": 95} if save_format == "JPEG" else {}

    fixed.save(path, format=save_format, **save_kwargs)

    return True





if __name__ == "__main__":

    targets = [Path(p) for p in sys.argv[1:]] if len(sys.argv) > 1 else list(SAVE_DIR.glob("*"))

    fixed_count = 0



    for path in targets:

        if not path.is_file():

            continue

        if fix_file(path):

            print(f"修正: {path}")

            fixed_count += 1



    print(f"完了: {fixed_count} 件を修正しました")

