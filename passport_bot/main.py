import asyncio
import os
from dotenv import load_dotenv
from slack_bolt.adapter.socket_mode.aiohttp import AsyncSocketModeHandler
from services.slack_handler import SlackHandler
from config.settings import SLACK_APP_TOKEN

# Load environment variables
load_dotenv(".env.dev")

async def main():
    """Main entry point for the bot"""
    # Initialize Slack handler
    slack_handler = SlackHandler()
    
    # Start Socket Mode handler
    handler = AsyncSocketModeHandler(
        slack_handler.app, 
        SLACK_APP_TOKEN
    )
    
    print("🚀 Passport Automation Bot running!")
    print("💬 DM the bot to get started")
    
    await handler.start_async()

if __name__ == "__main__":
    asyncio.run(main())