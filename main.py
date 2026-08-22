import os
import requests

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    ContextTypes,
    filters,
)

from config import BOT_TOKEN, IMGBB_API_KEY


# ─────────────────────────────────────────────
# START
# ─────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):

    keyboard = [
        [
            InlineKeyboardButton(
                "🖼️ Upload Image",
                callback_data="upload"
            )
        ]
    ]

    reply_markup = InlineKeyboardMarkup(keyboard)

    text = (
        "╭────────────────────╮\n"
        "│   🖼️ IMAGE TO URL   │\n"
        "╰────────────────────╯\n\n"
        "Send me an image and I'll\n"
        "convert it into a direct URL.\n\n"
        "⚡ Fast • Simple • Personal"
    )

    await update.message.reply_text(
        text,
        reply_markup=reply_markup
    )


# ─────────────────────────────────────────────
# BUTTON
# ─────────────────────────────────────────────

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):

    query = update.callback_query
    await query.answer()

    if query.data == "upload":

        await query.message.reply_text(
            "🖼️ Send your image now."
        )


# ─────────────────────────────────────────────
# IMAGE HANDLER
# ─────────────────────────────────────────────

async def handle_image(update: Update, context: ContextTypes.DEFAULT_TYPE):

    message = update.message

    try:

        # Get highest quality Telegram photo
        photo = message.photo[-1]

        # Telegram file
        telegram_file = await context.bot.get_file(
            photo.file_id
        )

        # Temporary filename
        filename = (
            f"telegram_image_"
            f"{photo.file_unique_id}.jpg"
        )

        file_path = os.path.join(
            ".",
            filename
        )

        # Download image
        await telegram_file.download_to_drive(
            file_path
        )

        # Upload to ImgBB
        with open(file_path, "rb") as image_file:

            response = requests.post(
                "https://api.imgbb.com/1/upload",

                params={
                    "key": IMGBB_API_KEY
                },

                files={
                    "image": image_file
                },

                timeout=60
            )

        # Delete temporary file
        if os.path.exists(file_path):
            os.remove(file_path)

        # Check HTTP response
        if response.status_code != 200:

            await message.reply_text(
                "❌ Upload failed.\n\n"
                "Please try again."
            )

            return

        data = response.json()

        # Check ImgBB result
        if not data.get("success"):

            await message.reply_text(
                "❌ ImgBB rejected the image."
            )

            return

        # Get URL
        image_url = data["data"]["url"]

        # Image information
        width = data["data"].get("width", "?")
        height = data["data"].get("height", "?")

        # Telegram UI
        text = (
            "╭───────────────╮\n"
            "│  ✨ IMAGE READY │\n"
            "╰───────────────╯\n\n"
            "🔗 Direct URL\n\n"
            f"<code>{image_url}</code>\n\n"
            "━━━━━━━━━━━━━━━━\n"
            f"🖼️ Format: JPG\n"
            f"📐 Size: {width} × {height}\n"
            "━━━━━━━━━━━━━━━━"
        )

        keyboard = [
            [
                InlineKeyboardButton(
                    "🖼️ Upload Another",
                    callback_data="upload"
                )
            ]
        ]

        reply_markup = InlineKeyboardMarkup(
            keyboard
        )

        await message.reply_text(
            text,
            parse_mode="HTML",
            reply_markup=reply_markup
        )

    except Exception as e:

        print("ERROR:", e)

        # Cleanup
        if (
            "file_path" in locals()
            and os.path.exists(file_path)
        ):
            os.remove(file_path)

        await message.reply_text(
            "❌ Something went wrong.\n\n"
            "Please send the image again."
        )


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():

    print("🤖 Image URL Bot starting...")

    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .build()
    )

    # /start
    app.add_handler(
        CommandHandler(
            "start",
            start
        )
    )

    # Buttons
    app.add_handler(
        MessageHandler(
            filters.StatusUpdate.ALL,
            lambda update, context: None
        )
    )

    # Image
    app.add_handler(
        MessageHandler(
            filters.PHOTO,
            handle_image
        )
    )

    # Callback buttons
    from telegram.ext import CallbackQueryHandler

    app.add_handler(
        CallbackQueryHandler(
            button_handler
        )
    )

    print("✅ Bot is running!")
    print("📸 Send an image to test.")

    app.run_polling()


# ─────────────────────────────────────────────

if __name__ == "__main__":
    main()