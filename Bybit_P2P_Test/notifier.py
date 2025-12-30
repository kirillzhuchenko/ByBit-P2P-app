import asyncio
import requests
import os


# --- Your Secondary Code (Synchronous) ---
def send_telegram_message(message):
    bot_token = os.getenv("BOT_TOKEN")
    chat_id = os.getenv("CHAT_ID")

    # Safety check to prevent crashing if env vars are missing
    if not bot_token or not chat_id:
        print("Error: BOT_TOKEN or CHAT_ID not found.")
        return

    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message
    }

    try:
        # This is a blocking call, but we will handle it safely below
        response = requests.post(url, json=payload)
        if response.status_code != 200:
            print(f"Failed to send notification: {response.text}")
    except Exception as e:
        print(f"Error connecting to Telegram: {e}")

async def main():

    await asyncio.to_thread(send_telegram_message, "🚀 Script Started: Heavy Task Analysis")

    # try:
    #     print("Work finished.")
    #     await asyncio.to_thread(send_telegram_message, "✅ Script Finished Successfully")
    # except Exception as e:
    #     print(f"Error connecting to Telegram: {e}")

if __name__ == "__main__":

    asyncio.run(main())