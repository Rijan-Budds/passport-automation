"""
Main entry point for the passport automation bot
"""

import asyncio
import os
from dotenv import load_dotenv
from slack_bolt.async_app import AsyncApp
from slack_bolt.adapter.socket_mode.aiohttp import AsyncSocketModeHandler

# Import all modules
from supabase_client import SupabaseClient
from website_scraper import WebsiteScraper
from form_filler import FormFiller
from captcha_solver import CaptchaSolver
from passport_automator import PassportAutomator
from slack_handler import SlackHandler

# Load environment
load_dotenv(".env.dev")

class PassportBot:
    def __init__(self):
        # Initialize all components
        self.supabase_client = SupabaseClient()
        self.website_scraper = WebsiteScraper()
        self.form_filler = FormFiller()
        self.captcha_solver = CaptchaSolver()
        
        # Create automator with dependencies
        self.passport_automator = PassportAutomator(
            self.captcha_solver,
            self.form_filler
        )
        
        # Create Slack handler
        self.slack_handler = SlackHandler(
            self.supabase_client,
            self.website_scraper,
            self.passport_automator
        )
        
        # Initialize Slack app
        self.app = AsyncApp(
            token=os.environ.get("SLACK_BOT_TOKEN"),
            signing_secret=os.environ.get("SLACK_SIGNING_SECRET")
        )
        
        # Register event handler
        @self.app.event("message")
        async def handle_message(event, say):
            await self.slack_handler.handle_message(event, say)
    
    async def run(self):
        """Start the bot"""
        handler = AsyncSocketModeHandler(self.app, os.environ.get("SLACK_APP_TOKEN"))
        print("🚀 Passport Automation Bot running! DM 'start' to begin.")
        await handler.start_async()

if __name__ == "__main__":
    bot = PassportBot()
    asyncio.run(bot.run())