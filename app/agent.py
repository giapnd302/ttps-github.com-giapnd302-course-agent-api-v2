import os
import google.generativeai as genai
from dotenv import load_dotenv

# Load biến môi trường từ file .env
load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

# Định nghĩa System Prompt ép kiểu đầu ra
system_instruction = """
Bạn là một Chuyên gia Thiết kế Chương trình Đào tạo (Instructional Designer) cấp cao.
Nhiệm vụ của bạn là nhận thông tin và tạo ra một Implementation Plan (Kế hoạch triển khai cấu trúc khóa học).
BẮT BUỘC TRẢ VỀ KẾT QUẢ ĐỊNH DẠNG MARKDOWN.
Trong kết quả bắt buộc phải có các mục sau ở phần đầu:
- Tên khóa học: ...
- Độ dài khóa học (thời lượng): ...
- Tổng số Chapter / Unit / Activity: ...
- Độ khó khóa học: (Beginner/Intermediate/Advanced)
Sau đó là chi tiết cấu trúc các module.
"""

# Khởi tạo model với System Instruction
model = genai.GenerativeModel(
    model_name="gemini-1.5-flash", # Dùng bản flash cho nhanh và rẻ
    system_instruction=system_instruction
)

def generate_plan(request_data) -> str:
    # Gom thông tin đầu vào thành prompt cho AI
    user_prompt = f"""
    Hãy tạo cấu trúc khóa học cho chủ đề: '{request_data.topic}'.
    Đối tượng học viên: {request_data.target_audience}.
    Số lượng module dự kiến: {request_data.estimated_modules}.
    Thông tin thêm: {request_data.additional_info}
    """
    response = model.generate_content(user_prompt)
    return response.text