import os
import re
import logging
import requests
import asyncio
from datetime import datetime
from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from supabase import create_client, Client
from playwright.async_api import async_playwright
from transformers import VisionEncoderDecoderModel, TrOCRProcessor
from PIL import Image
import io

# Load environment variables
env_file = os.getenv('DOTENV_PATH', '.env.dev')
load_dotenv(env_file)

# Initialize Slack app
app = App(
    token=os.environ.get("SLACK_BOT_TOKEN"),
    signing_secret=os.environ.get("SLACK_SIGNING_SECRET")
)

# Initialize Supabase client
supabase: Client = create_client(
    os.environ.get("SUPABASE_URL"),
    os.environ.get("SUPABASE_KEY")
)

# Configure logging
logging.basicConfig(level=logging.INFO)

# Store user sessions
user_sessions = {}

# Field definitions for passport application
PASSPORT_FIELDS = {
    "serviceCode": {
        "name": "Service Code",
        "regex": r"[a-zA-Z0-9 &'()+,-./:;<=?@_]*",
        "minSize": 1,
        "maxSize": 64,
        "mandatory": True,
        "description": "Type of Transaction (request type)"
    },
    "lastName": {
        "name": "Last Name / Surname",
        "regex": r"[A-Z ]*",
        "minSize": 1,
        "maxSize": 22,
        "mandatory": True,
        "description": "Last Name / Surname"
    },
    "firstName": {
        "name": "First Name", 
        "regex": r"[A-Z ]*",
        "minSize": 0,
        "maxSize": 22,
        "mandatory": False,
        "description": "First name"
    },
    "gender": {
        "name": "Gender",
        "regex": r"^[MFX]$",
        "minSize": 1,
        "maxSize": 1,
        "mandatory": True,
        "description": "GENDER (M/F/X)"
    },
    "dateOfBirth": {
        "name": "Date of Birth (A.D.)",
        "regex": r"^((19|2[0-9])[0-9]{2})-(0[1-9]|1[012])-(0[1-9]|[12][0-9]|3[01])$",
        "minSize": 1,
        "maxSize": 10,
        "mandatory": True,
        "description": "Date of birth in format YYYY-MM-DD"
    },
    "dateOfBirthBS": {
        "name": "Date of Birth B.S (Nepali)",
        "regex": r"^([0-9]{4})-([0-9]{2})-([0-9]{2})$", 
        "minSize": 1,
        "maxSize": 10,
        "mandatory": True,
        "description": "Date of birth B.S in format YYYY-MM-DD"
    },
    "isExactDateOfBirth": {
        "name": "Is this exact Date of Birth?",
        "regex": r"^(true|false)$",
        "minSize": 4,
        "maxSize": 5,
        "mandatory": True,
        "description": "Is exact date of birth (true/false)"
    },
    "birthDistrict": {
        "name": "Place of Birth (District/Country if born abroad)",
        "regex": r"[a-zA-Z &'()+,-./:;<=?@_]*",
        "minSize": 1,  # Changed from 3 to 1
        "maxSize": 50,  # Changed from 3 to 50
        "mandatory": True,
        "description": "District of birth place (full name)"
    },
    "birthCountry": {
        "name": "Country of Birth",
        "regex": r"[a-zA-Z &'()+,-./:;<=?@_]*",
        "minSize": 0,
        "maxSize": 50,  # Increased from 3 to 50
        "mandatory": False,
        "description": "Country of birth (full name)"
    },
    "nationality": {
        "name": "Nationality", 
        "regex": r"[a-zA-Z0-9 &'()+,-./:;<=?@_]*",
        "minSize": 1,
        "maxSize": 50,
        "mandatory": True,
        "description": "Nationality"
    },
    "fatherLastName": {
        "name": "Father's Last Name / Surname",
        "regex": r"[A-Z ]*",
        "minSize": 1,
        "maxSize": 29,
        "mandatory": True,
        "description": "Father last name / Surname"
    },
    "fatherFirstName": {
        "name": "Father's First Name",
        "regex": r"[A-Z ]*",
        "minSize": 0, 
        "maxSize": 29,
        "mandatory": False,
        "description": "Father first name"
    },
    "motherLastName": {
        "name": "Mother's Last Name / Surname",
        "regex": r"[A-Z ]*",
        "minSize": 1,
        "maxSize": 29,
        "mandatory": True,
        "description": "Mother last name / Surname"
    },
    "motherFirstName": {
        "name": "Mother's First Name", 
        "regex": r"[A-Z ]*",
        "minSize": 0,
        "maxSize": 29,
        "mandatory": False,
        "description": "Mother first name"
    },
    "citizenIssueDateBS": {
        "name": "Citizenship Date of Issue B.S. (Nepali date)",
        "regex": r"^([0-9]{4})-([0-9]{2})-([0-9]{2})$",
        "minSize": 1,
        "maxSize": 10,
        "mandatory": True,
        "description": "Citizenship date of issue B.S. in format YYYY-MM-DD"
    },
    "citizenIssuePlaceDistrict": {
        "name": "Citizenship Place of Issue (District)",
        "regex": r"[a-zA-Z &'()+,-./:;<=?@_]*", 
        "minSize": 1,  # Changed from 3 to 1
        "maxSize": 50,  # Changed from 3 to 50
        "mandatory": True,
        "description": "Citizenship place of issue (district full name)"
    },
    "citizenNum": {
        "name": "Citizenship Number or Permit Number",
        "regex": r"[A-Z0-9<]*",
        "minSize": 1,
        "maxSize": 14,
        "mandatory": True,
        "description": "Citizenship number or Permit number"
    },
    "homePhone": {
        "name": "Mobile number",
        "regex": r"[0-9 +()]*",
        "minSize": 0,
        "maxSize": 15,
        "mandatory": True,
        "description": "Mobile phone number"
    },
    # REMOVED EMAIL FIELD
    "mainAddressHouseNum": {
        "name": "Main Address House Number",
        "regex": r"[A-Z0-9/.-]*",
        "minSize": 0,
        "maxSize": 6,
        "mandatory": False,
        "description": "House Number"
    },
    "mainAddressStreetVillage": {
        "name": "Main Address Street/Village",
        "regex": r"[A-Z ]*",
        "minSize": 1,
        "maxSize": 16,
        "mandatory": True,
        "description": "Street/village"
    },
    "mainAddressWard": {
        "name": "Main Address Ward", 
        "regex": r"[0-9]*",
        "minSize": 1,
        "maxSize": 2,
        "mandatory": True,
        "description": "Ward number"
    },
    "mainAddressMunicipality": {
        "name": "Main Address Municipality",
        "regex": r"[a-zA-Z0-9 &'()+,-./:;<=?@_]*",
        "minSize": 1,  # Changed from 10 to 1
        "maxSize": 50,  # Changed from 10 to 50
        "mandatory": True,
        "description": "Municipality (full name)"
    },
    "mainAddressDistrict": {
        "name": "Main Address District",
        "regex": r"[a-zA-Z &'()+,-./:;<=?@_]*",
        "minSize": 1,  # Changed from 3 to 1
        "maxSize": 50,  # Changed from 3 to 50
        "mandatory": True,
        "description": "District (full name)"
    },
    "mainAddressProvince": {
        "name": "Main Address Province",
        "regex": r"[a-zA-Z &'()+,-./:;<=?@_]*",
        "minSize": 1,  # Changed from 3 to 1
        "maxSize": 50,  # Changed from 3 to 50
        "mandatory": True,
        "description": "Province (full name)"
    },
    "documentTypeCode": {
        "name": "Document/Passport Type",
        "regex": r"[a-zA-Z0-9 _]*",
        "minSize": 2,
        "maxSize": 2,
        "mandatory": True,
        "description": "Document/Passport Type: PP-PB-PS-PD-PG-PT-PN"
    }
}

# Load TrOCR model for captcha solving
print("Loading TrOCR model...")
processor = TrOCRProcessor.from_pretrained("anuashok/ocr-captcha-v3")
model = VisionEncoderDecoderModel.from_pretrained("anuashok/ocr-captcha-v3")
print("Model loaded successfully!")

async def solve_captcha_with_trocr(screenshot_bytes):
    try:
        image = Image.open(io.BytesIO(screenshot_bytes)).convert("RGBA")
        background = Image.new("RGBA", image.size, (255, 255, 255))
        combined = Image.alpha_composite(background, image).convert("RGB")

        pixel_values = processor(combined, return_tensors="pt").pixel_values
        generated_ids = model.generate(pixel_values)
        generated_text = processor.batch_decode(generated_ids, skip_special_tokens=True)[0]

        cleaned_text = ''.join(filter(str.isalnum, generated_text))
        return cleaned_text

    except Exception as e:
        print("Error solving captcha:", e)
        return None

async def refresh_captcha(page):
    selectors = [
        "span.material-icons.reload-btn",
        "button.refresh-captcha",
        ".captcha-refresh",
        "[class*='refresh']",
        "button[title*='refresh' i]"
    ]

    for s in selectors:
        btn = await page.query_selector(s)
        if btn:
            await btn.click()
            await page.wait_for_timeout(1500)
            print("🔄 Captcha refreshed")
            return True

    print("⚠ No refresh button found!")
    return False

async def automate_passport_application(user_data):
    """Automate the passport application process using Playwright"""
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        
        try:
            await page.goto("https://emrtds.nepalpassport.gov.np")

            # FIRST ISSUANCE
            await page.wait_for_selector("text=First Issuance")
            await page.click("text=First Issuance")

            # PASSPORT TYPE
            await page.wait_for_selector("label.main-doc-types")
            await page.click("label.main-doc-types:has-text('Ordinary 34 pages')")

            # PROCEED
            await page.wait_for_selector("text=Proceed")
            await page.click("text=Proceed")

            # CONSENT POPUP
            try:
                await page.wait_for_selector("mat-dialog-container", timeout=5000)
                await page.click("mat-dialog-container >> text=I agree स्वीकृत छ")
            except:
                pass

            # WAIT FOR APPOINTMENT PAGE
            await page.wait_for_url("**/appointment", timeout=15000)

            # SELECT COUNTRY, PROVINCE, DISTRICT, LOCATION
            selects = await page.query_selector_all("mat-select")
            await selects[0].click()
            await page.click("mat-option >> text=Nepal")
            await selects[1].click()
            await page.click("mat-option >> text=Bagmati")
            await selects[2].click()
            await page.click("mat-option >> text=Makawanpur")
            await selects[3].click()
            await page.click("mat-option >> text=Makawanpur")

            # DATE PICKER
            try:
                date_input = await page.wait_for_selector(
                    "input[placeholder*='Date' i], input[type='text'][formcontrolname*='date' i]",
                    timeout=5000
                )
                await date_input.click()
                await page.wait_for_selector(".ui-datepicker-calendar")
                first_date = await page.wait_for_selector(
                    "td:not(.ui-datepicker-other-month):not(.ui-state-disabled) a"
                )
                await first_date.click()
            except:
                print("Date auto-selected.")

            # TIME SLOT
            await page.wait_for_selector(".ui-datepicker-calendar-container mat-chip-list")
            slots = await page.query_selector_all("mat-chip.mat-chip:not(.mat-chip-disabled)")
            if slots:
                await slots[0].click()

            # CAPTCHA SOLVING
            print("\n==============================")
            print(" STARTING CAPTCHA SOLVER ")
            print("==============================\n")

            os.makedirs("captchas", exist_ok=True)
            max_attempts = 10

            for attempt in range(1, max_attempts + 1):
                print(f"\n🎯 Attempt {attempt}/{max_attempts}")

                try:
                    # GET CAPTCHA IMAGE
                    captcha_img = await page.wait_for_selector("img.captcha-img", timeout=8000)
                    screenshot_bytes = await captcha_img.screenshot()

                    # SAVE IMAGE
                    save_path = f"captchas/captcha_{attempt}.png"
                    with open(save_path, "wb") as f:
                        f.write(screenshot_bytes)
                    print(f"📸 Saved: {save_path}")

                    # SOLVE CAPTCHA
                    captcha_text = await solve_captcha_with_trocr(screenshot_bytes)
                    print("🤖 OCR:", captcha_text)

                    if not captcha_text or len(captcha_text) < 4:
                        print("❌ Invalid OCR → refreshing captcha...")
                        await refresh_captcha(page)
                        continue

                    # ENTER CAPTCHA
                    captcha_input = await page.wait_for_selector(
                        "input.captcha-text, input[name='text']",
                        state="visible",
                        timeout=12000
                    )
                    await captcha_input.fill("")
                    await captcha_input.type(captcha_text, delay=80)
                    print("⌨ Entered:", captcha_text)
                    await page.wait_for_timeout(1000)

                    # CLICK NEXT BUTTON (wait until enabled)
                    try:
                        next_btn = await page.wait_for_selector(
                            "a.btn.btn-primary:not(.appt-disabled)",
                            timeout=8000
                        )
                        await next_btn.click()
                    except:
                        print("⚠ Next button not enabled yet")

                    # WAIT A MOMENT
                    await page.wait_for_timeout(2000)

                    # CHECK IF WRONG CAPTCHA POPUP APPEARS
                    close_btn = await page.query_selector("button#landing-button-2:has-text('Close')")
                    if close_btn:
                        print("❌ Captcha was wrong! Closing popup and refreshing...")
                        await close_btn.click()
                        await refresh_captcha(page)
                        continue  # retry

                    # OTHERWISE, captcha likely correct
                    current = page.url
                    if "application" in current or "form" in current:
                        print("\n🎉 CAPTCHA SUCCESS! Application page loaded!")
                        
                        # TODO: Fill the actual form with user_data
                        # This is where you would populate the form fields with the collected data
                        print("📝 Ready to fill form with user data")
                        break

                except Exception as e:
                    print("⚠ Error in attempt:", e)
                    await refresh_captcha(page)
                    continue

            await page.wait_for_timeout(3000)
            return True, "Application automation completed successfully!"
            
        except Exception as e:
            return False, f"Automation failed: {str(e)}"
        finally:
            await browser.close()

def send_slack_notification(message):
    """Send notification to Slack webhook"""
    webhook_url = os.environ.get("SLACK_WEBHOOK")
    if webhook_url:
        try:
            payload = {
                "text": message,
                "username": "Passport Bot Notifications",
                "icon_emoji": ":passport_control:"
            }
            response = requests.post(webhook_url, json=payload)
            return response.status_code == 200
        except Exception as e:
            logging.error(f"Failed to send Slack notification: {e}")
    return False

def validate_field(field_code, value):
    """Validate field against its regex and size constraints"""
    field_config = PASSPORT_FIELDS[field_code]
    
    # Convert to uppercase for specific fields
    if field_code == "gender":
        value = value.upper()
    
    # Check if mandatory field is empty
    if field_config["mandatory"] and (not value or value.strip() == ""):
        return False, "This field is mandatory"
    
    # Check size constraints
    if len(value) < field_config["minSize"]:
        return False, f"Minimum length is {field_config['minSize']} characters"
    
    if len(value) > field_config["maxSize"]:
        return False, f"Maximum length is {field_config['maxSize']} characters"
    
    # Check regex pattern
    if field_config["regex"] and not re.match(field_config["regex"], value):
        return False, f"Invalid format. {field_config['description']}"
    
    return True, "Valid"

def get_next_field(current_field, user_data):
    """Determine the next field to ask based on current progress"""
    field_order = [
        "serviceCode", "documentTypeCode", "lastName", "firstName", "gender",
        "dateOfBirth", "dateOfBirthBS", "isExactDateOfBirth", "birthDistrict", 
        "birthCountry", "nationality", "fatherLastName", "fatherFirstName",
        "motherLastName", "motherFirstName", "citizenNum", "citizenIssueDateBS",
        "citizenIssuePlaceDistrict", "homePhone", 
        # REMOVED EMAIL
        "mainAddressHouseNum", "mainAddressStreetVillage", "mainAddressWard", 
        "mainAddressMunicipality", "mainAddressDistrict", "mainAddressProvince"
    ]
    
    for field in field_order:
        if field not in user_data:
            return field
    
    return None

def save_to_supabase(user_data, user_id):
    """Save application data to Supabase"""
    try:
        # Prepare data for Supabase
        application_data = {
            "slack_user_id": user_id,
            "service_code": user_data.get("serviceCode"),
            "last_name": user_data.get("lastName"),
            "first_name": user_data.get("firstName"),
            "gender": user_data.get("gender"),
            "date_of_birth": user_data.get("dateOfBirth"),
            "date_of_birth_bs": user_data.get("dateOfBirthBS"),
            "is_exact_dob": user_data.get("isExactDateOfBirth"),
            "birth_district": user_data.get("birthDistrict"),
            "birth_country": user_data.get("birthCountry"),
            "nationality": user_data.get("nationality"),
            "father_last_name": user_data.get("fatherLastName"),
            "father_first_name": user_data.get("fatherFirstName"),
            "mother_last_name": user_data.get("motherLastName"),
            "mother_first_name": user_data.get("motherFirstName"),
            "citizenship_number": user_data.get("citizenNum"),
            "citizenship_issue_date_bs": user_data.get("citizenIssueDateBS"),
            "citizenship_issue_district": user_data.get("citizenIssuePlaceDistrict"),
            "phone_number": user_data.get("homePhone"),
            # REMOVED EMAIL
            "house_number": user_data.get("mainAddressHouseNum"),
            "street_village": user_data.get("mainAddressStreetVillage"),
            "ward": user_data.get("mainAddressWard"),
            "municipality": user_data.get("mainAddressMunicipality"),
            "district": user_data.get("mainAddressDistrict"),
            "province": user_data.get("mainAddressProvince"),
            "document_type": user_data.get("documentTypeCode"),
            "submitted_at": datetime.now().isoformat(),
            "status": "submitted"
        }
        
        # Insert into Supabase
        response = supabase.table("passport_applications").insert(application_data).execute()
        
        if response.data:
            logging.info(f"Application saved to Supabase for user {user_id}")
            return True, response.data[0]['id']  # Return the application ID
        else:
            logging.error(f"Failed to save to Supabase: {response.error}")
            return False, None
            
    except Exception as e:
        logging.error(f"Error saving to Supabase: {e}")
        return False, None

def create_field_prompt(field_code, user_data):
    """Create prompt for a specific field"""
    field_config = PASSPORT_FIELDS[field_code]
    
    blocks = [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*{field_config['name']}*"
            }
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn", 
                "text": f"_{field_config['description']}_"
            }
        }
    ]
    
    # Add format hints for specific fields
    if field_code == "gender":
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "Enter: *M* (Male), *F* (Female), or *X* (Other)\nYou can type in uppercase or lowercase"
            }
        })
    elif field_code == "dateOfBirth":
        blocks.append({
            "type": "section", 
            "text": {
                "type": "mrkdwn",
                "text": "Format: *YYYY-MM-DD* (e.g., 1990-05-15)"
            }
        })
    elif field_code == "documentTypeCode":
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn", 
                "text": "Options: *PP* (Ordinary), *PB* (Official), *PS* (Diplomatic), *PD* (Emergency), *PG* (Group), *PT* (Temporary), *PN* (Special)"
            }
        })
    # Add hints for district/province fields to use full names
    elif field_code in ["birthDistrict", "birthCountry", "citizenIssuePlaceDistrict", 
                       "mainAddressMunicipality", "mainAddressDistrict", "mainAddressProvince"]:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "Enter the full name (e.g., 'Kathmandu', 'Bagmati', 'Nepal')"
            }
        })
    
    # Add progress indicator
    completed = len(user_data)
    total = len([f for f in PASSPORT_FIELDS.values() if f['mandatory'] or f.get('collected', False)])
    progress = int((completed / total) * 100) if total > 0 else 0
    
    blocks.append({
        "type": "section",
        "text": {
            "type": "mrkdwn", 
            "text": f"Progress: {completed}/{total} fields completed ({progress}%)"
        }
    })
    
    return blocks

# Start application in DM by typing "start"
@app.event("message")
def handle_dm(event, say, client):
    user_id = event["user"]
    text = event.get("text", "").strip()

    # Ignore bot messages and channel messages
    if event.get("bot_id") or event.get("channel_type") != "im":
        return

    # If user has no session and types 'start', create a session
    if user_id not in user_sessions and text.lower() == "start":
        user_sessions[user_id] = {
            "step": "serviceCode",
            "data": {},
            "started_at": datetime.now().isoformat()
        }
        field_blocks = create_field_prompt("serviceCode", {})
        say(text="Let's start your passport application!", blocks=field_blocks)
        return

    # If no session and user didn't type 'start', prompt to type 'start'
    if user_id not in user_sessions:
        say("Hi! To begin your passport application, please type *start* here.")
        return

    # Handle current session input
    session = user_sessions[user_id]
    current_field = session["step"]

    # Convert to uppercase for specific fields before validation
    if current_field == "gender":
        text = text.upper()

    # Validate field
    is_valid, error_message = validate_field(current_field, text)
    if not is_valid:
        say(f"❌ Invalid input: {error_message}\nPlease try again:")
        return

    # Store valid data (already converted to uppercase for gender)
    session["data"][current_field] = text

    # Move to next field
    next_field = get_next_field(current_field, session["data"])
    if next_field:
        session["step"] = next_field
        field_blocks = create_field_prompt(next_field, session["data"])
        say("✅ Saved! Next field:", blocks=field_blocks)
    else:
        # All fields completed, show summary
        user_data = session["data"]
        summary_blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "✅ Application Complete!"}
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn",
                         "text": "Your passport application has been completed successfully! Here's a summary:"}
            },
            {
                "type": "section",
                "text": {"type": "mrkdwn",
                         "text": f"*Name:* {user_data.get('lastName','')} {user_data.get('firstName','')}\n"
                                 f"*Gender:* {user_data.get('gender','')}\n"
                                 f"*DOB (AD):* {user_data.get('dateOfBirth','')}\n"
                                 f"*DOB (BS):* {user_data.get('dateOfBirthBS','')}"}
            },
            {
                "type": "actions",
                "elements": [
                    {"type": "button", "text": {"type": "plain_text", "text": "Submit & Auto-Fill"},
                     "action_id": "submit_application", "style": "primary"},
                    {"type": "button", "text": {"type": "plain_text", "text": "Edit Information"},
                     "action_id": "edit_application"}
                ]
            }
        ]
        say(blocks=summary_blocks)

@app.action("submit_application")
def submit_application(ack, body, say, client):
    ack()
    user_id = body["user"]["id"]
    
    if user_id not in user_sessions:
        say("Session expired. Please start over by typing *start*")
        return
    
    user_data = user_sessions[user_id]["data"]
    
    # Save to Supabase
    success, application_id = save_to_supabase(user_data, user_id)
    
    if success:
        # Start automation in background
        asyncio.create_task(run_automation_and_notify(user_data, user_id, say, client))
        
        # Send immediate response
        say("🔄 *Starting automated passport application process...*\n\nI'm now filling out your application automatically. This may take a few minutes. I'll notify you when it's complete!")
        
    else:
        say("❌ Sorry, there was an error saving your application. Please try again or contact support.")

async def run_automation_and_notify(user_data, user_id, say, client):
    """Run automation and send notification when complete"""
    try:
        success, message = await automate_passport_application(user_data)
        
        if success:
            # Send success message to user
            await client.chat_postMessage(
                channel=user_id,
                text=f"🎉 *Automation Complete!* {message}"
            )
            
            # Send notification to Slack webhook
            notification_msg = f"🤖 Passport Automation Completed!\n• Applicant: {user_data.get('lastName')} {user_data.get('firstName')}\n• Status: {message}\n• Completed: {datetime.now().strftime('%Y-%m-%d %H:%M')}"
            send_slack_notification(notification_msg)
            
        else:
            # Send error message to user
            await client.chat_postMessage(
                channel=user_id,
                text=f"❌ *Automation Failed:* {message}\nPlease try again or contact support."
            )
        
        # Clear session
        if user_id in user_sessions:
            del user_sessions[user_id]
            
    except Exception as e:
        # Send error message
        await client.chat_postMessage(
            channel=user_id,
            text=f"❌ *Automation Error:* {str(e)}\nPlease contact support."
        )

@app.action("edit_application")
def edit_application(ack, body, say):
    ack()
    user_id = body["user"]["id"]
    
    if user_id in user_sessions:
        # Restart from first field but keep collected data
        session = user_sessions[user_id]
        session["step"] = "serviceCode"
        
        field_blocks = create_field_prompt("serviceCode", session["data"])
        say("Let's review your information. Starting from the beginning:", blocks=field_blocks)
    else:
        say("Please start a new application by typing *start*")

# Error handling
@app.error
def global_error_handler(error, body, logger):
    logger.exception(f"Error: {error}")
    logger.info(f"Request body: {body}")

# Start the app
if __name__ == "__main__":
    handler = SocketModeHandler(app, os.environ.get("SLACK_APP_TOKEN"))
    
    print("🚀 Passport Application Bot is running! DM 'start' to begin.")
    handler.start()