from pydantic import BaseModel
from typing import Optional

class ChatRequest(BaseModel):
    session_id: Optional[str] = None # ID phiên làm việc
    user_id: str = "default_user"    # ADK yêu cầu phải có user_id
    message: str                     # Câu lệnh của người dùng