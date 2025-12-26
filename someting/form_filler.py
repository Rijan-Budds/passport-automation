import asyncio

class FormFiller:
    async def fill_personal_information(self, page, user_data, user_id, say):
        """Fill the personal information form"""
        try:
            await say("📝 Starting to fill personal information form...")
            
            await page.wait_for_selector("form", timeout=10000)
            
            form_fields = {
                "firstName": user_data.get("first_name", ""),
                "middleName": user_data.get("middle_name", ""),
                "lastName": user_data.get("last_name", ""),
                "email": user_data.get("email", ""),
                "phone": user_data.get("phone", ""),
                "citizenshipNumber": user_data.get("citizenship_number", ""),
                "dateOfBirth": user_data.get("dob", ""),
            }
            
            filled_fields = 0
            for field_name, value in form_fields.items():
                if value:
                    try:
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
                    except Exception as e:
                        await say(f"⚠️ Could not fill {field_name}: {e}")
            
            dropdown_fields = {
                "gender": user_data.get("gender", "Male"),
                "maritalStatus": user_data.get("marital_status", "Unmarried"),
                "education": user_data.get("education", "Bachelor"),
            }
            
            for field_name, value in dropdown_fields.items():
                try:
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
                except Exception as e:
                    await say(f"⚠️ Could not select {field_name}: {e}")
            
            await say(f"✅ Personal information form filled successfully! ({filled_fields} fields)")
            return True
            
        except Exception as e:
            await say(f"❌ Error filling personal information: {e}")
            return False
    
    async def fill_address_information(self, page, user_data, user_id, say):
        """Fill the address information form"""
        try:
            await say("🏠 Starting to fill address information...")
            
            address_fields = {
                "permanentDistrict": user_data.get("permanent_district", user_data.get("district", "")),
                "permanentMunicipality": user_data.get("permanent_municipality", ""),
                "permanentWard": user_data.get("permanent_ward", ""),
                "permanentTole": user_data.get("permanent_tole", ""),
                "currentDistrict": user_data.get("current_district", user_data.get("district", "")),
                "currentMunicipality": user_data.get("current_municipality", user_data.get("permanent_municipality", "")),
                "currentWard": user_data.get("current_ward", user_data.get("permanent_ward", "")),
                "currentTole": user_data.get("current_tole", user_data.get("permanent_tole", "")),
            }
            
            filled_fields = 0
            for field_name, value in address_fields.items():
                if value:
                    try:
                        selectors = [
                            f"input[name='{field_name}']",
                            f"input[formcontrolname='{field_name}']",
                            f"#{field_name}",
                            f"mat-select[formcontrolname='{field_name}']"
                        ]
                        
                        for selector in selectors:
                            try:
                                field = await page.wait_for_selector(selector, timeout=1000)
                                if field:
                                    if "mat-select" in selector:
                                        await field.click()
                                        await page.wait_for_selector("mat-option", timeout=2000)
                                        option = await page.query_selector(f"mat-option:has-text('{value}')")
                                        if option:
                                            await option.click()
                                    else:
                                        await field.fill(value)
                                    
                                    await say(f"✅ Filled {field_name}")
                                    filled_fields += 1
                                    break
                            except:
                                continue
                    except Exception as e:
                        await say(f"⚠️ Could not fill {field_name}: {e}")
            
            await say(f"✅ Address information filled successfully! ({filled_fields} fields)")
            return True
            
        except Exception as e:
            await say(f"❌ Error filling address information: {e}")
            return False
    
    async def fill_family_information(self, page, user_data, user_id, say):
        """Fill family information form"""
        try:
            await say("👨‍👩‍👧‍👦 Starting to fill family information...")
            
            family_fields = {
                "fatherName": user_data.get("father_name", ""),
                "motherName": user_data.get("mother_name", ""),
                "spouseName": user_data.get("spouse_name", ""),
            }
            
            filled_fields = 0
            for field_name, value in family_fields.items():
                if value:
                    try:
                        selectors = [
                            f"input[name='{field_name}']",
                            f"input[formcontrolname='{field_name}']",
                            f"#{field_name}"
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
                    except Exception as e:
                        await say(f"⚠️ Could not fill {field_name}: {e}")
            
            await say(f"✅ Family information filled successfully! ({filled_fields} fields)")
            return True
            
        except Exception as e:
            await say(f"❌ Error filling family information: {e}")
            return False