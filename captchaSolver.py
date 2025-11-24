import asyncio
from playwright.async_api import async_playwright
from transformers import VisionEncoderDecoderModel, TrOCRProcessor
from PIL import Image
import io
import os

print("Loading TrOCR model...")
processor = TrOCRProcessor.from_pretrained("anuashok/ocr-captcha-v3")
model = VisionEncoderDecoderModel.from_pretrained("anuashok/ocr-captcha-v3")
print("Model loaded successfully!")


async def solve_captcha_with_trocr(screenshot_bytes):
    try:
        image = Image.open(io.BytesIO(screenshot_bytes)).convert("RGBA")
        background = Image.new("RGBA", image.size, (255, 255, 255))
        combined = Image.alpha_composite(background, image).convert("RGB")

        pixel_values = processor(combined, return_tensors="pt").pixel_values
        generated_ids = model.generate(pixel_values)
        generated_text = processor.batch_decode(generated_ids, skip_special_tokens=True)[0]

        cleaned_text = ''.join(filter(str.isalnum, generated_text))
        return cleaned_text

    except Exception as e:
        print("Error solving captcha:", e)
        return None


async def refresh_captcha(page):
    selectors = [
        "span.material-icons.reload-btn",
        "button.refresh-captcha",
        ".captcha-refresh",
        "[class*='refresh']",
        "button[title*='refresh' i]"
    ]

    for s in selectors:
        btn = await page.query_selector(s)
        if btn:
            await btn.click()
            await page.wait_for_timeout(1500)
            print("🔄 Captcha refreshed")
            return True

    print("⚠ No refresh button found!")
    return False


async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        await page.goto("https://emrtds.nepalpassport.gov.np")

        # FIRST ISSUANCE
        await page.wait_for_selector("text=First Issuance")
        await page.click("text=First Issuance")

        # PASSPORT TYPE
        await page.wait_for_selector("label.main-doc-types")
        await page.click("label.main-doc-types:has-text('Ordinary 34 pages')")

        # PROCEED
        await page.wait_for_selector("text=Proceed")
        await page.click("text=Proceed")

        # CONSENT POPUP
        try:
            await page.wait_for_selector("mat-dialog-container", timeout=5000)
            await page.click("mat-dialog-container >> text=I agree स्वीकृत छ")
        except:
            pass

        # WAIT FOR APPOINTMENT PAGE
        await page.wait_for_url("**/appointment", timeout=15000)

        # SELECT COUNTRY, PROVINCE, DISTRICT, LOCATION
        selects = await page.query_selector_all("mat-select")
        await selects[0].click()
        await page.click("mat-option >> text=Nepal")
        await selects[1].click()
        await page.click("mat-option >> text=Bagmati")
        await selects[2].click()
        await page.click("mat-option >> text=Makawanpur")
        await selects[3].click()
        await page.click("mat-option >> text=Makawanpur")

        # DATE PICKER
        try:
            date_input = await page.wait_for_selector(
                "input[placeholder*='Date' i], input[type='text'][formcontrolname*='date' i]",
                timeout=5000
            )
            await date_input.click()
            await page.wait_for_selector(".ui-datepicker-calendar")
            first_date = await page.wait_for_selector(
                "td:not(.ui-datepicker-other-month):not(.ui-state-disabled) a"
            )
            await first_date.click()
        except:
            print("Date auto-selected.")

        # TIME SLOT
        await page.wait_for_selector(".ui-datepicker-calendar-container mat-chip-list")
        slots = await page.query_selector_all("mat-chip.mat-chip:not(.mat-chip-disabled)")
        if slots:
            await slots[0].click()

        # CAPTCHA SOLVING
        print("\n==============================")
        print(" STARTING CAPTCHA SOLVER ")
        print("==============================\n")

        os.makedirs("captchas", exist_ok=True)
        max_attempts = 10

        for attempt in range(1, max_attempts + 1):
            print(f"\n🎯 Attempt {attempt}/{max_attempts}")

            try:
                # GET CAPTCHA IMAGE
                captcha_img = await page.wait_for_selector("img.captcha-img", timeout=8000)
                screenshot_bytes = await captcha_img.screenshot()

                # SAVE IMAGE
                save_path = f"captchas/captcha_{attempt}.png"
                with open(save_path, "wb") as f:
                    f.write(screenshot_bytes)
                print(f"📸 Saved: {save_path}")

                # SOLVE CAPTCHA
                captcha_text = await solve_captcha_with_trocr(screenshot_bytes)
                print("🤖 OCR:", captcha_text)

                if not captcha_text or len(captcha_text) < 4:
                    print("❌ Invalid OCR → refreshing captcha...")
                    await refresh_captcha(page)
                    continue

                # ENTER CAPTCHA
                captcha_input = await page.wait_for_selector(
                    "input.captcha-text, input[name='text']",
                    state="visible",
                    timeout=12000
                )
                await captcha_input.fill("")
                await captcha_input.type(captcha_text, delay=80)
                print("⌨ Entered:", captcha_text)
                await page.wait_for_timeout(1000)

                # CLICK NEXT BUTTON (wait until enabled)
                try:
                    next_btn = await page.wait_for_selector(
                        "a.btn.btn-primary:not(.appt-disabled)",
                        timeout=8000
                    )
                    await next_btn.click()
                except:
                    print("⚠ Next button not enabled yet")

                # WAIT A MOMENT
                await page.wait_for_timeout(2000)

                # CHECK IF WRONG CAPTCHA POPUP APPEARS
                close_btn = await page.query_selector("button#landing-button-2:has-text('Close')")
                if close_btn:
                    print("❌ Captcha was wrong! Closing popup and refreshing...")
                    await close_btn.click()
                    await refresh_captcha(page)
                    continue  # retry

                # OTHERWISE, captcha likely correct
                current = page.url
                if "application" in current or "form" in current:
                    print("\n🎉 CAPTCHA SUCCESS! Application page loaded!")
                    break

            except Exception as e:
                print("⚠ Error in attempt:", e)
                await refresh_captcha(page)
                continue

        await page.wait_for_timeout(3000)
        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
