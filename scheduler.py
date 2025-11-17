from apscheduler.schedulers.background import BackgroundScheduler
from datetime import datetime, time as dt_time, timedelta
from jobs import check_passport_job

scheduler = BackgroundScheduler()

def dynamic_scheduler():
    now = datetime.now().time()
    start_fast = dt_time(10, 0)
    end_fast = dt_time(10, 5)
    interval_seconds = 5 if start_fast <= now <= end_fast else 180

    scheduler.add_job(
        dynamic_scheduler,
        'date',
        run_date=datetime.now() + timedelta(seconds=interval_seconds)
    )

    check_passport_job()
    print(f"Next check in {interval_seconds} seconds.")

def start_scheduler():
    scheduler.start()
    dynamic_scheduler()
