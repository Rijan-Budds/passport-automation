import json
import time
import requests
from datetime import datetime
from utils import load_last_slots, save_last_slots, send_slack, slots_changed, HEADERS
from schedule_days import get_valid_dates

LOCATIONS_FILE = "locations.json"

def check_passport_job():
    try:
        with open(LOCATIONS_FILE, "r") as f:
            locations = json.load(f)
    except Exception as e:
        print(f"Failed to load locations.json: {e}")
        return

    valid_dates = get_valid_dates(days_ahead=7)
    last_slots = load_last_slots()
    weekly_results = []
    any_new_slots = False

    for district_name, code in locations.items():
        base_url = f"https://emrtds.nepalpassport.gov.np/iups-api/timeslots/{code}"
        for date in valid_dates:
            url = f"{base_url}/{date}/false"

            for attempt in range(1, 10):
                try:
                    response = requests.get(url, headers=HEADERS, timeout=10)
                    text = response.text

                    if "Online Waiting Room" in text:
                        msg = f"⚠️ Waiting Room detected for {district_name}"
                        send_slack(msg)
                        print(msg)
                        break

                    try:
                        slots = response.json()
                    except json.JSONDecodeError:
                        time.sleep(2)
                        continue

                    if not isinstance(slots, list) or len(slots) == 0:
                        break

                    available = [s for s in slots if isinstance(s, dict) and s.get("status")]
                    prev = last_slots.get(district_name, {}).get(date, [])

                    if available and slots_changed(prev, available):
                        any_new_slots = True
                        day_block = [f"📍 *{district_name}* — *{date}*:\n"]
                        for s in available:
                            day_block.append(
                                f"• `{s.get('name','UNKNOWN')}` — Normal: {s.get('capacity',0)} | VIP: {s.get('vipCapacity',0)}"
                            )
                        weekly_results.append("\n".join(day_block))

                        last_slots.setdefault(district_name, {})[date] = available
                    break
                except Exception as e:
                    time.sleep(2)

    save_last_slots(last_slots)

    if any_new_slots:
        final_msg = "🎉 *New Passport Slot Report*\n\n" + "\n\n".join(weekly_results)
        send_slack(final_msg)
        print(final_msg)
    else:
        print("❌ No new slots available this run.")


def manual_check_job():
    check_passport_job()
