import asyncio

async def demographic_information(page, user_data, user_id, say):
    """Fill the personal information form on the next page"""
    try:
        await say("📝 Starting to fill demographic information form...")
        
        # Debug: Check page content
        try:
            await page.screenshot(path="debug_demographic_start.png")
            print("📸 Saved demographic page screenshot")
        except:
            pass

        # Wait for the form to be visible
        try:
            await page.wait_for_selector("form", timeout=10000)
        except Exception as e:
            await say(f"⚠️ Could not find 'form' element. Page might be structured differently.")
            # Dump page source to file for inspection
            content = await page.content()
            with open("debug_demographic_page.html", "w") as f:
                f.write(content)
            await say("📄 Saved page HTML to debug_demographic_page.html")
            raise e
        
        # ------------------------------
        # 1️⃣ Handle missing gender
        # ------------------------------
        if "gender" not in user_data:
            print("⚠️ Gender not in user data, defaulting to 'M'")
            user_data["gender"] = "M"
        
        # ------------------------------
        # 2️⃣ Handle missing exact DOB flag
        # ------------------------------
        if "isExactDateOfBirth" not in user_data:
            print("⚠️ isExactDateOfBirth not in user data, defaulting to 'true'")
            user_data["isExactDateOfBirth"] = "true"
        
        # ------------------------------
        # 3️⃣ Fill text inputs
        # ------------------------------
        form_fields = {
            "firstName": user_data.get("first_name", ""),
            "lastName": user_data.get("last_name", ""),
            "dateOfBirth": user_data.get("dob", ""),
            "dateOfBirthBS": user_data.get("dob_bs",""),
            "birthDistrict": user_data.get("birth_district",""),
            "fatherLastName": user_data.get("father_last_name", ""),
            "fatherFirstName": user_data.get("father_first_name", ""),
            "motherLastName": user_data.get("mother_last_name", ""),
            "motherFirstName": user_data.get("mother_first_name", "")
        }
        
        filled_fields = 0
        for field_name, value in form_fields.items():
            if not value:
                continue
            selectors = [
                f"input[name='{field_name}']",
                f"input[formcontrolname='{field_name}']",
                f"#{field_name}",
                f"input[placeholder*='{field_name.title()}']",
                f"input[placeholder*='{field_name}']"
            ]
            field_filled = False
            for selector in selectors:
                try:
                    # Increased timeout to 3s
                    field = await page.wait_for_selector(selector, timeout=3000)
                    if field:
                        await field.scroll_into_view_if_needed()
                        await field.fill("") # Clear first
                        await field.fill(value)
                        
                        # Trigger events for Angular
                        await page.evaluate('''
                            (element) => {
                                element.dispatchEvent(new Event('input', { bubbles: true }));
                                element.dispatchEvent(new Event('change', { bubbles: true }));
                                element.dispatchEvent(new Event('blur', { bubbles: true }));
                            }
                        ''', field)
                        
                        print(f"✅ Filled {field_name}")
                        filled_fields += 1
                        field_filled = True
                        break
                except Exception as e:
                    # print(f"Debug: Selector {selector} failed: {e}")
                    continue
            
            if not field_filled:
                print(f"⚠️ Failed to fill field: {field_name}")
        
        # ------------------------------
        # 4️⃣ Handle radio buttons
        # ------------------------------
        # Gender radio
        gender_value = user_data.get("gender", "M")
        try:
            gender_selector = f"input[formcontrolname='gender'][value='{gender_value}']"
            gender_radio = await page.wait_for_selector(gender_selector, timeout=2000)
            if gender_radio:
                await gender_radio.check()
                await say(f"✅ Selected gender: {gender_value}")
                filled_fields += 1
        except Exception as e:
            await say(f"⚠️ Could not select gender radio: {e}")
        
        # Exact DOB radio
        dob_radio_value = user_data.get("isExactDateOfBirth", "true")
        try:
            dob_selector = f"input[formcontrolname='isExactDateOfBirth'][value='{dob_radio_value}']"
            dob_radio = await page.wait_for_selector(dob_selector, timeout=2000)
            if dob_radio:
                await dob_radio.check()
                await say(f"✅ Selected exact DOB: {dob_radio_value}")
                filled_fields += 1
        except Exception as e:
            await say(f"⚠️ Could not select exact DOB radio: {e}")
        
        # ------------------------------
        # 5️⃣ Handle dropdowns
        # ------------------------------
        dropdown_fields = {
            "maritalStatus": user_data.get("marital_status", "Unmarried"),
            "education": user_data.get("education", "Bachelor"),
        }
        
        for field_name, value in dropdown_fields.items():
            dropdown_selectors = [
                f"mat-select[formcontrolname='{field_name}']",
                f"mat-select[name='{field_name}']",
                f"select[name='{field_name}']"
            ]
            for selector in dropdown_selectors:
                try:
                    dropdown = await page.wait_for_selector(selector, timeout=1000)
                    if dropdown:
                        await dropdown.click()
                        await page.wait_for_selector("mat-option", timeout=2000)
                        option = await page.query_selector(f"mat-option:has-text('{value}')")
                        if option:
                            await option.click()
                            await say(f"✅ Selected {field_name}: {value}")
                            filled_fields += 1
                        break
                except:
                    continue
        
        await say(f"✅ Personal information form filled successfully! ({filled_fields} fields)")
        return True
        
    except Exception as e:
        await say(f"❌ Error filling personal information: {e}")
        return False
