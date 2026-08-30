import os
import json
import requests
from datetime import datetime, timezone, timedelta
from http.server import BaseHTTPRequestHandler


BOT_TOKEN = os.environ["BOT_TOKEN"]
IMGBB_API_KEY = os.environ["IMGBB_API_KEY"]
SUPABASE_URL = os.environ["SUPABASE_URL"].rstrip("/")
SUPABASE_KEY = os.environ["SUPABASE_KEY"]
ADMIN_ID = str(os.environ["ADMIN_ID"])


TELEGRAM_API = f"https://api.telegram.org/bot{BOT_TOKEN}"


def telegram(method, data=None):
    response = requests.post(
        f"{TELEGRAM_API}/{method}",
        data=data or {},
        timeout=30,
    )
    return response.json()


def supabase_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json",
    }


def supabase_get(table, params=None):
    response = requests.get(
        f"{SUPABASE_URL}/rest/v1/{table}",
        headers=supabase_headers(),
        params=params or {},
        timeout=20,
    )
    response.raise_for_status()
    return response.json()


def supabase_insert(table, data, upsert=False):
    headers = supabase_headers()

    if upsert:
        headers["Prefer"] = "resolution=merge-duplicates"

    response = requests.post(
        f"{SUPABASE_URL}/rest/v1/{table}",
        headers=headers,
        json=data,
        timeout=20,
    )
    response.raise_for_status()
    return response.json()


def supabase_update(table, data, params):
    response = requests.patch(
        f"{SUPABASE_URL}/rest/v1/{table}",
        headers=supabase_headers(),
        params=params,
        json=data,
        timeout=20,
    )
    response.raise_for_status()
    return response.json()


def send_message(chat_id, text):
    telegram(
        "sendMessage",
        {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        },
    )


def record_user(user_id):
    try:
        users = supabase_get(
            "bot_users",
            {
                "select": "user_id",
                "user_id": f"eq.{user_id}",
                "limit": "1",
            },
        )

        now = datetime.now(timezone.utc).isoformat()

        if users:
            supabase_update(
                "bot_users",
                {"last_seen": now},
                {"user_id": f"eq.{user_id}"},
            )
            return False

        supabase_insert(
            "bot_users",
            {
                "user_id": user_id,
                "last_seen": now,
            },
        )

        return True

    except Exception as error:
        print("USER ERROR:", error)
        return False


def update_stats(upload=False, ping=False, new_user=False):
    try:
        rows = supabase_get(
            "bot_stats",
            {
                "select": "*",
                "id": "eq.1",
                "limit": "1",
            },
        )

        if not rows:
            supabase_insert(
                "bot_stats",
                {
                    "id": 1,
                    "total_uploads": 1 if upload else 0,
                    "unique_users": 1 if new_user else 0,
                    "weekly_uploads": 1 if upload else 0,
                    "pings": 1 if ping else 0,
                },
            )
            return

        stats = rows[0]

        values = {
            "total_uploads": int(stats.get("total_uploads", 0))
            + (1 if upload else 0),

            "unique_users": int(stats.get("unique_users", 0))
            + (1 if new_user else 0),

            "weekly_uploads": int(stats.get("weekly_uploads", 0))
            + (1 if upload else 0),

            "pings": int(stats.get("pings", 0))
            + (1 if ping else 0),
        }

        supabase_update(
            "bot_stats",
            values,
            {"id": "eq.1"},
        )

    except Exception as error:
        print("STATS ERROR:", error)


def bot_stats(chat_id):
    if str(chat_id) != ADMIN_ID:
        send_message(
            chat_id,
            "⛔ <b>Access Denied</b>\n\n"
            "This command is available to the bot administrator only.",
        )
        return

    try:
        rows = supabase_get(
            "bot_stats",
            {
                "select": "*",
                "id": "eq.1",
                "limit": "1",
            },
        )

        if not rows:
            send_message(
                chat_id,
                "📊 <b>BOT STATS</b>\n\n"
                "No statistics available yet.",
            )
            return

        stats = rows[0]

        text = (
            "╭────────────────────╮\n"
            "│    🛠️ BOT STATS    │\n"
            "╰────────────────────╯\n\n"
            f"📸 Total Uploads: <b>{stats.get('total_uploads', 0)}</b>\n"
            f"👥 Unique Users: <b>{stats.get('unique_users', 0)}</b>\n"
            f"📅 This Week: <b>{stats.get('weekly_uploads', 0)}</b>\n"
            f"📢 Pings: <b>{stats.get('pings', 0)}</b>\n\n"
            "🟢 Status: <b>ACTIVE</b>\n"
            "🔐 Access: <b>ADMIN ONLY</b>"
        )

        send_message(chat_id, text)

    except Exception as error:
        print("STATS DISPLAY ERROR:", error)

        send_message(
            chat_id,
            "❌ Couldn't load statistics.",
        )


def upload_image(image_bytes, filename):
    response = requests.post(
        "https://api.imgbb.com/1/upload",
        params={
            "key": IMGBB_API_KEY,
        },
        files={
            "image": (filename, image_bytes),
        },
        timeout=30,
    )

    response.raise_for_status()

    data = response.json()

    if not data.get("success"):
        raise Exception("ImgBB upload failed")

    return data["data"]


def process_update(update):
    message = update.get("message")

    if not message:
        return

    chat_id = message["chat"]["id"]

    user = message.get("from", {})
    user_id = user.get("id")

    if user_id:
        new_user = record_user(user_id)
    else:
        new_user = False

    # /start
    message_text = message.get("text", "")

    if message_text.startswith("/start"):
        update_stats(
            ping=True,
            new_user=new_user,
        )

        send_message(
            chat_id,
            "╭────────────────────╮\n"
            "│ 🖼️ <b>IMAGE TO URL BOT</b> │\n"
            "╰────────────────────╯\n\n"
            "Send me an image and I'll convert it into a public direct URL.\n\n"
            "🔒 <b>Privacy Notice</b>\n\n"
            "Please <b>do not send private, personal, confidential, "
            "or sensitive photos</b>.\n\n"
            "Uploaded images are sent to a third-party image-hosting "
            "service to generate the URL.\n\n"
            "⚡ Fast • Simple • Personal",
        )
        return

    # /botstats
    if message_text.startswith("/botstats"):
        bot_stats(chat_id)
        return

    # Image
    photos = message.get("photo")

    if not photos:
        return

    try:
        photo = photos[-1]

        file_id = photo["file_id"]
        unique_id = photo["file_unique_id"]

        file_info = telegram(
            "getFile",
            {
                "file_id": file_id,
            },
        )

        if not file_info.get("ok"):
            raise Exception("Telegram getFile failed")

        telegram_path = file_info["result"]["file_path"]

        download_url = (
            f"https://api.telegram.org/file/"
            f"bot{BOT_TOKEN}/{telegram_path}"
        )

        image_response = requests.get(
            download_url,
            timeout=30,
        )

        image_response.raise_for_status()

        filename = f"telegram-image-{unique_id}.jpg"

        image_data = upload_image(
            image_response.content,
            filename,
        )

        image_url = image_data["url"]

        width = photo.get("width", "?")
        height = photo.get("height", "?")

        update_stats(upload=True)

        result = (
            "╭───────────────╮\n"
            "│  ✨ <b>IMAGE READY</b> │\n"
            "╰───────────────╯\n\n"
            "🔗 <b>Direct URL</b>\n\n"
            f"<code>{image_url}</code>\n\n"
            "━━━━━━━━━━━━━━━━\n"
            "🖼️ Format: JPG\n"
            f"📐 Size: {width} × {height}\n"
            "━━━━━━━━━━━━━━━━"
        )

        send_message(
            chat_id,
            result,
        )

    except Exception as error:
        print("IMAGE ERROR:", error)

        send_message(
            chat_id,
            "❌ <b>Upload failed.</b>\n\n"
            "Please try sending the image again.",
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

            body = self.rfile.read(content_length)

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
