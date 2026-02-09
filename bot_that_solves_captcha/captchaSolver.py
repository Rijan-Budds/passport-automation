import asyncio
import os
import io
from datetime import datetime
from dotenv import load_dotenv
from slack_bolt.async_app import AsyncApp
from slack_bolt.adapter.socket_mode.aiohttp import AsyncSocketModeHandler
from transformers import VisionEncoderDecoderModel, TrOCRProcessor
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from PIL import Image
from supabase import create_client, Client

# Load environment
load_dotenv(".env.dev")

# ================= Supabase Setup =================


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


# ================= Supabase Functions =================
async def get_available_slots(district: str):
    """Fetch available slots from Supabase for a specific district"""
    try:
        # Query the slots_available table
        response = supabase.table("slots_available")\
            .select("*")\
            .eq("district", district)\
            .gte("date", datetime.now().date().isoformat())\
            .order("date", desc=False)\
            .execute()
        
        if response.data:
            return response.data
        else:
            return []
    except Exception as e:
        print(f"Error fetching slots from Supabase: {e}")
        return []


async def get_available_offices(district: str):
    """Fetch available offices for a district from Supabase"""
    try:
        response = supabase.table("slots_available")\
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


async def format_slots_for_date_selection(available_slots):
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


async def format_time_slots_for_selection(date_slots):
    """Format time slots for selection display"""
    if not date_slots:
        return None, None
    
    formatted_times = []
    time_mapping = {}
    
    for i, slot in enumerate(date_slots, 1):
        time_slot = slot.get("name", "Unknown")
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


# ================= Form Modules =================

async def demographic_information(page, user_data, user_id, say):
    """Fill the personal information form on the next page"""
    try:
        await say("📝 Starting to fill demographic information form...")
        
        # Wait for the form to be visible
        await page.wait_for_selector("form", timeout=10000)
        
        # Fill text inputs
        form_fields = {
            "firstName": user_data.get("first_name", ""),
            "lastName": user_data.get("last_name", ""),
            "dateOfBirth": user_data.get("date_of_birth_ad", ""),  # AD date
            "dateOfBirthBS": user_data.get("date_of_birth_bs", ""),  # BS date
            "birthDistrict": user_data.get("birth_district", ""),
            "fatherLastName": user_data.get("father_last_name", ""),
            "fatherFirstName": user_data.get("father_first_name", ""),
            "motherLastName": user_data.get("mother_last_name", ""),
            "motherFirstName": user_data.get("mother_first_name", "")
        }
        
        filled_fields = 0
        for field_name, value in form_fields.items():
            if not value:
                continue
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
        
        # Handle radio buttons
        # Gender radio
        gender = user_data.get("gender", "Male").lower()
        gender_mapping = {
            "male": "M",
            "female": "F", 
            "other": "X"
        }
        gender_value = gender_mapping.get(gender, "M")
        
        try:
            gender_selectors = [
                f"input[formcontrolname='gender'][value='{gender_value}']",
                f"input[name='gender'][value='{gender_value}']",
                f"input[value='{gender_value}']"
            ]
            for selector in gender_selectors:
                try:
                    gender_radio = await page.wait_for_selector(selector, timeout=1000)
                    if gender_radio:
                        await gender_radio.click()
                        await say(f"✅ Selected gender: {gender}")
                        filled_fields += 1
                        break
                except:
                    continue
        except Exception as e:
            await say(f"⚠️ Could not select gender radio: {e}")
        
        # Exact DOB radio (default to Yes/true)
        try:
            dob_selectors = [
                "input[formcontrolname='isExactDateOfBirth'][value='true']",
                "input[name='isExactDateOfBirth'][value='true']",
                "input[value='true']:has(+ label:has-text('Yes'))"
            ]
            for selector in dob_selectors:
                try:
                    dob_radio = await page.wait_for_selector(selector, timeout=1000)
                    if dob_radio:
                        await dob_radio.click()
                        await say("✅ Selected exact DOB: Yes")
                        filled_fields += 1
                        break
                except:
                    continue
        except Exception as e:
            await say(f"⚠️ Could not select exact DOB radio: {e}")
        
        # Handle dropdowns
        dropdown_fields = {
            "maritalStatus": user_data.get("marital_status", "Unmarried"),
            "education": user_data.get("education", "Bachelor"),
        }
        
        for field_name, value in dropdown_fields.items():
            if not value:
                continue
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
                        option = await page.query_selector(f"mat-option:has-text('{value}')")
                        if option:
                            await option.click()
                            await say(f"✅ Selected {field_name}: {value}")
                            filled_fields += 1
                        break
                except:
                    continue
        
        await say(f"✅ Demographic information filled successfully! ({filled_fields} fields)")
        return True
        
    except Exception as e:
        await say(f"❌ Error filling demographic information: {e}")
        return False


async def citizen_information(page, user_data, user_id, say):
    """Fill the citizenship information form"""
    try:
        await say("🆔 Starting to fill citizenship information...")
        await page.wait_for_selector("form", timeout=10000)
        
        # Field mapping
        field_mapping = {
            "nin": "nin",
            "citizen_number": "citizenNum",
            "citizen_issue_date_bs": "citizenIssueDateBS",
            "citizen_issue_place_district": "citizenIssuePlaceDistrict"
        }
        
        filled_fields = 0
        for question_key, form_field in field_mapping.items():
            value = user_data.get(question_key, "")
            if not value:
                continue
            
            selectors = [
                f"input[name='{form_field}']",
                f"input[formcontrolname='{form_field}']",
                f"#{form_field}",
                f"input[placeholder*='{form_field}']"
            ]
            
            for selector in selectors:
                try:
                    field = await page.wait_for_selector(selector, timeout=1000)
                    if field:
                        await field.fill(value)
                        await say(f"✅ Filled {form_field}")
                        filled_fields += 1
                        break
                except:
                    continue
        
        await say(f"✅ Citizenship information filled! ({filled_fields} fields)")
        return True
        
    except Exception as e:
        await say(f"❌ Error filling citizenship information: {e}")
        return False


async def contact_information(page, user_data, user_id, say):
    """Fill the contact information form"""
    try:
        await say("📱 Starting to fill contact information...")
        await page.wait_for_selector("form", timeout=10000)
        
        # Field mapping
        field_mapping = {
            "email": "email",
            "mobile": "mobile",
            "home_phone": "homePhone",
            "main_address_street": "mainAddressStreetVillage", 
            "main_ward": "mainAddressWard",
            "main_province": "mainAddressProvince",
            "main_district": "mainAddressDistrict",
            "main_municipality": "mainAddressMunicipality"
        }
        
        filled_fields = 0
        for question_key, form_field in field_mapping.items():
            value = user_data.get(question_key, "")
            if not value:
                continue
            
            selectors = [
                f"input[name='{form_field}']",
                f"input[formcontrolname='{form_field}']",
                f"#{form_field}",
                f"input[placeholder*='{form_field}']"
            ]
            
            for selector in selectors:
                try:
                    field = await page.wait_for_selector(selector, timeout=1000)
                    if field:
                        await field.fill(value)
                        await say(f"✅ Filled {form_field}")
                        filled_fields += 1
                        break
                except:
                    continue
        
        await say(f"✅ Contact information filled! ({filled_fields} fields)")
        return True
        
    except Exception as e:
        await say(f"❌ Error filling contact information: {e}")
        return False


async def emergency_info(page, user_data, user_id, say):
    """Fill the emergency contact information form"""
    try:
        await say("🆘 Starting to fill emergency information...")
        await page.wait_for_selector("form", timeout=10000)
        
        # Field mapping
        field_mapping = {
            "contact_last_name": "contactLastName",
            "contact_first_name": "contactFirstName",
            "contact_house_number": "contactHouseNum",
            "contact_street": "contactStreetVillage",
            "contact_ward": "contactWard",
            "contact_province": "contactProvince",
            "contact_district": "contactDistrict",
            "contact_municipality": "contactMunicipality",
            "contact_phone": "contactPhone"
        }
        
        filled_fields = 0
        for question_key, form_field in field_mapping.items():
            value = user_data.get(question_key, "")
            if not value:
                continue
            
            selectors = [
                f"input[name='{form_field}']",
                f"input[formcontrolname='{form_field}']",
                f"#{form_field}",
                f"input[placeholder*='{form_field}']"
            ]
            
            for selector in selectors:
                try:
                    field = await page.wait_for_selector(selector, timeout=1000)
                    if field:
                        await field.fill(value)
                        await say(f"✅ Filled {form_field}")
                        filled_fields += 1
                        break
                except:
                    continue
        
        await say(f"✅ Emergency information filled! ({filled_fields} fields)")
        return True
        
    except Exception as e:
        await say(f"❌ Error filling emergency information: {e}")
        return False


async def fill_renewal_information(page, user_data, user_id, say):
    """Fill the renewal-specific information fields"""
    try:
        await say("📋 Starting to fill renewal information...")
        
        # Renewal fields
        renewal_fields = {
            "currentTDNum": {
                "value": user_data.get("currentTDNum", ""),
                "type": "input",
                "placeholder": "current Travel Document number"
            },
            "currentTDIssueDate": {
                "value": user_data.get("currentTDIssueDate", ""),
                "type": "date",
                "placeholder": "current TD issue date"
            },
            "currenttdIssuePlaceDistrict": {
                "value": user_data.get("currenttdIssuePlaceDistrict", ""),
                "type": "dropdown",
                "placeholder": "current TD issue district"
            }
        }
        
        filled_fields = 0
        for field_name, field_info in renewal_fields.items():
            value = field_info.get("value")
            field_type = field_info.get("type")
            placeholder_hint = field_info.get("placeholder", "")
            
            if value:
                try:
                    if field_type == "input":
                        selectors = [
                            f"input[name='{field_name}']",
                            f"input[formcontrolname='{field_name}']",
                            f"input[placeholder*='{placeholder_hint}']",
                            f"#{field_name}",
                            f"input.ng-pristine[formcontrolname*='TD']"
                        ]
                        
                        for selector in selectors:
                            try:
                                field = await page.wait_for_selector(selector, timeout=2000)
                                if field:
                                    await field.fill(value)
                                    await say(f"✅ Filled {field_name}: {value}")
                                    filled_fields += 1
                                    break
                            except:
                                continue
                    
                    elif field_type == "date":
                        date_selectors = [
                            f"input[name='{field_name}']",
                            f"input[formcontrolname='{field_name}']",
                            f"input.dateInput[formcontrolname*='Date']",
                            f"input[readonly][formcontrolname*='Date']"
                        ]
                        
                        for selector in date_selectors:
                            try:
                                date_field = await page.wait_for_selector(selector, timeout=2000)
                                if date_field:
                                    await date_field.click()
                                    await page.wait_for_timeout(1000)
                                    
                                    await page.evaluate(f'''
                                        (selector, value) => {{
                                            const element = document.querySelector(selector);
                                            if (element) {{
                                                element.value = value;
                                                element.dispatchEvent(new Event('input', {{ bubbles: true }}));
                                                element.dispatchEvent(new Event('change', {{ bubbles: true }}));
                                            }}
                                        }}
                                    ''', selector, value)
                                    
                                    await page.keyboard.press("Tab")
                                    await say(f"✅ Set {field_name}: {value}")
                                    filled_fields += 1
                                    break
                            except:
                                continue
                    
                    elif field_type == "dropdown":
                        dropdown_selectors = [
                            f"mat-select[formcontrolname='{field_name}']",
                            f"mat-select[name='{field_name}']",
                            f"mat-select[formcontrolname*='District']",
                            f"mat-select.ng-pristine[formcontrolname*='Place']"
                        ]
                        
                        for selector in dropdown_selectors:
                            try:
                                dropdown = await page.wait_for_selector(selector, timeout=2000)
                                if dropdown:
                                    await dropdown.click()
                                    await page.wait_for_selector("mat-option", timeout=3000)
                                    
                                    option_selectors = [
                                        f"mat-option:has-text('{value}')",
                                        f"mat-option span:has-text('{value}')",
                                        f"mat-option:contains('{value}')"
                                    ]
                                    
                                    option_found = False
                                    for opt_selector in option_selectors:
                                        try:
                                            option = await page.wait_for_selector(opt_selector, timeout=1500)
                                            if option:
                                                await option.click()
                                                await say(f"✅ Selected {field_name}: {value}")
                                                filled_fields += 1
                                                option_found = True
                                                break
                                        except:
                                            continue
                                    
                                    if not option_found:
                                        await page.keyboard.type(value)
                                        await page.wait_for_timeout(1000)
                                        await page.keyboard.press("Enter")
                                        await say(f"✅ Typed and selected {field_name}: {value}")
                                        filled_fields += 1
                                    
                                    break
                            except:
                                continue
                
                except Exception as e:
                    await say(f"⚠️ Could not fill {field_name}: {str(e)}")
        
        # Also handle old passport number if present
        old_passport = user_data.get("old_passport_number")
        if old_passport:
            try:
                old_passport_selectors = [
                    "input[name='oldPassportNumber']",
                    "input[formcontrolname='oldPassportNumber']",
                    "input[placeholder*='Old Passport']",
                    "input[placeholder*='Previous Passport']"
                ]
                
                for selector in old_passport_selectors:
                    try:
                        field = await page.wait_for_selector(selector, timeout=1500)
                        if field:
                            await field.fill(old_passport)
                            await say(f"✅ Filled old passport number: {old_passport}")
                            filled_fields += 1
                            break
                    except:
                        continue
            except Exception as e:
                await say(f"⚠️ Could not fill old passport number: {e}")
        
        await say(f"✅ Renewal information filled successfully! ({filled_fields} fields)")
        return True
        
    except Exception as e:
        await say(f"❌ Error filling renewal information: {e}")
        return False


async def handle_next_page(page, user_data, user_id, say):
    """Handle the form on the next page after captcha"""
    try:
        # Wait for the next page to load
        await page.wait_for_timeout(3000)
        
        # Check if we're on the personal information page
        current_url = page.url
        await say(f"🔗 Now on page: {current_url}")
        
        # Check if this is a renewal application
        is_renewal = user_data.get("application_type") == "renewal"
        
        if is_renewal:
            await say("🔄 This is a renewal application. Looking for renewal-specific fields...")
            
            renewal_field_indicators = [
                "input[formcontrolname='currentTDNum']",
                "input[formcontrolname='currentTDIssueDate']",
                "mat-select[formcontrolname='currenttdIssuePlaceDistrict']",
                "text*='Travel Document'",
                "text*='Previous Passport'"
            ]
            
            has_renewal_fields = False
            for indicator in renewal_field_indicators:
                try:
                    await page.wait_for_selector(indicator, timeout=2000)
                    has_renewal_fields = True
                    break
                except:
                    continue
            
            if has_renewal_fields:
                await say("✅ Found renewal-specific fields. Filling them first...")
                renewal_success = await fill_renewal_information(page, user_data, user_id, say)
                if not renewal_success:
                    await say("⚠️ Could not fill all renewal information, but continuing...")
            else:
                await say("ℹ️ No renewal-specific fields found on this page.")
        
        # FILL DEMOGRAPHIC INFORMATION
        await say("👤 Starting to fill demographic information...")
        demographic_success = await demographic_information(page, user_data, user_id, say)
        if not demographic_success:
            return False
        
        # Navigate to next section (Citizen Info)
        next_btn_selectors = [
            "button:has-text('Next')",
            "a.btn-primary:has-text('Next')",
            "button[type='submit']:has-text('Next')",
            "button:has-text('Continue')"
        ]
        
        next_btn = None
        for selector in next_btn_selectors:
            try:
                next_btn = await page.wait_for_selector(selector, timeout=3000)
                if next_btn:
                    break
            except:
                continue
        
        if next_btn:
            async with page.expect_navigation(timeout=15000) as navigation_info:
                await next_btn.click()
            await navigation_info.value
            await say("✅ Moved to citizenship information page!")
            
            # FILL CITIZEN INFORMATION
            await say("📄 Filling citizenship information...")
            citizen_success = await citizen_information(page, user_data, user_id, say)
            if not citizen_success:
                return False
            
            # Navigate to next section (Contact Info)
            next_btn = None
            for selector in next_btn_selectors:
                try:
                    next_btn = await page.wait_for_selector(selector, timeout=3000)
                    if next_btn:
                        break
                except:
                    continue
            
            if next_btn:
                async with page.expect_navigation(timeout=15000) as navigation_info:
                    await next_btn.click()
                await navigation_info.value
                await say("✅ Moved to contact information page!")
                
                # FILL CONTACT INFORMATION
                await say("📱 Filling contact information...")
                contact_success = await contact_information(page, user_data, user_id, say)
                if not contact_success:
                    return False
                
                # Navigate to next section (Emergency Info)
                next_btn = None
                for selector in next_btn_selectors:
                    try:
                        next_btn = await page.wait_for_selector(selector, timeout=3000)
                        if next_btn:
                            break
                    except:
                        continue
                
                if next_btn:
                    async with page.expect_navigation(timeout=15000) as navigation_info:
                        await next_btn.click()
                    await navigation_info.value
                    await say("✅ Moved to emergency information page!")
                    
                    # FILL EMERGENCY INFORMATION
                    await say("🆘 Filling emergency information...")
                    emergency_success = await emergency_info(page, user_data, user_id, say)
                    if not emergency_success:
                        return False
                    
                    await say("🎉 All forms filled successfully! Ready for final submission.")
                    return True
        
        return True
        
    except Exception as e:
        await say(f"❌ Error handling next page: {e}")
        return False


async def handle_captcha_failure(page, say, attempt):
    """Handle the captcha failure by clicking the Close button and reloading captcha"""
    try:
        await say(f"🔄 Handling captcha failure for attempt {attempt}...")
        
        # Look for the Close button
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
            "img.captcha-img"
        ]
        
        reload_btn = None
        for selector in reload_button_selectors:
            try:
                reload_btn = await page.wait_for_selector(selector, timeout=3000)
                if reload_btn:
                    await reload_btn.click()
                    await say("🔄 Captcha reloaded.")
                    await page.wait_for_timeout(2002)
                    break
            except:
                continue
        
        if not reload_btn:
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
            await page.wait_for_timeout(3000)

            # DETERMINE APPLICATION TYPE
            if user_data.get("application_type") == "renewal":
                await say("🔄 Starting passport renewal process...")
                await page.wait_for_selector("text=Passport Renewal", timeout=10000)
                await page.click("text=Passport Renewal")
            else:
                await say("🆕 Starting new passport application (First Issuance)...")
                await page.wait_for_selector("text=First Issuance", timeout=10000)
                await page.click("text=First Issuance")

            # PASSPORT TYPE
            await page.wait_for_selector("label.main-doc-types", timeout=10000)
            passport_type = user_data.get('passport_type', 'Regular')
            await page.click(f"label.main-doc-types:has-text('{passport_type}')")

            # PROCEED
            await page.wait_for_selector("text=Proceed", timeout=10000)
            await page.click("text=Proceed")

            # CONSENT POPUP
            try:
                await page.wait_for_selector("mat-dialog-container", timeout=5000)
                await page.click("mat-dialog-container >> text=I agree स्वीकृत छ")
            except:
                pass

            # WAIT FOR APPOINTMENT PAGE
            await page.wait_for_url("**/appointment", timeout=15000)
            await page.wait_for_timeout(2000)

            # SELECT COUNTRY, PROVINCE, DISTRICT, OFFICE
            selects = await page.query_selector_all("mat-select")
            await say(f"Found {len(selects)} dropdowns on the page")
            
            # Country
            if len(selects) > 0:
                await selects[0].click()
                await page.wait_for_selector("mat-option", timeout=5000)
                nepal_selectors = [
                    "mat-option:has-text('Nepal')",
                    "mat-option span:has-text('Nepal')",
                    "mat-option .mat-option-text:has-text('Nepal')"
                ]
                
                nepal_selected = False
                for selector in nepal_selectors:
                    try:
                        nepal_option = await page.wait_for_selector(selector, timeout=2000)
                        if nepal_option:
                            await nepal_option.click()
                            await say("✅ Selected country: Nepal")
                            nepal_selected = True
                            break
                    except:
                        continue
                
                if not nepal_selected:
                    await say("⚠️ Could not select Nepal, trying keyboard navigation...")
                    await page.keyboard.press("ArrowDown")
                    await page.wait_for_timeout(500)
                    await page.keyboard.press("Enter")

            # Province
            await page.wait_for_timeout(2000)
            if len(selects) > 1:
                province = user_data.get('province', '')
                await selects[1].click()
                await page.wait_for_selector("mat-option", timeout=5000)
                
                province_selected = False
                province_selectors = [
                    f"mat-option:has-text('{province}')",
                    f"mat-option span:has-text('{province}')",
                    f"mat-option .mat-option-text:has-text('{province}')"
                ]
                
                for selector in province_selectors:
                    try:
                        province_option = await page.wait_for_selector(selector, timeout=2000)
                        if province_option:
                            await province_option.click()
                            await say(f"✅ Selected province: {province}")
                            province_selected = True
                            break
                    except:
                        continue
                
                if not province_selected:
                    await say(f"⚠️ Could not select province {province}, trying alternative method...")
                    await page.keyboard.type(province)
                    await page.wait_for_timeout(1000)
                    await page.keyboard.press("Enter")

            # District
            await page.wait_for_timeout(2000)
            if len(selects) > 2:
                district = user_data.get('district', '')
                await selects[2].click()
                await page.wait_for_selector("mat-option", timeout=5000)
                
                district_selected = False
                district_selectors = [
                    f"mat-option:has-text('{district}')",
                    f"mat-option span:has-text('{district}')",
                    f"mat-option .mat-option-text:has-text('{district}')",
                    f"mat-option:contains('{district}')"
                ]
                
                for selector in district_selectors:
                    try:
                        district_option = await page.wait_for_selector(selector, timeout=2000)
                        if district_option:
                            await district_option.click()
                            await say(f"✅ Selected district: {district}")
                            district_selected = True
                            break
                    except:
                        continue
                
                if not district_selected:
                    await say(f"⚠️ Could not select district {district}, trying search...")
                    search_input = await page.query_selector("input[placeholder*='Search'], input[type='search']")
                    if search_input:
                        await search_input.fill(district)
                        await page.wait_for_timeout(1000)
                        first_option = await page.query_selector("mat-option")
                        if first_option:
                            await first_option.click()
                    else:
                        await page.keyboard.type(district)
                        await page.wait_for_timeout(1000)
                        await page.keyboard.press("Enter")

            # Office
            await page.wait_for_timeout(2000)
            if len(selects) > 3:
                office = user_data.get('office', '')
                await selects[3].click()
                await page.wait_for_selector("mat-option", timeout=5000)
                
                office_selected = False
                office_selectors = [
                    f"mat-option:has-text('{office}')",
                    f"mat-option span:has-text('{office}')",
                    f"mat-option .mat-option-text:has-text('{office}')"
                ]
                
                for selector in office_selectors:
                    try:
                        office_option = await page.wait_for_selector(selector, timeout=2000)
                        if office_option:
                            await office_option.click()
                            await say(f"✅ Selected office: {office}")
                            office_selected = True
                            break
                    except:
                        continue
                
                if not office_selected:
                    await say(f"⚠️ Could not select office {office}, trying alternative...")
                    await page.keyboard.type(office[:3])
                    await page.wait_for_timeout(1000)
                    await page.keyboard.press("Enter")

            # For Renewal
            if user_data.get("application_type") == "renewal":
                try:
                    await page.wait_for_timeout(2000)
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
                selected_date = user_data.get("selected_date")
                if selected_date:
                    try:
                        date_obj = datetime.strptime(selected_date, "%Y-%m-%d")
                        formatted_date = date_obj.strftime("%d/%m/%Y")
                    except:
                        formatted_date = selected_date
                    
                    date_input_selectors = [
                        "input[placeholder*='Date' i]",
                        "input[type='text'][formcontrolname*='date' i]",
                        "input.mat-input-element[formcontrolname*='date']",
                        "input[readonly][formcontrolname*='date']"
                    ]
                    
                    date_input = None
                    for selector in date_input_selectors:
                        try:
                            date_input = await page.wait_for_selector(selector, timeout=5000)
                            if date_input:
                                break
                        except:
                            continue
                    
                    if date_input:
                        await date_input.fill("")
                        await date_input.fill(formatted_date)
                        await page.wait_for_timeout(1000)
                        
                        await page.evaluate('''
                            (element) => {
                                element.dispatchEvent(new Event('input', { bubbles: true }));
                                element.dispatchEvent(new Event('change', { bubbles: true }));
                                element.dispatchEvent(new Event('blur', { bubbles: true }));
                            }
                        ''', date_input)
                        
                        await say(f"✅ Selected date: {selected_date}")
                    else:
                        await say("⚠️ Date input not found, trying auto-selection...")
                        try:
                            date_input = await page.wait_for_selector(
                                "input[placeholder*='Date' i], input[type='text'][formcontrolname*='date' i]",
                                timeout=3000
                            )
                            await date_input.click()
                            await page.wait_for_selector(".ui-datepicker-calendar", timeout=3000)
                            first_date = await page.wait_for_selector(
                                "td:not(.ui-datepicker-other-month):not(.ui-state-disabled) a",
                                timeout=3000
                            )
                            await first_date.click()
                            await say("✅ Date auto-selected.")
                        except:
                            await say("⚠️ Could not auto-select date")
                else:
                    try:
                        date_input = await page.wait_for_selector(
                            "input[placeholder*='Date' i], input[type='text'][formcontrolname*='date' i]",
                            timeout=5000
                        )
                        await date_input.click()
                        await page.wait_for_selector(".ui-datepicker-calendar", timeout=3000)
                        first_date = await page.wait_for_selector(
                            "td:not(.ui-datepicker-other-month):not(.ui-state-disabled) a",
                            timeout=3000
                        )
                        await first_date.click()
                        await say("✅ Date auto-selected.")
                    except Exception as e:
                        await say(f"⚠️ Date auto-selection error: {e}")
            except Exception as e:
                await say(f"⚠️ Date selection error: {e}")

            # TIME SLOT
            try:
                selected_time = user_data.get("selected_time")
                if selected_time:
                    await page.wait_for_selector(".ui-datepicker-calendar-container mat-chip-list", timeout=5000)
                    
                    time_chip_selectors = [
                        f"mat-chip:has-text('{selected_time}')",
                        f"mat-chip .mat-chip-ripple:has-text('{selected_time}')",
                        f"mat-chip:contains('{selected_time}')"
                    ]
                    
                    time_selected = False
                    for selector in time_chip_selectors:
                        try:
                            time_chip = await page.wait_for_selector(selector, timeout=2000)
                            if time_chip:
                                await time_chip.click()
                                await say(f"✅ Selected time slot: {selected_time}")
                                time_selected = True
                                break
                        except:
                            continue
                    
                    if not time_selected:
                        slots = await page.query_selector_all("mat-chip.mat-chip:not(.mat-chip-disabled)")
                        if slots:
                            await slots[0].click()
                            await say("✅ Time slot auto-selected (fallback).")
                        else:
                            await say("⚠️ No time slots available.")
                else:
                    await page.wait_for_selector(".ui-datepicker-calendar-container mat-chip-list", timeout=5000)
                    slots = await page.query_selector_all("mat-chip.mat-chip:not(.mat-chip-disabled)")
                    if slots:
                        await slots[0].click()
                        await say("✅ Time slot auto-selected.")
                    else:
                        await say("⚠️ No time slots available.")
            except Exception as e:
                await say(f"⚠️ Time slot selection error: {e}")

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

                    # Click Next button
                    next_btn = await page.wait_for_selector("a.btn.btn-primary", timeout=5000)
                    if next_btn:
                        async with page.expect_navigation(timeout=10000) as navigation_info:
                            await next_btn.click()
                        
                        await navigation_info.value
                        await say(f"✅ Captcha solved successfully on attempt {attempt}. Moving to next page...")
                        captcha_success = True
                        
                        await page.wait_for_timeout(3000)
                        
                        # Continue with next page automation
                        next_page_success = await handle_next_page(page, user_data, user_id, say)
                        
                        if next_page_success:
                            await say(f"🎉 Full automation completed successfully for <@{user_id}>!")
                            return True, "Full passport application automation completed successfully!"
                        else:
                            return False, "Failed to complete forms on next pages"
                        
                        break

                except PlaywrightTimeoutError:
                    await say(f"❌ Captcha attempt {attempt} failed (timeout). Handling failure...")
                    
                    failure_handled = await handle_captcha_failure(page, say, attempt)
                    
                    if not failure_handled:
                        await say("⚠️ Could not properly handle captcha failure, trying to continue...")
                        await page.wait_for_timeout(3000)
                    
                except Exception as e:
                    await say(f"❌ Captcha attempt {attempt} error: {e}")
                    
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
                    await asyncio.sleep(300)
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
# Update questions to include all new fields
QUESTIONS_PRE_CAPTCHA = [
    ("application_type", "What type of application?\n1. First Issuance (New Passport)\n2. Passport Renewal\nPlease type '1' or '2':"),
    ("passport_type", "What type of passport do you want? (Regular/Diplomatic/Official)"),
    ("province", "Which province? (e.g., Bagmati, Gandaki, Koshi)"),
    ("district", "Which district?"),
    ("office", "Which office?"),
]

# Additional questions for renewal
QUESTIONS_RENEWAL = [
    ("old_passport_number", "What is your old passport number?"),
    ("currentTDNum", "What is your current Travel Document (TD) number?"),
    ("currentTDIssueDate", "When was your current TD issued? (YYYY-MM-DD)"),
    ("currenttdIssuePlaceDistrict", "Which district was your current TD issued in?"),
]

# Updated questions for demographic information
QUESTIONS_DEMOGRAPHIC = [
    ("first_name", "What is your first name?"),
    ("last_name", "What is your last name?"),
    ("gender", "What is your gender? (Male/Female/Other)"),
    ("date_of_birth_ad", "What is your date of birth in AD? (YYYY-MM-DD)"),
    ("date_of_birth_bs", "What is your date of birth in Nepali (BS)? (YYYY-MM-DD format)"),
    ("birth_district", "What is your birth district?"),
    ("father_first_name", "What is your father's first name?"),
    ("father_last_name", "What is your father's last name?"),
    ("mother_first_name", "What is your mother's first name?"),
    ("mother_last_name", "What is your mother's last name?"),
    ("marital_status", "What is your marital status? (Single/Married/Divorced/Widowed)"),
    ("education", "What is your education level? (e.g., Bachelor, Master, High School)"),
]

# Questions for citizenship information
QUESTIONS_CITIZENSHIP = [
    ("nin", "What is your National Identity Number (NIN)?"),
    ("citizen_number", "What is your citizenship certificate number?"),
    ("citizen_issue_date_bs", "When was your citizenship issued (BS)? (YYYY-MM-DD)"),
    ("citizen_issue_place_district", "Which district was your citizenship issued in?"),
]

# Questions for contact information  
QUESTIONS_CONTACT = [
    ("email", "What is your email address?"),
    ("mobile", "What is your mobile number?"),
    ("home_phone", "What is your home phone number? (optional)"),
    ("main_address_street", "What is your main address (street/village)?"),
    ("main_ward", "What is your main address ward number?"),
    ("main_province", "What is your main address province?"),
    ("main_district", "What is your main address district?"),
    ("main_municipality", "What is your main address municipality?"),
]

# Questions for emergency contact
QUESTIONS_EMERGENCY = [
    ("contact_first_name", "Emergency contact: First name?"),
    ("contact_last_name", "Emergency contact: Last name?"),
    ("contact_house_number", "Emergency contact: House number?"),
    ("contact_street", "Emergency contact: Street/Village?"),
    ("contact_ward", "Emergency contact: Ward number?"),
    ("contact_province", "Emergency contact: Province?"),
    ("contact_district", "Emergency contact: District?"),
    ("contact_municipality", "Emergency contact: Municipality?"),
    ("contact_phone", "Emergency contact: Phone number?"),
]

# Combine all question phases in order
QUESTION_PHASES = [
    ("pre_captcha", QUESTIONS_PRE_CAPTCHA),
    ("renewal_info", QUESTIONS_RENEWAL),
    ("demographic_info", QUESTIONS_DEMOGRAPHIC),
    ("citizenship_info", QUESTIONS_CITIZENSHIP),
    ("contact_info", QUESTIONS_CONTACT),
    ("emergency_info", QUESTIONS_EMERGENCY),
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
            "phase_index": 0,
            "step": 0,
            "question_phase": "pre_captcha",
            "additional_renewal_questions": False
        }
        await say("👋 Welcome to the Passport Automation Bot! Let's get started.")
        await say(QUESTIONS_PRE_CAPTCHA[0][1])
        return

    session = user_sessions[user_id]
    phase = session["question_phase"]
    step = session["step"]

    # Handle date selection phase
    if phase == "date_selection":
        # Handle date selection
        if text.isdigit() and text in session.get("date_mapping", {}):
            selected_date_info = session["date_mapping"][text]
            selected_date = selected_date_info["date"]
            formatted_date = selected_date_info["formatted_date"]
            date_slots = selected_date_info["slots"]
            
            session["data"]["selected_date"] = selected_date
            session["selected_date_slots"] = date_slots
            
            # Format time slots for selection
            formatted_times, time_mapping = await format_time_slots_for_selection(date_slots)
            
            if formatted_times:
                session["time_mapping"] = time_mapping
                session["question_phase"] = "time_selection"
                
                message = f"""
✅ *Date selected: {formatted_date}*

⏰ *Available time slots:*

{formatted_times}

Please type the number of the time slot you want to select (e.g., '1'):
                """
                await say(message)
            else:
                await say(f"❌ No time slots available for {formatted_date}.\n\nPlease select another date:")
        else:
            # Show dates again
            formatted_dates, _ = await format_slots_for_date_selection(session.get("available_slots", []))
            await say(f"""
❌ Invalid selection. Please choose a valid date number:

{formatted_dates}

Type the number (e.g., '1'):
            """)
        return

    # Handle time selection phase
    elif phase == "time_selection":
        if text.isdigit() and text in session.get("time_mapping", {}):
            selected_time_info = session["time_mapping"][text]
            selected_time = selected_time_info["time_slot"]
            
            session["data"]["selected_time"] = selected_time
            
            # Now ask for office selection
            district = session["data"]["district"]
            available_offices = await get_available_offices(district)
            
            if available_offices:
                session["available_offices"] = available_offices
                session["question_phase"] = "office_selection"
                
                offices_text = "\n".join(f"• {office}" for office in available_offices)
                message = f"""
✅ *Time slot selected: {selected_time}*

🏢 *Available offices in {district}:*

{offices_text}

Please type the office name you want to select:
                """
                await say(message)
            else:
                await say(f"✅ Time slot selected: *{selected_time}*")
                # Move to next question phase
                session = await move_to_next_question_phase(session, say)
        else:
            formatted_times, _ = await format_time_slots_for_selection(session.get("selected_date_slots", []))
            await say(f"""
❌ Invalid selection. Please choose a valid time slot number:

{formatted_times}

Type the number (e.g., '1'):
            """)
        return

    # Handle office selection phase
    elif phase == "office_selection":
        district = session["data"]["district"]
        available_offices = session.get("available_offices", [])
        
        selected_office = None
        for office in available_offices:
            if text.lower() in office.lower() or office.lower() in text.lower():
                selected_office = office
                break
        
        if selected_office:
            session["data"]["office"] = selected_office
            await say(f"✅ Office selected: *{selected_office}*")
            # Move to next question phase
            session = await move_to_next_question_phase(session, say)
        else:
            offices_text = "\n".join(f"• {office}" for office in available_offices)
            await say(f"""
❌ Office not found. Available offices in {district}:
{offices_text}

Please type the office name exactly as shown:
            """)
        return

    # Handle all other question phases
    current_phase_data = None
    for phase_name, questions in QUESTION_PHASES:
        if phase == phase_name:
            current_phase_data = questions
            break
    
    if current_phase_data and step < len(current_phase_data):
        key = current_phase_data[step][0]
        
        # Special handling for application_type
        if key == "application_type":
            if text == "1":
                session["data"]["application_type"] = "first_issuance"
                session["step"] += 1
            elif text == "2":
                session["data"]["application_type"] = "renewal"
                session["step"] += 1
                session["additional_renewal_questions"] = True
            else:
                await say("Please type '1' for First Issuance or '2' for Passport Renewal:")
                return
        
        # Special handling for district (check available slots)
        elif key == "district":
            district = text.title()
            await say(f"🔍 Checking available slots for {district}...")
            available_slots = await get_available_slots(district)
            
            if available_slots:
                session["data"]["district"] = district
                session["available_slots"] = available_slots
                session["step"] += 1
                
                formatted_dates, date_mapping = await format_slots_for_date_selection(available_slots)
                
                if formatted_dates:
                    session["date_mapping"] = date_mapping
                    session["question_phase"] = "date_selection"
                    
                    message = f"""
📅 *Available dates for {district}:*

{formatted_dates}

Please type the number of the date you want to select (e.g., '1'):
                    """
                    await say(message)
                else:
                    await say(f"❌ No available dates found for {district}.\n\nPlease try another district:")
            else:
                await say(f"❌ No available slots found for {district}.\n\nPlease try another district:")
            return
        
        # Normal field handling
        else:
            session["data"][key] = text
            session["step"] += 1
        
        # Check if current phase is complete
        if session["step"] >= len(current_phase_data):
            # Move to next phase
            session = await move_to_next_question_phase(session, say)
        else:
            # Ask next question in current phase
            next_question = current_phase_data[session["step"]][1]
            await say(next_question)
    
    # Update session
    user_sessions[user_id] = session


async def move_to_next_question_phase(session, say):
    """Move to the next question phase"""
    current_phase_index = -1
    for i, (phase_name, _) in enumerate(QUESTION_PHASES):
        if session["question_phase"] == phase_name:
            current_phase_index = i
            break
    
    # Check if we should skip renewal questions
    if session["question_phase"] == "pre_captcha":
        if not session.get("additional_renewal_questions"):
            # Skip renewal questions
            current_phase_index += 1
    
    # Move to next phase
    next_phase_index = current_phase_index + 1
    
    if next_phase_index < len(QUESTION_PHASES):
        next_phase_name, next_phase_questions = QUESTION_PHASES[next_phase_index]
        session["question_phase"] = next_phase_name
        session["step"] = 0
        
        # Announce new phase
        phase_titles = {
            "demographic_info": "📋 *Personal Information:*",
            "citizenship_info": "🆔 *Citizenship Information:*",
            "contact_info": "📱 *Contact Information:*",
            "emergency_info": "🆘 *Emergency Contact Information:*"
        }
        
        if next_phase_name in phase_titles:
            await say(phase_titles[next_phase_name])
        
        # Ask first question of new phase
        await say(next_phase_questions[0][1])
    else:
        # All questions completed, start automation
        await start_automation(session, say)
    
    return session


async def start_automation(session, say):
    """Start the automation process after all questions are answered"""
    user_id = None
    for uid, sess in user_sessions.items():
        if sess == session:
            user_id = uid
            break
    
    if not user_id:
        await say("❌ Error: Could not find user session")
        return
    
    # Create summary
    app_type = session["data"].get("application_type", "first_issuance")
    district = session["data"].get("district", "Unknown")
    office = session["data"].get("office", "Unknown")
    selected_date = session["data"].get("selected_date", "Auto-select")
    selected_time = session["data"].get("selected_time", "Auto-select")
    
    summary = f"""
📋 *Application Summary:*
• Type: {'Renewal' if app_type == 'renewal' else 'First Issuance'}
• District: {district}
• Office: {office}
• Date: {selected_date}
• Time: {selected_time}
• Name: {session['data'].get('first_name', '')} {session['data'].get('last_name', '')}
    """
    
    await say(summary)
    
    if app_type == "renewal":
        await say("🔄 *Starting automated passport RENEWAL process...*\nI'll book your selected appointment. This may take a few minutes.")
    else:
        await say("🔄 *Starting automated NEW PASSPORT application...*\nI'll book your selected appointment. This may take a few minutes.")
    
    success, message = await automate_passport_application(session["data"], user_id, say)
    if success:
        await say(f"🎉 *Automation completed successfully for <@{user_id}>!*")
    else:
        await say(f"❌ *Automation failed:* {message}")
    
    # Clean up session
    if user_id in user_sessions:
        del user_sessions[user_id]


# ================= Start the Bot =================
if __name__ == "__main__":
    async def main():
        handler = AsyncSocketModeHandler(app, os.environ.get("SLACK_APP_TOKEN"))
        print("🚀 Passport Automation Bot running! DM 'start' to begin.")
        await handler.start_async()

    asyncio.run(main())
