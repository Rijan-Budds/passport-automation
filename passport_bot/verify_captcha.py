import asyncio
import os
from services.captcha_solver import CaptchaSolver

async def main():
    solver = CaptchaSolver()
    
    # Path to the user provided image
    image_path = "/home/rijan/.gemini/antigravity/brain/614716fe-bcb0-4bf7-b365-75f79a54ac0c/uploaded_image_1767362573646.png"
    
    if not os.path.exists(image_path):
        print(f"Error: Image not found at {image_path}")
        return

    print(f"Testing CAPTCHA solver with image: {image_path}")
    
    with open(image_path, "rb") as f:
        image_bytes = f.read()
    
    result = await solver.solve_captcha(image_bytes)
    print(f"Result: '{result}'")

if __name__ == "__main__":
    asyncio.run(main())
