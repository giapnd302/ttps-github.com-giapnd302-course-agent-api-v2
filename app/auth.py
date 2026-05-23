import jwt
import os
from datetime import datetime, timedelta
from passlib.context import CryptContext
from dotenv import load_dotenv

load_dotenv()

# Cấu hình "Chữ ký bí mật" (Secret Key) để chống làm giả thẻ Token
SECRET_KEY = os.getenv("SECRET_KEY", "mot_chuoi_bi_mat_sieu_kho_doan_cua_kpim_2024")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7 # Thẻ Token có hạn sử dụng 7 ngày

# Công cụ băm (Mã hóa) mật khẩu thành các ký tự loằng ngoằng
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password, hashed_password):
    """Kiểm tra mật khẩu nhập vào có khớp với mật khẩu đã mã hóa không"""
    # Fix lỗi Bcrypt 72 bytes: Cắt ngắn mật khẩu nếu nó quá dài
    plain_password = plain_password[:72]
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    """Biến mật khẩu gốc thành cục mã hóa"""
    # Fix lỗi Bcrypt 72 bytes: Cắt ngắn mật khẩu trước khi mã hóa
    password = password[:72]
    return pwd_context.hash(password)

def create_access_token(data: dict):
    """Tạo thẻ JWT (Cấp vé vào cổng cho User)"""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt