import json
import time
import requests
from datetime import datetime
from utils import (
    load_last_slots,
    save_last_slots,
    save_unavailable_slots, 
    send_slack,
    slots_changed,
    clean_old_slots,
    HEADERS
)
from schedule_days import get_valid_dates
from waiting_room_handler import add_to_waiting_room_queue

LOCATIONS_FILE = "locations.json"

def check_passport_job():
    """
    Main checker - ALWAYS saves to database (even if unchanged)
    Only sends Slack notifications when slots change
    """
    # Clean old data first
    clean_old_slots()
    
    try:
        with open(LOCATIONS_FILE, "r") as f:
            locations = json.load(f)
    except Exception as e:
        print(f"Failed to load locations.json: {e}")
        return
    
    valid_dates = get_valid_dates(days_ahead=7)
    last_slots = load_last_slots()
    
    # For tracking what to notify about
    notification_results = []
    any_new_slots = False
    
    print(f"\n{'='*60}")
    print(f"🔍 Starting slot check at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}")
    
    # Temporary storage for THIS run's results
    current_run_slots = {}
    
    for district_name, code in locations.items():
        base_url = f"https://emrtds.nepalpassport.gov.np/iups-api/timeslots/{code}"
        
        for date in valid_dates:
            url = f"{base_url}/{date}/false"
            
            try:
                response = requests.get(url, headers=HEADERS, timeout=10)
                text = response.text
                
                # Waiting room - delegate to background
                if "Online Waiting Room" in text:
                    print(f"⏸️  Waiting room: {district_name} on {date}")
                    add_to_waiting_room_queue(district_name, code, date, url)
                    continue
                
                if response.status_code != 200:
                    print(f"⚠️ Status {response.status_code}: {district_name} on {date}")
                    continue
                
                try:
                    slots = response.json()
                except json.JSONDecodeError:
                    print(f"⚠️ JSON decode failed: {district_name} on {date}")
                    continue
                
                if not isinstance(slots, list) or len(slots) == 0:
                    continue
                
                # Process slots
                available = [s for s in slots if isinstance(s, dict) and s.get("status")]
                unavailable = [s for s in slots if isinstance(s, dict) and not s.get("status")]
                
                # ALWAYS store current available slots (even if unchanged)
                if available:
                    current_run_slots.setdefault(district_name, {})[date] = available
                    
                    # Check if changed for NOTIFICATION purposes only
                    prev_available = last_slots.get(district_name, {}).get(date, [])
                    if slots_changed(prev_available, available):
                        # NEW or CHANGED slots - add to notification
                        any_new_slots = True
                        day_block = [f"📍 *{district_name}* — *{date}*:\n"]
                        for s in available:
                            day_block.append(
                                f"• `{s.get('name','UNKNOWN')}` — Normal: {s.get('capacity',0)} | VIP: {s.get('vipCapacity',0)}"
                            )
                        notification_results.append("\n".join(day_block))
                        print(f"🆕 NEW/CHANGED: {district_name} on {date} - {len(available)} slots")
                    else:
                        print(f"✓ Unchanged: {district_name} on {date} - {len(available)} slots")
                
                # Save unavailable slots
                if unavailable:
                    save_unavailable_slots({district_name: {date: unavailable}})
                
            except requests.exceptions.Timeout:
                print(f"⏱️ Timeout: {district_name} on {date}")
                continue
            except Exception as e:
                print(f"⚠️ Error: {district_name} on {date}: {e}")
                continue
    
    # ALWAYS save to database (this updates last_checked timestamp)
    print(f"\n💾 Saving ALL slots to database (updates timestamps)...")
    if current_run_slots:
        save_last_slots(current_run_slots)
    else:
        print("   No available slots to save")
    
    # Send notifications ONLY for changed slots
    if any_new_slots:
        final_msg = "🎉 *New/Changed Passport Slots*\n\n" + "\n\n".join(notification_results)
        send_slack(final_msg)
        print(f"\n{final_msg}\n")
    else:
        print("ℹ️  No new or changed slots (database still updated with timestamps)")
    
    print(f"{'='*60}")
    print(f"✓ Check complete at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*60}\n")

def manual_check_job():
    """Manual trigger"""
    check_passport_job()