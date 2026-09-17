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


#===== TELEGRAM =====

def telegram(method, data=None):
    response = requests.post(
        f"{TELEGRAM_API}/{method}",
        data=data or {},
        timeout=30
    )
    return response.json()


def send_message(
    chat_id,
    text,
    reply_markup=None,
    reply_to_message_id=None
):
    data = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "HTML",
        "disable_web_page_preview": True
    }

    if reply_markup:
        data["reply_markup"] = json.dumps(
            reply_markup
        )

    if reply_to_message_id:
        data["reply_to_message_id"] = (
            reply_to_message_id
        )

    telegram(
        "sendMessage",
        data
    )


def remove_keyboard(chat_id, text):
    send_message(
        chat_id,
        text,
        {
            "remove_keyboard": True
        }
    )


#===== SUPABASE =====

def supabase_headers():
    return {
        "apikey": SUPABASE_KEY,
        "Authorization": f"Bearer {SUPABASE_KEY}",
        "Content-Type": "application/json"
    }


def supabase_get(table, params=None):
    response = requests.get(
        f"{SUPABASE_URL}/rest/v1/{table}",
        headers=supabase_headers(),
        params=params or {},
        timeout=20
    )

    response.raise_for_status()

    if not response.text.strip():
        return []

    return response.json()


def supabase_insert(
    table,
    data,
    upsert=False
):
    headers = supabase_headers()

    if upsert:
        headers["Prefer"] = (
            "resolution=merge-duplicates"
        )

    response = requests.post(
        f"{SUPABASE_URL}/rest/v1/{table}",
        headers=headers,
        json=data,
        timeout=20
    )

    response.raise_for_status()

    if not response.text.strip():
        return []

    return response.json()


def supabase_update(
    table,
    data,
    params
):
    response = requests.patch(
        f"{SUPABASE_URL}/rest/v1/{table}",
        headers=supabase_headers(),
        params=params,
        json=data,
        timeout=20
    )

    response.raise_for_status()

    if not response.text.strip():
        return []

    return response.json()


#===== USER RECORDING =====

def record_user(user_id):
    try:
        users = supabase_get(
            "bot_users",
            {
                "select": "user_id,supermode",
                "user_id": f"eq.{user_id}",
                "limit": "1"
            }
        )

        now = datetime.now(
            timezone.utc
        ).isoformat()

        if users:

            supabase_update(
                "bot_users",
                {
                    "last_seen": now
                },
                {
                    "user_id":
                        f"eq.{user_id}"
                }
            )

            return False

        supabase_insert(
            "bot_users",
            {
                "user_id": user_id,
                "last_seen": now,
                "supermode": False
            }
        )

        return True

    except Exception as error:
        print(
            "USER ERROR:",
            error
        )
        return False


#===== GROUP RECORDING =====

def save_chat(message):
    try:

        chat = message.get(
            "chat",
            {}
        )

        chat_id = chat.get("id")
        chat_type = chat.get("type")

        if not chat_id:
            return

        if chat_type not in [
            "group",
            "supergroup"
        ]:
            return

        supabase_insert(
            "bot_chats",
            {
                "chat_id": chat_id,
                "type": chat_type,
                "last_seen":
                    datetime.now(
                        timezone.utc
                    ).isoformat()
            },
            upsert=True
        )

    except Exception as error:
        print(
            "CHAT ERROR:",
            error
        )


#===== SUPERMODE =====

def get_supermode(user_id):
    try:

        rows = supabase_get(
            "bot_users",
            {
                "select": "supermode",
                "user_id":
                    f"eq.{user_id}",
                "limit": "1"
            }
        )

        if rows:
            return bool(
                rows[0].get(
                    "supermode",
                    False
                )
            )

    except Exception as error:
        print(
            "SUPERMODE GET ERROR:",
            error
        )

    return False


def set_supermode(
    user_id,
    enabled
):
    supabase_update(
        "bot_users",
        {
            "supermode": enabled
        },
        {
            "user_id":
                f"eq.{user_id}"
        }
    )


def supermode_keyboard():
    return {
        "keyboard": [
            [
                {
                    "text":
                        "🚪 Exit Super Mode"
                }
            ]
        ],
        "resize_keyboard": True,
        "is_persistent": True
    }


#===== STATS =====

def update_stats(
    upload=False,
    ping=False,
    new_user=False
):
    try:

        rows = supabase_get(
            "bot_stats",
            {
                "select": "*",
                "id": "eq.1",
                "limit": "1"
            }
        )

        if not rows:

            supabase_insert(
                "bot_stats",
                {
                    "id": 1,
                    "total_uploads":
                        1 if upload else 0,
                    "unique_users":
                        1 if new_user else 0,
                    "weekly_uploads":
                        1 if upload else 0,
                    "pings":
                        1 if ping else 0
                }
            )

            return

        stats = rows[0]

        values = {
            "total_uploads":
                int(
                    stats.get(
                        "total_uploads",
                        0
                    )
                )
                + (1 if upload else 0),

            "unique_users":
                int(
                    stats.get(
                        "unique_users",
                        0
                    )
                )
                + (1 if new_user else 0),

            "weekly_uploads":
                int(
                    stats.get(
                        "weekly_uploads",
                        0
                    )
                )
                + (1 if upload else 0),

            "pings":
                int(
                    stats.get(
                        "pings",
                        0
                    )
                )
                + (1 if ping else 0)
        }

        supabase_update(
            "bot_stats",
            values,
            {
                "id": "eq.1"
            }
        )

    except Exception as error:
        print(
            "STATS ERROR:",
            error
        )


def bot_stats(chat_id):

    if str(chat_id) != ADMIN_ID:

        send_message(
            chat_id,
            "⛔ <b>Access Denied</b>\n\n"
            "This command is available to "
            "the bot administrator only."
        )

        return

    try:

        rows = supabase_get(
            "bot_stats",
            {
                "select": "*",
                "id": "eq.1",
                "limit": "1"
            }
        )

        if not rows:

            send_message(
                chat_id,
                "📊 <b>BOT STATS</b>\n\n"
                "No statistics available yet."
            )

            return

        stats = rows[0]

        text = (
            "╭────────────────────╮\n"
            "│    🛠️ BOT STATS    │\n"
            "╰────────────────────╯\n\n"

            f"📸 Total Uploads: "
            f"<b>{stats.get('total_uploads', 0)}</b>\n"

            f"👥 Unique Users: "
            f"<b>{stats.get('unique_users', 0)}</b>\n"

            f"📅 This Week: "
            f"<b>{stats.get('weekly_uploads', 0)}</b>\n"

            f"📢 Pings: "
            f"<b>{stats.get('pings', 0)}</b>\n\n"

            "🟢 Status: <b>ACTIVE</b>\n"
            "🔐 Access: <b>ADMIN ONLY</b>"
        )

        send_message(
            chat_id,
            text
        )

    except Exception as error:

        print(
            "STATS DISPLAY ERROR:",
            error
        )

        send_message(
            chat_id,
            "❌ Couldn't load statistics."
        )


#===== IMAGE UPLOAD =====

def upload_image(
    image_bytes,
    filename
):
    response = requests.post(
        "https://api.imgbb.com/1/upload",
        params={
            "key":
                IMGBB_API_KEY
        },
        files={
            "image":
                (
                    filename,
                    image_bytes
                )
        },
        timeout=30
    )

    response.raise_for_status()

    data = response.json()

    if not data.get("success"):
        raise Exception(
            "ImgBB upload failed"
        )

    return data["data"]


#===== SAVED IMAGES =====

def get_next_image_number(
    user_id
):
    rows = supabase_get(
        "saved_images",
        {
            "select": "id",
            "user_id":
                f"eq.{user_id}"
        }
    )

    return len(rows) + 1


def save_image(
    user_id,
    name,
    url
):
    supabase_insert(
        "saved_images",
        {
            "user_id": user_id,
            "name": name,
            "url": url
        }
    )


#===== MY IMAGES =====

def library_keyboard(
    page,
    total_pages
):
    buttons = []
    navigation = []

    if page > 1:
        navigation.append(
            {
                "text":
                    "◀️ Previous",
                "callback_data":
                    f"library:{page - 1}"
            }
        )

    if page < total_pages:
        navigation.append(
            {
                "text":
                    "Next ▶️",
                "callback_data":
                    f"library:{page + 1}"
            }
        )

    if navigation:
        buttons.append(
            navigation
        )

    return {
        "inline_keyboard":
            buttons
    }


def send_library(
    chat_id,
    user_id,
    page=1
):
    try:

        rows = supabase_get(
            "saved_images",
            {
                "select":
                    "id,name,url,created_at",

                "user_id":
                    f"eq.{user_id}",

                "order":
                    "id.desc"
            }
        )

        total = len(rows)

        if total == 0:

            send_message(
                chat_id,

                "╭────────────────────╮\n"
                "│   🖼️ <b>MY IMAGES</b>   │\n"
                "╰────────────────────╯\n\n"

                "📭 Your image library is empty.\n\n"

                "Use /supermode and send "
                "an image to save it."
            )

            return

        per_page = 15

        total_pages = (
            total + per_page - 1
        ) // per_page

        if page < 1:
            page = 1

        if page > total_pages:
            page = total_pages

        start = (
            page - 1
        ) * per_page

        page_rows = rows[
            start:
            start + per_page
        ]

        lines = [
            "╭────────────────────╮",
            "│   🖼️ <b>MY IMAGES</b>   │",
            "╰────────────────────╯",
            ""
        ]

        for index, image in enumerate(
            page_rows,
            start=start + 1
        ):

            name = image.get(
                "name",
                "Image"
            )

            url = image.get(
                "url",
                ""
            )

            lines.append(
                f"<b>{index}. "
                f"{name}</b>\n"
                f"<code>{url}</code>\n"
            )

        lines.extend(
            [
                "━━━━━━━━━━━━━━━━",

                f"📄 Page <b>{page}</b> / "
                f"<b>{total_pages}</b>",

                f"🖼️ Total: "
                f"<b>{total}</b>"
            ]
        )

        send_message(
            chat_id,
            "\n".join(lines),
            library_keyboard(
                page,
                total_pages
            )
        )

    except Exception as error:

        print(
            "LIBRARY ERROR:",
            error
        )

        send_message(
            chat_id,
            "❌ Couldn't load your "
            "image library."
        )


