from fastapi import FastAPI
from app.models import ChatRequest
from app.agent import session_service, course_agent
import uuid

app = FastAPI(title="Course Agent API (Powered by Google ADK)")

APP_NAME = "course_implementation_app"

@app.post("/api/v1/chat-plan")
async def interact_with_plan(request: ChatRequest):
    try:
        # 1. TẠO HOẶC LẤY SESSION (Start or Resume)
        current_session_id = request.session_id
        
        if not current_session_id:
            # Tạo mới nếu chưa có
            current_session_id = str(uuid.uuid4())
            session = await session_service.create_session(
                app_name=APP_NAME,
                user_id=request.user_id,
                session_id=current_session_id,
                state={"revision_count": 0, "plan_status": "Drafting"} # Khởi tạo State
            )
        else:
            # Lấy lại session cũ
            session = await session_service.get_session(
                app_name=APP_NAME,
                user_id=request.user_id,
                session_id=current_session_id
            )

        # 2. CẬP NHẬT STATE (Tùy chọn: Tăng biến đếm số lần sửa)
        current_revisions = session.state.get("revision_count", 0)
        session.state["revision_count"] = current_revisions + 1
        if current_revisions > 0:
            session.state["plan_status"] = "Revising"

        # 3. CHẠY AGENT VỚI SESSION NÀY
        # Agent sẽ tự động đọc lịch sử (events) và trạng thái (state) từ session
        response = await course_agent.run(
            session=session,
            user_message=request.message
        )
        
        # 4. LƯU LẠI SESSION XUỐNG SERVICE (Save Interaction)
        await session_service.update_session(session)

        return {
            "status": "success",
            "session_id": session.id,
            "state_info": session.state, # Trả về state để Client (Frontend) thấy
            "data": {
                "response": response.text
            }
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}