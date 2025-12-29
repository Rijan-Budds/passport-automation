from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any

@dataclass
class UserData:
    """Stores all user information for passport application"""
    # Application Type
    application_type: str = "first_issuance"  # "first_issuance" or "renewal"
    passport_type: str = "Regular"
    
    # Location
    province: str = ""
    district: str = ""
    office: str = ""
    
    # Appointment
    selected_date: Optional[str] = None
    selected_time: Optional[str] = None
    
    # Personal Information
    first_name: str = ""
    middle_name: str = ""
    last_name: str = ""
    email: str = ""
    phone: str = ""
    citizenship_number: str = ""
    dob: str = ""
    gender: str = "Male"
    marital_status: str = "Unmarried"
    education: str = "Bachelor"
    
    # Renewal Information (if applicable)
    old_passport_number: str = ""
    currentTDNum: str = ""
    currentTDIssueDate: str = ""
    currenttdIssuePlaceDistrict: str = ""
    
    # Family Information
    father_name: str = ""
    mother_name: str = ""
    spouse_name: str = ""
    
    # Address Information
    permanent_district: str = ""
    permanent_municipality: str = ""
    permanent_ward: str = ""
    permanent_tole: str = ""
    current_district: str = ""
    current_municipality: str = ""
    current_ward: str = ""
    current_tole: str = ""
    
    # Additional data
    available_slots: Optional[list] = None
    date_mapping: Optional[Dict] = None
    time_mapping: Optional[Dict] = None
    available_offices: Optional[list] = None
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        return asdict(self)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]):
        """Create from dictionary"""
        # Filter out keys that aren't in the dataclass
        valid_keys = {field.name for field in cls.__dataclass_fields__.values()}
        filtered_data = {k: v for k, v in data.items() if k in valid_keys}
        return cls(**filtered_data)

    def get(self, key, default=None):
        """Get attribute value with dictionary-like interface"""
        return getattr(self, key, default)