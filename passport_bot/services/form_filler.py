import asyncio
from datetime import datetime
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

# Import form modules
from forms.demographic_info import demographic_information
from forms.citizen_info import citizen_information
from forms.contact_info import contact_information
from forms.emergency_info import emergency_info
from forms.renewal_info import fill_renewal_information

# Import other services
from services.captcha_solver import CaptchaSolver
from config import selectors

class FormFiller:
    """Main form automation handler"""
    
    def __init__(self): 
        self.captcha_solver = CaptchaSolver()
    
    async def automate_passport_application(self, user_data: dict, user_id: str, say):
        """Main automation function"""
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=False,
                args=['--disable-blink-features=AutomationControlled']
            )
            page = await browser.new_page()
            
            # Add stealth to avoid detection
            await page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
            """)
            
            try:
                await page.goto("https://emrtds.nepalpassport.gov.np")
                await page.wait_for_load_state('networkidle')
                await page.wait_for_timeout(2000)
                
                # Take screenshot for debugging
                await page.screenshot(path=f"debug_{user_id}_initial.png")
                print(f"🌐 Loaded website for <@{user_id}>")

                # Application type selection
                await self.select_application_type(page, user_data, say)
                
                # Wait for passport type section
                await page.wait_for_timeout(2000)

                # Passport type - FIXED HERE
                passport_type = user_data.get('passport_type', 'Regular')
                print(f"📄 Selecting passport type: {passport_type}")
                
                # Map passport types to actual labels
                passport_mapping = {
                    'Regular': 'Ordinary 34 pages',
                    '34 pages': 'Ordinary 34 pages',
                    'Ordinary': 'Ordinary 34 pages',
                    '66 pages': 'Ordinary 66 pages',
                    'Diplomatic': 'Diplomatic',
                    'Official': 'Official'
                }
                
                actual_label = passport_mapping.get(passport_type, 'Ordinary 34 pages')
                print(f"🔍 Looking for: '{actual_label}'")
                
                # Try multiple selectors to find the passport type
                passport_selectors = [
                    f"label.main-doc-types:has-text('{actual_label}')",
                    f"label.radio-label:has-text('{actual_label}')",
                    f"label:has-text('{actual_label}')",
                    f"//label[contains(text(), '{actual_label}')]",
                    f"input[value*='ordinary'] + label"  # Fallback
                ]
                
                passport_selected = False
                for selector in passport_selectors:
                    try:
                        print(f"Trying selector: {selector}")
                        if selector.startswith('//'):
                            # XPath selector
                            element = await page.wait_for_selector(f"xpath={selector}", timeout=2000)
                        else:
                            # CSS selector
                            element = await page.wait_for_selector(selector, timeout=2000)
                        
                        if element:
                            await element.scroll_into_view_if_needed()
                            await element.click()
                            print(f"✅ Selected passport type: {actual_label}")
                            passport_selected = True
                            break
                    except Exception as e:
                        print(f"❌ Selector failed: {str(e)[:50]}...")
                        continue
                
                if not passport_selected:
                    # Try clicking the first available passport type
                    try:
                        first_type = await page.query_selector("label.main-doc-types, label.radio-label")
                        if first_type:
                            await first_type.click()
                            print("⚠️ Selected first available passport type (fallback)")
                        else:
                            await say("❌ Could not find any passport type options")
                            return False, "No passport type options found"
                    except Exception as e:
                        print(f"❌ Fallback also failed: {e}")
                        return False, f"Passport type selection failed: {e}"
                
                # Wait a moment for UI to update
                await page.wait_for_timeout(1000)
                
                # Take screenshot after selection
                await page.screenshot(path=f"debug_{user_id}_passport_selected.png")

                # Proceed button with multiple selector attempts
                print("🔘 Looking for 'Proceed' button...")
                proceed_selectors = [
                    selectors.SELECTORS["proceed_button"],
                    "button:has-text('Proceed')",
                    "button.submit-button:has-text('Proceed')",
                    "button.mat-raised-button:has-text('Proceed')",
                    "//button[contains(text(), 'Proceed')]"
                ]
                
                proceed_clicked = False
                for selector in proceed_selectors:
                    try:
                        print(f"Looking for proceed with: {selector}")
                        if selector.startswith('//'):
                            element = await page.wait_for_selector(f"xpath={selector}", timeout=2000)
                        else:
                            element = await page.wait_for_selector(selector, timeout=2000)
                        
                        if element:
                            await element.scroll_into_view_if_needed()
                            await element.click()
                            print("✅ Clicked 'Proceed' button")
                            proceed_clicked = True
                            break
                    except Exception as e:
                        print(f"Proceed selector {selector} failed: {str(e)[:50]}...")
                        continue
                
                if not proceed_clicked:
                    print("❌ Could not find 'Proceed' button")
                    # Try to find any button that might be proceed
                    all_buttons = await page.query_selector_all("button")
                    for button in all_buttons:
                        text = await button.text_content()
                        if text and 'proceed' in text.lower():
                            await button.click()
                            print("✅ Clicked proceed button (found by text content)")
                            proceed_clicked = True
                            break
                    
                    if not proceed_clicked:
                        return False, "Proceed button not found"

                # Consent popup
                try:
                    await page.wait_for_selector("mat-dialog-container", timeout=5000)
                    await page.click(selectors.SELECTORS["agree_button"])
                    print("✅ Accepted consent agreement")
                except:
                    print("ℹ️ No consent popup found or already dismissed")
                    pass

                # Wait for appointment page
                try:
                    await page.wait_for_url("**/appointment", timeout=15000)
                    await page.wait_for_load_state('networkidle')
                    await page.wait_for_timeout(2000)
                    print("✅ Navigated to appointment page")
                except Exception as e:
                    print(f"⚠️ Could not verify appointment page: {e}")
                    # Continue anyway

                # Fill location dropdowns
                await self.fill_location_dropdowns(page, user_data, say)
                
                # Fill date and time
                date_success = await self.fill_appointment_datetime(page, user_data, say)
                if not date_success:
                    return False, "Failed to select appointment date/time"

                # Handle CAPTCHA
                captcha_success = await self.handle_captcha(page, user_data, user_id, say)
                if not captcha_success:
                    return False, "Captcha could not be solved after 10 attempts."

                # Fill remaining forms
                next_page_success = await self.handle_next_page(page, user_data, user_id, say)
                if next_page_success:
                    await say(f"🎉 Full automation completed successfully for <@{user_id}>!")
                    return True, "Full passport application automation completed successfully!"
                else:
                    return False, "Failed to complete forms on next pages"

            except Exception as e:
                await say(f"❌ Critical error: {str(e)}")
                # Take screenshot on error
                try:
                    await page.screenshot(path=f"error_{user_id}_{int(datetime.now().timestamp())}.png")
                except:
                    pass
                return False, str(e)
            finally:
                await browser.close()
    
    async def select_application_type(self, page, user_data, say):
        """Select first issuance or renewal based on user_data"""
        try:
            # Wait for page to load completely
            await page.wait_for_timeout(3000)
            print("🔄 Checking for application type options...")
            
            # First, check what the user actually selected
            # Check for different possible key names in user_data
            app_type = user_data.get("application_type") or user_data.get("type") or "first_issuance"
            print(f"📋 User wants: {app_type}")
            
            # Map to actual values on the website
            if app_type == "renewal" or app_type == "2" or app_type == "Passport Renewal":
                print("🔄 Looking for 'Renewal' option...")
                
                # Try multiple selectors for renewal - targeting div.iups-service-box
                renewal_selectors = [
                    "div.iups-service-box:has-text('Renewal')",
                    "div.iups-service-box h3:has-text('Renewal')",
                    "//div[contains(@class, 'iups-service-box')]//h3[contains(text(), 'Renewal')]/..",
                    "//div[contains(@class, 'iups-service-box') and contains(., 'Renewal')]",
                ]
                
                renewal_selected = False
                for selector in renewal_selectors:
                    try:
                        print(f"Trying renewal selector: {selector}")
                        if selector.startswith('//'):
                            element = await page.wait_for_selector(f"xpath={selector}", timeout=3000)
                        else:
                            element = await page.wait_for_selector(selector, timeout=3000)
                        
                        if element and await element.is_visible():
                            await element.scroll_into_view_if_needed()
                            await page.wait_for_timeout(500)
                            await element.click()
                            print("✅ Selected 'Passport Renewal'")
                            renewal_selected = True
                            break
                    except Exception as e:
                        await say(f"Selector failed: {str(e)[:100]}")
                        continue
                
                if not renewal_selected:
                    print("⚠️ Could not find Renewal option, defaulting to First Issuance")
                    # Fall back to First Issuance
                    app_type = "first_issuance"
            
            # Select First Issuance (either user choice or fallback)
            if app_type == "first_issuance" or app_type == "1" or app_type == "First Issuance" or app_type == "new":
                print("🆕 Looking for 'First Issuance' option...")
                
                # Try multiple selectors for first issuance - targeting div.iups-service-box
                first_issuance_selectors = [
                    "div.iups-service-box:has-text('First Issuance')",
                    "div.iups-service-box h3:has-text('First Issuance')",
                    "//div[contains(@class, 'iups-service-box')]//h3[contains(text(), 'First Issuance')]/..",
                    "//div[contains(@class, 'iups-service-box') and contains(., 'First Issuance')]",
                ]
                
                first_issuance_clicked = False
                for selector in first_issuance_selectors:
                    try:
                        print(f"Trying first issuance selector: {selector}")
                        if selector.startswith('//'):
                            element = await page.wait_for_selector(f"xpath={selector}", timeout=3000)
                        else:
                            element = await page.wait_for_selector(selector, timeout=3000)
                        
                        if element and await element.is_visible():
                            await element.scroll_into_view_if_needed()
                            await page.wait_for_timeout(500)
                            await element.click()
                            print("✅ Selected 'First Issuance'")
                            first_issuance_clicked = True
                            break
                    except Exception as e:
                        await say(f"Selector failed: {str(e)[:100]}")
                        continue
                
                if not first_issuance_clicked:
                    # Last resort: look for div.iups-service-box elements
                    print("🔍 Searching for any iups-service-box elements...")
                    service_boxes = await page.query_selector_all("div.iups-service-box")
                    if service_boxes:
                        print(f"Found {len(service_boxes)} service box elements")
                        # Click the first one as fallback
                        await service_boxes[0].scroll_into_view_if_needed()
                        await page.wait_for_timeout(500)
                        await service_boxes[0].click()
                        print("⚠️ Clicked first service box element (fallback)")
                    else:
                        print("❌ No application type options found at all!")
            
            # Take screenshot to debug
            await page.screenshot(path=f"debug_{int(datetime.now().timestamp())}_application_type.png")
            await page.wait_for_timeout(1000)
                
        except Exception as e:
            print(f"⚠️ Error in application type selection: {e}")
            # Try to continue anyway
        
        # Add more debugging to see what's on the page
        try:
            # Check what text is visible on the page
            page_text = await page.evaluate("() => document.body.innerText")
            if len(page_text) > 500:
                print(f"📄 Page text (first 500 chars): {page_text[:500]}")
            else:
                print(f"📄 Page text: {page_text}")
            
            # Look for any labels or text that might indicate the options
            all_elements = await page.query_selector_all("label, div, span, button, p")
            found_options = []
            for element in all_elements[:30]:  # Check first 30 elements
                try:
                    text = await element.text_content()
                    if text:
                        text = text.strip()
                        if text and ("first" in text.lower() or "renewal" in text.lower() or "issuance" in text.lower() or "passport" in text.lower()):
                            found_options.append(text)
                            print(f"Found relevant element: {text[:50]}")
                except:
                    continue
            
            if found_options:
                print(f"📋 Found these options on page: {', '.join(found_options[:5])}")
        except Exception as e:
            print(f"Debug failed: {e}")
    
    async def fill_location_dropdowns(self, page, user_data, say):
        """Fill country, province, district, office dropdowns"""
        try:
            selects = await page.query_selector_all(selectors.SELECTORS["mat_select"])
            print(f"Found {len(selects)} dropdowns on the page")
            
            # Fill each dropdown
            dropdown_data = [
                ("Nepal", "country"),
                (user_data.get('province', ''), "province"),
                (user_data.get('district', ''), "district"),
                (user_data.get('office', ''), "office"),
            ]
            
            for i, (value, field_name) in enumerate(dropdown_data):
                if i < len(selects):
                    success = await self.select_dropdown_option(page, selects[i], value, field_name, say)
                    if not success and field_name == "country":
                        # For country, try a different approach
                        print(f"⚠️ Could not select {field_name}, trying alternative...")
                        country_input = await page.query_selector("input[placeholder*='Country']")
                        if country_input:
                            await country_input.fill("Nepal")
                            await page.wait_for_timeout(1000)
                            await page.keyboard.press("Enter")
                    await page.wait_for_timeout(2000)
        except Exception as e:
            print(f"⚠️ Error filling location dropdowns: {e}")
    
    async def select_dropdown_option(self, page, dropdown, value, field_name, say):
        """Select an option from a dropdown"""
        try:
            await dropdown.scroll_into_view_if_needed()
            await dropdown.click()
            await page.wait_for_selector(selectors.SELECTORS["mat_option"], timeout=5000)
            
            # Try to find and click the option
            option_selectors = [
                f"mat-option:has-text('{value}')",
                f"mat-option span:has-text('{value}')",
                f"mat-option .mat-option-text:has-text('{value}')",
                f"mat-option:contains('{value}')",
                f"//mat-option[contains(text(), '{value}')]"
            ]
            
            for selector in option_selectors:
                try:
                    if selector.startswith('//'):
                        option = await page.wait_for_selector(f"xpath={selector}", timeout=2000)
                    else:
                        option = await page.wait_for_selector(selector, timeout=2000)
                    
                    if option:
                        await option.click()
                        print(f"✅ Selected {field_name}: {value}")
                        return True
                except:
                    continue
            
            # Fallback: type and select
            await page.keyboard.type(value[:3])
            await asyncio.sleep(1)
            await page.keyboard.press("Enter")
            print(f"✅ Typed and selected {field_name}: {value}")
            return True
            
        except Exception as e:
            print(f"⚠️ Could not select {field_name}: {e}")
            return False
    
    async def fill_appointment_datetime(self, page, user_data, say):
        """Fill appointment date and time"""
        # Date selection
        try:
            date_input = await page.wait_for_selector(
                selectors.SELECTORS["date_input"], 
                timeout=5000
            )
            
            date_filled = False
            selected_date = user_data.get("selected_date")
            
            # Method 1: Try typing the date directly (if provided)
            if selected_date:
                try:
                    date_obj = datetime.strptime(selected_date, "%Y-%m-%d")
                    formatted_date = date_obj.strftime("%d/%m/%Y")
                    
                    if date_input:
                        await date_input.click() # Ensure calendar opens or field is focused
                        await asyncio.sleep(0.5)
                        
                        # Clear and type
                        await date_input.fill("")
                        await date_input.fill(formatted_date)
                        await asyncio.sleep(1)
                        
                        # Trigger events
                        await page.evaluate('''
                            (element) => {
                                element.dispatchEvent(new Event('input', { bubbles: true }));
                                element.dispatchEvent(new Event('change', { bubbles: true }));
                                element.dispatchEvent(new Event('blur', { bubbles: true }));
                            }
                        ''', date_input)
                        
                        print(f"✅ Typed date: {selected_date}")
                        date_filled = True
                except Exception as e:
                    print(f"⚠️ Text date selection failed: {e}")
            
            # Method 2: Click on the closest available date
            # This runs if Method 1 didn't happen or we want to ensure a valid date is picked
            if not date_filled: 
                print("📅 Trying to click closest available date...")
                
                # Make sure calendar is visible
                try:
                    await date_input.click()
                    await page.wait_for_selector(selectors.SELECTORS["date_picker_calendar"], timeout=3000)
                except:
                    print("⚠️ Calendar did not pop up, trying to find available dates anyway...")

                # Find available dates
                # Using the selector from selectors.py: "td:not(.ui-datepicker-other-month):not(.ui-state-disabled) a"
                available_dates = await page.query_selector_all(selectors.SELECTORS["available_date"])
                
                if available_dates:
                    # Click the first one (closest date)
                    await available_dates[0].click()
                    print("✅ Clicked the closest available date in the calendar.")
                    date_filled = True
                else:
                    print("❌ No available dates found in the calendar!")
                    
        except Exception as e:
            print(f"⚠️ Date selection error: {e}")
            
        if not date_filled:
            print("❌ Date passed but was not filled!")
            return False
        
        # Time selection
        selected_time = user_data.get("selected_time")
        if selected_time:
            try:
                await page.wait_for_selector(
                    selectors.SELECTORS["time_slots_container"], 
                    timeout=5000
                )
                
                # Try to find and click the time slot
                time_chip_selectors = [
                    f"mat-chip:has-text('{selected_time}')",
                    f"mat-chip .mat-chip-ripple:has-text('{selected_time}')",
                    f"mat-chip:contains('{selected_time}')",
                    f"//mat-chip[contains(text(), '{selected_time}')]"
                ]
                
                for selector in time_chip_selectors:
                    try:
                        if selector.startswith('//'):
                            time_chip = await page.wait_for_selector(f"xpath={selector}", timeout=2000)
                        else:
                            time_chip = await page.wait_for_selector(selector, timeout=2000)
                        
                        if time_chip:
                            await time_chip.click()
                            print(f"✅ Selected time slot: {selected_time}")
                            return True
                    except:
                        continue
                
                # Fallback: click first available
                slots = await page.query_selector_all(selectors.SELECTORS["time_slot"])
                if slots:
                    await slots[0].click()
                    print("✅ Time slot auto-selected (fallback).")
                    
            except Exception as e:
                print(f"⚠️ Time slot selection error: {e}")
                return False
        
        return True
    
    async def handle_captcha(self, page, user_data, user_id, say):
        """Handle CAPTCHA solving with retries"""
        from config.settings import MAX_CAPTCHA_ATTEMPTS
        
        for attempt in range(1, MAX_CAPTCHA_ATTEMPTS + 1):
            try:
                print(f"🔄 Attempt {attempt}/{MAX_CAPTCHA_ATTEMPTS}: Solving captcha...")
                
                # Get captcha image (increased timeout)
                captcha_img = await page.wait_for_selector(
                    selectors.SELECTORS["captcha_image"], 
                    timeout=15000
                )
                screenshot_bytes = await captcha_img.screenshot()
                captcha_text = await self.captcha_solver.solve_captcha(screenshot_bytes)

                print(f"🔤 Captcha text detected: {captcha_text}")

                # Fill captcha input (increased timeout)
                captcha_input = await page.wait_for_selector(
                    selectors.SELECTORS["captcha_input"],
                    state="visible",
                    timeout=15000
                )
                await captcha_input.fill(captcha_text)

                # Click Next button (increased timeout)
                next_btn = await page.wait_for_selector(
                    selectors.SELECTORS["captcha_next_button"], 
                    timeout=10000
                )
                if next_btn:
                    async with page.expect_navigation(timeout=15000) as navigation_info:
                        await next_btn.click()
                    
                    await navigation_info.value
                    if attempt > 1:
                       await say(f"✅ Captcha solved successfully on attempt {attempt}.")
                    else:
                       print(f"✅ Captcha solved successfully on attempt {attempt}.")
                    return True

            except PlaywrightTimeoutError:
                print(f"❌ Captcha attempt {attempt} failed (timeout).")
                await self.handle_captcha_failure(page, say, attempt)
                
            except Exception as e:
                print(f"❌ Captcha attempt {attempt} error: {e}")
                await self.handle_captcha_failure(page, say, attempt)
            
            await asyncio.sleep(2)
        
        return False
    
    async def handle_captcha_failure(self, page, say, attempt):
        """Handle CAPTCHA failure"""
        try:
            # Close error dialog
            close_selectors = [
                selectors.SELECTORS["captcha_close_button"],
                "button.mat-dialog-close:has-text('Close')",
                "button:has-text('Close')",
                "//button[contains(text(), 'Close')]"
            ]
            
            for selector in close_selectors:
                try:
                    if selector.startswith('//'):
                        close_btn = await page.wait_for_selector(f"xpath={selector}", timeout=5000)
                    else:
                        close_btn = await page.wait_for_selector(selector, timeout=5000)
                    
                    if close_btn:
                        await close_btn.click()
                        print("✅ Closed the error dialog.")
                        await asyncio.sleep(2)
                        break
                except:
                    continue
            
            # Reload captcha
            reload_selectors = [
                selectors.SELECTORS["captcha_reload"],
                "img.captcha-img",
                "//img[contains(@class, 'captcha')]"
            ]
            
            for selector in reload_selectors:
                try:
                    if selector.startswith('//'):
                        reload_btn = await page.wait_for_selector(f"xpath={selector}", timeout=3000)
                    else:
                        reload_btn = await page.wait_for_selector(selector, timeout=3000)
                    
                    if reload_btn:
                        await reload_btn.click()
                        print("🔄 Captcha reloaded.")
                        await asyncio.sleep(2)
                        break
                except:
                    continue
                    
        except Exception as e:
            print(f"❌ Error handling captcha failure: {e}")
    
    async def handle_next_page(self, page, user_data, user_id, say):
        """Handle forms on the next page after CAPTCHA"""
        try:
            await asyncio.sleep(3000)
            print(f"🔗 Now on page: {page.url}")
            
            # Check for renewal fields
            is_renewal = user_data.get("application_type") == "renewal"
            if is_renewal:
                print("🔄 This is a renewal application...")
                renewal_success = await fill_renewal_information(page, user_data, user_id, say)
                if not renewal_success:
                    print("⚠️ Could not fill all renewal information, but continuing...")
            
            # FILL DEMOGRAPHIC INFORMATION (Personal Info)
            print("👤 Starting to fill demographic information...")
            demographic_success = await demographic_information(page, user_data, user_id, say)
            if not demographic_success:
                return False
            
            # Navigate to next section (Citizen Info)
            next_btn = await self.find_next_button(page)
            if next_btn:
                async with page.expect_navigation(timeout=15000) as navigation_info:
                    await next_btn.click()
                await navigation_info.value
                print("✅ Moved to citizenship information page!")
                
                # FILL CITIZEN INFORMATION
                print("📄 Filling citizenship information...")
                citizen_success = await citizen_information(page, user_data, user_id, say)
                if not citizen_success:
                    return False
                
                # Navigate to next section (Contact Info)
                next_btn = await self.find_next_button(page)
                if next_btn:
                    async with page.expect_navigation(timeout=15000) as navigation_info:
                        await next_btn.click()
                    await navigation_info.value
                    print("✅ Moved to contact information page!")
                    
                    # FILL CONTACT INFORMATION
                    print("📱 Filling contact information...")
                    contact_success = await contact_information(page, user_data, user_id, say)
                    if not contact_success:
                        return False
                    
                    # Navigate to next section (Emergency Info)
                    next_btn = await self.find_next_button(page)
                    if next_btn:
                        async with page.expect_navigation(timeout=15000) as navigation_info:
                            await next_btn.click()
                        await navigation_info.value
                        print("✅ Moved to emergency information page!")
                        
                        # FILL EMERGENCY INFORMATION
                        print("🆘 Filling emergency information...")
                        emergency_success = await emergency_info(page, user_data, user_id, say)
                        if not emergency_success:
                            return False
                        
                        await say("🎉 All forms filled successfully!")
                        return True
            
            return True
            
        except Exception as e:
            await say(f"❌ Error handling next page: {e}")
            try:
                # Take error screenshot
                timestamp = int(datetime.now().timestamp())
                filename = f"debug_error_next_page_{timestamp}.png"
                await page.screenshot(path=filename)
                await say(f"📸 Saved error screenshot to {filename}")
            except:
                pass
            return False
    
    async def find_next_button(self, page):
        """Find and return the next button"""
        next_selectors = [
            selectors.SELECTORS["next_button"],
            "button[type='submit']:has-text('Next')",
            "button:has-text('Next')",
            "//button[contains(text(), 'Next')]"
        ]
        
        for selector in next_selectors:
            try:
                if selector.startswith('//'):
                    button = await page.wait_for_selector(f"xpath={selector}", timeout=3000)
                else:
                    button = await page.wait_for_selector(selector, timeout=3000)
                
                if button:
                    return button
            except:
                continue
        return None