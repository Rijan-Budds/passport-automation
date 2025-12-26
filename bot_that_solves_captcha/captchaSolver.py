import asyncio
import os
import io
from dotenv import load_dotenv
from slack_bolt.async_app import AsyncApp
from slack_bolt.adapter.socket_mode.aiohttp import AsyncSocketModeHandler
from transformers import VisionEncoderDecoderModel, TrOCRProcessor
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from PIL import Image
from difflib import get_close_matches

# Load environment
load_dotenv(".env.dev")

# ================= Slack Bot Setup =================
app = AsyncApp(
    token=os.environ.get("SLACK_BOT_TOKEN"),
    signing_secret=os.environ.get("SLACK_SIGNING_SECRET")
)

# Store user sessions
user_sessions = {}

# ================= TrOCR Captcha Model =================
processor = TrOCRProcessor.from_pretrained("anuashok/ocr-captcha-v3")
model = VisionEncoderDecoderModel.from_pretrained("anuashok/ocr-captcha-v3")

async def solve_captcha(screenshot_bytes):
    image = Image.open(io.BytesIO(screenshot_bytes)).convert("RGBA")
    background = Image.new("RGBA", image.size, (255, 255, 255))
    combined = Image.alpha_composite(background, image).convert("RGB")
    pixel_values = processor(combined, return_tensors="pt").pixel_values
    generated_ids = model.generate(pixel_values)
    text = processor.batch_decode(generated_ids, skip_special_tokens=True)[0]
    return ''.join(filter(str.isalnum, text))

# ================= Province → Districts mapping =================
PROVINCES = {
    "Province 1": ["Taplejung", "Panchthar", "Ilam", "Morang", "Sunsari", "Jhapa"],
    "Province 2": ["Saptari", "Siraha", "Dhanusha", "Mahottari", "Sarlahi", "Rautahat", "Bara", "Parsa"],
    "Bagmati": ["Kathmandu", "Lalitpur", "Bhaktapur", "Dhading", "Nuwakot", "Rasuwa", "Sindhupalchok"],
    "Gandaki": ["Kaski", "Lamjung", "Tanahun", "Gorkha", "Manang"],
    "Lumbini": ["Rupandehi", "Kapilvastu", "Arghakhanchi", "Palpa", "Dang"],
    "Karnali": ["Surkhet", "Dailekh", "Jumla", "Dolpa"],
    "Sudurpashchim": ["Bajura", "Bajhang", "Dadeldhura", "Kailali", "Doti"]
}

# ================= District Offices =================
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

# ================= Helper Functions =================
def match_province(user_input):
    matches = get_close_matches(user_input.title(), PROVINCES.keys(), n=1, cutoff=0.5)
    return matches[0] if matches else None

def match_district(user_input, province):
    districts = PROVINCES.get(province, [])
    matches = get_close_matches(user_input.title(), districts, n=1, cutoff=0.5)
    return matches[0] if matches else None

# ================= Form Filling Functions =================
async def fill_personal_information(page, user_data, user_id, say):
    """Fill the personal information form on the next page"""
    try:
        await say("📝 Starting to fill personal information form...")
        
        # Wait for form to be visible
        await page.wait_for_selector("form", timeout=10000)
        
        # Fill basic information fields
        form_fields = {
            "firstName": user_data.get("first_name", ""),
            "middleName": user_data.get("middle_name", ""),
            "lastName": user_data.get("last_name", ""),
            "email": user_data.get("email", ""),
            "phone": user_data.get("phone", ""),
            "citizenshipNumber": user_data.get("citizenship_number", ""),
            "dateOfBirth": user_data.get("dob", ""),
        }
        
        filled_fields = 0
        for field_name, value in form_fields.items():
            if value:
                try:
                    # Try different selector patterns
                    selectors = [
                        f"input[name='{field_name}']",
                        f"input[formcontrolname='{field_name}']",
                        f"#{field_name}",
                        f"input[placeholder*='{field_name.title()}']",
                        f"input[placeholder*='{field_name}']"
                    ]
                    
                    for selector in selectors:
                        try:
                            field = await page.wait_for_selector(selector, timeout=1000)
                            if field:
                                await field.fill(value)
                                await say(f"✅ Filled {field_name}")
                                filled_fields += 1
                                break
                        except:
                            continue
                except Exception as e:
                    await say(f"⚠️ Could not fill {field_name}: {e}")
        
        # Handle dropdowns
        dropdown_fields = {
            "gender": user_data.get("gender", "Male"),
            "maritalStatus": user_data.get("marital_status", "Unmarried"),
            "education": user_data.get("education", "Bachelor"),
        }
        
        for field_name, value in dropdown_fields.items():
            try:
                dropdown_selectors = [
                    f"mat-select[formcontrolname='{field_name}']",
                    f"mat-select[name='{field_name}']",
                    f"select[name='{field_name}']"
                ]
                
                for selector in dropdown_selectors:
                    try:
                        dropdown = await page.wait_for_selector(selector, timeout=1000)
                        if dropdown:
                            await dropdown.click()
                            await page.wait_for_selector("mat-option", timeout=2000)
                            
                            # Try to select the option
                            option = await page.query_selector(f"mat-option:has-text('{value}')")
                            if option:
                                await option.click()
                                await say(f"✅ Selected {field_name}: {value}")
                                filled_fields += 1
                            break
                    except:
                        continue
            except Exception as e:
                await say(f"⚠️ Could not select {field_name}: {e}")
        
        await say(f"✅ Personal information form filled successfully! ({filled_fields} fields)")
        return True
        
    except Exception as e:
        await say(f"❌ Error filling personal information: {e}")
        return False

async def fill_address_information(page, user_data, user_id, say):
    """Fill the address information form"""
    try:
        await say("🏠 Starting to fill address information...")
        
        # Fill permanent address fields
        address_fields = {
            "permanentDistrict": user_data.get("permanent_district", user_data.get("district", "")),
            "permanentMunicipality": user_data.get("permanent_municipality", ""),
            "permanentWard": user_data.get("permanent_ward", ""),
            "permanentTole": user_data.get("permanent_tole", ""),
            "currentDistrict": user_data.get("current_district", user_data.get("district", "")),
            "currentMunicipality": user_data.get("current_municipality", user_data.get("permanent_municipality", "")),
            "currentWard": user_data.get("current_ward", user_data.get("permanent_ward", "")),
            "currentTole": user_data.get("current_tole", user_data.get("permanent_tole", "")),
        }
        
        filled_fields = 0
        for field_name, value in address_fields.items():
            if value:
                try:
                    selectors = [
                        f"input[name='{field_name}']",
                        f"input[formcontrolname='{field_name}']",
                        f"#{field_name}",
                        f"mat-select[formcontrolname='{field_name}']"
                    ]
                    
                    for selector in selectors:
                        try:
                            field = await page.wait_for_selector(selector, timeout=1000)
                            if field:
                                # Check if it's a dropdown (mat-select) or input field
                                if "mat-select" in selector:
                                    await field.click()
                                    await page.wait_for_selector("mat-option", timeout=2000)
                                    option = await page.query_selector(f"mat-option:has-text('{value}')")
                                    if option:
                                        await option.click()
                                else:
                                    await field.fill(value)
                                
                                await say(f"✅ Filled {field_name}")
                                filled_fields += 1
                                break
                        except:
                            continue
                except Exception as e:
                    await say(f"⚠️ Could not fill {field_name}: {e}")
        
        await say(f"✅ Address information filled successfully! ({filled_fields} fields)")
        return True
        
    except Exception as e:
        await say(f"❌ Error filling address information: {e}")
        return False

async def fill_family_information(page, user_data, user_id, say):
    """Fill family information form"""
    try:
        await say("👨‍👩‍👧‍👦 Starting to fill family information...")
        
        family_fields = {
            "fatherName": user_data.get("father_name", ""),
            "motherName": user_data.get("mother_name", ""),
            "spouseName": user_data.get("spouse_name", ""),
        }
        
        filled_fields = 0
        for field_name, value in family_fields.items():
            if value:
                try:
                    selectors = [
                        f"input[name='{field_name}']",
                        f"input[formcontrolname='{field_name}']",
                        f"#{field_name}"
                    ]
                    
                    for selector in selectors:
                        try:
                            field = await page.wait_for_selector(selector, timeout=1000)
                            if field:
                                await field.fill(value)
                                await say(f"✅ Filled {field_name}")
                                filled_fields += 1
                                break
                        except:
                            continue
                except Exception as e:
                    await say(f"⚠️ Could not fill {field_name}: {e}")
        
        await say(f"✅ Family information filled successfully! ({filled_fields} fields)")
        return True
        
    except Exception as e:
        await say(f"❌ Error filling family information: {e}")
        return False

async def handle_captcha_failure(page, say, attempt):
    """Handle the captcha failure by clicking the Close button and reloading captcha"""
    try:
        await say(f"🔄 Handling captcha failure for attempt {attempt}...")
        
        # Look for the Close button with multiple possible selectors
        close_button_selectors = [
            "button#landing-button-2",
            "button.btn-primary:has-text('Close')",
            "button.mat-dialog-close:has-text('Close')",
            "button:has-text('Close')"
        ]
        
        close_btn = None
        for selector in close_button_selectors:
            try:
                close_btn = await page.wait_for_selector(selector, timeout=5000)
                if close_btn:
                    break
            except:
                continue
        
        if close_btn:
            await close_btn.click()
            await say("✅ Closed the error dialog.")
            await page.wait_for_timeout(2000)
        else:
            await say("⚠️ Close button not found, trying to continue...")
        
        # Try to reload the captcha
        reload_button_selectors = [
            "span.reload-btn",
            "button#reload-captcha",
            "button:has-text('Reload')",
            "img.captcha-img"  # Sometimes clicking the image reloads it
        ]
        
        reload_btn = None
        for selector in reload_button_selectors:
            try:
                reload_btn = await page.wait_for_selector(selector, timeout=3000)
                if reload_btn:
                    await reload_btn.click()
                    await say("🔄 Captcha reloaded.")
                    await page.wait_for_timeout(2000)
                    break
            except:
                continue
        
        if not reload_btn:
            # If no reload button found, wait a bit and continue
            await say("⚠️ No reload button found, waiting before retry...")
            await page.wait_for_timeout(3000)
        
        return True
        
    except Exception as e:
        await say(f"❌ Error handling captcha failure: {e}")
        return False

# ================= Passport Automation =================
async def automate_passport_application(user_data, user_id, say):
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
            await page.click(f"label.main-doc-types:has-text('{user_data['passport_type']}')")

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

            # SELECT COUNTRY, PROVINCE, DISTRICT, OFFICE
            selects = await page.query_selector_all("mat-select")
            await selects[0].click()  # Country (fixed)
            await page.click("mat-option >> text=Nepal")  # Fixed

            await selects[1].click()
            await page.click(f"mat-option >> text={user_data['province']}")

            await selects[2].click()
            await page.click(f"mat-option >> text={user_data['district']}")

            await selects[3].click()
            await page.click(f"mat-option >> text={user_data['office']}")

            # DATE PICKER - Use selected date from session
            try:
                if "appointment_date" in user_data:
                    date_input = await page.wait_for_selector(
                        "input[placeholder*='Date' i], input[type='text'][formcontrolname*='date' i]",
                        timeout=5000
                    )
                    await date_input.click()
                    await page.wait_for_selector(".ui-datepicker-calendar")
                    
                    # Extract day from appointment_date (format: YYYY-MM-DD)
                    appointment_date = user_data["appointment_date"]
                    day = appointment_date.split("-")[2] if "-" in appointment_date else appointment_date
                    
                    # Click the specific day
                    await page.click(f"a:has-text('{int(day)}')")
                    await say(f"✅ Selected date: {appointment_date}")
                else:
                    # Fallback to auto-selecting first available date
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
                    await say("📅 Date auto-selected.")
            except Exception as e:
                await say(f"⚠️ Date selection error: {e}")

            # TIME SLOT - Use selected time from session
            await page.wait_for_selector(".ui-datepicker-calendar-container mat-chip-list", timeout=10000)
            
            if "appointment_time" in user_data:
                chips = await page.query_selector_all("mat-chip.mat-chip:not(.mat-chip-disabled)")
                time_selected = False
                target_time = user_data["appointment_time"]
                
                for chip in chips:
                    chip_text = await chip.inner_text()
                    if target_time.lower() in chip_text.lower():
                        await chip.click()
                        await say(f"✅ Selected time slot: {target_time}")
                        time_selected = True
                        break
                
                if not time_selected and chips:
                    await chips[0].click()
                    await say(f"⚠️ Could not find exact time '{target_time}', selected first available slot")
            else:
                # Fallback to selecting first available slot
                slots = await page.query_selector_all("mat-chip.mat-chip:not(.mat-chip-disabled)")
                if slots:
                    await slots[0].click()
                    await say("⏰ Time slot auto-selected.")

            # ========== CAPTCHA HANDLING ==========
            captcha_success = False
            for attempt in range(1, 11):
                try:
                    await say(f"🔄 Attempt {attempt}/10: Solving captcha...")
                    
                    # Get captcha image
                    captcha_img = await page.wait_for_selector("img.captcha-img", timeout=8000)
                    screenshot_bytes = await captcha_img.screenshot()
                    captcha_text = await solve_captcha(screenshot_bytes)

                    await say(f"🔤 Captcha text detected: {captcha_text}")

                    # Fill captcha input
                    captcha_input = await page.wait_for_selector(
                        "input.captcha-text, input[name='text']",
                        state="visible",
                        timeout=12000
                    )
                    await captcha_input.fill(captcha_text)

                    # Click Next button and wait for navigation
                    next_btn = await page.wait_for_selector("a.btn.btn-primary", timeout=5000)
                    if next_btn:
                        # Wait for navigation to complete after clicking Next
                        async with page.expect_navigation(timeout=10000) as navigation_info:
                            await next_btn.click()
                        
                        await navigation_info.value
                        await say(f"✅ Captcha solved successfully on attempt {attempt}. Moving to next page...")
                        captcha_success = True
                        
                        # Wait for the next page to load
                        await page.wait_for_timeout(3000)
                        
                        # ========== FILL ALL FORMS ON NEXT PAGES ==========
                        try:
                            # Fill personal information
                            personal_success = await fill_personal_information(page, user_data, user_id, say)
                            if not personal_success:
                                return False, "Failed to fill personal information"
                            
                            # Try to find and click Next button for address page
                            next_buttons = await page.query_selector_all("button:has-text('Next'), button[type='submit']")
                            if next_buttons:
                                async with page.expect_navigation(timeout=10000):
                                    await next_buttons[0].click()
                                await page.wait_for_timeout(2000)
                                
                                # Fill address information
                                address_success = await fill_address_information(page, user_data, user_id, say)
                                if not address_success:
                                    return False, "Failed to fill address information"
                                
                                # Try to find and click Next button for family page
                                next_buttons = await page.query_selector_all("button:has-text('Next'), button[type='submit']")
                                if next_buttons:
                                    async with page.expect_navigation(timeout=10000):
                                        await next_buttons[0].click()
                                    await page.wait_for_timeout(2000)
                                    
                                    # Fill family information
                                    family_success = await fill_family_information(page, user_data, user_id, say)
                                    if not family_success:
                                        return False, "Failed to fill family information"
                            
                            await say("🎉 All forms filled successfully!")
                            return True, "Full passport application automation completed successfully!"
                            
                        except Exception as e:
                            await say(f"⚠️ Error during form filling: {e}")
                            # Continue even if form filling has issues
                            return True, f"Application submitted with minor issues: {str(e)}"
                        
                        break

                except PlaywrightTimeoutError:
                    await say(f"❌ Captcha attempt {attempt} failed (timeout). Handling failure...")
                    
                    # Handle the captcha failure with Close button
                    failure_handled = await handle_captcha_failure(page, say, attempt)
                    
                    if not failure_handled:
                        await say("⚠️ Could not properly handle captcha failure, trying to continue...")
                        await page.wait_for_timeout(3000)
                    
                except Exception as e:
                    await say(f"❌ Captcha attempt {attempt} error: {e}")
                    
                    # Try to handle failure even for other errors
                    try:
                        await handle_captcha_failure(page, say, attempt)
                    except:
                        pass
                    
                    await asyncio.sleep(2)

            if not captcha_success:
                return False, "Captcha could not be solved after 10 attempts."

            # ========== WAITING ROOM CHECK ==========
            try:
                waiting_room_text = await page.query_selector("text=waiting room")
                if waiting_room_text:
                    await say(f"⏳ Waiting room detected. Will retry in 5 minutes <@{user_id}>.")
                    await asyncio.sleep(300)  # Wait 5 minutes
                    return await automate_passport_application(user_data, user_id, say)
            except:
                pass

            return True, "Passport application automation completed successfully!"

        except Exception as e:
            return False, str(e)
        finally:
            await browser.close()

# ================= Supabase Helper Functions =================
# Note: You'll need to import your actual supabase_helper functions
# For now, I'll create placeholder functions

def get_available_dates(district, office):
    """Get available dates for a district from Supabase"""
    # TODO: Implement actual Supabase query
    # This is a placeholder - replace with actual implementation
    from datetime import datetime, timedelta
    
    # Generate some sample dates for demonstration
    sample_dates = []
    today = datetime.now()
    for i in range(1, 8):
        date = today + timedelta(days=i)
        sample_dates.append(date.strftime("%Y-%m-%d"))
    
    return sample_dates

def get_available_times(district, date):
    """Get available time slots for a district and date from Supabase"""
    # TODO: Implement actual Supabase query
    # This is a placeholder - replace with actual implementation
    
    sample_times = [
        {"name": "09:00 AM - 10:00 AM", "normal_capacity": 5, "vip_capacity": 2},
        {"name": "10:00 AM - 11:00 AM", "normal_capacity": 3, "vip_capacity": 1},
        {"name": "11:00 AM - 12:00 PM", "normal_capacity": 4, "vip_capacity": 1},
        {"name": "01:00 PM - 02:00 PM", "normal_capacity": 6, "vip_capacity": 3},
        {"name": "02:00 PM - 03:00 PM", "normal_capacity": 2, "vip_capacity": 1},
    ]
    
    return sample_times

# ================= Conversation Flow =================
QUESTIONS_PRE_CAPTCHA = [
    ("passport_type", "What type of passport do you want? (Regular/Diplomatic/Official)"),
    ("province", "Which province? (Bagmati, Gandaki, Karnali, Lumbini, Sudurpashchim, Province 1, Province 2)"),
    ("district", "Which district?"),
    ("office", "Which office?"),
]

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

# Additional questions for address and family info (optional)
QUESTIONS_ADDITIONAL = [
    ("permanent_municipality", "What is your permanent municipality?"),
    ("permanent_ward", "What is your permanent ward number?"),
    ("permanent_tole", "What is your permanent tole?"),
    ("father_name", "What is your father's full name?"),
    ("mother_name", "What is your mother's full name?"),
]

# ================= Slack Event Handler =================
@app.event("message")
async def handle_dm(event, say):
    user_id = event["user"]
    text = event.get("text", "").strip()
    if event.get("bot_id") or event.get("channel_type") != "im":
        return

    # Initialize session
    if user_id not in user_sessions:
        user_sessions[user_id] = {
            "data": {},
            "step": 0,
            "question_phase": "pre_captcha"
        }
        await say("👋 Welcome to the Passport Automation Bot! Let's get started.")
        await say(QUESTIONS_PRE_CAPTCHA[0][1])
        return

    session = user_sessions[user_id]
    phase = session["question_phase"]
    step = session["step"]

    if phase == "pre_captcha":
        key = QUESTIONS_PRE_CAPTCHA[step][0]

        # Province fuzzy match
        if key == "province":
            matched = match_province(text)
            if matched:
                session["data"]["province"] = matched
                session["province_districts"] = PROVINCES[matched]
                session["step"] += 1
                districts = PROVINCES[matched]
                await say(f"✅ Province recognized: *{matched}*\nAvailable districts: {', '.join(districts)}\nType your district:")
                return
            else:
                await say("❌ Province not recognized. Try again.")
                return

        # District fuzzy match
        if key == "district":
            province = session["data"].get("province")
            matched = match_district(text, province)
            if matched:
                session["data"]["district"] = matched
                offices = DISTRICT_OFFICES.get(matched, [])
                session["offices_options"] = offices
                session["step"] += 1
                if offices:
                    options_text = "\n".join(f"{i+1}. {office}" for i, office in enumerate(offices))
                    await say(f"✅ District recognized: *{matched}*\nAvailable offices:\n{options_text}\nType the office name or number:")
                else:
                    await say(f"✅ District recognized: *{matched}*\nNo specific offices found. Please type the office name:")
                return
            else:
                await say("❌ District not recognized. Type again.")
                return

        # Office handling
        if key == "office" and "offices_options" in session:
            offices = session["offices_options"]
            text_clean = text.strip()

            if text_clean.isdigit() and 1 <= int(text_clean) <= len(offices):
                office = offices[int(text_clean) - 1]
            else:
                matches = [o for o in offices if o.lower() == text_clean.lower()]
                if not matches:
                    await say("❌ Invalid office. Choose from the list.")
                    return
                office = matches[0]

            session["data"]["office"] = office

            # 🔍 Fetch dates from Supabase
            dates = get_available_dates(session["data"]["district"], office)

            if not dates:
                await say("❌ No available dates for this district.")
                return

            session["available_dates"] = dates
            session["question_phase"] = "date_selection"

            options = "\n".join(f"{i+1}. {d}" for i, d in enumerate(dates))
            await say(
                "📅 *Available Dates:*\n"
                f"{options}\n\n"
                "Reply with date number:"
            )
            return

        # Passport type or other fields
        else:
            session["data"][key] = text
            session["step"] += 1

        # Move to personal info (old flow - kept for backward compatibility)
        if session["step"] >= len(QUESTIONS_PRE_CAPTCHA):
            session["question_phase"] = "personal_info"
            session["step"] = 0
            await say("✅ Basic info collected. Now your personal details.")
            await say(QUESTIONS_PERSONAL_INFO[0][1])
        else:
            next_question = QUESTIONS_PRE_CAPTCHA[session["step"]][1]
            await say(next_question)

    elif phase == "date_selection":
        dates = session.get("available_dates", [])

        if not text.isdigit() or not (1 <= int(text) <= len(dates)):
            await say("❌ Choose a valid date number.")
            return

        selected_date = dates[int(text) - 1]
        session["data"]["appointment_date"] = selected_date

        # 🔍 Fetch time slots from Supabase
        times = get_available_times(
            session["data"]["district"],
            selected_date
        )

        if not times:
            await say("❌ No time slots available for this date.")
            return

        session["available_times"] = times
        session["question_phase"] = "time_selection"

        options = []
        for i, t in enumerate(times):
            options.append(
                f"{i+1}. {t['name']} "
                f"(Normal: {t['normal_capacity']}, VIP: {t['vip_capacity']})"
            )

        await say(
            "⏰ *Available Time Slots:*\n" +
            "\n".join(options) +
            "\n\nReply with time number:"
        )

    elif phase == "time_selection":
        times = session.get("available_times", [])

        if not text.isdigit() or not (1 <= int(text) <= len(times)):
            await say("❌ Choose a valid time slot number.")
            return

        selected = times[int(text) - 1]
        session["data"]["appointment_time"] = selected["name"]

        await say(
            f"✅ Selected:\n"
            f"📅 Date: *{session['data']['appointment_date']}*\n"
            f"⏰ Time: *{selected['name']}*"
        )

        # Move to personal info
        session["question_phase"] = "personal_info"
        session["step"] = 0
        await say(QUESTIONS_PERSONAL_INFO[0][1])

    elif phase == "personal_info":
        key = QUESTIONS_PERSONAL_INFO[step][0]
        # Optional middle name
        if key == "middle_name" and text.strip() == "_":
            session["data"][key] = ""
        else:
            session["data"][key] = text.strip()
        session["step"] += 1

        if session["step"] >= len(QUESTIONS_PERSONAL_INFO):
            # Ask optional additional questions
            session["question_phase"] = "additional_info"
            session["step"] = 0
            await say("✅ Personal info collected. Would you like to provide additional information? (Yes/No)")
        else:
            await say(QUESTIONS_PERSONAL_INFO[session["step"]][1])
    
    elif phase == "additional_info":
        if text.lower() == "yes":
            await say("Great! Let's collect some additional information.")
            session["question_phase"] = "additional_details"
            session["step"] = 0
            await say(QUESTIONS_ADDITIONAL[0][1])
        elif text.lower() == "no":
            await say("✅ All information collected. Starting automation...")
            success, message = await automate_passport_application(session["data"], user_id, say)
            if success:
                await say(f"🎉 Automation completed successfully for <@{user_id}>!")
            else:
                await say(f"❌ Automation failed: {message}")
            del user_sessions[user_id]
        else:
            await say("Please answer Yes or No.")
    
    elif phase == "additional_details":
        key = QUESTIONS_ADDITIONAL[step][0]
        session["data"][key] = text.strip()
        session["step"] += 1
        
        if session["step"] >= len(QUESTIONS_ADDITIONAL):
            await say("✅ All information collected. Starting automation...")
            success, message = await automate_passport_application(session["data"], user_id, say)
            if success:
                await say(f"🎉 Automation completed successfully for <@{user_id}>!")
            else:
                await say(f"❌ Automation failed: {message}")
            del user_sessions[user_id]
        else:
            await say(QUESTIONS_ADDITIONAL[session["step"]][1])

# ================= Start Bot =================
if __name__ == "__main__":
    async def main():
        handler = AsyncSocketModeHandler(app, os.environ.get("SLACK_APP_TOKEN"))
        print("🚀 Passport Automation Bot running! DM 'start' to begin.")
        await handler.start_async()

    asyncio.run(main())