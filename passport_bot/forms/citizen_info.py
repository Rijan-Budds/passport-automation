async def citizen_information(page, user_data, user_id, say):
    """Fill the citizenship information form"""
    try:
        await say("🆔 Starting to fill citizenship information...")
        await page.wait_for_selector("form", timeout=10000)
        
        # Field mapping: question_key -> form_field_name
        field_mapping = {
            "nin": "nin",
            "citizen_num": "citizenNum",  # Map snake_case to camelCase
            "citizen_issue_date_bs": "citizenIssueDateBS",
            "citizen_issue_place_district": "citizenIssuePlaceDistrict"
        }
        
        filled_fields = 0
        for question_key, form_field in field_mapping.items():
            value = user_data.get(question_key, "")
            if not value:
                continue
            
            selectors = [
                f"input[name='{form_field}']",
                f"input[formcontrolname='{form_field}']",
                f"#{form_field}"
            ]
            
            for selector in selectors:
                try:
                    field = await page.wait_for_selector(selector, timeout=1000)
                    if field:
                        await field.fill(value)
                        await say(f"✅ Filled {form_field}")
                        filled_fields += 1
                        break
                except:
                    continue
        
        await say(f"✅ Citizenship information filled! ({filled_fields} fields)")
        return True
        
    except Exception as e:
        await say(f"❌ Error filling citizenship information: {e}")
        return False