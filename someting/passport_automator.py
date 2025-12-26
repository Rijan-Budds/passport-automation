"""
Main passport automation orchestrator
"""

import asyncio
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from captcha_solver import CaptchaSolver
from form_filler import FormFiller

class PassportAutomator:
    def __init__(self, captcha_solver, form_filler):
        self.captcha_solver = captcha_solver
        self.form_filler = form_filler
    
    async def automate(self, user_data, user_id, say):
        """Main automation function"""
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
                await selects[0].click()
                await page.click("mat-option >> text=Nepal")
                
                await selects[1].click()
                await page.click(f"mat-option >> text={user_data['province']}")
                
                await selects[2].click()
                await page.click(f"mat-option >> text={user_data['district']}")
                
                await selects[3].click()
                await page.click(f"mat-option >> text={user_data['office']}")
                
                # DATE SELECTION
                try:
                    if "appointment_date" in user_data:
                        date_input = await page.wait_for_selector(
                            "input[placeholder*='Date' i], input[type='text'][formcontrolname*='date' i]",
                            timeout=5000
                        )
                        await date_input.click()
                        await page.wait_for_selector(".ui-datepicker-calendar")
                        
                        appointment_date = user_data["appointment_date"]
                        day = appointment_date.split("-")[2] if "-" in appointment_date else appointment_date
                        
                        await page.click(f"a:has-text('{int(day)}')")
                        await say(f"✅ Selected date: {appointment_date}")
                except Exception as e:
                    await say(f"⚠️ Date selection error: {e}")
                
                # TIME SLOT SELECTION
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
                
                # CAPTCHA HANDLING
                captcha_success = False
                for attempt in range(1, 11):
                    try:
                        await say(f"🔄 Attempt {attempt}/10: Solving captcha...")
                        
                        # Get captcha image
                        captcha_img = await page.wait_for_selector("img.captcha-img", timeout=8000)
                        screenshot_bytes = await captcha_img.screenshot()
                        captcha_text = await self.captcha_solver.solve_captcha(screenshot_bytes)
                        
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
                            
                            # FILL ALL FORMS
                            personal_success = await self.form_filler.fill_personal_information(page, user_data, user_id, say)
                            if not personal_success:
                                return False, "Failed to fill personal information"
                            
                            next_buttons = await page.query_selector_all("button:has-text('Next'), button[type='submit']")
                            if next_buttons:
                                async with page.expect_navigation(timeout=10000):
                                    await next_buttons[0].click()
                                await page.wait_for_timeout(2000)
                                
                                address_success = await self.form_filler.fill_address_information(page, user_data, user_id, say)
                                if not address_success:
                                    return False, "Failed to fill address information"
                                
                                next_buttons = await page.query_selector_all("button:has-text('Next'), button[type='submit']")
                                if next_buttons:
                                    async with page.expect_navigation(timeout=10000):
                                        await next_buttons[0].click()
                                    await page.wait_for_timeout(2000)
                                    
                                    family_success = await self.form_filler.fill_family_information(page, user_data, user_id, say)
                                    if not family_success:
                                        return False, "Failed to fill family information"
                            
                            await say("🎉 All forms filled successfully!")
                            return True, "Full passport application automation completed successfully!"
                        
                    except PlaywrightTimeoutError:
                        await say(f"❌ Captcha attempt {attempt} failed (timeout).")
                        await self.captcha_solver.handle_captcha_failure(page, say, attempt)
                    except Exception as e:
                        await say(f"❌ Captcha attempt {attempt} error: {e}")
                        await asyncio.sleep(2)
                
                if not captcha_success:
                    return False, "Captcha could not be solved after 10 attempts."
                
                return True, "Passport application automation completed successfully!"
                
            except Exception as e:
                return False, str(e)
            finally:
                await browser.close()