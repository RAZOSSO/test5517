"""
LINEで送信された画像を取得してローカルに保存するスクリプト。

使い方:
  1. .env.example を .env にコピーし、トークンを設定
  2. pip install -r requirements.txt
  3. python save_line_image.py
  4. ngrok 等でローカルを公開し、LINE Developers の Webhook URL に設定
"""

import io
import os
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from PIL import Image, ImageOps
from flask import Flask, abort, request
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import ImageMessage, MessageEvent

load_dotenv()

CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
SAVE_DIR = Path(os.getenv("IMAGE_SAVE_DIR", "images"))
PORT = int(os.getenv("PORT", "5001"))

if not CHANNEL_ACCESS_TOKEN or not CHANNEL_SECRET:
    raise SystemExit(
        "LINE_CHANNEL_ACCESS_TOKEN と LINE_CHANNEL_SECRET を .env に設定してください。"
    )

line_bot_api = LineBotApi(CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(CHANNEL_SECRET)
app = Flask(__name__)

CONTENT_TYPE_TO_EXT = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
}


def fix_orientation(data: bytes, ext: str) -> bytes:
    """EXIFの向き情報を反映して画像を正しい向きにする。"""
    if ext not in {".jpg", ".jpeg", ".png", ".webp"}:
        return data

    img = Image.open(io.BytesIO(data))
    img = ImageOps.exif_transpose(img)

    output = io.BytesIO()
    save_format = {".jpg": "JPEG", ".jpeg": "JPEG", ".png": "PNG", ".webp": "WEBP"}[ext]
    save_kwargs = {"quality": 95} if save_format == "JPEG" else {}
    img.save(output, format=save_format, **save_kwargs)
    return output.getvalue()


def save_image(message_id: str) -> Path:
    """message_id から画像をダウンロードして保存する。"""
    content = line_bot_api.get_message_content(message_id)
    ext = CONTENT_TYPE_TO_EXT.get(content.content_type, ".jpg")

    SAVE_DIR.mkdir(parents=True, exist_ok=True)
    filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{message_id}{ext}"
    filepath = SAVE_DIR / filename

    data = b"".join(content.iter_content())
    data = fix_orientation(data, ext)

    filepath.write_bytes(data)
    return filepath


@app.route("/", methods=["GET"])
def health():
    return "LINE webhook server is running", 200


@app.route("/callback", methods=["POST"])
@app.route("/", methods=["POST"])
def callback():
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)

    if not signature:
        print("Webhook error: missing X-Line-Signature header")
        abort(400)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        print("Webhook error: invalid signature (check LINE_CHANNEL_SECRET in .env)")
        abort(400)

    return "OK", 200


@handler.add(MessageEvent, message=ImageMessage)
def handle_image(event):
    message_id = event.message.id
    filepath = save_image(message_id)
    print(f"保存しました: {filepath}")


if __name__ == "__main__":
    # debug=True だと Webhook が二重送信されることがあるため無効化
    print(f"Webhook URL: http://localhost:{PORT}/callback")
    app.run(host="0.0.0.0", port=PORT, debug=False)
