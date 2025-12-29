import os
from dotenv import load_dotenv

load_dotenv(".env.dev")

# Supabase Configuration
SUPABASE_URL = "https://zgsdyxdjrietcfvnnpij.supabase.co"
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Inpnc2R5eGRqcmlldGNmdm5ucGlqIiwicm9sZSI6InNlcnZpY2Vfcm9sZSIsImlhdCI6MTc2MzM5MTUzMywiZXhwIjoyMDc4OTY3NTMzfQ.plczcmX25JAXxJvdGjMlKpuDny2RTZtjsVqOiNJyGBo"

# Slack Configuration
SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN")
SLACK_SIGNING_SECRET = os.environ.get("SLACK_SIGNING_SECRET")
SLACK_APP_TOKEN = os.environ.get("SLACK_APP_TOKEN")

# Bot Configuration
MAX_CAPTCHA_ATTEMPTS = 10
WAITING_ROOM_RETRY_MINUTES = 5

# Question Configurations
QUESTIONS_PRE_CAPTCHA = [
    ("application_type", "What type of application?\n1. First Issuance (New Passport)\n2. Passport Renewal\nPlease type '1' or '2':"),
    ("passport_type", "What type of passport do you want? (Regular/Diplomatic/Official)"),
    ("province", "Which province? (e.g., Bagmati, Gandaki, Koshi)"),
    ("district", "Which district?"),
    ("office", "Which office?"),
]

QUESTIONS_RENEWAL = [
    ("old_passport_number", "What is your old passport number?"),
    ("currentTDNum", "What is your current Travel Document (TD) number?"),
    ("currentTDIssueDate", "When was your current TD issued? (YYYY-MM-DD)"),
    ("currenttdIssuePlaceDistrict", "Which district was your current TD issued in?"),
]


QUESTIONS_DEMOGRAPHIC_INFO = [
    ("firstName", "What is your first name?"),
    ("lastName", "What is your last name?"),
    ("gender", "What is your gender? (M for Male, F for Female, X for Other)"),
    ("dob", "What is your date of birth AD? (YYYY-MM-DD)"),
    ("dobBs", "What is your date of birth in Nepali calendar? (YYYY-MM-DD)"),
    ("isExactDateOfBirth", "Is your date of birth exact? (Y/N)"),
    ("birthDistrict", "What is your birth district?"),
    ("fatherLastName", "What is your father's last name?"),
    ("fatherFirstName", "What is your father's first name?"),
    ("motherLastName", "What is your mother's last name?"),
    ("motherFirstName", "What is your mother's first name?")
]

QUESTIONS_CITIZEN_INFO = [
    ("nin", "What is your NIN?"),
    ("citizenNum", "What is your citizen number?"),
    ("citizenIssueDateBS", "When was your citizen issued Nepali calendar?? (YYYY-MM-DD)"),
    ("citizenIssuePlaceDistrict", "Which district was your citizen issued in?")
]

QUESTIONS_CONTACT_INFO = [
    ("home_phone", "What is your home phone number?"),
    ("main_address", "What is your main address?"),
    ("main_ward", "What is your main ward?"),
    ("main_province", "What is your main province?"),
    ("main_district", "What is your main district?"),
    ("main_municipality", "What is your main municipality?")
]

QUESTIONS_EMERGENCY_INFO = [
    ("contactLastName", "What is your contact last name?"),
    ("contactFirstName", "What is your contact first name?"),
    ("contactHouseNum", "What is your contact house number?"),
    ("contactStreetVillage", "What is your contact street/village?"),
    ("contactWard", "What is your contact ward?"),
    ("contactProvince", "What is your contact province?"),
    ("contactDistrict", "What is your contact district?"),
    ("contactMunicipality", "What is your contact municipality?"),
    ("contactPhone", "What is your contact phone number?")
]

# District Offices
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
}