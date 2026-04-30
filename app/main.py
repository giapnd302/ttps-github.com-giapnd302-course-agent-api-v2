from fastapi import FastAPI
from app.models import CourseRequest
from app.agent import generate_plan

app = FastAPI(title="Course Implementation Agent API")

@app.post("/api/v1/generate-plan")
async def create_course_plan(request: CourseRequest):
    try:
        # Gọi hàm xử lý từ agent.py
        plan_markdown = generate_plan(request)
        return {
            "status": "success",
            "message": "Đã tạo kế hoạch thành công",
            "data": {
                "implementation_plan_markdown": plan_markdown
            }
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}