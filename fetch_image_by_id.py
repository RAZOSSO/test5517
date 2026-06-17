"""
既に message_id が分かっている場合に、画像だけを取得して保存する単体スクリプト。

例:
  python fetch_image_by_id.py 1234567890abcdef
"""

import os
import sys
from datetime import datetime
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
SAVE_DIR = Path(os.getenv("IMAGE_SAVE_DIR", "images"))

CONTENT_TYPE_TO_EXT = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
}


def fetch_and_save(message_id: str) -> Path:
    if not TOKEN:
        raise SystemExit("LINE_CHANNEL_ACCESS_TOKEN を .env に設定してください。")

    url = f"https://api-data.line.me/v2/bot/message/{message_id}/content"
    headers = {"Authorization": f"Bearer {TOKEN}"}

    response = requests.get(url, headers=headers, stream=True, timeout=30)
    response.raise_for_status()

    ext = CONTENT_TYPE_TO_EXT.get(response.headers.get("Content-Type", ""), ".jpg")
    SAVE_DIR.mkdir(parents=True, exist_ok=True)

    filepath = SAVE_DIR / f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{message_id}{ext}"
    with filepath.open("wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)

    return filepath


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("使い方: python fetch_image_by_id.py <message_id>")

    path = fetch_and_save(sys.argv[1])
    print(f"保存しました: {path}")
