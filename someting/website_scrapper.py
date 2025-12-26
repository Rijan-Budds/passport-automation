import asyncio
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

class WebsiteScraper:
    def __init__(self):
        self.month_map = {
            "January": "01", "February": "02", "March": "03", "April": "04",
            "May": "05", "June": "06", "July": "07", "August": "08",
            "September": "09", "October": "10", "November": "11", "December": "12"
        }
    
    async def extract_dates_from_website(self, page, say):
        """Extract available dates from the date picker"""
        try:
            await say("📅 Extracting available dates from website...")
            
            # Open the date picker
            date_input = await page.wait_for_selector(
                "input[placeholder*='Date' i], input[type='text'][formcontrolname*='date' i]",
                timeout=5000
            )
            await date_input.click()
            await page.wait_for_selector(".ui-datepicker-calendar", timeout=3000)
            
            # Extract month and year
            current_month_element = await page.query_selector(".ui-datepicker-title span.ui-datepicker-month")
            current_year_element = await page.query_selector(".ui-datepicker-title span.ui-datepicker-year")
            
            current_month = await current_month_element.inner_text() if current_month_element else ""
            current_year = await current_year_element.inner_text() if current_year_element else ""
            
            month_num = self.month_map.get(current_month, "01")
            
            # Get all available dates
            date_links = await page.query_selector_all(
                "td:not(.ui-datepicker-other-month):not(.ui-state-disabled) a"
            )
            
            available_dates = []
            for date_link in date_links:
                day = await date_link.inner_text()
                formatted_date = f"{current_year}-{month_num}-{day.zfill(2)}"
                available_dates.append(formatted_date)
            
            # Close date picker
            if date_links:
                await date_links[0].click()
            
            await page.wait_for_timeout(1000)
            
            await say(f"✅ Found {len(available_dates)} available dates")
            return available_dates
            
        except Exception as e:
            await say(f"❌ Error extracting dates: {e}")
            return []
    
    async def extract_times_from_website(self, page, say):
        """Extract available time slots from the time picker"""
        try:
            await say("⏰ Extracting available time slots...")
            
            await page.wait_for_selector(".ui-datepicker-calendar-container mat-chip-list", timeout=5000)
            
            time_chips = await page.query_selector_all("mat-chip.mat-chip:not(.mat-chip-disabled)")
            
            time_slots = []
            for chip in time_chips:
                slot_text = await chip.inner_text()
                time_slots.append(slot_text.strip())
            
            await say(f"✅ Found {len(time_slots)} available time slots")
            return time_slots
            
        except Exception as e:
            await say(f"❌ Error extracting time slots: {e}")
            return []
    
    async def scrape_appointment_page(self, district, office, user_data, say):
        """Scrape the appointment page to get real-time availability"""
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            try:
                await say(f"🌐 Opening passport website for {district}...")
                await page.goto("https://emrtds.nepalpassport.gov.np")
                
                # Basic navigation to appointment page
                await page.wait_for_selector("text=First Issuance")
                await page.click("text=First Issuance")
                
                await page.wait_for_selector("label.main-doc-types")
                await page.click(f"label.main-doc-types:has-text('{user_data.get('passport_type', 'Regular')}')")
                
                await page.wait_for_selector("text=Proceed")
                await page.click("text=Proceed")
                
                # Consent popup
                try:
                    await page.wait_for_selector("mat-dialog-container", timeout=3000)
                    await page.click("mat-dialog-container >> text=I agree स्वीकृत छ")
                except:
                    pass
                
                await page.wait_for_url("**/appointment", timeout=10000)
                
                # Select location
                selects = await page.query_selector_all("mat-select")
                if len(selects) >= 4:
                    await selects[0].click()
                    await page.click("mat-option >> text=Nepal")
                    
                    await selects[1].click()
                    await page.click(f"mat-option >> text={user_data.get('province', 'Bagmati')}")
                    
                    await selects[2].click()
                    await page.click(f"mat-option >> text={district}")
                    
                    await selects[3].click()
                    await page.click(f"mat-option >> text={office}")
                
                await page.wait_for_timeout(2000)
                
                # Extract dates and times
                dates = await self.extract_dates_from_website(page, say)
                times = await self.extract_times_from_website(page, say) if dates else []
                
                return dates, times
                
            except Exception as e:
                await say(f"❌ Error scraping website: {e}")
                return [], []
            finally:
                await browser.close()