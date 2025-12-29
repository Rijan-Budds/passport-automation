# CSS Selectors for Nepal Passport Website
SELECTORS = {
    # Initial Page
    "first_issuance_button": "text=First Issuance",
    "renewal_button": "text=Passport Renewal",
    "passport_type_regular": "label.main-doc-types:has-text('Regular')",
    "passport_type_diplomatic": "label.main-doc-types:has-text('Diplomatic')",
    "passport_type_official": "label.main-doc-types:has-text('Official')",
    "proceed_button": "text=Proceed",
    "agree_button": "mat-dialog-container >> text=I agree स्वीकृत छ",
    
    # Appointment Page
    "mat_select": "mat-select",
    "nepal_option": "mat-option:has-text('Nepal')",
    "date_input": "input[placeholder*='Date' i]",
    "date_picker_calendar": ".ui-datepicker-calendar",
    "available_date": "td:not(.ui-datepicker-other-month):not(.ui-state-disabled) a",
    "time_slots_container": ".ui-datepicker-calendar-container mat-chip-list",
    "time_slot": "mat-chip.mat-chip:not(.mat-chip-disabled)",
    
    # CAPTCHA
    "captcha_image": "img.captcha-img",
    "captcha_input": "input.captcha-text, input[name='text']",
    "captcha_next_button": "a.btn.btn-primary",
    "captcha_close_button": "button#landing-button-2, button.btn-primary:has-text('Close')",
    "captcha_reload": "span.reload-btn, button#reload-captcha, button:has-text('Reload')",
    
    # Form Navigation
    "next_button": "button:has-text('Next'), a.btn-primary:has-text('Next'), button:has-text('Continue')",
    
    # Form Sections
    "personal_info_header": "text=Personal Information, text=Applicant Details",
    "citizenship_section": "h5:has-text('CITIZENSHIP INFORMATION'), h5:has-text('नागरिकता सम्बन्धी जानकारी')",
    
    # Form Fields - Generic
    "input_field": "input[name='{field}'], input[formcontrolname='{field}'], #{field}",
    "dropdown_field": "mat-select[formcontrolname='{field}'], mat-select[name='{field}'], select[name='{field}']",
    "mat_option": "mat-option",
    
    # Renewal Specific
    "old_passport_field": "input[name='oldPassportNumber'], input[formcontrolname='oldPassportNumber']",
    "currentTDNum_field": "input[formcontrolname='currentTDNum']",
    "currentTDIssueDate_field": "input[formcontrolname='currentTDIssueDate']",
    "currenttdIssuePlaceDistrict_field": "mat-select[formcontrolname='currenttdIssuePlaceDistrict']",
}