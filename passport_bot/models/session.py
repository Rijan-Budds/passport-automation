from typing import Dict, Any
from models.user_data import UserData

class UserSession:
    """Manages user conversation state"""
    
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.data = UserData()
        self.step: int = 0
        self.question_phase: str = "pre_captcha"
        self.additional_renewal_questions: bool = False
        self.additional_data: Dict[str, Any] = {}  # For temporary storage
    
    def update(self, key: str, value: Any):
        """Update user data"""
        if hasattr(self.data, key):
            setattr(self.data, key, value)
        else:
            self.additional_data[key] = value
    
    def get(self, key: str, default=None) -> Any:
        """Get value from user data"""
        if hasattr(self.data, key):
            return getattr(self.data, key)
        return self.additional_data.get(key, default)


class SessionManager:
    """Manages all user sessions"""
    
    def __init__(self):
        self.sessions: Dict[str, UserSession] = {}
    
    def get_session(self, user_id: str) -> UserSession:
        """Get or create user session"""
        if user_id not in self.sessions:
            self.sessions[user_id] = UserSession(user_id)
        return self.sessions[user_id]
    
    def delete_session(self, user_id: str):
        """Delete user session"""
        if user_id in self.sessions:
            del self.sessions[user_id]