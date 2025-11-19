import asyncio
from playwright.async_api import async_playwright
import base64
from PIL import Image, ImageEnhance, ImageFilter
import io
import re
import cv2
import numpy as np
import random
from collections import Counter
import os

# Check and import OCR libraries
def setup_ocr():
    try:
        import easyocr
        reader = easyocr.Reader(['en'], gpu=True)
        print("✓ Using EasyOCR with GPU acceleration")
        return reader, 'easyocr'
    except Exception as e:
        print(f"EasyOCR GPU failed: {e}")
        try:
            import easyocr
            reader = easyocr.Reader(['en'], gpu=False)
            print("⚠ Using EasyOCR with CPU")
            return reader, 'easyocr'
        except ImportError:
            try:
                import pytesseract
                print("⚠ Using Pytesseract for captcha solving")
                return pytesseract, 'pytesseract'
            except ImportError:
                print("✗ No OCR library found")
                return None, None

# Initialize OCR
ocr_engine, ocr_type = setup_ocr()

async def enhanced_preprocess_captcha(image_bytes):
    """Enhanced preprocessing for CAPTCHA images with better character recognition"""
    img = Image.open(io.BytesIO(image_bytes))
    
    # Convert to OpenCV format
    img_cv = np.array(img.convert('RGB'))
    img_cv = cv2.cvtColor(img_cv, cv2.COLOR_RGB2BGR)
    gray = cv2.cvtColor(img_cv, cv2.COLOR_BGR2GRAY)
    
    processed_images = []
    
    # Technique 1: Basic Otsu threshold
    _, th1 = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    processed_images.append(th1)
    
    # Technique 2: Adaptive Gaussian (better for variable lighting)
    th2 = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY, 11, 2)
    processed_images.append(th2)
    
    # Technique 3: Adaptive Mean
    th3 = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_MEAN_C, cv2.THRESH_BINARY, 11, 2)
    processed_images.append(th3)
    
    # Technique 4: Morphological operations to enhance characters
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (2,2))
    closed = cv2.morphologyEx(th1, cv2.MORPH_CLOSE, kernel)
    processed_images.append(closed)
    
    # Technique 5: Denoising
    denoised = cv2.fastNlMeansDenoising(th1)
    processed_images.append(denoised)
    
    # Technique 6: Sharpen the image
    kernel_sharp = np.array([[-1,-1,-1], [-1,9,-1], [-1,-1,-1]])
    sharpened = cv2.filter2D(th1, -1, kernel_sharp)
    processed_images.append(sharpened)
    
    # Technique 7: High contrast with different levels
    for alpha in [1.5, 2.0, 2.5]:
        high_contrast = cv2.convertScaleAbs(gray, alpha=alpha, beta=0)
        _, high_contrast_th = cv2.threshold(high_contrast, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        processed_images.append(high_contrast_th)
    
    # Technique 8: Resize with different factors for better character recognition
    for factor in [3, 4]:
        large = cv2.resize(th1, None, fx=factor, fy=factor, interpolation=cv2.INTER_CUBIC)
        processed_images.append(large)
    
    return processed_images

async def solve_captcha_advanced(captcha_base64):
    """Advanced CAPTCHA solving with multiple techniques - PRESERVES CASE"""
    
    if not ocr_engine:
        return None
        
    image_bytes = base64.b64decode(captcha_base64)
    processed_images = await enhanced_preprocess_captcha(image_bytes)
    
    all_results = []
    
    for i, processed_img in enumerate(processed_images):
        if ocr_type == 'easyocr':
            # Convert to bytes for EasyOCR
            _, buffer = cv2.imencode('.png', processed_img)
            img_bytes = buffer.tobytes()
            
            # Multiple OCR configurations
            configs = [
                {'paragraph': False, 'width_ths': 0.3, 'text_threshold': 0.4},
                {'paragraph': True, 'width_ths': 0.5, 'text_threshold': 0.5},
                {'paragraph': False, 'width_ths': 1.0, 'text_threshold': 0.7},
            ]
            
            for config in configs:
                try:
                    result = ocr_engine.readtext(img_bytes, detail=0, **config)
                    text = ''.join(result).strip()
                    # DON'T convert to uppercase - preserve original case
                    text = re.sub(r'[^a-zA-Z0-9]', '', text)
                    if text and 3 <= len(text) <= 8:
                        all_results.append(text)
                except Exception as e:
                    continue
                    
        elif ocr_type == 'pytesseract':
            # Try different PSM modes for pytesseract
            for psm in [7, 8, 13, 6]:
                try:
                    text = ocr_engine.image_to_string(
                        processed_img, 
                        config=f'--psm {psm} -c tessedit_char_whitelist=0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz'
                    )
                    text = re.sub(r'[^a-zA-Z0-9]', '', text)
                    if text and 5 <= len(text) <= 7:
                        all_results.append(text)
                except:
                    pass
    
    # Filter and rank results - PRESERVE ORIGINAL CASE
    valid_results = []
    for text in all_results:
        text = text.strip()  # Remove .upper() to preserve case
      # CAPTCHA is always exactly 5 characters (letters + digits)
        if len(text) == 5 and re.match(r'^[A-Za-z0-9]+$', text):
            valid_results.append(text)

    
    if not valid_results:
        valid_results = [text for text in all_results if 3 <= len(text) <= 8]  # Keep original case
    
    if valid_results:
        counter = Counter(valid_results)
        best_result = counter.most_common(1)[0][0]
        
        print(f"🔍 OCR variants: {list(set(valid_results))}")
        print(f"🎯 Selected: {best_result} (confidence: {counter[best_result]}/{len(valid_results)})")
        return best_result  # Return with original case
    
    return None

async def get_captcha_data(page):
    """Get CAPTCHA image data from page"""
    captcha_data = {}
    
    # Method 1: Direct image element
    captcha_selectors = [
        "img[src*='captcha']",
        "img[alt*='captcha' i]",
        ".captcha-image",
        "[class*='captcha'] img",
        "img[src*='base64']"
    ]
    
    for selector in captcha_selectors:
        try:
            captcha_img = await page.query_selector(selector)
            if captcha_img:
                src = await captcha_img.get_attribute('src')
                if src and 'base64,' in src:
                    captcha_data['image'] = src.split('base64,')[1]
                    print("✓ CAPTCHA captured from image element")
                    return captcha_data
        except:
            continue
    
    # Method 2: Network interception
    response_data = {}
    
    async def capture_response(response):
        if 'captcha' in response.url.lower():
            try:
                json_data = await response.json()
                if 'captchaImage' in json_data:
                    response_data.update({
                        'image': json_data['captchaImage'],
                        'id': json_data.get('captchaId', '')
                    })
            except:
                pass
    
    page.on('response', capture_response)
    await page.wait_for_timeout(3000)
    page.remove_listener('response', capture_response)
    
    if response_data:
        captcha_data.update(response_data)
        print(f"✓ CAPTCHA captured from API: {response_data.get('id', 'Unknown')}")
    
    return captcha_data

async def refresh_captcha(page):
    """Refresh CAPTCHA using the exact refresh button selector"""
    try:
        # Exact selector for the refresh button
        refresh_btn = await page.query_selector("span.material-icons.reload-btn")
        if refresh_btn:
            await refresh_btn.click()
            print("🔄 CAPTCHA refreshed using reload button")
            await page.wait_for_timeout(2000)
            return True
        else:
            print("❌ Refresh button not found")
            return False
    except Exception as e:
        print(f"❌ Error refreshing CAPTCHA: {e}")
        return False

async def fill_captcha_input(page, solution):
    """Fill CAPTCHA input field with case handling"""
    # Try multiple selectors for CAPTCHA input
    input_selectors = [
        "input[name='text']",
        "input.captcha-text",
        "input[class*='captcha']",
        "input[placeholder*='captcha' i]",
        "input[formcontrolname*='captcha']",
        "input[type='text']"
    ]
    
    captcha_input = None
    for selector in input_selectors:
        captcha_input = await page.query_selector(selector)
        if captcha_input:
            break
    
    if not captcha_input:
        print("❌ Could not find CAPTCHA input field")
        return False
    
    try:
        # Clear the field first
        await captcha_input.click()
        await page.wait_for_timeout(200)
        await captcha_input.fill('')
        await page.wait_for_timeout(200)
        
        # Try different case strategies
        strategies = [
            solution,           # Original case
            solution.upper(),   # Uppercase
            solution.lower(),   # Lowercase
        ]
        
        for strategy in strategies:
            await captcha_input.fill('')
            await captcha_input.fill(strategy)
            await page.wait_for_timeout(500)
            
            # Check what was actually entered
            current_value = await captcha_input.input_value()
            print(f"🔍 Trying '{strategy}' -> input contains: '{current_value}'")
            
            if current_value == strategy:
                print(f"✓ Strategy worked: {strategy}")
                return True
        
        # If no strategy worked, use the original solution
        await captcha_input.fill('')
        await captcha_input.fill(solution)
        print(f"✓ Using original solution: {solution}")
        return True
        
    except Exception as e:
        print(f"❌ Error filling CAPTCHA: {e}")
        return False

async def click_submit_button(page):
    """Click the submit/next button"""
    # Try multiple strategies to find and click the Next button
    
    # Strategy 1: Exact selector from your HTML
    next_button = await page.query_selector("a.btn.btn-primary")
    if next_button:
        try:
            button_text = await next_button.text_content()
            if 'Next' in button_text:
                print(f"✓ Found Next button: '{button_text.strip()}'")
                await next_button.click()
                print("✓ Next button clicked")
                return True
        except:
            pass
    
    # Strategy 2: Look for any element with btn-primary class
    next_buttons = await page.query_selector_all(".btn-primary")
    for button in next_buttons:
        try:
            text = await button.text_content()
            if text and ('Next' in text or 'अर्को' in text):
                print(f"✓ Found Next button via class: '{text.strip()}'")
                await button.click()
                print("✓ Next button clicked")
                return True
        except:
            continue
    
    # Strategy 3: Try all possible selectors
    submit_selectors = [
        "a.btn.btn-primary:has-text('Next')",
        "a:has-text('Next')",
        "button:has-text('Next')",
        "button:has-text('अर्को')",
        "button[type='submit']",
        "button.btn-primary",
        "input[type='submit']"
    ]
    
    for selector in submit_selectors:
        try:
            submit_button = await page.query_selector(selector)
            if submit_button:
                is_visible = await submit_button.is_visible()
                is_enabled = await submit_button.is_enabled()
                if is_visible and is_enabled:
                    button_text = await submit_button.text_content()
                    print(f"✓ Found submit button using: {selector} - '{button_text.strip()}'")
                    await submit_button.click()
                    print("✓ Submit button clicked")
                    return True
        except:
            continue
    
    print("❌ Could not find or click submit button")
    return False

async def solve_captcha_automated(page, max_attempts=50):
    """Fully automated CAPTCHA solving"""
    
    attempt = 0
    while attempt < max_attempts:
        attempt += 1
        print(f"\n🔄 Attempt {attempt}/{max_attempts}")
        
        # Get CAPTCHA data
        captcha_data = await get_captcha_data(page)
        
        if 'image' not in captcha_data:
            print("❌ No CAPTCHA found, trying to refresh...")
            await refresh_captcha(page)
            continue
        
        # Solve CAPTCHA with OCR
        solution = await solve_captcha_advanced(captcha_data['image'])
        
        if not solution:
            print("❌ OCR failed, refreshing CAPTCHA...")
            await refresh_captcha(page)
            continue
        
        print(f"🤖 Trying: '{solution}'")
        
        # Fill CAPTCHA input
        if not await fill_captcha_input(page, solution):
            continue
        
        # Click submit button
        if not await click_submit_button(page):
            continue
        
        print("✓ Submitted CAPTCHA, waiting for response...")
        
        # Wait and check result
        await page.wait_for_timeout(3000)
        
        # Check for success (navigated away from appointment page)
        current_url = page.url
        if 'appointment' not in current_url:
            print(f"\n🎉 SUCCESS! CAPTCHA solved in {attempt} attempts!")
            print(f"🎉 Navigated to: {current_url}")
            return True
        
        # Check for error modal
        error_modal = await page.query_selector(
            "button:has-text('Close'), button[mat-dialog-close], .mat-dialog-container"
        )
        
        if error_modal:
            print("❌ CAPTCHA incorrect, closing error modal...")
            try:
                close_btn = await page.query_selector("button:has-text('Close'), button[mat-dialog-close]")
                if close_btn:
                    await close_btn.click()
                    await page.wait_for_timeout(1000)
            except:
                pass
        
        # Refresh CAPTCHA for next attempt
        await refresh_captcha(page)
        
        # Small random delay to avoid detection
        await page.wait_for_timeout(random.randint(1000, 3000))
    
    print(f"\n💥 Failed to solve CAPTCHA after {max_attempts} attempts")
    return False

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=['--disable-blink-features=AutomationControlled']
        )
        
        page = await browser.new_page()
        await page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => undefined });
        """)
        
        try:
            await page.goto("https://emrtds.nepalpassport.gov.np", wait_until='networkidle')
            print("✓ Page loaded")
            
            # Navigate through initial steps
            await page.wait_for_selector("text=First Issuance", timeout=15000)
            await page.click("text=First Issuance")
            print("✓ First Issuance")
            
            await page.wait_for_selector("label.main-doc-types", timeout=15000)
            await page.click("label.main-doc-types:has-text('Ordinary 34 pages')")
            print("✓ Passport type")
            
            await page.wait_for_selector("text=Proceed", timeout=15000)
            await page.click("text=Proceed")
            print("✓ Proceed")
            
            # Consent modal
            try:
                await page.wait_for_selector("mat-dialog-container", timeout=5000)
                await page.click("mat-dialog-container >> text=I agree स्वीकृत छ")
                print("✓ Consent accepted")
            except:
                print("⚠ No consent modal")
            
            await page.wait_for_url("**/appointment", timeout=20000)
            print("✓ Appointment page loaded")
            
            # Fill location details
            await page.wait_for_selector("mat-select", timeout=15000)
            all_selects = await page.query_selector_all("mat-select")
            
            await all_selects[0].click()
            await page.click("mat-option >> text=Nepal")
            
            await all_selects[1].click()
            await page.click("mat-option >> text=Bagmati")
            
            await all_selects[2].click()
            await page.click("mat-option >> text=Nuwakot")
            
            await all_selects[3].click()
            await page.click("mat-option >> text=Nuwakot")
            print("✓ Location filled")
            
            # Select time slot
            try:
                await page.wait_for_selector("mat-chip:not([disabled])", timeout=5000)
                time_slots = await page.query_selector_all("mat-chip:not([disabled])")
                if time_slots:
                    await time_slots[0].click()
                    slot_text = await time_slots[0].text_content()
                    print(f"✓ Time slot selected: {slot_text}")
            except:
                print("⚠ No time slots or already selected")
            
            # Start automated CAPTCHA solving
            print("\n" + "="*60)
            print("🚀 STARTING FULLY AUTOMATED CAPTCHA SOLVING")
            print("="*60)
            
            success = await solve_captcha_automated(page, max_attempts=50)
            
            if success:
                print("\n🎉🎉🎉 CAPTCHA SOLVED AUTOMATICALLY! 🎉🎉🎉")
            else:
                print("\n💥 Maximum attempts reached")
            
            # Keep browser open
            print("Browser will remain open for 60 seconds...")
            await page.wait_for_timeout(60000)
            
        except Exception as e:
            print(f"❌ Main process error: {e}")
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(main())