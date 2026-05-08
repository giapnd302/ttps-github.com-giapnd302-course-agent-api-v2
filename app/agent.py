import os
from dotenv import load_dotenv
from google.adk.sessions import DatabaseSessionService # Đổi từ InMemory sang Database
from google.adk.agents import LlmAgent

load_dotenv()

# 1. KHỞI TẠO SESSION SERVICE (DÙNG DATABASE SQLITE)
# Tài liệu ADK bắt buộc dùng 'sqlite+aiosqlite' cho async driver
db_url = "sqlite+aiosqlite:///./course_agent.db"
session_service = DatabaseSessionService(db_url=db_url)

# 2. ĐỊNH NGHĨA PROMPT CÓ CHỨA STATE TEMPLATE
AGENT_INSTRUCTIONS = """
Bạn là một Chuyên gia Thiết kế Chương trình Đào tạo cấp cao.
Nhiệm vụ của bạn là nhận thông tin, trò chuyện với người dùng và tạo ra/chỉnh sửa một Implementation Plan.
BẮT BUỘC TRẢ VỀ KẾT QUẢ ĐỊNH DẠNG MARKDOWN.

TRẠNG THÁI PHIÊN LÀM VIỆC HIỆN TẠI (Đọc kỹ thông tin này):
- Số lần người dùng đã yêu cầu chỉnh sửa: {revision_count}
- Trạng thái kế hoạch: {plan_status}

Nếu người dùng yêu cầu chỉnh sửa, hãy nhớ cấu trúc cũ và chỉ in ra bản kế hoạch đã được cập nhật mới nhất.
"""

# 3. KHỞI TẠO ADK AGENT
course_agent = LlmAgent(
    model="gemini-flash-latest",
    name="course_creator_agent",
    instruction=AGENT_INSTRUCTIONS,
)