import os
import time
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import requests
from supabase import create_client
from dotenv import load_dotenv

# Nepal timezone
NEPAL_TZ = ZoneInfo("Asia/Kathmandu")

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

# -------------------- Retry Helper --------------------
def retry_operation(operation, max_retries=3, delay=2):
    """Retry a database operation if it fails due to network issues"""
    for attempt in range(1, max_retries + 1):
        try:
            return operation()
        except Exception as e:
            error_str = str(e).lower()
            is_network_error = any(keyword in error_str for keyword in [
                'winerror 10035', 'connection', 'timeout', 'socket', 'network', 'read error'
            ])
            
            if is_network_error and attempt < max_retries:
                print(f"⚠️ Network error (attempt {attempt}/{max_retries}), retrying...")
                time.sleep(delay)
                continue
            else:
                raise

# -------------------- Slack --------------------
def send_slack(message: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        response = requests.post(SLACK_WEBHOOK, json={"text": f"[{ts}]\n{message}"}, timeout=10)
        if response.status_code == 200:
            print(f"✅ Slack sent")
    except Exception as e:
        print(f"⚠️ Slack Error: {e}")

# -------------------- Slots helpers --------------------
def load_last_slots():
    """Load last slots from Supabase with retry logic"""
    def _load():
        response = supabase.table(TABLE_NAME).select("*").execute()
        print(f"📥 Loaded {len(response.data)} rows from Supabase")
        return response.data
    
    try:
        data = retry_operation(_load, max_retries=3, delay=2)
    except Exception as e:
        print(f"❌ Supabase load error: {e}")
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

def clean_old_slots():
    """Delete slots from past dates"""
    def _clean():
        today = datetime.now().date()
        yesterday = (today - timedelta(days=1)).strftime("%Y-%m-%d")
        
        print(f"🧹 Cleaning slots before {yesterday}...")
        
        response1 = supabase.table("slots_available").delete().lt("date", yesterday).execute()
        deleted_available = len(response1.data) if response1.data else 0
        
        response2 = supabase.table("slots_unavailable").delete().lt("date", yesterday).execute()
        deleted_unavailable = len(response2.data) if response2.data else 0
        
        return deleted_available + deleted_unavailable
    
    try:
        total_deleted = retry_operation(_clean, max_retries=3, delay=2)
        if total_deleted > 0:
            print(f"✅ Cleaned {total_deleted} old records")
    except Exception as e:
        print(f"⚠️ Error during cleanup: {e}")

def delete_all_slots():
    """
    Delete ALL records from both tables
    Run this at midnight to clear the database
    """
    def _delete_all():
        print("🗑️ Deleting ALL records from database...")
        
        # Delete from slots_available
        response1 = supabase.table("slots_available").delete().neq("id", 0).execute()
        deleted_available = len(response1.data) if response1.data else 0
        
        # Delete from slots_unavailable  
        response2 = supabase.table("slots_unavailable").delete().neq("id", 0).execute()
        deleted_unavailable = len(response2.data) if response2.data else 0
        
        return deleted_available, deleted_unavailable
    
    try:
        available, unavailable = retry_operation(_delete_all, max_retries=3, delay=2)
        total = available + unavailable
        
        msg = f"🗑️ Midnight cleanup: Deleted {total} records ({available} available, {unavailable} unavailable)"
        print(msg)
        send_slack(msg)
        
        return total
    except Exception as e:
        error_msg = f"❌ Midnight cleanup failed: {e}"
        print(error_msg)
        send_slack(error_msg)
        return 0

def save_last_slots(slots_dict):
    """
    ALWAYS INSERT new records (never update existing ones)
    Each run creates fresh database entries
    """
    if not slots_dict:
        print("⚠️ Empty slots_dict - skipping save")
        return
    
    print(f"💾 Inserting NEW slots to Supabase...")
    
    saved = 0
    errors = 0
    current_time = datetime.now(NEPAL_TZ).isoformat()
    
    for district, dates in slots_dict.items():
        for date, slots in dates.items():
            for s in slots:
                def _save_slot():
                    row = {
                        "district": district,
                        "date": date,
                        "name": s.get("name", "UNKNOWN"),
                        "normal_capacity": s.get("capacity", 0),
                        "vip_capacity": s.get("vipCapacity", 0),
                        "last_checked": current_time
                    }
                    
                    # Changed from upsert to insert - creates new record every time
                    return supabase.table(TABLE_NAME).insert(row).execute()
                
                try:
                    response = retry_operation(_save_slot, max_retries=3, delay=1)
                    if response.data:
                        saved += 1
                    else:
                        errors += 1
                except Exception as e:
                    errors += 1
                    print(f"❌ Failed to save {district}/{date}/{s.get('name')}: {e}")
    
    print(f"✅ Insert complete: {saved} new records, {errors} errors")
    
    if errors > 0:
        send_slack(f"⚠️ Supabase insert had {errors} errors")
    
    return saved, errors

def slots_changed(prev, current):
    """Return True if any slot has changed"""
    if not prev:
        return True
    
    prev_map = {s["name"]: (s["capacity"], s["vipCapacity"]) for s in prev}
    curr_map = {s.get("name"): (s.get("capacity", 0), s.get("vipCapacity", 0)) for s in current}
    
    return prev_map != curr_map

def save_unavailable_slots(slots_dict):
    """Save unavailable slots - also changed to insert"""
    if not slots_dict:
        return
    
    total_saved = 0
    current_time = datetime.now(NEPAL_TZ).isoformat()
    
    for district, dates in slots_dict.items():
        for date, slots in dates.items():
            for s in slots:
                def _save_unavailable():
                    row = {
                        "district": district,
                        "date": date,
                        "name": s.get("name", "UNKNOWN"),
                        "normal_capacity": s.get("capacity", 0),
                        "vip_capacity": s.get("vipCapacity", 0),
                        "last_checked": current_time
                    }
                    
                    # Changed from upsert to insert
                    return supabase.table("slots_unavailable").insert(row).execute()
                
                try:
                    retry_operation(_save_unavailable, max_retries=3, delay=1)
                    total_saved += 1
                except Exception as e:
                    print(f"⚠️ Failed to save unavailable: {e}")
    
    if total_saved > 0:
        print(f"💾 Saved {total_saved} unavailable slots")