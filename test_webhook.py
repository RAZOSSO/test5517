"""Webhook が正しく 200 を返すか確認するテストスクリプト。"""

import base64
import hashlib
import hmac
import os

import requests
from dotenv import load_dotenv

load_dotenv()

secret = os.getenv("LINE_CHANNEL_SECRET", "")
port = os.getenv("PORT", "5001")
body = '{"events":[],"destination":"Udeadbeef"}'
signature = base64.b64encode(
    hmac.new(secret.encode(), body.encode(), hashlib.sha256).digest()
).decode()

local_url = f"http://127.0.0.1:{port}/callback"
headers = {"Content-Type": "application/json", "X-Line-Signature": signature}

r = requests.post(local_url, data=body, headers=headers, timeout=10)
print(f"local: {r.status_code} {r.text}")

try:
    tunnels = requests.get("http://127.0.0.1:4040/api/tunnels", timeout=5).json()
    public_url = tunnels["tunnels"][0]["public_url"] + "/callback"
    r2 = requests.post(public_url, data=body, headers=headers, timeout=10)
    print(f"ngrok: {r2.status_code} {r2.text}")
    print(f"Webhook URL: {public_url}")
except Exception as e:
    print(f"ngrok test skipped: {e}")
