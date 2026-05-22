from fastapi import FastAPI
from app.models import ChatRequest
from app.auth import get_password_hash, verify_password, create_access_token
from pydantic import BaseModel
import aiosqlite
from app.agent import session_service, course_agent
from google.adk.runners import Runner   # Thư viện Người quản lý
from google.genai import types          # Thư viện định dạng tin nhắn của Google
from fastapi.middleware.cors import CORSMiddleware
import uuid
class UserCreate(BaseModel):
    username: str
    password: str

app = FastAPI(title="Course Agent API (Powered by Google ADK)")
# ======== THÊM ĐOẠN NÀY ĐỂ MỞ CỬA CHO FRONTEND GỌI API ========
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Cho phép mọi nguồn gọi đến (để test cho dễ)
    allow_credentials=True,
    allow_methods=["*"], # Cho phép GET, POST...
    allow_headers=["*"],
)
# ===============================================================

# ... (Giữ nguyên các code bên dưới)

APP_NAME = "course_implementation_app"

# KHỞI TẠO RUNNER (Trái tim điều phối của hệ thống ADK)
agent_runner = Runner(
    app_name=APP_NAME,
    agent=course_agent,
    session_service=session_service
)

@app.post("/api/v1/chat-plan")
async def interact_with_plan(request: ChatRequest):
    try:
        current_session_id = request.session_id
        
        # 1. TẠO HOẶC LẤY SESSION ĐỂ CẬP NHẬT TRẠNG THÁI (STATE)
        if not current_session_id:
            current_session_id = str(uuid.uuid4())
            session = await session_service.create_session(
                app_name=APP_NAME,
                user_id=request.user_id,
                session_id=current_session_id,
                state={"revision_count": 0, "plan_status": "Drafting"} 
            )
        else:
            session = await session_service.get_session(
                app_name=APP_NAME,
                user_id=request.user_id,
                session_id=current_session_id
            )
            
            if session is None:
                return {
                    "status": "error", 
                    "message": f"Không tìm thấy dữ liệu cho session_id: '{current_session_id}'. Vui lòng để trống session_id để tạo mới."
                }
                
            # Cập nhật State (Trạng thái)
            current_revisions = session.state.get("revision_count", 0)
            session.state["revision_count"] = current_revisions + 1
            if current_revisions > 0:
                session.state["plan_status"] = "Revising"
            
            #await session_service.update_session(session)

        # 2. ĐÓNG GÓI TIN NHẮN THEO CHUẨN ADK
        content = types.Content(role='user', parts=[types.Part(text=request.message)])

        # 3. CHẠY AGENT THÔNG QUA "RUNNER" THAY VÌ GỌI TRỰC TIẾP
        events = agent_runner.run_async(
            user_id=request.user_id,
            session_id=current_session_id,
            new_message=content
        )
        
        # 4. CHỜ AGENT CHẠY XONG VÀ LẤY KẾT QUẢ CUỐI CÙNG
        final_answer = ""
        async for event in events:
            # ADK sẽ nhả ra nhiều luồng sự kiện, mình chỉ lấy kết quả Final
            if hasattr(event, 'is_final_response') and event.is_final_response():
                if event.content and event.content.parts:
                    final_answer = event.content.parts[0].text
                    final_answer = ""
        async for event in events:
            if hasattr(event, 'is_final_response') and event.is_final_response():
                if event.content and event.content.parts:
                    final_answer = event.content.parts[0].text

        # ==========================================
        # ĐẾM ƯỚC LƯỢNG VÀ LƯU TOKEN VÀO DATABASE
        # (1 từ ~ 1.3 token)
        # ==========================================
        word_count = len(request.message.split()) + len(final_answer.split())
        estimated_tokens = int(word_count * 1.3)

        async with aiosqlite.connect("./course_agent.db") as db:
            await db.execute("""
                INSERT INTO token_usage (username, total_tokens) 
                VALUES (?, ?) 
                ON CONFLICT(username) DO UPDATE SET total_tokens = total_tokens + ?
            """, (request.user_id, estimated_tokens, estimated_tokens))
            await db.commit()
        # ==========================================

        return {
            "status": "success",
            "session_id": current_session_id,
            "data": {
                "response": final_answer
            }
        }

        return {
            "status": "success",
            "session_id": current_session_id,
            "data": {
                "response": final_answer
            }
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}
    
    # ==========================================
# CÁC API MỚI PHỤC VỤ CHO FRONTEND UI
# ==========================================

@app.get("/api/v1/sessions/{user_id}")
async def get_user_sessions(user_id: str):
    """API 1: Lấy danh sách lịch sử các cuộc trò chuyện (Phục vụ cho Sidebar bên trái)"""
    try:
        # Lấy danh sách session từ Database của ADK
        sessions = await session_service.list_sessions(app_name=APP_NAME, user_id=user_id)
        
        session_list = []
        # Chuyển đổi dữ liệu và bóc tách những thông tin cần thiết
        for s in sessions:
            session_list.append({
                "session_id": s.id,
                "last_update_time": s.last_update_time,
                "state": s.state # Trả về state để UI biết trạng thái kế hoạch
            })
            
        # Sắp xếp cuộc trò chuyện mới nhất lên đầu tiên
        session_list.sort(key=lambda x: x["last_update_time"], reverse=True)

        return {"status": "success", "data": session_list}
    except Exception as e:
        return {"status": "error", "message": str(e)}


@app.get("/api/v1/sessions/{user_id}/{session_id}")
async def get_session_history(user_id: str, session_id: str):
    """API 2: Lấy chi tiết lịch sử tin nhắn (Phục vụ cho màn hình Chat ở giữa)"""
    try:
        session = await session_service.get_session(
            app_name=APP_NAME,
            user_id=user_id,
            session_id=session_id
        )
        
        if session is None:
            return {"status": "error", "message": "Không tìm thấy phiên trò chuyện này!"}

        history = []
        # Duyệt qua lịch sử (events) được lưu trong ADK Database
        for event in session.events:
            # Kiểm tra xem event có chứa nội dung text không
            if hasattr(event, 'content') and event.content:
                role = getattr(event.content, 'role', 'unknown')
                
                text = ""
                if hasattr(event.content, 'parts') and event.content.parts:
                    text = event.content.parts[0].text
                
                # Chỉ lọc lấy tin nhắn của người dùng (user) và AI (model)
                if role in ['user', 'model'] and text:
                    history.append({
                        "role": role,
                        "text": text
                    })

        return {
            "status": "success",
            "session_id": session.id,
            "data": {"history": history}
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}
    
    # Sự kiện chạy 1 lần khi bật Server: Tự động tạo Bảng chứa User và Bảng Token trong DB
@app.on_event("startup")
async def startup_event():
    async with aiosqlite.connect("./course_agent.db") as db:
        # 1. Bảng lưu tài khoản
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL
            )
        """)
        
        # 2. Bảng lưu số Token đã dùng
        await db.execute("""
            CREATE TABLE IF NOT EXISTS token_usage (
                username TEXT PRIMARY KEY,
                total_tokens INTEGER DEFAULT 0
            )
        """)
        
        await db.commit()

        @app.get("/api/v1/tokens/{username}")
async def get_token_usage(username: str):
    """API Xem số lượng Token User đã tiêu thụ"""
    async with aiosqlite.connect("./course_agent.db") as db:
        cursor = await db.execute("SELECT total_tokens FROM token_usage WHERE username = ?", (username,))
        row = await cursor.fetchone()
        return {
            "status": "success", 
            "username": username, 
            "total_tokens_used": row[0] if row else 0
        }