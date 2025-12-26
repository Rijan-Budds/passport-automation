from supabase import create_client
import os
from collections import defaultdict

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

def get_available_dates(district, office):
    """
    Returns list of dates that have ANY capacity
    """
    response = (
        supabase
        .table("appointment_dates")
        .select("date, normal_capacity, vip_capacity")
        .eq("district", district)
        .execute()
    )

    dates = set()
    for row in response.data or []:
        if (row["normal_capacity"] or 0) > 0 or (row["vip_capacity"] or 0) > 0:
            dates.add(row["date"])

    return sorted(list(dates))


def get_available_times(district, date):
    """
    Returns available time slots (name column)
    """
    response = (
        supabase
        .table("appointment_dates")
        .select("name, normal_capacity, vip_capacity")
        .eq("district", district)
        .eq("date", date)
        .execute()
    )

    slots = []
    for row in response.data or []:
        if (row["normal_capacity"] or 0) > 0 or (row["vip_capacity"] or 0) > 0:
            slots.append(row)

    return slots
