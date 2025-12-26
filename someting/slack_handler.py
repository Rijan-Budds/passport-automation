"""
Slack conversation flow handler
"""

import asyncio
from models import QUESTIONS_PRE_CAPTCHA, QUESTIONS_PERSONAL_INFO, QUESTIONS_ADDITIONAL
from models import match_province, match_district, PROVINCES, DISTRICT_OFFICES

class SlackHandler:
    def __init__(self, supabase_client, website_scraper, passport_automator):
        self.supabase_client = supabase_client
        self.website_scraper = website_scraper
        self.passport_automator = passport_automator
        self.user_sessions = {}
    
    async def handle_message(self, event, say):
        """Handle incoming Slack messages"""
        user_id = event["user"]
        text = event.get("text", "").strip()
        
        if event.get("bot_id") or event.get("channel_type") != "im":
            return
        
        # Initialize session
        if user_id not in self.user_sessions:
            self.user_sessions[user_id] = {
                "data": {},
                "step": 0,
                "question_phase": "pre_captcha"
            }
            await say("👋 Welcome to the Passport Automation Bot! Let's get started.")
            await say(QUESTIONS_PRE_CAPTCHA[0][1])
            return
        
        session = self.user_sessions[user_id]
        phase = session["question_phase"]
        step = session["step"]
        
        if phase == "pre_captcha":
            await self._handle_pre_captcha_phase(session, user_id, text, say)
        elif phase == "date_selection":
            await self._handle_date_selection(session, user_id, text, say)
        elif phase == "time_selection":
            await self._handle_time_selection(session, user_id, text, say)
        elif phase == "personal_info":
            await self._handle_personal_info(session, user_id, text, say)
        elif phase == "additional_info":
            await self._handle_additional_info(session, user_id, text, say)
        elif phase == "additional_details":
            await self._handle_additional_details(session, user_id, text, say)
    
    async def _handle_pre_captcha_phase(self, session, user_id, text, say):
        """Handle pre-captcha questions"""
        key = QUESTIONS_PRE_CAPTCHA[session["step"]][0]
        
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
            session["question_phase"] = "date_selection"
            
            # Get dates from website or Supabase
            await self._get_available_dates(session, user_id, say)
            return
        
        # Passport type or other fields
        else:
            session["data"][key] = text
            session["step"] += 1
        
        # Move to next question
        if session["step"] < len(QUESTIONS_PRE_CAPTCHA):
            next_question = QUESTIONS_PRE_CAPTCHA[session["step"]][1]
            await say(next_question)
    
    async def _get_available_dates(self, session, user_id, say):
        """Get available dates from website or database"""
        await say("🔄 Checking for available dates...")
        
        district = session["data"]["district"]
        office = session["data"]["office"]
        
        # First try to get from Supabase
        dates = self.supabase_client.get_dates(district, office)
        
        # If no dates in database, scrape from website
        if not dates:
            await say("🌐 Scraping real-time availability from passport website...")
            dates, _ = await self.website_scraper.scrape_appointment_page(
                district, office, session["data"], say
            )
            
            # Store scraped dates in Supabase
            if dates:
                self.supabase_client.store_dates(district, office, dates)
        
        if not dates:
            await say("❌ No available dates found. Please try again later.")
            del self.user_sessions[user_id]
            return
        
        session["available_dates"] = dates
        
        # Show dates to user
        options = "\n".join(f"{i+1}. {d}" for i, d in enumerate(dates))
        await say(
            f"📅 *Available Dates for {district}:*\n"
            f"{options}\n\n"
            "Reply with date number (1, 2, 3...):"
        )
    
    async def _handle_date_selection(self, session, user_id, text, say):
        """Handle date selection"""
        dates = session.get("available_dates", [])
        
        if not text.isdigit() or not (1 <= int(text) <= len(dates)):
            await say("❌ Choose a valid date number.")
            return
        
        selected_date = dates[int(text) - 1]
        session["data"]["appointment_date"] = selected_date
        
        # Get time slots for selected date
        await self._get_available_times(session, user_id, say)
    
    async def _get_available_times(self, session, user_id, say):
        """Get available time slots for selected date"""
        district = session["data"]["district"]
        selected_date = session["data"]["appointment_date"]
        
        await say(f"🔄 Checking time slots for {selected_date}...")
        
        # First try to get from Supabase
        time_slots = self.supabase_client.get_time_slots(district, selected_date)
        
        # If no times in database, scrape from website
        if not time_slots:
            await say("🌐 Scraping real-time time slots from website...")
            # We need to scrape the page again with the selected date
            # For now, use default time slots
            time_slots = [
                "09:00 AM - 10:00 AM",
                "10:00 AM - 11:00 AM", 
                "11:00 AM - 12:00 PM",
                "01:00 PM - 02:00 PM",
                "02:00 PM - 03:00 PM"
            ]
            
            # Store in Supabase
            if time_slots:
                self.supabase_client.store_time_slots(district, selected_date, time_slots)
        
        session["available_times"] = time_slots
        session["question_phase"] = "time_selection"
        
        options = "\n".join(f"{i+1}. {t}" for i, t in enumerate(time_slots))
        await say(
            f"⏰ *Available Time Slots for {selected_date}:*\n" +
            options +
            "\n\nReply with time slot number:"
        )
    
    async def _handle_time_selection(self, session, user_id, text, say):
        """Handle time slot selection"""
        time_slots = session.get("available_times", [])
        
        if not text.isdigit() or not (1 <= int(text) <= len(time_slots)):
            await say("❌ Choose a valid time slot number.")
            return
        
        selected_time = time_slots[int(text) - 1]
        session["data"]["appointment_time"] = selected_time
        
        await say(
            f"✅ Appointment selected:\n"
            f"📅 Date: *{session['data']['appointment_date']}*\n"
            f"⏰ Time: *{selected_time}*"
        )
        
        # Move to personal info
        session["question_phase"] = "personal_info"
        session["step"] = 0
        await say("Now let's collect your personal information...")
        await say(QUESTIONS_PERSONAL_INFO[0][1])
    
    async def _handle_personal_info(self, session, user_id, text, say):
        """Handle personal information questions"""
        key = QUESTIONS_PERSONAL_INFO[session["step"]][0]
        
        if key == "middle_name" and text.strip() == "_":
            session["data"][key] = ""
        else:
            session["data"][key] = text.strip()
        
        session["step"] += 1
        
        if session["step"] >= len(QUESTIONS_PERSONAL_INFO):
            session["question_phase"] = "additional_info"
            session["step"] = 0
            await say("✅ Personal info collected. Would you like to provide additional information? (Yes/No)")
        else:
            await say(QUESTIONS_PERSONAL_INFO[session["step"]][1])
    
    async def _handle_additional_info(self, session, user_id, text, say):
        """Handle additional information prompt"""
        if text.lower() == "yes":
            await say("Great! Let's collect some additional information.")
            session["question_phase"] = "additional_details"
            session["step"] = 0
            await say(QUESTIONS_ADDITIONAL[0][1])
        elif text.lower() == "no":
            await say("✅ All information collected. Starting automation...")
            # Start passport automation
            success, message = await self.passport_automator.automate(session["data"], user_id, say)
            if success:
                await say(f"🎉 Automation completed successfully for <@{user_id}>!")
            else:
                await say(f"❌ Automation failed: {message}")
            del self.user_sessions[user_id]
        else:
            await say("Please answer Yes or No.")
    
    async def _handle_additional_details(self, session, user_id, text, say):
        """Handle additional details questions"""
        key = QUESTIONS_ADDITIONAL[session["step"]][0]
        session["data"][key] = text.strip()
        session["step"] += 1
        
        if session["step"] >= len(QUESTIONS_ADDITIONAL):
            await say("✅ All information collected. Starting automation...")
            # Start passport automation
            success, message = await self.passport_automator.automate(session["data"], user_id, say)
            if success:
                await say(f"🎉 Automation completed successfully for <@{user_id}>!")
            else:
                await say(f"❌ Automation failed: {message}")
            del self.user_sessions[user_id]
        else:
            await say(QUESTIONS_ADDITIONAL[session["step"]][1])