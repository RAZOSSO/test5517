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
import csv
import json
import base64
import shutil
import tempfile
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from PIL import Image, ImageOps
from flask import Flask, abort, request
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import ImageMessage, MessageEvent

try:
    import pytesseract
except ImportError:
    pytesseract = None

try:
    import gspread
except ImportError:
    gspread = None

load_dotenv()

CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")
SAVE_DIR = Path(os.getenv("IMAGE_SAVE_DIR", "images"))
PORT = int(os.getenv("PORT", "5001"))
OCR_OUTPUT_CSV = Path(os.getenv("OCR_OUTPUT_CSV", "line_ocr_records.csv"))
OCR_LANGUAGE = os.getenv("OCR_LANGUAGE", "jpn+eng")
GOOGLE_SERVICE_ACCOUNT_JSON = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON", "")
GOOGLE_SERVICE_ACCOUNT_JSON_CONTENT = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON_CONTENT", "")
GOOGLE_SERVICE_ACCOUNT_JSON_B64 = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON_B64", "")
GOOGLE_SHEET_ID = os.getenv("GOOGLE_SHEET_ID", "")
GOOGLE_SHEET_NAME = os.getenv("GOOGLE_SHEET_NAME", "Sheet1")
TESSERACT_CMD = os.getenv("TESSERACT_CMD", "")
TESSDATA_PREFIX = os.getenv("TESSDATA_PREFIX", "")

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
worksheet_cache = None
service_account_tempfile = None


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


def extract_text_from_image(image_path: Path) -> str:
    """画像からテキストを抽出する。pytesseract未導入時は空文字。"""
    if pytesseract is None:
        return ""

    if TESSERACT_CMD:
        pytesseract.pytesseract.tesseract_cmd = TESSERACT_CMD
    else:
        detected = shutil.which("tesseract")
        default_windows = Path("C:/Program Files/Tesseract-OCR/tesseract.exe")
        if detected:
            pytesseract.pytesseract.tesseract_cmd = detected
        elif default_windows.exists():
            pytesseract.pytesseract.tesseract_cmd = str(default_windows)

    if TESSDATA_PREFIX:
        os.environ["TESSDATA_PREFIX"] = TESSDATA_PREFIX
    else:
        heroku_tessdata = Path("/app/.apt/usr/share/tesseract-ocr/5/tessdata")
        if heroku_tessdata.exists():
            os.environ["TESSDATA_PREFIX"] = str(heroku_tessdata)

    try:
        img = Image.open(image_path)
        # OCR精度向上のため、グレースケール化して処理する
        img = ImageOps.grayscale(ImageOps.exif_transpose(img))
        text = pytesseract.image_to_string(img, lang=OCR_LANGUAGE)
        return text.strip()
    except Exception as e:
        print(f"OCRエラー: {e}")
        return ""


def append_ocr_record(
    received_at: str, message_id: str, image_path: Path, ocr_text: str
) -> Path:
    """OCR結果をスプレッドシート取り込みしやすいCSVに追記する。"""
    OCR_OUTPUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    should_write_header = not OCR_OUTPUT_CSV.exists()

    with OCR_OUTPUT_CSV.open("a", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        if should_write_header:
            writer.writerow(
                ["received_at", "message_id", "image_path", "ocr_text"]
            )
        writer.writerow(
            [
                received_at,
                message_id,
                str(image_path),
                ocr_text,
            ]
        )

    return OCR_OUTPUT_CSV


def get_google_worksheet():
    """Googleスプレッドシートの追記先ワークシートを取得する。"""
    global worksheet_cache
    if worksheet_cache is not None:
        return worksheet_cache

    if not GOOGLE_SHEET_ID:
        return None
    if gspread is None:
        return None

    credentials_path = Path(GOOGLE_SERVICE_ACCOUNT_JSON) if GOOGLE_SERVICE_ACCOUNT_JSON else None
    global service_account_tempfile
    json_content = None
    if GOOGLE_SERVICE_ACCOUNT_JSON_B64:
        try:
            json_content = base64.b64decode(GOOGLE_SERVICE_ACCOUNT_JSON_B64).decode("utf-8")
            json.loads(json_content)
        except Exception as e:
            print(f"Google Sheets設定エラー: GOOGLE_SERVICE_ACCOUNT_JSON_B64 が不正です: {e}")
            return None
    elif GOOGLE_SERVICE_ACCOUNT_JSON_CONTENT:
        try:
            json_content = GOOGLE_SERVICE_ACCOUNT_JSON_CONTENT
            json.loads(json_content)
        except Exception as e:
            print(f"Google Sheets設定エラー: GOOGLE_SERVICE_ACCOUNT_JSON_CONTENT が不正です: {e}")
            return None

    if not credentials_path and json_content:
        try:
            tmp = tempfile.NamedTemporaryFile(
                mode="w", suffix=".json", delete=False, encoding="utf-8"
            )
            tmp.write(json_content)
            tmp.flush()
            tmp.close()
            service_account_tempfile = tmp.name
            credentials_path = Path(tmp.name)
        except Exception as e:
            print(f"Google Sheets設定エラー: 鍵ファイル作成に失敗しました: {e}")
            return None

    if not credentials_path or not credentials_path.exists():
        print("Google Sheets設定エラー: サービスアカウント鍵ファイルが見つかりません。CSVのみ保存します。")
        return None

    try:
        gc = gspread.service_account(filename=str(credentials_path))
        spreadsheet = gc.open_by_key(GOOGLE_SHEET_ID)
        worksheet_cache = spreadsheet.worksheet(GOOGLE_SHEET_NAME)
        return worksheet_cache
    except Exception as e:
        print(f"Google Sheets接続エラー: {e}")
        return None


def append_ocr_record_to_sheet(
    received_at: str, message_id: str, image_path: Path, ocr_text: str
) -> bool:
    """OCR結果をGoogleスプレッドシートへ1行追記する。"""
    ws = get_google_worksheet()
    if ws is None:
        return False

    try:
        ws.append_row(
            [received_at, message_id, str(image_path), ocr_text],
            value_input_option="USER_ENTERED",
        )
        return True
    except Exception as e:
        print(f"Google Sheets追記エラー: {e}")
        return False


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
    ocr_text = extract_text_from_image(filepath)
    received_at = datetime.now().isoformat(timespec="seconds")
    csv_path = append_ocr_record(received_at, message_id, filepath, ocr_text)
    saved_to_sheet = append_ocr_record_to_sheet(
        received_at=received_at,
        message_id=message_id,
        image_path=filepath,
        ocr_text=ocr_text,
    )

    print(f"保存しました: {filepath}")
    print(f"OCR結果を追記しました: {csv_path}")
    if saved_to_sheet:
        print("Googleスプレッドシートにも追記しました。")
    else:
        print("Googleスプレッドシート追記はスキップしました。")
    if not ocr_text:
        print(
            "OCRテキストは空です。pytesseractまたはTesseract OCRの設定を確認してください。"
        )


if __name__ == "__main__":
    # debug=True だと Webhook が二重送信されることがあるため無効化
    print(f"Webhook URL: http://localhost:{PORT}/callback")
    app.run(host="0.0.0.0", port=PORT, debug=False)
