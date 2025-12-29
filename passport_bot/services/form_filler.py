import asyncio
from datetime import datetime
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

# Import form modules - UPDATED IMPORTS
from forms.demographic_info import demographic_information
# from forms.citizen_info import citizen_information
# from forms.contact_info import contact_information
# from forms.emergency_info import emergency_information
# from forms.renewal_info import renewal_information

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
            browser = await p.chromium.launch(headless=False)
            page = await browser.new_page()
            try:
                await page.goto("https://emrtds.nepalpassport.gov.np")
                await page.wait_for_timeout(3000)

                # Application type selection
                await self.select_application_type(page, user_data, say)
                
                # Passport type
                await page.wait_for_selector(selectors.SELECTORS["passport_type_regular"], timeout=10000)
                passport_type = user_data.get('passport_type', 'Regular')
                await page.click(f"label.main-doc-types:has-text('{passport_type}')")

                # Proceed
                await page.wait_for_selector(selectors.SELECTORS["proceed_button"], timeout=10000)
                await page.click(selectors.SELECTORS["proceed_button"])

                # Consent popup
                try:
                    await page.wait_for_selector("mat-dialog-container", timeout=5000)
                    await page.click(selectors.SELECTORS["agree_button"])
                except:
                    pass

                # Wait for appointment page
                await page.wait_for_url("**/appointment", timeout=15000)
                await page.wait_for_timeout(2000)

                # Fill location dropdowns
                await self.fill_location_dropdowns(page, user_data, say)
                
                # Fill date and time
                await self.fill_appointment_datetime(page, user_data, say)

                # Handle CAPTCHA
                captcha_success = await self.handle_captcha(page, user_data, user_id, say)
                if not captcha_success:
                    return False, "Captcha could not be solved after 10 attempts."

                # Fill remaining forms - UPDATED
                next_page_success = await self.handle_next_page(page, user_data, user_id, say)
                if next_page_success:
                    await say(f"🎉 Full automation completed successfully for <@{user_id}>!")
                    return True, "Full passport application automation completed successfully!"
                else:
                    return False, "Failed to complete forms on next pages"

            except Exception as e:
                return False, str(e)
            finally:
                await browser.close()
    
    async def select_application_type(self, page, user_data, say):
        """Select first issuance or renewal"""
        if user_data.get("application_type") == "renewal":
            await say("🔄 Starting passport renewal process...")
            await page.wait_for_selector(selectors.SELECTORS["renewal_button"], timeout=10000)
            await page.click(selectors.SELECTORS["renewal_button"])
        else:
            await say("🆕 Starting new passport application (First Issuance)...")
            await page.wait_for_selector(selectors.SELECTORS["first_issuance_button"], timeout=10000)
            await page.click(selectors.SELECTORS["first_issuance_button"])
    
    async def fill_location_dropdowns(self, page, user_data, say):
        """Fill country, province, district, office dropdowns"""
        selects = await page.query_selector_all(selectors.SELECTORS["mat_select"])
        await say(f"Found {len(selects)} dropdowns on the page")
        
        # Fill each dropdown
        dropdown_data = [
            ("Nepal", "country"),
            (user_data.get('province', ''), "province"),
            (user_data.get('district', ''), "district"),
            (user_data.get('office', ''), "office"),
        ]
        
        for i, (value, field_name) in enumerate(dropdown_data):
            if i < len(selects):
                await self.select_dropdown_option(page, selects[i], value, field_name, say)
                await page.wait_for_timeout(2000)
    
    async def select_dropdown_option(self, page, dropdown, value, field_name, say):
        """Select an option from a dropdown"""
        try:
            await dropdown.click()
            await page.wait_for_selector(selectors.SELECTORS["mat_option"], timeout=5000)
            
            # Try to find and click the option
            option_selectors = [
                f"mat-option:has-text('{value}')",
                f"mat-option span:has-text('{value}')",
                f"mat-option .mat-option-text:has-text('{value}')",
                f"mat-option:contains('{value}')"
            ]
            
            for selector in option_selectors:
                try:
                    option = await page.wait_for_selector(selector, timeout=2000)
                    if option:
                        await option.click()
                        await say(f"✅ Selected {field_name}: {value}")
                        return True
                except:
                    continue
            
            # Fallback: type and select
            await page.keyboard.type(value[:3])
            await asyncio.sleep(1)
            await page.keyboard.press("Enter")
            await say(f"✅ Typed and selected {field_name}: {value}")
            return True
            
        except Exception as e:
            await say(f"⚠️ Could not select {field_name}: {e}")
            return False
    
    async def fill_appointment_datetime(self, page, user_data, say):
        """Fill appointment date and time"""
        # Date selection
        selected_date = user_data.get("selected_date")
        if selected_date:
            try:
                date_obj = datetime.strptime(selected_date, "%Y-%m-%d")
                formatted_date = date_obj.strftime("%d/%m/%Y")
                
                date_input = await page.wait_for_selector(
                    selectors.SELECTORS["date_input"], 
                    timeout=5000
                )
                if date_input:
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
                    
                    await say(f"✅ Selected date: {selected_date}")
            except Exception as e:
                await say(f"⚠️ Date selection error: {e}")
        
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
                    f"mat-chip:contains('{selected_time}')"
                ]
                
                for selector in time_chip_selectors:
                    try:
                        time_chip = await page.wait_for_selector(selector, timeout=2000)
                        if time_chip:
                            await time_chip.click()
                            await say(f"✅ Selected time slot: {selected_time}")
                            return
                    except:
                        continue
                
                # Fallback: click first available
                slots = await page.query_selector_all(selectors.SELECTORS["time_slot"])
                if slots:
                    await slots[0].click()
                    await say("✅ Time slot auto-selected (fallback).")
                    
            except Exception as e:
                await say(f"⚠️ Time slot selection error: {e}")
    
    async def handle_captcha(self, page, user_data, user_id, say):
        """Handle CAPTCHA solving with retries"""
        from config.settings import MAX_CAPTCHA_ATTEMPTS
        
        for attempt in range(1, MAX_CAPTCHA_ATTEMPTS + 1):
            try:
                await say(f"🔄 Attempt {attempt}/{MAX_CAPTCHA_ATTEMPTS}: Solving captcha...")
                
                # Get captcha image
                captcha_img = await page.wait_for_selector(
                    selectors.SELECTORS["captcha_image"], 
                    timeout=8000
                )
                screenshot_bytes = await captcha_img.screenshot()
                captcha_text = await self.captcha_solver.solve_captcha(screenshot_bytes)

                await say(f"🔤 Captcha text detected: {captcha_text}")

                # Fill captcha input
                captcha_input = await page.wait_for_selector(
                    selectors.SELECTORS["captcha_input"],
                    state="visible",
                    timeout=12000
                )
                await captcha_input.fill(captcha_text)

                # Click Next button
                next_btn = await page.wait_for_selector(
                    selectors.SELECTORS["captcha_next_button"], 
                    timeout=5000
                )
                if next_btn:
                    async with page.expect_navigation(timeout=10000) as navigation_info:
                        await next_btn.click()
                    
                    await navigation_info.value
                    await say(f"✅ Captcha solved successfully on attempt {attempt}.")
                    return True

            except PlaywrightTimeoutError:
                await say(f"❌ Captcha attempt {attempt} failed (timeout).")
                await self.handle_captcha_failure(page, say, attempt)
                
            except Exception as e:
                await say(f"❌ Captcha attempt {attempt} error: {e}")
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
                "button:has-text('Close')"
            ]
            
            for selector in close_selectors:
                try:
                    close_btn = await page.wait_for_selector(selector, timeout=5000)
                    if close_btn:
                        await close_btn.click()
                        await say("✅ Closed the error dialog.")
                        await asyncio.sleep(2)
                        break
                except:
                    continue
            
            # Reload captcha
            reload_selectors = [
                selectors.SELECTORS["captcha_reload"],
                "img.captcha-img"
            ]
            
            for selector in reload_selectors:
                try:
                    reload_btn = await page.wait_for_selector(selector, timeout=3000)
                    if reload_btn:
                        await reload_btn.click()
                        await say("🔄 Captcha reloaded.")
                        await asyncio.sleep(2)
                        break
                except:
                    continue
                    
        except Exception as e:
            await say(f"❌ Error handling captcha failure: {e}")
    
    async def handle_next_page(self, page, user_data, user_id, say):
        """Handle forms on the next page after CAPTCHA"""
        try:
            await asyncio.sleep(3000)
            await say(f"🔗 Now on page: {page.url}")
            
            # Check for renewal fields
            is_renewal = user_data.get("application_type") == "renewal"
            if is_renewal:
                await say("🔄 This is a renewal application...")
                renewal_success = await fill_renewal_information(page, user_data, user_id, say)
                if not renewal_success:
                    await say("⚠️ Could not fill all renewal information, but continuing...")
            
            # FILL DEMOGRAPHIC INFORMATION (Personal Info) - UPDATED
            await say("👤 Starting to fill demographic information...")
            demographic_success = await fill_demographic_information(page, user_data, user_id, say)
            if not demographic_success:
                return False
            
            # Navigate to next section (Citizen Info)
            next_btn = await self.find_next_button(page)
            if next_btn:
                async with page.expect_navigation(timeout=15000) as navigation_info:
                    await next_btn.click()
                await navigation_info.value
                await say("✅ Moved to citizenship information page!")
                
                # FILL CITIZEN INFORMATION - UPDATED
                await say("📄 Filling citizenship information...")
                citizen_success = await fill_citizen_information(page, user_data, user_id, say)
                if not citizen_success:
                    return False
                
                # Navigate to next section (Contact Info)
                next_btn = await self.find_next_button(page)
                if next_btn:
                    async with page.expect_navigation(timeout=15000) as navigation_info:
                        await next_btn.click()
                    await navigation_info.value
                    await say("✅ Moved to contact information page!")
                    
                    # FILL CONTACT INFORMATION - UPDATED
                    await say("📱 Filling contact information...")
                    contact_success = await fill_contact_information(page, user_data, user_id, say)
                    if not contact_success:
                        return False
                    
                    # Navigate to next section (Emergency Info)
                    next_btn = await self.find_next_button(page)
                    if next_btn:
                        async with page.expect_navigation(timeout=15000) as navigation_info:
                            await next_btn.click()
                        await navigation_info.value
                        await say("✅ Moved to emergency information page!")
                        
                        # FILL EMERGENCY INFORMATION - UPDATED
                        await say("🆘 Filling emergency information...")
                        emergency_success = await fill_emergency_information(page, user_data, user_id, say)
                        if not emergency_success:
                            return False
                        
                        await say("🎉 All forms filled successfully!")
                        return True
            
            return True
            
        except Exception as e:
            await say(f"❌ Error handling next page: {e}")
            return False
    
    async def find_next_button(self, page):
        """Find and return the next button"""
        next_selectors = [
            selectors.SELECTORS["next_button"],
            "button[type='submit']:has-text('Next')"
        ]
        
        for selector in next_selectors:
            try:
                button = await page.wait_for_selector(selector, timeout=3000)
                if button:
                    return button
            except:
                continue
        return None