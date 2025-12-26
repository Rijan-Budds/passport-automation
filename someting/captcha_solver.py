
import io
from PIL import Image
from transformers import VisionEncoderDecoderModel, TrOCRProcessor

class CaptchaSolver:
    def __init__(self):
        self.processor = TrOCRProcessor.from_pretrained("anuashok/ocr-captcha-v3")
        self.model = VisionEncoderDecoderModel.from_pretrained("anuashok/ocr-captcha-v3")
    
    async def solve_captcha(self, screenshot_bytes):
        """Solve captcha using TrOCR model"""
        try:
            image = Image.open(io.BytesIO(screenshot_bytes)).convert("RGBA")
            background = Image.new("RGBA", image.size, (255, 255, 255))
            combined = Image.alpha_composite(background, image).convert("RGB")
            
            pixel_values = self.processor(combined, return_tensors="pt").pixel_values
            generated_ids = self.model.generate(pixel_values)
            text = self.processor.batch_decode(generated_ids, skip_special_tokens=True)[0]
            
            return ''.join(filter(str.isalnum, text))
        except Exception as e:
            print(f"❌ Error solving captcha: {e}")
            return ""
    
    async def handle_captcha_failure(self, page, say, attempt):
        """Handle captcha failure by closing error dialog"""
        try:
            await say(f"🔄 Handling captcha failure for attempt {attempt}...")
            
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
            
            reload_button_selectors = [
                "span.reload-btn",
                "button#reload-captcha",
                "button:has-text('Reload')",
                "img.captcha-img"
            ]
            
            for selector in reload_button_selectors:
                try:
                    reload_btn = await page.wait_for_selector(selector, timeout=3000)
                    if reload_btn:
                        await reload_btn.click()
                        await say("🔄 Captcha reloaded.")
                        await page.wait_for_timeout(2000)
                        break
                except:
                    continue
            
            return True
            
        except Exception as e:
            await say(f"❌ Error handling captcha failure: {e}")
            return False