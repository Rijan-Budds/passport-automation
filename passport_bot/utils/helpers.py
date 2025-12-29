from datetime import datetime
from typing import Tuple, Optional, Dict, Any

async def format_slots_for_date_selection(available_slots: list) -> Tuple[Optional[str], Optional[Dict]]:
    """Format slots for date selection display"""
    if not available_slots:
        return None, None
    
    # Group slots by date
    dates_slots = {}
    for slot in available_slots:
        date_str = slot.get("date")
        if date_str:
            if date_str not in dates_slots:
                dates_slots[date_str] = []
            dates_slots[date_str].append(slot)
    
    # Format dates for selection
    formatted_dates = []
    date_mapping = {}
    
    for i, (date_str, slots) in enumerate(dates_slots.items(), 1):
        try:
            date_obj = datetime.strptime(date_str, "%Y-%m-%d")
            day_name = date_obj.strftime("%A")
            formatted_date = date_obj.strftime("%B %d, %Y")
            short_date = date_obj.strftime("%m-%d")
            
            # Count available time slots
            time_slots_count = len(slots)
            
            formatted_dates.append(f"{i}. {short_date} ({day_name}) - {time_slots_count} slots available")
            date_mapping[str(i)] = {
                "date": date_str,
                "formatted_date": formatted_date,
                "slots": slots
            }
        except:
            continue
    
    return "\n".join(formatted_dates), date_mapping


async def format_time_slots_for_selection(date_slots: list) -> Tuple[Optional[str], Optional[Dict]]:
    """Format time slots for selection display"""
    if not date_slots:
        return None, None
    
    formatted_times = []
    time_mapping = {}
    
    for i, slot in enumerate(date_slots, 1):
        time_slot = slot.get("time_slot", "Unknown")
        normal_capacity = slot.get("normal_capacity", 0)
        vip_capacity = slot.get("vip_capacity", 0)
        
        capacity_text = []
        if normal_capacity > 0:
            capacity_text.append(f"Normal: {normal_capacity}")
        if vip_capacity > 0:
            capacity_text.append(f"VIP: {vip_capacity}")
        
        capacity_str = f" ({', '.join(capacity_text)})" if capacity_text else ""
        formatted_times.append(f"{i}. {time_slot}{capacity_str}")
        time_mapping[str(i)] = {
            "time_slot": time_slot,
            "normal_capacity": normal_capacity,
            "vip_capacity": vip_capacity,
            "slot_data": slot
        }
    
    return "\n".join(formatted_times), time_mapping