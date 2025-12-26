import asyncio
from playwright.async_api import async_playwright
from transformers import VisionEncoderDecoderModel, TrOCRProcessor
from PIL import Image
import io

# ==============================
# LOAD OCR MODEL
# ==============================
print("🔄 Loading TrOCR captcha model...")
processor = TrOCRProcessor.from_pretrained("anuashok/ocr-captcha-v3")
model = VisionEncoderDecoderModel.from_pretrained("anuashok/ocr-captcha-v3")
print("✅ TrOCR model loaded!")

# ==============================
# CAPTCHA SOLVER
# ==============================
async def solve_captcha(image_bytes):
    image = Image.open(io.BytesIO(image_bytes)).convert("RGBA")
    bg = Image.new("RGBA", image.size, (255, 255, 255))
    image = Image.alpha_composite(bg, image).convert("RGB")

    pixel_values = processor(image, return_tensors="pt").pixel_values
    ids = model.generate(pixel_values)
    text = processor.batch_decode(ids, skip_special_tokens=True)[0]

    return "".join(filter(str.isalnum, text))


async def refresh_captcha(page):
    for selector in [
        "span.material-icons.reload-btn",
        "button.refresh-captcha",
        ".captcha-refresh"
    ]:
        btn = await page.query_selector(selector)
        if btn:
            await btn.click()
            await page.wait_for_timeout(1500)
            print("🔄 Captcha refreshed")
            return True
    return False

# ==============================
# MAIN AUTOMATION
# ==============================
async def automate_passport():
    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            slow_mo=50
        )
        page = await browser.new_page()

        try:
            await page.goto("https://emrtds.nepalpassport.gov.np")

            # FIRST ISSUANCE
            await page.click("text=First Issuance")
            await page.click("label.main-doc-types:has-text('Ordinary 34 pages')")
            await page.click("text=Proceed")

            # CONSENT
            try:
                await page.wait_for_selector("mat-dialog-container", timeout=5000)
                await page.click("text=I agree")
            except:
                pass

            await page.wait_for_url("**/appointment")
            print("📅 Appointment page loaded")

            selects = await page.query_selector_all("mat-select")

            # LOCATION SELECTION
            await selects[0].click()
            await page.click("mat-option >> text=Nepal")
            await selects[1].click()
            await page.click("mat-option >> text=Bagmati")
            await selects[2].click()
            await page.click("mat-option >> text=Kathmandu")
            await selects[3].click()
            await page.click("mat-option >> text=Kathmandu")

            # ==============================
            # AUTO-SELECT FIRST AVAILABLE DATE
            # ==============================
            print("📅 Selecting first available date...")
            await page.wait_for_selector("a.ui-state-default:not(.ui-state-disabled)")
            first_date = await page.query_selector("a.ui-state-default:not(.ui-state-disabled)")
            if first_date:
                await first_date.click()
                print("✅ Date selected automatically")
            else:
                print("⚠ No available date found")

            # ==============================
            # AUTO-SELECT FIRST AVAILABLE TIME SLOT
            # ==============================
            print("⏰ Selecting first available time slot...")
            await page.wait_for_selector("mat-chip:not(.mat-chip-disabled)")
            slots = await page.query_selector_all("mat-chip:not(.mat-chip-disabled)")
            if slots:
                await slots[0].click()
                print("✅ Time slot selected automatically")
            else:
                print("⚠ No available slots found")

            # ==============================
            # CAPTCHA SOLVING WITH RETRY
            # ==============================
            print("🤖 Solving captcha...")
            for attempt in range(1, 11):
                print(f"🎯 Attempt {attempt}/10")
                captcha_img = await page.wait_for_selector("img.captcha-img")
                img_bytes = await captcha_img.screenshot()
                text = await solve_captcha(img_bytes)
                print("🤖 OCR:", text)

                if not text or len(text) < 4:
                    await refresh_captcha(page)
                    continue

                input_box = await page.wait_for_selector("input.captcha-text")
                await input_box.fill("")
                await input_box.type(text, delay=80)

                # CLICK NEXT BUTTON
                next_btn = await page.query_selector("a.btn.btn-primary:not(.appt-disabled)")
                if next_btn:
                    await next_btn.click()

                await page.wait_for_timeout(2000)

                # CHECK IF CAPTCHA FAILED
                close_btn = await page.query_selector("#landing-button-2")
                if close_btn:
                    print("❌ Captcha was wrong, closing popup and retrying...")
                    await close_btn.click()
                    await refresh_captcha(page)
                    continue

                if "application" in page.url or "form" in page.url:
                    print("🎉 Application form loaded!")
                    break

            print("📝 Ready to fill application form")

            await page.wait_for_timeout(5000)

        except Exception as e:
            print("❌ Error:", e)

        finally:
            await browser.close()

# ==============================
# RUN
# ==============================
if __name__ == "__main__":
    asyncio.run(automate_passport())
