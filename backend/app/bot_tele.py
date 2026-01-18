from telegram import Update
from telegram.ext import ApplicationBuilder, MessageHandler, CommandHandler, filters, ContextTypes
import requests
import logging
from io import BytesIO
from .core.config import settings_network
from dotenv import load_dotenv
load_dotenv()
import os

API_URL = f"{settings_network.BASE_URL_API}/api/v1/chat_no_auth"
BOT_TOKEN = os.getenv("BOT_TOKEN")

logging.basicConfig(level=logging.INFO)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Hello! Send me a message and I'll help you 😊")

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    
    try:
        # Send to API backend
        res = requests.post(API_URL, json={"message": user_text}, timeout=30)
        data = res.json()
        
        # Send reply text
        if "message" in data:
            await update.message.reply_text(data["message"])
        
        # Send returned images (if any)
        if "image" in data and isinstance(data["image"], list):
            for img_url in data["image"]:
                try:
                    # Fetch image from URL (API returns binary)
                    img_response = requests.get(img_url, timeout=10)
                    
                    if img_response.status_code == 200:
                        # Convert bytes to file object
                        img_bytes = BytesIO(img_response.content)
                        img_bytes.name = 'image.jpg'
                        
                        # Send image
                        await update.message.reply_photo(photo=img_bytes)
                    else:
                        await update.message.reply_text(f"❌ Could not load image from: {img_url}")
                        
                except Exception as img_err:
                    logging.error(f"Error loading image: {img_err}")
                    await update.message.reply_text(f"❌ Error processing image: {str(img_err)}")
                    
    except requests.exceptions.Timeout:
        await update.message.reply_text("⏱️ API response took too long, please try again!")
    except requests.exceptions.RequestException as e:
        await update.message.reply_text(f"❌ API connection error: {str(e)}")
    except Exception as e:
        logging.error(f"Unexpected error: {e}")
        await update.message.reply_text(f"❌ An error occurred: {str(e)}")

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    
    print("🤖 Bot đang chạy...")
    app.run_polling()

if __name__ == "__main__":
    main()