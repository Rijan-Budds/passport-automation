from datetime import datetime
from supabase import create_client, Client
from config.settings import SUPABASE_URL, SUPABASE_KEY

class SupabaseClient:
    """Handles all Supabase database operations"""
    
    def __init__(self):
        self.client: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
    
    async def get_available_slots(self, district: str) -> list:
        """Fetch available slots from Supabase for a specific district"""
        try:
            response = self.client.table("slots_available")\
                .select("*")\
                .eq("district", district)\
                .gte("date", datetime.now().date().isoformat())\
                .order("date", desc=False)\
                .execute()
            
            return response.data if response.data else []
        except Exception as e:
            print(f"Error fetching slots from Supabase: {e}")
            return []
    
    async def get_available_offices(self, district: str) -> list:
        """Fetch available offices for a district from Supabase"""
        try:
            response = self.client.table("slots_available")\
                .select("name")\
                .eq("district", district)\
                .gte("date", datetime.now().date().isoformat())\
                .execute()
            
            # Extract unique office names
            offices = []
            seen = set()
            for item in response.data:
                office_name = item.get("name")
                if office_name and office_name not in seen:
                    offices.append(office_name)
                    seen.add(office_name)
            
            return offices
        except Exception as e:
            print(f"Error fetching offices from Supabase: {e}")
            return []