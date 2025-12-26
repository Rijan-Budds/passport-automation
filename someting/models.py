PROVINCES = {
    "Province 1": ["Taplejung", "Panchthar", "Ilam", "Morang", "Sunsari", "Jhapa"],
    "Province 2": ["Saptari", "Siraha", "Dhanusha", "Mahottari", "Sarlahi", "Rautahat", "Bara", "Parsa"],
    "Bagmati": ["Kathmandu", "Lalitpur", "Bhaktapur", "Dhading", "Nuwakot", "Rasuwa", "Sindhupalchok"],
    "Gandaki": ["Kaski", "Lamjung", "Tanahun", "Gorkha", "Manang"],
    "Lumbini": ["Rupandehi", "Kapilvastu", "Arghakhanchi", "Palpa", "Dang"],
    "Karnali": ["Surkhet", "Dailekh", "Jumla", "Dolpa"],
    "Sudurpashchim": ["Bajura", "Bajhang", "Dadeldhura", "Kailali", "Dotl"]
}

DISTRICT_OFFICES = {
    "Kathmandu": ["DAO Kathmandu", "Department of Passport"],
    "Lalitpur": ["Lalitpur"],
    "Bhaktapur": ["Bhaktapur"],
    "Kaski": ["Kaski"],
    "Morang": ["Morang"],
    "Jhapa": ["Jhapa"],
    "Rupandehi": ["Rupandehi"],
    "Sunsari": ["Sunsari"],
    "Banke": ["Banke"],
    "Bardiya": ["Bardiya"],
    "Chitwan": ["Chitwan"]
}

QUESTIONS_PERSONAL_INFO = [
    ("first_name", "What is your first name?"),
    ("middle_name", "What is your middle name? Type '_' if none."),
    ("last_name", "What is your last name?"),
    ("email", "What is your email address?"),
    ("phone", "What is your phone number?"),
    ("citizenship_number", "What is your citizenship number?"),
    ("dob", "What is your date of birth? (YYYY-MM-DD)"),
    ("gender", "What is your gender? (Male/Female/Other)"),
    ("marital_status", "What is your marital status? (Married/Unmarried)"),
]

QUESTIONS_ADDITIONAL = [
    ("permanent_municipality", "What is your permanent municipality?"),
    ("permanent_ward", "What is your permanent ward number?"),
    ("permanent_tole", "What is your permanent tole?"),
    ("father_name", "What is your father's full name?"),
    ("mother_name", "What is your mother's full name?"),
]

from difflib import get_close_matches

def match_province(user_input):
    matches = get_close_matches(user_input.title(), PROVINCES.keys(), n=1, cutoff=0.5)
    return matches[0] if matches else None

def match_district(user_input, province):
    districts = PROVINCES.get(province, [])
    matches = get_close_matches(user_input.title(), districts, n=1, cutoff=0.5)
    return matches[0] if matches else None