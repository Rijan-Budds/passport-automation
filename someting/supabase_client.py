import os
from datetime import datetime
from supabase import create_client, Client
from dotenv import load_dotenv

load_dotenv(".env.dev")

class SupabaseClient:
    def __init__(self):
        self.SUPABASE_URL = "https://zgsdyxdjrietcvvnnpij.supabase.co"
        self.SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inpnc2R5eGRqcmlldGNmdm5ucGlqIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2MzM5MTUzMywiZXhwIjoyMDc4OTY3NTMzfQ.plczcmX25JAXxJvdGjMlKpuDny2RTZtjsVqOiNJyGBo")
        self.client: Client = create_client(self.SUPABASE_URL, self.SUPABASE_KEY)
    
    def store_dates(self, district, office, dates):
        """Store extracted dates in Supabase"""
        try:
            for date_str in dates:
                response = (
                    self.client.table("available_dates")
                    .upsert({
                        "district": district,
                        "office": office,
                        "date": date_str,
                        "last_checked": datetime.now().isoformat()
                    })
                    .execute()
                )
            print(f"✅ Stored {len(dates)} dates in Supabase")
            return True
        except Exception as e:
            print(f"❌ Error storing dates in Supabase: {e}")
            return False
    
    def get_dates(self, district, office):
        """Get dates from Supabase"""
        try:
            response = (
                self.client.table("available_dates")
                .select("*")
                .eq("district", district)
                .eq("office", office)
                .order("date", desc=False)
                .execute()
            )
            dates = [row["date"] for row in response.data]
            print(f"📊 Retrieved {len(dates)} dates from Supabase")
            return dates
        except Exception as e:
            print(f"❌ Error getting dates from Supabase: {e}")
            return []
    
    def store_time_slots(self, district, date, time_slots):
        """Store time slots in Supabase"""
        try:
            for time_slot in time_slots:
                response = (
                    self.client.table("available_times")
                    .upsert({
                        "district": district,
                        "date": date,
                        "time_slot": time_slot,
                        "capacity_normal": 5,
                        "capacity_vip": 2,
                        "last_checked": datetime.now().isoformat()
                    })
                    .execute()
                )
            print(f"✅ Stored {len(time_slots)} time slots in Supabase")
            return True
        except Exception as e:
            print(f"❌ Error storing times in Supabase: {e}")
            return False
    
    def get_time_slots(self, district, date):
        """Get time slots from Supabase"""
        try:
            response = (
                self.client.table("available_times")
                .select("*")
                .eq("district", district)
                .eq("date", date)
                .order("time_slot", desc=False)
                .execute()
            )
            time_slots = [row["time_slot"] for row in response.data]
            print(f"📊 Retrieved {len(time_slots)} time slots from Supabase")
            return time_slots
        except Exception as e:
            print(f"❌ Error getting times from Supabase: {e}")
            return []