import asyncio

async def emergency_info(page, user_data, user_id, say):
    """Fill the emergency contact information form"""
    try:
        await say("🆘 Starting to fill emergency information...")
        
        # Wait for the form to be visible
        await page.wait_for_selector("form", timeout=10000)
        
        # Field mapping: question_key -> form_field_name
        field_mapping = {
            "contactLastName": "contactLastName",
            "contactFirstName": "contactFirstName",
            "contactHouseNum": "contactHouseNum",
            "contactStreetVillage": "contactStreetVillage",
            "contactWard": "contactWard",
            "contactProvince": "contactProvince",
            "contactDistrict": "contactDistrict",
            "contactMunicipality": "contactMunicipality",
            "contactPhone": "contactPhone"
        }
        
        filled_fields = 0
        for question_key, form_field in field_mapping.items():
            value = user_data.get(question_key, "")
            if not value:
                continue
            
            # Try different selector patterns
            selectors = [
                f"input[name='{form_field}']",
                f"input[formcontrolname='{form_field}']",
                f"#{form_field}",
                f"input[placeholder*='{form_field}']"
            ]
            
            field_filled = False
            for selector in selectors:
                try:
                    field = await page.wait_for_selector(selector, timeout=1000)
                    if field:
                        await field.fill(value)
                        await say(f"✅ Filled {form_field}")
                        filled_fields += 1
                        field_filled = True
                        break
                except:
                    continue
            
            # If field not found with normal selectors
            if not field_filled and value:
                try:
                    # Search for any input with similar name
                    all_inputs = await page.query_selector_all("input")
                    for inp in all_inputs:
                        placeholder = await inp.get_attribute("placeholder") or ""
                        name = await inp.get_attribute("name") or ""
                        formcontrolname = await inp.get_attribute("formcontrolname") or ""
                        
                        if (form_field.lower() in placeholder.lower() or 
                            form_field.lower() in name.lower() or 
                            form_field.lower() in formcontrolname.lower()):
                            await inp.fill(value)
                            await say(f"✅ Found and filled {form_field}")
                            filled_fields += 1
                            break
                except:
                    pass
        
        await say(f"✅ Emergency information filled! ({filled_fields} fields)")
        return True
        
    except Exception as e:
        await say(f"❌ Error filling emergency information: {e}")
        return False