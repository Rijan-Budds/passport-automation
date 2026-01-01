import asyncio
import os
from slack_bolt.async_app import AsyncApp
from models.session import SessionManager
from services.form_filler import FormFiller
from services.supabase_client import SupabaseClient
from utils.helpers import format_slots_for_date_selection, format_time_slots_for_selection
from config.settings import (
    QUESTIONS_PRE_CAPTCHA, QUESTIONS_RENEWAL, 
    QUESTIONS_DEMOGRAPHIC_INFO, QUESTIONS_CITIZEN_INFO, 
    QUESTIONS_CONTACT_INFO, QUESTIONS_EMERGENCY_INFO
)

class SlackHandler:
    """Handles all Slack interactions"""
    
    def __init__(self):
        self.app = AsyncApp(
            token=os.environ.get("SLACK_BOT_TOKEN"),
            signing_secret=os.environ.get("SLACK_SIGNING_SECRET")
        )
        self.session_manager = SessionManager()
        self.form_filler = FormFiller()
        self.supabase_client = SupabaseClient()
        
        # Register event handlers
        self.app.event("message")(self.handle_message)
    
    async def handle_message(self, event, say):
        """Handle incoming Slack messages"""
        user_id = event["user"]
        text = event.get("text", "").strip()
        
        # Ignore bot messages and non-DM
        if event.get("bot_id") or event.get("channel_type") != "im":
            return

        # Initialize session
        if user_id not in self.session_manager.sessions:
            await say("👋 Welcome to the Passport Automation Bot! Let's get started.")
            await say(QUESTIONS_PRE_CAPTCHA[0][1])
            session = self.session_manager.get_session(user_id)
            return

        session = self.session_manager.get_session(user_id)
        phase = session.question_phase
        step = session.step

        # Route to appropriate handler
        if phase == "pre_captcha":
            await self.handle_pre_captcha(session, text, say)
        elif phase == "date_selection":
            await self.handle_date_selection(session, text, say)
        elif phase == "time_selection":
            await self.handle_time_selection(session, text, say)
        elif phase == "office_selection":
            await self.handle_office_selection(session, text, say)
        elif phase == "renewal_info":
            await self.handle_renewal_info(session, text, say)
        elif phase == "demographic_info":
            await self.handle_demographic_info(session, text, say)
        elif phase == "citizen_info":
            await self.handle_citizen_info(session, text, say)
        elif phase == "contact_info":
            await self.handle_contact_info(session, text, say)
        elif phase == "emergency_info":  # REMOVED address_info
            await self.handle_emergency_info(session, text, say)
    
    async def handle_pre_captcha(self, session, text, say):
        """Handle pre-captcha questions"""
        key = QUESTIONS_PRE_CAPTCHA[session.step][0]

        if key == "application_type":
            if text == "1":
                session.update("application_type", "first_issuance")
                session.step += 1
                await say(QUESTIONS_PRE_CAPTCHA[session.step][1])
            elif text == "2":
                session.update("application_type", "renewal")
                session.step += 1
                session.additional_renewal_questions = True
                await say(QUESTIONS_PRE_CAPTCHA[session.step][1])
            else:
                await say("Please type '1' for First Issuance or '2' for Passport Renewal:")
        
        elif key == "passport_type":
            session.update("passport_type", text.title())
            session.step += 1
            await say(QUESTIONS_PRE_CAPTCHA[session.step][1])
        
        elif key == "province":
            session.update("province", text.title())
            session.step += 1
            await say(QUESTIONS_PRE_CAPTCHA[session.step][1])
        
        elif key == "district":
            district = text.title()
            await say(f"🔍 Checking available slots for {district}...")
            
            available_slots = await self.supabase_client.get_available_slots(district)
            if available_slots:
                session.update("district", district)
                session.data.available_slots = available_slots
                session.step += 1
                
                formatted_dates, date_mapping = await format_slots_for_date_selection(available_slots)
                if formatted_dates:
                    session.data.date_mapping = date_mapping
                    session.question_phase = "date_selection"
                    
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
    
    async def handle_date_selection(self, session, text, say):
        """Handle date selection"""
        if text.isdigit() and text in session.data.date_mapping:
            selected_date_info = session.data.date_mapping[text]
            session.update("selected_date", selected_date_info["date"])
            session.data.selected_date_slots = selected_date_info["slots"]
            
            formatted_times, time_mapping = await format_time_slots_for_selection(
                selected_date_info["slots"]
            )
            
            if formatted_times:
                session.data.time_mapping = time_mapping
                session.question_phase = "time_selection"
                
                message = f"""
✅ *Date selected: {selected_date_info['formatted_date']}*
⏰ *Available time slots:*
{formatted_times}
Please type the number of the time slot you want to select (e.g., '1'):
                """
                await say(message)
            else:
                await say(f"❌ No time slots available for {selected_date_info['formatted_date']}.")
        else:
            formatted_dates, _ = await format_slots_for_date_selection(session.data.available_slots)
            await say(f"""
❌ Invalid selection. Please choose a valid date number:
{formatted_dates}
Type the number (e.g., '1'):
            """)
    
    async def handle_time_selection(self, session, text, say):
        """Handle time slot selection"""
        if text.isdigit() and text in session.data.time_mapping:
            selected_time_info = session.data.time_mapping[text]
            session.update("selected_time", selected_time_info["time_slot"])
            
            available_offices = await self.supabase_client.get_available_offices(session.data.district)
            if available_offices:
                session.data.available_offices = available_offices
                session.question_phase = "office_selection"
                
                offices_text = "\n".join(f"• {office}" for office in available_offices)
                message = f"""
✅ *Time slot selected: {selected_time_info['time_slot']}*
🏢 *Available offices in {session.data.district}:*
{offices_text}
Please type the office name you want to select:
                """
                await say(message)
            else:
                await self.move_to_next_phase(session, say)
        else:
            formatted_times, _ = await format_time_slots_for_selection(session.data.selected_date_slots)
            await say(f"""
❌ Invalid selection. Please choose a valid time slot number:
{formatted_times}
Type the number (e.g., '1'):
            """)
    
    async def handle_office_selection(self, session, text, say):
        """Handle office selection"""
        available_offices = session.data.available_offices or []
        selected_office = None
        
        for office in available_offices:
            if text.lower() in office.lower() or office.lower() in text.lower():
                selected_office = office
                break
        
        if selected_office:
            session.update("office", selected_office)
            await say(f"✅ Office selected: *{selected_office}*")
            await self.move_to_next_phase(session, say)
        else:
            offices_text = "\n".join(f"• {office}" for office in available_offices)
            await say(f"""
❌ Office not found. Available offices in {session.data.district}:
{offices_text}
Please type the office name exactly as shown:
            """)
    
    async def move_to_next_phase(self, session, say):
        """Move to next question phase"""
        if session.additional_renewal_questions:
            session.question_phase = "renewal_info"
            session.step = 0
            await say("🔄 *Passport Renewal Information:*")
            await say(QUESTIONS_RENEWAL[0][1])
        else:
            session.question_phase = "demographic_info"
            session.step = 0
            await say("✅ *Appointment scheduled!*\nNow I need your personal details.")
            await say(QUESTIONS_DEMOGRAPHIC_INFO[0][1])
    
    async def handle_renewal_info(self, session, text, say):
        """Handle renewal information questions"""
        key = QUESTIONS_RENEWAL[session.step][0]
        session.update(key, text)
        session.step += 1

        if session.step >= len(QUESTIONS_RENEWAL):
            session.question_phase = "demographic_info"
            session.step = 0
            await say("✅ *Renewal information collected!*\nNow I need your personal details.")
            await say(QUESTIONS_DEMOGRAPHIC_INFO[0][1])
        else:
            await say(QUESTIONS_RENEWAL[session.step][1])
    
    async def handle_demographic_info(self, session, text, say):
        """Handle demographic information questions"""
        key = QUESTIONS_DEMOGRAPHIC_INFO[session.step][0]
        session.update(key, text)
        session.step += 1

        if session.step >= len(QUESTIONS_DEMOGRAPHIC_INFO):
            session.question_phase = "citizen_info"
            session.step = 0
            await say("✅ *Demographic information collected!*\nNow I need your citizenship details.")
            await say(QUESTIONS_CITIZEN_INFO[0][1])
        else:
            await say(QUESTIONS_DEMOGRAPHIC_INFO[session.step][1])
    
    async def handle_citizen_info(self, session, text, say):
        """Handle citizenship information questions"""
        key = QUESTIONS_CITIZEN_INFO[session.step][0]
        session.update(key, text)
        session.step += 1

        if session.step >= len(QUESTIONS_CITIZEN_INFO):
            session.question_phase = "contact_info"
            session.step = 0
            await say("✅ *Citizenship information collected!*\nNow I need your contact details.")
            await say(QUESTIONS_CONTACT_INFO[0][1])
        else:
            await say(QUESTIONS_CITIZEN_INFO[session.step][1])
    
    async def handle_contact_info(self, session, text, say):
        """Handle contact information questions"""
        key = QUESTIONS_CONTACT_INFO[session.step][0]
        session.update(key, text)
        session.step += 1

        if session.step >= len(QUESTIONS_CONTACT_INFO):
            session.question_phase = "emergency_info"  # CHANGED: contact → emergency
            session.step = 0
            await say("✅ *Contact information collected!*\nNow I need emergency contact details.")
            await say(QUESTIONS_EMERGENCY_INFO[0][1])
        else:
            await say(QUESTIONS_CONTACT_INFO[session.step][1])
    
    async def handle_emergency_info(self, session, text, say):
        """Handle emergency contact information questions"""
        key = QUESTIONS_EMERGENCY_INFO[session.step][0]
        session.update(key, text)
        session.step += 1
    
        if session.step >= len(QUESTIONS_EMERGENCY_INFO):
            await self.start_automation(session, say)
        else:
            await say(QUESTIONS_EMERGENCY_INFO[session.step][1])

    async def start_automation(self, session, say):
        """Start the passport automation process"""
        app_type = session.data.application_type
        district = session.data.district
        office = session.data.office
        selected_date = session.data.selected_date
        selected_time = session.data.selected_time
        
        # Get name from UserData attributes
        first_name = getattr(session.data, 'firstName', '') or getattr(session.data, 'first_name', '')
        last_name = getattr(session.data, 'lastName', '') or getattr(session.data, 'last_name', '')
        
        summary = f"""
📋 *Application Summary:*
• Type: {'Renewal' if app_type == 'renewal' else 'First Issuance'}
• District: {district}
• Office: {office}
• Date: {selected_date}
• Time: {selected_time}
• Name: {first_name} {last_name}
        """
        
        await say(summary)
        
        if app_type == "renewal":
            await say("🔄 *Starting automated passport RENEWAL process...*")
        else:
            await say("🔄 *Starting automated NEW PASSPORT application...*")
        
        success, message = await self.form_filler.automate_passport_application(
            session.data.to_dict(),
            session.user_id,
            say
        )
        
        if success:
            await say(f"🎉 *Automation completed successfully for <@{session.user_id}>!*")
        else:
            await say(f"❌ *Automation failed:* {message}")
        
        self.session_manager.delete_session(session.user_id)