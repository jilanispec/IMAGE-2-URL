import os
import json
import requests

from http.server import BaseHTTPRequestHandler


BOT_TOKEN = os.environ["BOT_TOKEN"]
IMGBB_API_KEY = os.environ["IMGBB_API_KEY"]


TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"


def telegram_send_message(chat_id, text):
    requests.post(
        f"{TELEGRAM_API}/sendMessage",
        data={
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        },
        timeout=20,
    )


def upload_to_imgbb(file_bytes, filename):
    response = requests.post(
        "https://api.imgbb.com/1/upload",
        params={
            "key": IMGBB_API_KEY,
        },
        files={
            "image": (filename, file_bytes),
        },
        timeout=30,
    )

    if response.status_code != 200:
        raise Exception(
            f"ImgBB HTTP {response.status_code}"
        )

    data = response.json()

    if not data.get("success"):
        raise Exception("ImgBB upload failed")

    return data["data"]


def process_update(update):
    message = update.get("message")

    if not message:
        return

    chat_id = message["chat"]["id"]

    # /start
    text = message.get("text", "")

    if text.startswith("/start"):
        telegram_send_message(
            chat_id,
            "╭────────────────────╮\n"
            "│   🖼️ IMAGE TO URL   │\n"
            "╰────────────────────╯\n\n"
            "Send me an image and I'll convert it into a direct URL.\n\n"
            "⚡ Fast • Simple • Personal",
        )
        return

    # Image
    photos = message.get("photo")

    if not photos:
        return

    try:
        # Highest-quality Telegram photo
        photo = photos[-1]

        file_id = photo["file_id"]
        unique_id = photo["file_unique_id"]

        # Get Telegram file information
        file_response = requests.get(
            f"{TELEGRAM_API}/getFile",
            params={
                "file_id": file_id,
            },
            timeout=20,
        )

        file_data = file_response.json()

        if not file_data.get("ok"):
            raise Exception("Telegram getFile failed")

        telegram_path = file_data["result"]["file_path"]

        # Download image from Telegram
        download_url = (
            f"https://api.telegram.org/file/"
            f"bot{BOT_TOKEN}/{telegram_path}"
        )

        image_response = requests.get(
            download_url,
            timeout=30,
        )

        if image_response.status_code != 200:
            raise Exception("Telegram image download failed")

        # Upload to ImgBB
        filename = f"telegram-image-{unique_id}.jpg"

        image_data = upload_to_imgbb(
            image_response.content,
            filename,
        )

        image_url = image_data["url"]

        width = photo.get("width", "?")
        height = photo.get("height", "?")

        result = (
            "╭───────────────╮\n"
            "│  ✨ IMAGE READY │\n"
            "╰───────────────╯\n\n"
            "🔗 Direct URL\n\n"
            f"<code>{image_url}</code>\n\n"
            "━━━━━━━━━━━━━━━━\n"
            "🖼️ Format: JPG\n"
            f"📐 Size: {width} × {height}\n"
            "━━━━━━━━━━━━━━━━"
        )

        telegram_send_message(
            chat_id,
            result,
        )

    except Exception as error:
        print("ERROR:", error)

        telegram_send_message(
            chat_id,
            "❌ Something went wrong.\n\n"
            "Please send the image again.",
        )


class handler(BaseHTTPRequestHandler):

    def do_GET(self):
        self.send_response(200)
        self.send_header(
            "Content-Type",
            "text/plain; charset=utf-8",
        )
        self.end_headers()

        self.wfile.write(
            b"Image URL Bot is online!"
        )

    def do_POST(self):
        try:
            content_length = int(
                self.headers.get(
                    "Content-Length",
                    0,
                )
            )

            body = self.rfile.read(
                content_length
            )

            update = json.loads(
                body.decode("utf-8")
            )

            process_update(update)

            self.send_response(200)
            self.send_header(
                "Content-Type",
                "text/plain",
            )
            self.end_headers()

            self.wfile.write(b"OK")

        except Exception as error:
            print("WEBHOOK ERROR:", error)

            self.send_response(500)
            self.send_header(
                "Content-Type",
                "text/plain",
            )
            self.end_headers()

            self.wfile.write(
                b"Internal Server Error"
            )
