from datetime import datetime, timedelta

def get_valid_dates(days_ahead=7):
    """Return list of dates skipping Saturdays"""
    valid_dates = []
    for i in range(days_ahead):
        date = datetime.now() + timedelta(days=i)
        if date.weekday() == 5:  # skip Saturday
            continue
        valid_dates.append(date.strftime("%Y-%m-%d"))
    return valid_dates
