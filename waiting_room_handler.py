import time
import json
import requests
from datetime import datetime
from threading import Thread
from queue import Queue
from utils import (
    load_last_slots,
    save_last_slots,
    save_unavailable_slots,
    send_slack,
    slots_changed,
    HEADERS
)

# Queue to hold waiting room tasks
waiting_room_queue = Queue()

class WaitingRoomTask:
    def __init__(self, district_name, code, date, url):
        self.district_name = district_name
        self.code = code
        self.date = date
        self.url = url
        self.timestamp = datetime.now()

def process_waiting_room_task(task: WaitingRoomTask):
    """
    Process a single waiting room task
    Retries 3 times over 30 seconds (10 second intervals)
    """
    print(f"🕐 Handling waiting room for {task.district_name} on {task.date}")
    
    max_attempts = 3
    check_interval = 10  # seconds
    
    for attempt in range(1, max_attempts + 1):
        elapsed = (datetime.now() - task.timestamp).total_seconds()
        print(f"⏳ Retry {attempt}/{max_attempts} for {task.district_name} on {task.date} (elapsed: {elapsed:.0f}s)")
        
        try:
            response = requests.get(task.url, headers=HEADERS, timeout=10)
            text = response.text
            
            # Still in waiting room?
            if "Online Waiting Room" in text:
                if attempt < max_attempts:
                    time.sleep(check_interval)
                    continue
                else:
                    # Give up after max attempts
                    msg = f"❌ Waiting room persisted for {task.district_name} on {task.date} after {elapsed:.0f}s. Marking unavailable."
                    print(msg)
                    send_slack(msg)
                    mark_as_unavailable_due_to_waiting_room(task.district_name, task.date)
                    return False
            
            # Got past waiting room!
            if response.status_code == 200:
                try:
                    slots = response.json()
                    
                    if not isinstance(slots, list) or len(slots) == 0:
                        print(f"✓ Past waiting room but no slots for {task.district_name} on {task.date}")
                        mark_as_unavailable_due_to_waiting_room(task.district_name, task.date)
                        return True
                    
                    # Process slots
                    available = [s for s in slots if isinstance(s, dict) and s.get("status")]
                    unavailable = [s for s in slots if isinstance(s, dict) and not s.get("status")]
                    
                    # Handle available slots
                    if available:
                        last_slots = load_last_slots()
                        prev_available = last_slots.get(task.district_name, {}).get(task.date, [])
                        
                        if slots_changed(prev_available, available):
                            # Found slots after waiting room cleared!
                            msg_lines = [f"🎉 *SLOTS FOUND AFTER WAITING ROOM!*\n📍 *{task.district_name}* — *{task.date}*:\n"]
                            for s in available:
                                msg_lines.append(
                                    f"• `{s.get('name','UNKNOWN')}` — Normal: {s.get('capacity',0)} | VIP: {s.get('vipCapacity',0)}"
                                )
                            send_slack("\n".join(msg_lines))
                            
                            # Save available slots
                            last_slots.setdefault(task.district_name, {})[task.date] = available
                            save_last_slots(last_slots)
                            print(f"✓ Saved {len(available)} available slots for {task.district_name} on {task.date}")
                        else:
                            print(f"✓ No changes in available slots for {task.district_name} on {task.date}")
                    
                    # Save unavailable slots
                    if unavailable:
                        save_unavailable_slots({task.district_name: {task.date: unavailable}})
                        print(f"✓ Saved {len(unavailable)} unavailable slots for {task.district_name} on {task.date}")
                    
                    return True
                    
                except json.JSONDecodeError as e:
                    print(f"⚠️ JSON decode error: {e}")
                    if attempt < max_attempts:
                        time.sleep(check_interval)
                        continue
                    return False
            else:
                print(f"⚠️ Status {response.status_code} for {task.district_name} on {task.date}")
                if attempt < max_attempts:
                    time.sleep(check_interval)
                    continue
            
        except Exception as e:
            print(f"⚠️ Error in waiting room handler: {e}")
            if attempt < max_attempts:
                time.sleep(check_interval)
                continue
    
    # If we get here, all retries failed
    mark_as_unavailable_due_to_waiting_room(task.district_name, task.date)
    return False

def mark_as_unavailable_due_to_waiting_room(district_name, date):
    """Mark previously available slots as unavailable"""
    last_slots = load_last_slots()
    prev_available = last_slots.get(district_name, {}).get(date, [])
    
    if prev_available:
        unavailable_slots = []
        for slot in prev_available:
            slot_copy = {
                "name": slot.get("name", "UNKNOWN"),
                "capacity": 0,
                "vipCapacity": 0,
                "status": False
            }
            unavailable_slots.append(slot_copy)
        
        save_unavailable_slots({district_name: {date: unavailable_slots}})
        
        # Clear from last_slots
        if district_name in last_slots and date in last_slots[district_name]:
            del last_slots[district_name][date]
            save_last_slots(last_slots)
        
        print(f"✓ Marked slots as unavailable for {district_name} on {date}")

def waiting_room_worker():
    """Background worker that processes waiting room tasks"""
    print("🚀 Waiting room worker started")
    while True:
        try:
            task = waiting_room_queue.get(timeout=1)
            if task is None:  # Poison pill to stop worker
                break
            process_waiting_room_task(task)
            waiting_room_queue.task_done()
        except:
            # Queue empty, keep waiting
            continue

def start_waiting_room_worker():
    """Start the background worker thread"""
    worker_thread = Thread(target=waiting_room_worker, daemon=True)
    worker_thread.start()
    print("✓ Waiting room worker thread started")

def add_to_waiting_room_queue(district_name, code, date, url):
    """Add a waiting room task to the queue"""
    task = WaitingRoomTask(district_name, code, date, url)
    waiting_room_queue.put(task)
    queue_size = waiting_room_queue.qsize()
    print(f"➕ Added to waiting room queue: {district_name} on {date} (queue size: {queue_size})")
    send_slack(f"⏳ Waiting room detected: {district_name} on {date}. Will retry 3x over 30 seconds.")