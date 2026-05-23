from fastapi import FastAPI
from app.models import ChatRequest
from app.auth import get_password_hash, verify_password, create_access_token
from pydantic import BaseModel
import aiosqlite
from app.agent import session_service, course_agent
from google.adk.runners import Runner
from google.genai import types
from fastapi.middleware.cors import CORSMiddleware
import uuid

class UserCreate(BaseModel):
    username: str
    password: str

app = FastAPI(title="Course Agent API (Powered by Google ADK)")

# MỞ CỬA CORS CHO FRONTEND
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

APP_NAME = "course_implementation_app"
agent_runner = Runner(app_name=APP_NAME, agent=course_agent, session_service=session_service)

# ==========================================
# 1. API KHỞI TẠO DATABASE KHI CHẠY SERVER
# ==========================================
@app.on_event("startup")
async def startup_event():
    async with aiosqlite.connect("./course_agent.db") as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL
            )
        """)
        await db.execute("""
            CREATE TABLE IF NOT EXISTS token_usage (
                username TEXT PRIMARY KEY,
                total_tokens INTEGER DEFAULT 0
            )
        """)
        await db.commit()

# ==========================================
# 2. CÁC API XÁC THỰC NGƯỜI DÙNG (AUTH)
# ==========================================
@app.post("/api/v1/register")
async def register(user: UserCreate):
    try:
        async with aiosqlite.connect("./course_agent.db") as db:
            cursor = await db.execute("SELECT id FROM users WHERE username = ?", (user.username,))
            if await cursor.fetchone():
                return {"status": "error", "message": "Tên đăng nhập đã tồn tại!"}
            
            hashed_pw = get_password_hash(user.password)
            await db.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)", (user.username, hashed_pw))
            await db.commit()
            return {"status": "success", "message": "Đăng ký thành công!"}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.post("/api/v1/login")
async def login(user: UserCreate):
    async with aiosqlite.connect("./course_agent.db") as db:
        cursor = await db.execute("SELECT username, password_hash FROM users WHERE username = ?", (user.username,))
        row = await cursor.fetchone()
        
        if not row or not verify_password(user.password, row[1]):
            return {"status": "error", "message": "Sai tên đăng nhập hoặc mật khẩu!"}
        
        access_token = create_access_token(data={"sub": row[0]})
        return {
            "status": "success", 
            "access_token": access_token, 
            "username": row[0],
            "message": "Đăng nhập thành công!"
        }

# ==========================================
# 3. API CHAT VỚI AI & ĐẾM TOKEN
# ==========================================
@app.post("/api/v1/chat-plan")
async def interact_with_plan(request: ChatRequest):
    try:
        current_session_id = request.session_id
        
        if not current_session_id:
            current_session_id = str(uuid.uuid4())
            session = await session_service.create_session(
                app_name=APP_NAME, user_id=request.user_id, session_id=current_session_id,
                state={"revision_count": 0, "plan_status": "Drafting"} 
            )
        else:
            session = await session_service.get_session(app_name=APP_NAME, user_id=request.user_id, session_id=current_session_id)
            if session is None:
                return {"status": "error", "message": f"Không tìm thấy dữ liệu cho session_id: '{current_session_id}'. Vui lòng để trống session_id để tạo mới."}
                
            current_revisions = session.state.get("revision_count", 0)
            session.state["revision_count"] = current_revisions + 1
            if current_revisions > 0:
                session.state["plan_status"] = "Revising"

        content = types.Content(role='user', parts=[types.Part(text=request.message)])
        events = agent_runner.run_async(user_id=request.user_id, session_id=current_session_id, new_message=content)
        
        final_answer = ""
        async for event in events:
            if hasattr(event, 'is_final_response') and event.is_final_response():
                if event.content and event.content.parts:
                    final_answer = event.content.parts[0].text

        word_count = len(request.message.split()) + len(final_answer.split())
        estimated_tokens = int(word_count * 1.3)

        async with aiosqlite.connect("./course_agent.db") as db:
            await db.execute("""
                INSERT INTO token_usage (username, total_tokens) 
                VALUES (?, ?) 
                ON CONFLICT(username) DO UPDATE SET total_tokens = total_tokens + ?
            """, (request.user_id, estimated_tokens, estimated_tokens))
            await db.commit()

        return {
            "status": "success",
            "session_id": current_session_id,
            "data": {"response": final_answer}
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}

# ==========================================
# 4. API LẤY LỊCH SỬ CHAT CHO FRONTEND UI
# ==========================================
@app.get("/api/v1/sessions/{user_id}")
async def get_user_sessions(user_id: str):
    try:
        sessions = await session_service.list_sessions(app_name=APP_NAME, user_id=user_id)
        session_list = []
        for s in sessions:
            session_list.append({
                "session_id": s.id, "last_update_time": s.last_update_time, "state": s.state 
            })
        session_list.sort(key=lambda x: x["last_update_time"], reverse=True)
        return {"status": "success", "data": session_list}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/api/v1/sessions/{user_id}/{session_id}")
async def get_session_history(user_id: str, session_id: str):
    try:
        session = await session_service.get_session(app_name=APP_NAME, user_id=user_id, session_id=session_id)
        if session is None:
            return {"status": "error", "message": "Không tìm thấy phiên trò chuyện này!"}

        history = []
        for event in session.events:
            if hasattr(event, 'content') and event.content:
                role = getattr(event.content, 'role', 'unknown')
                text = ""
                if hasattr(event.content, 'parts') and event.content.parts:
                    text = event.content.parts[0].text
                if role in ['user', 'model'] and text:
                    history.append({"role": role, "text": text})

        return {"status": "success", "session_id": session.id, "data": {"history": history}}
    except Exception as e:
        return {"status": "error", "message": str(e)}

# ==========================================
# 5. API XEM SỐ LƯỢNG TOKEN
# ==========================================
@app.get("/api/v1/tokens/{username}")
async def get_token_usage(username: str):
    try:
        async with aiosqlite.connect("./course_agent.db") as db:
            cursor = await db.execute("SELECT total_tokens FROM token_usage WHERE username = ?", (username,))
            row = await cursor.fetchone()
            return {"status": "success", "username": username, "total_tokens_used": row[0] if row else 0}
    except Exception as e:
        return {"status": "error", "message": str(e)}