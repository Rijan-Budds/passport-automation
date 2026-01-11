import io
from PIL import Image, ImageOps, ImageEnhance, ImageFilter
from transformers import VisionEncoderDecoderModel, TrOCRProcessor
import torch

IMAGE_PATH = "/home/rijan/.gemini/antigravity/brain/614716fe-bcb0-4bf7-b365-75f79a54ac0c/uploaded_image_1767362573646.png"

def preprocess_image(image_path, method="default"):
    with open(image_path, "rb") as f:
        image_bytes = f.read()
    
    image = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
    background = Image.new("RGBA", image.size, (255, 255, 255))
    image = Image.alpha_composite(background, image).convert("RGB")
    
    if method == "grayscale":
        image = image.convert("L").convert("RGB")
    elif method == "contrast":
        enhancer = ImageEnhance.Contrast(image)
        image = enhancer.enhance(2.0)
    elif method == "sharpen":
        enhancer = ImageEnhance.Contrast(image)
        image = enhancer.enhance(2.0)
        image = image.filter(ImageFilter.SHARPEN)
    elif method == "binary":
        image = image.convert("L")
        image = image.point(lambda x: 0 if x < 140 else 255, '1').convert("RGB")
        
    return image

def test_model(model_name, image):
    print(f"Testing model: {model_name}")
    try:
        processor = TrOCRProcessor.from_pretrained(model_name)
        model = VisionEncoderDecoderModel.from_pretrained(model_name)
        
        pixel_values = processor(image, return_tensors="pt").pixel_values
        generated_ids = model.generate(pixel_values)
        text = processor.batch_decode(generated_ids, skip_special_tokens=True)[0]
        return text
    except Exception as e:
        return f"Error: {e}"

def main():
    models = [
        "anuashok/ocr-captcha-v3",
        "microsoft/trocr-base-printed",
        # "microsoft/trocr-small-printed"
    ]
    
    preprocessing_methods = ["default", "grayscale", "contrast", "sharpen", "binary"]
    
    print(f"Target Text: kw2ym (Manual read from screenshot)")
    print("-" * 50)
    
    for method in preprocessing_methods:
        print(f"\nExample Preprocessing: {method}")
        image = preprocess_image(IMAGE_PATH, method)
        
        for model_name in models:
            result = test_model(model_name, image)
            print(f"Model: {model_name} | Result: '{result}'")

if __name__ == "__main__":
    main()
