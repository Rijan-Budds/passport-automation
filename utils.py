import os
from datetime import datetime
import requests
from supabase import create_client
from dotenv import load_dotenv

# -------------------- Environment --------------------
load_dotenv(".env.dev")
SLACK_WEBHOOK = os.environ.get("SLACK_WEBHOOK")
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

if not SLACK_WEBHOOK or not SUPABASE_URL or not SUPABASE_KEY:
    raise ValueError("⚠️ SLACK_WEBHOOK, SUPABASE_URL or SUPABASE_KEY not set!")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
TABLE_NAME = "slots_available"

HEADERS = {
    "Accept": "application/json, text/plain, */*",
    "Accept-Language": "en-US,en;q=0.8",
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "DNT": "1",
    "Pragma": "no-cache",
    "Referer": "https://emrtds.nepalpassport.gov.np/",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    ),
    "Accept-Encoding": "gzip, deflate, br",
}

# -------------------- Slack --------------------
def send_slack(message: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        requests.post(SLACK_WEBHOOK, json={"text": f"[{ts}]\n{message}"}, timeout=5)
    except Exception as e:
        print("⚠️ Slack Error:", e)

# -------------------- Slots helpers --------------------
def load_last_slots():
    """Load last slots from Supabase"""
    try:
        data = supabase.table(TABLE_NAME).select("*").execute().data
    except Exception as e:
        print("⚠️ Supabase fetch error:", e)
        return {}

    result = {}
    for row in data:
        district = row["district"]
        date = str(row["date"])
        slot_info = {
            "name": row["name"],
            "capacity": row["normal_capacity"],
            "vipCapacity": row["vip_capacity"],
            "status": True
        }
        result.setdefault(district, {}).setdefault(date, []).append(slot_info)
    return result

def save_last_slots(slots_dict):
    """Upsert slots into Supabase"""
    for district, dates in slots_dict.items():
        for date, slots in dates.items():
            for s in slots:
                row = {
                    "district": district,
                    "date": date,
                    "name": s["name"],
                    "normal_capacity": s["capacity"],
                    "vip_capacity": s["vipCapacity"]
                }
                supabase.table(TABLE_NAME).upsert(
                    row,
                    on_conflict="district,date,name" 
                ).execute()

def slots_changed(prev, current):
    """Return True if any slot has changed"""
    if not prev:
        return True
    prev_map = {s["name"]: (s["capacity"], s["vipCapacity"]) for s in prev}
    for s in current:
        name = s.get("name")
        cap = s.get("capacity", 0)
        vip = s.get("vipCapacity", 0)
        if name not in prev_map or prev_map[name] != (cap, vip):
            return True
    return False
