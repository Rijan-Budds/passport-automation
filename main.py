from fastapi import FastAPI
from scheduler import start_scheduler
from jobs import manual_check_job
from waiting_room_handler import start_waiting_room_worker, waiting_room_queue

app = FastAPI(title="Passport Slot Checker API")

@app.on_event("startup")
def startup_event():
    # Start the waiting room handler first
    start_waiting_room_worker()
    # Then start the scheduler
    start_scheduler()

@app.get("/")
def root():
    return {
        "status": "running",
        "message": "Passport Slot Checker API is running"
    }

@app.get("/check_slots")
def manual_check():
    """Manually trigger a slot check"""
    manual_check_job()
    return {
        "status": "success",
        "message": "Manual slot check completed"
    }

@app.get("/waiting_room_queue")
def check_queue():
    """Check waiting room queue status"""
    return {
        "queue_size": waiting_room_queue.qsize(),
        "message": f"{waiting_room_queue.qsize()} tasks currently in waiting room queue"
    }