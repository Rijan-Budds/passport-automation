from fastapi import FastAPI
from scheduler import start_scheduler
from jobs import manual_check_job

app = FastAPI(title="Passport Slot Checker API")

@app.on_event("startup")
def startup_event():
    start_scheduler()

@app.get("/check_slots")
def manual_check():
    manual_check_job()
    return {"status": "manual_check_done", "message": "Passport check executed manually."}
