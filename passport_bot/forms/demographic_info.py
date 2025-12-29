import asyncio

async def demographic_information(page, user_data, user_id, say):
    """Fill the personal information form on the next page"""
    try:
        await say("📝 Starting to fill demographic information form...")
        
        # Wait for the form to be visible
        await page.wait_for_selector("form", timeout=10000)
        
        # ------------------------------
        # 1️⃣ Ask for gender if missing
        # ------------------------------
        if "gender" not in user_data:
            while True:
                gender = input("Enter your gender (M for Male, F for Female, X for Other): ").upper()
                if gender in ["M", "F", "X"]:
                    user_data["gender"] = gender
                    break
                else:
                    print("Invalid input. Please type M, F, or X.")
        
        # ------------------------------
        # 2️⃣ Ask for exact DOB if missing
        # ------------------------------
        if "isExactDateOfBirth" not in user_data:
            while True:
                dob_exact = input("Is your date of birth exact? (Y/N): ").upper()
                if dob_exact in ["Y", "N"]:
                    user_data["isExactDateOfBirth"] = "true" if dob_exact == "Y" else "false"
                    break
                else:
                    print("Invalid input. Please type Y or N.")
        
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
            for selector in selectors:
                try:
                    field = await page.wait_for_selector(selector, timeout=1000)
                    if field:
                        await field.fill(value)
                        await say(f"✅ Filled {field_name}")
                        filled_fields += 1
                        break
                except:
                    continue
        
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
