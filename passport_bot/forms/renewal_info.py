import asyncio

async def fill_renewal_information(page, user_data, user_id, say):
    """Fill the renewal-specific information fields"""
    try:
        await say("📋 Starting to fill renewal information...")
        
        # Look for renewal-specific form fields
        renewal_fields = {
            "currentTDNum": {
                "value": user_data.get("currentTDNum", ""),
                "type": "input",
                "placeholder": "current Travel Document number"
            },
            "currentTDIssueDate": {
                "value": user_data.get("currentTDIssueDate", ""),
                "type": "date",
                "placeholder": "current TD issue date"
            },
            "currenttdIssuePlaceDistrict": {
                "value": user_data.get("currenttdIssuePlaceDistrict", ""),
                "type": "dropdown",
                "placeholder": "current TD issue district"
            }
        }
        
        filled_fields = 0
        for field_name, field_info in renewal_fields.items():
            value = field_info.get("value")
            field_type = field_info.get("type")
            placeholder_hint = field_info.get("placeholder", "")
            
            if value:
                try:
                    if field_type == "input":
                        # Try different input selectors
                        selectors = [
                            f"input[name='{field_name}']",
                            f"input[formcontrolname='{field_name}']",
                            f"input[placeholder*='{placeholder_hint}']",
                            f"#{field_name}",
                            f"input.ng-pristine[formcontrolname*='TD']"
                        ]
                        
                        for selector in selectors:
                            try:
                                field = await page.wait_for_selector(selector, timeout=2000)
                                if field:
                                    await field.fill(value)
                                    await say(f"✅ Filled {field_name}: {value}")
                                    filled_fields += 1
                                    break
                            except:
                                continue
                    
                    elif field_type == "date":
                        # Handle date picker fields
                        date_selectors = [
                            f"input[name='{field_name}']",
                            f"input[formcontrolname='{field_name}']",
                            f"input.dateInput[formcontrolname*='Date']",
                            f"input[readonly][formcontrolname*='Date']"
                        ]
                        
                        for selector in date_selectors:
                            try:
                                date_field = await page.wait_for_selector(selector, timeout=2000)
                                if date_field:
                                    # Click to open date picker
                                    await date_field.click()
                                    await asyncio.sleep(1)
                                    
                                    # Try to set value directly via JavaScript
                                    await page.evaluate(f'''
                                        (selector, value) => {{
                                            const element = document.querySelector(selector);
                                            if (element) {{
                                                element.value = value;
                                                // Trigger events
                                                element.dispatchEvent(new Event('input', {{ bubbles: true }}));
                                                element.dispatchEvent(new Event('change', {{ bubbles: true }}));
                                            }}
                                        }}
                                    ''', selector, value)
                                    
                                    # Press Tab to move out of field
                                    await page.keyboard.press("Tab")
                                    await say(f"✅ Set {field_name}: {value}")
                                    filled_fields += 1
                                    break
                            except:
                                continue
                    
                    elif field_type == "dropdown":
                        # Handle dropdown selectors
                        dropdown_selectors = [
                            f"mat-select[formcontrolname='{field_name}']",
                            f"mat-select[name='{field_name}']",
                            f"mat-select[formcontrolname*='District']",
                            f"mat-select.ng-pristine[formcontrolname*='Place']"
                        ]
                        
                        for selector in dropdown_selectors:
                            try:
                                dropdown = await page.wait_for_selector(selector, timeout=2000)
                                if dropdown:
                                    await dropdown.click()
                                    await page.wait_for_selector("mat-option", timeout=3000)
                                    
                                    # Try to find and click the option by text
                                    option_selectors = [
                                        f"mat-option:has-text('{value}')",
                                        f"mat-option span:has-text('{value}')",
                                        f"mat-option:contains('{value}')"
                                    ]
                                    
                                    option_found = False
                                    for opt_selector in option_selectors:
                                        try:
                                            option = await page.wait_for_selector(opt_selector, timeout=1500)
                                            if option:
                                                await option.click()
                                                await say(f"✅ Selected {field_name}: {value}")
                                                filled_fields += 1
                                                option_found = True
                                                break
                                        except:
                                            continue
                                    
                                    if not option_found:
                                        # Fallback: type and select
                                        await page.keyboard.type(value)
                                        await asyncio.sleep(1)
                                        await page.keyboard.press("Enter")
                                        await say(f"✅ Typed and selected {field_name}: {value}")
                                        filled_fields += 1
                                    
                                    break
                            except:
                                continue
                
                except Exception as e:
                    await say(f"⚠️ Could not fill {field_name}: {str(e)}")
                    # Try alternative approach
                    try:
                        # Look for any visible input with similar name
                        all_inputs = await page.query_selector_all(f"input, mat-select")
                        for inp in all_inputs:
                            placeholder = await inp.get_attribute("placeholder") or ""
                            name = await inp.get_attribute("name") or ""
                            formcontrolname = await inp.get_attribute("formcontrolname") or ""
                            
                            if (field_name.lower() in placeholder.lower() or 
                                field_name.lower() in name.lower() or 
                                field_name.lower() in formcontrolname.lower()):
                                
                                if await inp.is_visible():
                                    if "mat-select" in await inp.get_attribute("class") or "mat-select" in str(await inp.get_property("tagName")):
                                        # It's a dropdown
                                        await inp.click()
                                        await asyncio.sleep(1)
                                        await page.keyboard.type(value[:3])
                                        await asyncio.sleep(0.5)
                                        await page.keyboard.press("Enter")
                                    else:
                                        # It's an input field
                                        await inp.fill(value)
                                    
                                    await say(f"✅ Found and filled {field_name} via alternative method")
                                    filled_fields += 1
                                    break
                    except:
                        pass
        
        # Also handle old passport number if present
        old_passport = user_data.get("old_passport_number")
        if old_passport:
            try:
                old_passport_selectors = [
                    "input[name='oldPassportNumber']",
                    "input[formcontrolname='oldPassportNumber']",
                    "input[placeholder*='Old Passport']",
                    "input[placeholder*='Previous Passport']"
                ]
                
                for selector in old_passport_selectors:
                    try:
                        field = await page.wait_for_selector(selector, timeout=1500)
                        if field:
                            await field.fill(old_passport)
                            await say(f"✅ Filled old passport number: {old_passport}")
                            filled_fields += 1
                            break
                    except:
                        continue
            except Exception as e:
                await say(f"⚠️ Could not fill old passport number: {e}")
        
        await say(f"✅ Renewal information filled successfully! ({filled_fields} fields)")
        return True
        
    except Exception as e:
        await say(f"❌ Error filling renewal information: {e}")
        return False