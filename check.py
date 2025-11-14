import requests
import json
import time
from datetime import datetime
import os
from dotenv import load_dotenv

load_dotenv()

SLACK_WEBHOOK = os.environ.get("SLACK_WEBHOOK")

if not SLACK_WEBHOOK:
    raise ValueError("⚠️ SLACK_WEBHOOK environment variable not set!")

HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.9",
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "Referer": "https://emrtds.nepalpassport.gov.np/",
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Encoding": "gzip, deflate",
}

def send_slack(message: str):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    data = {"text": f"[{timestamp}] {message}"}
    try:
        requests.post(SLACK_WEBHOOK, json=data, timeout=5)
    except Exception as e:
        print("⚠️ Failed to send Slack notification:", e)

def check_passport():
    print("🔍 Checking passport slot availability...")
    print("==========================================\n")

    for i in range(1, 31):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"⏳ Attempt {i} of 30 at {timestamp}...")

        try:
            response = requests.get(
                "https://emrtds.nepalpassport.gov.np/iups-api/calendars/77/false",
                headers=HEADERS,
                timeout=10,
            )
            text = response.text
            print(f"Status Code: {response.status_code}")

            # Waiting room detection
            if "Online Waiting Room" in text:
                print("⚠️ HIGH TRAFFIC - Website has a waiting queue")
                send_slack("⚠️ Passport site has a waiting room active. Try later.")
                return

            # Valid JSON with offDates
            if '"offDates"' in text:
                print("✅ Success! Got response:")
                try:
                    data = response.json()
                    print(json.dumps(data, indent=2))
                    if data.get("offDates") == []:
                        print("🎉 SLOTS ARE AVAILABLE!")
                        send_slack("🎉 SLOTS AVAILABLE for passport application! Check now: https://emrtds.nepalpassport.gov.np/")
                    else:
                        print("❌ NO SLOTS AVAILABLE - Date is marked as off")
                except json.JSONDecodeError:
                    print(text)
                return

            # Unexpected response
            print(f"❌ Unexpected response at {timestamp}. Retrying in 3 seconds...")
            time.sleep(3)

        except Exception as e:
            print(f"❌ Connection failed at {timestamp}: {e}. Retrying in 3 seconds...")
            time.sleep(3)

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n⛔ All attempts failed at {timestamp}")
    send_slack("⛔ Passport check failed after 30 attempts. Site may be down or high traffic.")

if __name__ == "__main__":
    check_passport()
