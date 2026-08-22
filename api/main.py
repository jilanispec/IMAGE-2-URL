import os
import requests

from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)


BOT_TOKEN = os.environ["BOT_TOKEN"]
IMGBB_API_KEY = os.environ["IMGBB_API_KEY"]


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "╭────────────────────╮\n"
        "│   🖼️ IMAGE TO URL   │\n"
        "╰────────────────────╯\n\n"
        "Send me an image and I'll convert it into a direct URL.\n\n"
        "⚡ Fast • Simple • Personal"
    )

    await update.message.reply_text(text)


async def handle_image(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE
):
    message = update.message
    file_path = None

    try:
        photo = message.photo[-1]

        telegram_file = await context.bot.get_file(
            photo.file_id
        )

        file_path = f"/tmp/{photo.file_unique_id}.jpg"

        await telegram_file.download_to_drive(file_path)

        with open(file_path, "rb") as image_file:
            response = requests.post(
                "https://api.imgbb.com/1/upload",
                params={
                    "key": IMGBB_API_KEY
                },
                files={
                    "image": image_file
                },
                timeout=30,
            )

        if response.status_code != 200:
            await message.reply_text(
                "❌ Upload failed.\n\n"
                "Please try again."
            )
            return

        data = response.json()

        if not data.get("success"):
            await message.reply_text(
                "❌ Image hosting failed."
            )
            return

        image_url = data["data"]["url"]

        width = data["data"].get("width", "?")
        height = data["data"].get("height", "?")

        text = (
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

        await message.reply_text(
            text,
            parse_mode="HTML"
        )

    except Exception as e:
        print("ERROR:", e)

        await message.reply_text(
            "❌ Something went wrong.\n\n"
            "Please send the image again."
        )

    finally:
        if file_path and os.path.exists(file_path):
            os.remove(file_path)


# Create the Telegram application
application = (
    Application.builder()
    .token(BOT_TOKEN)
    .build()
)

application.add_handler(
    CommandHandler("start", start)
)

application.add_handler(
    MessageHandler(
        filters.PHOTO,
        handle_image
    )
)


async def handler(request):
    """
    Vercel serverless webhook handler.
    """

    if request.method == "GET":
        return {
            "statusCode": 200,
            "body": "🟢 Image URL Bot is online!"
        }

    if request.method != "POST":
        return {
            "statusCode": 405,
            "body": "Method Not Allowed"
        }

    try:
        body = await request.json()

        update = Update.de_json(
            body,
            application.bot
        )

        await application.initialize()

        await application.process_update(
            update
        )

        await application.shutdown()

        return {
            "statusCode": 200,
            "body": "OK"
        }

    except Exception as e:
        print("WEBHOOK ERROR:", e)

        return {
            "statusCode": 500,
            "body": "Internal Server Error"
        }
