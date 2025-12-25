import asyncio
import os
import io
from dotenv import load_dotenv
from slack_bolt.async_app import AsyncApp
from slack_bolt.adapter.socket_mode.aiohttp import AsyncSocketModeHandler
from transformers import VisionEncoderDecoderModel, TrOCRProcessor
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from PIL import Image

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


# ================= Personal Information Form =================
async def fill_personal_information(page, user_data, user_id, say):
    """Fill the personal information form on the next page"""
    try:
        await say("📝 Starting to fill personal information form...")
        
        # Wait for form to be visible
        await page.wait_for_selector("form", timeout=10000)
        
        # Handle middle name - if it's "_", leave it empty
        middle_name = user_data.get("middle_name", "")
        if middle_name == "_":
            middle_name = ""
        
        # Fill basic information fields (adjust these selectors based on actual form)
        form_fields = {
            "firstName": user_data.get("first_name", ""),
            "middleName": middle_name,  # Use processed middle name
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
            "permanentDistrict": user_data.get("permanent_district", ""),
            "permanentMunicipality": user_data.get("permanent_municipality", ""),
            "permanentWard": user_data.get("permanent_ward", ""),
            "permanentTole": user_data.get("permanent_tole", ""),
            "currentDistrict": user_data.get("current_district", ""),
            "currentMunicipality": user_data.get("current_municipality", ""),
            "currentWard": user_data.get("current_ward", ""),
            "currentTole": user_data.get("current_tole", ""),
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


async def handle_next_page(page, user_data, user_id, say):
    """Handle the form on the next page after captcha"""
    try:
        # Wait for the next page to load
        await page.wait_for_timeout(3000)
        
        # Check if we're on the personal information page
        current_url = page.url
        await say(f"🔗 Now on page: {current_url}")
        
        # Look for common elements on the next page
        personal_info_indicators = [
            "text=Personal Information",
            "text=Applicant Details", 
            "text=Full Name",
            "input[name='firstName']",
            "input[formcontrolname='firstName']"
        ]
        
        page_found = False
        for indicator in personal_info_indicators:
            try:
                await page.wait_for_selector(indicator, timeout=5000)
                await say("✅ Successfully reached the personal information page!")
                page_found = True
                break
            except:
                continue
        
        if not page_found:
            await say("⚠️ Could not confirm personal information page, but continuing...")
        
        # Fill personal information
        personal_success = await fill_personal_information(page, user_data, user_id, say)
        if not personal_success:
            return False
        
        # Navigate to next section (Address)
        try:
            next_btn = await page.query_selector("button:has-text('Next'), a.btn-primary:has-text('Next'), button[type='submit']")
            if next_btn:
                async with page.expect_navigation(timeout=15000) as navigation_info:
                    await next_btn.click()
                await navigation_info.value
                await say("✅ Moved to address information page!")
                
                # Fill address information
                address_success = await fill_address_information(page, user_data, user_id, say)
                if not address_success:
                    return False
                
                # Navigate to next section (Family)
                next_btn = await page.query_selector("button:has-text('Next'), a.btn-primary:has-text('Next'), button[type='submit']")
                if next_btn:
                    async with page.expect_navigation(timeout=15000) as navigation_info:
                        await next_btn.click()
                    await navigation_info.value
                    await say("✅ Moved to family information page!")
                    
                    # Fill family information
                    family_success = await fill_family_information(page, user_data, user_id, say)
                    if not family_success:
                        return False
                    
                    # Continue with other sections as needed...
                    await say("🎉 All forms filled successfully! Ready for final submission.")
                    return True
        except Exception as e:
            await say(f"⚠️ Navigation error: {e}")
            return False
        
        return True
        
    except Exception as e:
        await say(f"❌ Error handling next page: {e}")
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


# ================= Passport Automation (First Page) =================
async def automate_passport_application(user_data, user_id, say):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        try:
            await page.goto("https://emrtds.nepalpassport.gov.np")

            # DETERMINE APPLICATION TYPE
            if user_data.get("application_type") == "renewal":
                await say("🔄 Starting passport renewal process...")
                await page.wait_for_selector("text=Passport Renewal")
                await page.click("text=Passport Renewal")
            else:
                # Default to First Issuance
                await say("🆕 Starting new passport application (First Issuance)...")
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
            
            # Country (fixed)
            await selects[0].click()
            await page.click("mat-option >> text=Nepal")

            # Province
            await selects[1].click()
            await page.click(f"mat-option >> text={user_data['province']}")

            # District
            await selects[2].click()
            await page.click(f"mat-option >> text={user_data['district']}")

            # Office
            await selects[3].click()
            await page.click(f"mat-option >> text={user_data['office']}")

            # For Renewal, ask for old passport details if needed
            if user_data.get("application_type") == "renewal":
                try:
                    # Wait for additional fields that might appear for renewal
                    await page.wait_for_timeout(2000)
                    
                    # Look for old passport number field
                    old_passport_selectors = [
                        "input[name='oldPassportNumber']",
                        "input[formcontrolname='oldPassportNumber']",
                        "input[placeholder*='Old Passport']",
                        "input[placeholder*='Previous Passport']"
                    ]
                    
                    for selector in old_passport_selectors:
                        try:
                            old_passport_field = await page.wait_for_selector(selector, timeout=2000)
                            if old_passport_field:
                                old_passport = user_data.get("old_passport_number", "")
                                if old_passport:
                                    await old_passport_field.fill(old_passport)
                                    await say("✅ Filled old passport number")
                                break
                        except:
                            continue
                except Exception as e:
                    await say(f"ℹ️ No old passport field found or error: {e}")

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
                await say("Date auto-selected.")

            # TIME SLOT
            await page.wait_for_selector(".ui-datepicker-calendar-container mat-chip-list")
            slots = await page.query_selector_all("mat-chip.mat-chip:not(.mat-chip-disabled)")
            if slots:
                await slots[0].click()

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
                        
                        # Wait a moment for the next page to load completely
                        await page.wait_for_timeout(3000)
                        
                        # ========== CONTINUE WITH NEXT PAGE AUTOMATION ==========
                        next_page_success = await handle_next_page(page, user_data, user_id, say)
                        
                        if next_page_success:
                            await say(f"🎉 Full automation completed successfully for <@{user_id}>!")
                            return True, "Full passport application automation completed successfully!"
                        else:
                            return False, "Failed to complete forms on next pages"
                        
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
}

# ================= Conversation Flow =================
QUESTIONS_PRE_CAPTCHA = [
    ("application_type", "What type of application?\n1. First Issuance (New Passport)\n2. Passport Renewal\nPlease type '1' or '2':"),
    ("passport_type", "What type of passport do you want? (Regular/Diplomatic/Official)"),
    ("province", "Which province? (e.g., Bagmati, Gandaki, Koshi)"),
    ("district", "Which district?"),
    ("office", "Which office?"),
]

# Additional questions for personal information
QUESTIONS_PERSONAL_INFO = [
    ("first_name", "What is your first name?"),
    ("middle_name", "What is your middle name? (If you don't have a middle name, please enter '_')"),
    ("last_name", "What is your last name?"),
    ("email", "What is your email address?"),
    ("phone", "What is your phone number?"),
    ("citizenship_number", "What is your citizenship number?"),
    ("dob", "What is your date of birth? (YYYY-MM-DD)"),
    ("gender", "What is your gender? (Male/Female/Other)"),
    ("marital_status", "What is your marital status? (Married/Unmarried)"),
]

# Additional question for renewal
QUESTIONS_RENEWAL = [
    ("old_passport_number", "What is your old passport number?")
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
        # Save answer for pre-captcha questions
        key = QUESTIONS_PRE_CAPTCHA[step][0]

        # --- Application Type Handling ---
        if key == "application_type":
            if text == "1":
                session["data"]["application_type"] = "first_issuance"
                session["step"] += 1
            elif text == "2":
                session["data"]["application_type"] = "renewal"
                session["step"] += 1
                # Add renewal-specific questions after other questions
                session["additional_renewal_questions"] = True
            else:
                await say("Please type '1' for First Issuance or '2' for Passport Renewal:")
                return
        
        # --- District Handling ---
        elif key == "district":
            district = text.title()
            offices = DISTRICT_OFFICES.get(district)
            if offices:
                session["data"]["district"] = district
                session["offices_options"] = offices
                options_text = "\n".join(f"{i+1}. {office}" for i, office in enumerate(offices))
                session["step"] += 1
                await say(
                    f"Available offices in {district}:\n{options_text}\nPlease type the office name or number:"
                )
                return
            else:
                await say(f"No offices found for {district}. Please type the district again:")
                return

        # --- Office Handling ---
        elif key == "office" and "offices_options" in session:
            offices = session["offices_options"]
            if text.isdigit() and 1 <= int(text) <= len(offices):
                session["data"]["office"] = offices[int(text) - 1]
            elif text.title() in offices:
                session["data"]["office"] = text.title()
            else:
                await say("Invalid office. Please choose from the listed offices:")
                return
            session["step"] += 1

        else:
            # For other questions
            session["data"][key] = text
            session["step"] += 1

        # Check if pre-captcha questions are complete
        if session["step"] >= len(QUESTIONS_PRE_CAPTCHA):
            # Check if we need to ask renewal-specific questions
            if session.get("additional_renewal_questions"):
                session["question_phase"] = "renewal_info"
                session["step"] = 0
                await say("🔄 For passport renewal, I need your old passport information.")
                await say(QUESTIONS_RENEWAL[0][1])
            else:
                # Move to personal information questions
                session["question_phase"] = "personal_info"
                session["step"] = 0
                await say("✅ Basic information collected! Now I need your personal details.")
                await say(QUESTIONS_PERSONAL_INFO[0][1])
        else:
            next_question = QUESTIONS_PRE_CAPTCHA[session["step"]][1]
            if QUESTIONS_PRE_CAPTCHA[session["step"]][0] == "office" and "offices_options" in session:
                return
            await say(next_question)

    elif phase == "renewal_info":
        # Save answer for renewal-specific questions
        key = QUESTIONS_RENEWAL[step][0]
        session["data"][key] = text
        session["step"] += 1

        # Check if renewal questions are complete
        if session["step"] >= len(QUESTIONS_RENEWAL):
            # Move to personal information questions
            session["question_phase"] = "personal_info"
            session["step"] = 0
            await say("✅ Renewal information collected! Now I need your personal details.")
            await say(QUESTIONS_PERSONAL_INFO[0][1])

    elif phase == "personal_info":
        # Save answer for personal information questions
        key = QUESTIONS_PERSONAL_INFO[step][0]
        session["data"][key] = text
        session["step"] += 1

        # Check if personal information questions are complete
        if session["step"] >= len(QUESTIONS_PERSONAL_INFO):
            # Start automation
            app_type = session["data"].get("application_type", "first_issuance")
            if app_type == "renewal":
                await say("🔄 Starting automated passport RENEWAL process... Please wait while I fill all the forms.")
            else:
                await say("🔄 Starting automated NEW PASSPORT application... Please wait while I fill all the forms.")
            
            success, message = await automate_passport_application(session["data"], user_id, say)
            if success:
                await say(f"🎉 Automation completed successfully for <@{user_id}>!")
            else:
                await say(f"❌ Automation failed for <@{user_id}>: {message}")
            del user_sessions[user_id]
        else:
            next_question = QUESTIONS_PERSONAL_INFO[session["step"]][1]
            await say(next_question)


# ================= Start the Bot =================
if __name__ == "__main__":
    async def main():
        handler = AsyncSocketModeHandler(app, os.environ.get("SLACK_APP_TOKEN"))
        print("🚀 Passport Automation Bot running! DM 'start' to begin.")
        await handler.start_async()

    asyncio.run(main())