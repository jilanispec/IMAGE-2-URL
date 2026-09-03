import os
import json
import requests
from datetime import datetime, timezone
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

    print("SUPABASE GET STATUS:", response.status_code)
    print("SUPABASE GET RESPONSE:", response.text[:500])

    response.raise_for_status()

    if not response.text.strip():
        return []

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

    if not response.text.strip():
        return []

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

    if not response.text.strip():
        return []

    return response.json()



def send_message(chat_id, text, reply_markup=None):
    data = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }

    if reply_markup:
        data["reply_markup"] = json.dumps(reply_markup)

    telegram("sendMessage", data)

def remove_keyboard(chat_id, text):
    send_message(
        chat_id,
        text,
        {
            "remove_keyboard": True
        }
    )

def answer_callback(callback_id):
    telegram(
        "answerCallbackQuery",
        {
            "callback_query_id": callback_id,
        },
    )


def edit_message(chat_id, message_id, text, reply_markup=None):
    data = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True,
    }

    if reply_markup:
        data["reply_markup"] = json.dumps(reply_markup)

    telegram("editMessageText", data)


def record_user(user_id):
    try:
        users = supabase_get(
            "bot_users",
            {
                "select": "user_id,supermode",
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
                "supermode": False,
            },
        )

        return True

    except Exception as error:
        print("USER ERROR:", error)
        return False


def get_supermode(user_id):
    try:
        rows = supabase_get(
            "bot_users",
            {
                "select": "supermode",
                "user_id": f"eq.{user_id}",
                "limit": "1",
            },
        )

        if rows:
            return bool(rows[0].get("supermode", False))

    except Exception as error:
        print("SUPERMODE GET ERROR:", error)

    return False


def set_supermode(user_id, enabled):
    supabase_update(
        "bot_users",
        {"supermode": enabled},
        {"user_id": f"eq.{user_id}"},
    )


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


def get_next_image_number(user_id):
    rows = supabase_get(
        "saved_images",
        {
            "select": "id",
            "user_id": f"eq.{user_id}",
        },
    )

    return len(rows) + 1


def save_image(user_id, name, url):
    supabase_insert(
        "saved_images",
        {
            "user_id": user_id,
            "name": name,
            "url": url,
        },
    )


def supermode_keyboard():
    return {
        "keyboard": [
            [
                {
                    "text": "🚪 Exit Super Mode"
                }
            ]
        ],
        "resize_keyboard": True,
        "is_persistent": True
    }


def library_keyboard(page, total_pages):
    buttons = []

    navigation = []

    if page > 1:
        navigation.append(
            {
                "text": "◀️ Previous",
                "callback_data": f"library:{page - 1}",
            }
        )

    if page < total_pages:
        navigation.append(
            {
                "text": "Next ▶️",
                "callback_data": f"library:{page + 1}",
            }
        )

    if navigation:
        buttons.append(navigation)

    return {
        "inline_keyboard": buttons
    }


def send_library(chat_id, user_id, page=1, message_id=None):
    try:
        rows = supabase_get(
            "saved_images",
            {
                "select": "id,name,url,created_at",
                "user_id": f"eq.{user_id}",
                "order": "id.desc",
            },
        )

        total = len(rows)

        if total == 0:
            text = (
                "╭────────────────────╮\n"
                "│   🖼️ <b>MY IMAGES</b>   │\n"
                "╰────────────────────╯\n\n"
                "📭 Your image library is empty.\n\n"
                "Use /supermode and send an image to save it."
            )

            if message_id:
                edit_message(chat_id, message_id, text)
            else:
                send_message(chat_id, text)

            return

        per_page = 15
        total_pages = (total + per_page - 1) // per_page

        if page < 1:
            page = 1

        if page > total_pages:
            page = total_pages

        start = (page - 1) * per_page
        page_rows = rows[start:start + per_page]

        lines = [
            "╭────────────────────╮",
            "│   🖼️ <b>MY IMAGES</b>   │",
            "╰────────────────────╯",
            "",
        ]

        for index, image in enumerate(page_rows, start=start + 1):
            name = image.get("name", "Image")
            url = image.get("url", "")

            lines.append(
                f"<b>{index}. {name}</b>\n"
                f"<code>{url}</code>\n"
            )

        lines.extend(
            [
                "━━━━━━━━━━━━━━━━",
                f"📄 Page <b>{page}</b> / <b>{total_pages}</b>",
                f"🖼️ Total: <b>{total}</b>",
            ]
        )

        text = "\n".join(lines)

        keyboard = library_keyboard(page, total_pages)

        if message_id:
            edit_message(
                chat_id,
                message_id,
                text,
                keyboard,
            )
        else:
            send_message(
                chat_id,
                text,
                keyboard,
            )

    except Exception as error:
        print("LIBRARY ERROR:", error)

        if message_id:
            edit_message(
                chat_id,
                message_id,
                "❌ Couldn't load your image library.",
            )
        else:
            send_message(
                chat_id,
                "❌ Couldn't load your image library.",
            )


def process_callback(update):
    callback = update.get("callback_query")

    if not callback:
        return

    callback_id = callback.get("id")
    data = callback.get("data", "")

    message = callback.get("message", {})

    chat = message.get("chat", {})
    chat_id = chat.get("id")

    user = callback.get("from", {})
    user_id = user.get("id")

    if callback_id:
        answer_callback(callback_id)

    if not chat_id or not user_id:
        return

    if data == "exit_supermode":
        try:
            set_supermode(user_id, False)

            edit_message(
                chat_id,
                message.get("message_id"),
                "╭────────────────────╮\n"
                "│   🟢 <b>SUPER MODE OFF</b>   │\n"
                "╰────────────────────╯\n\n"
                "You're back in normal mode.\n\n"
                "Send an image anytime to get its URL.",
            )

        except Exception as error:
            print("EXIT SUPERMODE ERROR:", error)

        return

    if data.startswith("library:"):
        try:
            page = int(data.split(":")[1])
        except Exception:
            page = 1

        send_library(
            chat_id,
            user_id,
            page,
            message.get("message_id"),
        )


def process_update(update):
    if update.get("callback_query"):
        process_callback(update)
        return

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

    message_text = message.get("text", "")
    # Exit Super Mode
    if message_text == "🚪 Exit Super Mode":
        if user_id:
            try:
                set_supermode(user_id, False)

                remove_keyboard(
                    chat_id,
                    "╭────────────────────╮\n"
                    "│   🟢 <b>SUPER MODE OFF</b>   │\n"
                    "╰────────────────────╯\n\n"
                    "You're back in normal mode.\n\n"
                    "Send an image anytime to get its URL."
                )

            except Exception as error:
                print("EXIT SUPERMODE ERROR:", error)

        return
    # /start
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

    # /supermode
    if message_text.startswith("/supermode"):
        if not user_id:
            return

        try:
            set_supermode(user_id, True)

            send_message(
                chat_id,
                "╭────────────────────╮\n"
                "│   🚀 <b>SUPER MODE ON</b>   │\n"
                "╰────────────────────╯\n\n"
                "Your images will now be saved to your personal library.\n\n"
                "🏷️ <b>How naming works:</b>\n"
                "• Add a caption to the image → caption becomes the name.\n"
                "• No caption → automatically named Image 1, Image 2, etc.\n\n"
                "Use /myimages anytime to view your library.",
                supermode_keyboard(),
            )

        except Exception as error:
            print("SUPERMODE ERROR:", error)

        return

    # /myimages
    if message_text.startswith("/myimages"):
        if not user_id:
            return

        send_library(
            chat_id,
            user_id,
            page=1,
        )
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

        # Save image when Super Mode is active
        saved_name = None

        if user_id and get_supermode(user_id):
            caption = message.get("caption", "").strip()

            if caption:
                saved_name = caption
            else:
                saved_name = f"Image {get_next_image_number(user_id)}"

            save_image(
                user_id,
                saved_name,
                image_url,
            )

        result = (
            "╭───────────────╮\n"
            "│  ✨ <b>IMAGE READY</b> │\n"
            "╰───────────────╯\n\n"
            "🔗 <b>Direct URL</b>\n\n"
            f"<code>{image_url}</code>\n\n"
        )

        if saved_name:
            result += (
                f"💾 <b>Saved as:</b> {saved_name}\n\n"
            )

        result += (
            "━━━━━━━━━━━━━━━━\n"
            "🖼️ Format: JPG\n"
            f"📐 Size: {width} × {height}\n"
            "━━━━━━━━━━━━━━━━"
        )

        send_message(
            chat_id,
            result,
            supermode_keyboard() if saved_name else None,
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
