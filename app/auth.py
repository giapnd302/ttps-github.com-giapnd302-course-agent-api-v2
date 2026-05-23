import jwt
import os
import bcrypt
from datetime import datetime, timedelta
from dotenv import load_dotenv

load_dotenv()

# Cấu hình "Chữ ký bí mật" (Secret Key) để chống làm giả thẻ Token
SECRET_KEY = os.getenv("SECRET_KEY", "mot_chuoi_bi_mat_sieu_kho_doan_cua_kpim_2026")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7 # Thẻ Token có hạn sử dụng 7 ngày

def verify_password(plain_password, hashed_password):
    """Kiểm tra mật khẩu nhập vào có khớp với mật khẩu đã mã hóa không"""
    # Lõi bcrypt yêu cầu mã hóa dưới dạng bytes
    return bcrypt.checkpw(
        plain_password.encode('utf-8'), 
        hashed_password.encode('utf-8')
    )

def get_password_hash(password):
    """Biến mật khẩu gốc thành cục mã hóa"""
    # Tạo chuỗi muối (salt) và mã hóa trực tiếp bằng lõi bcrypt
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
    # Giải mã về dạng chuỗi (string) để lưu vào SQLite
    return hashed.decode('utf-8')

def create_access_token(data: dict):
    """Tạo thẻ JWT (Cấp vé vào cổng cho User)"""
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt