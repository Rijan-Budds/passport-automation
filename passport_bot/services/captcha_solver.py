import io
from PIL import Image
from transformers import VisionEncoderDecoderModel, TrOCRProcessor

class CaptchaSolver:
    """Handles CAPTCHA solving using TrOCR model"""
    
    def __init__(self):
        self.processor = TrOCRProcessor.from_pretrained("anuashok/ocr-captcha-v3")
        self.model = VisionEncoderDecoderModel.from_pretrained("anuashok/ocr-captcha-v3")
    
    async def solve_captcha(self, screenshot_bytes: bytes) -> str:
        """Solve CAPTCHA from screenshot bytes"""
        try:
            # Open and process image
            image = Image.open(io.BytesIO(screenshot_bytes)).convert("RGBA")
            background = Image.new("RGBA", image.size, (255, 255, 255))
            combined = Image.alpha_composite(background, image).convert("RGB")
            
            # Process with TrOCR model
            pixel_values = self.processor(combined, return_tensors="pt").pixel_values
            generated_ids = self.model.generate(pixel_values)
            text = self.processor.batch_decode(generated_ids, skip_special_tokens=True)[0]
            
            # Clean text (keep only alphanumeric)
            return ''.join(filter(str.isalnum, text))
        except Exception as e:
            print(f"Error solving CAPTCHA: {e}")
            return ""