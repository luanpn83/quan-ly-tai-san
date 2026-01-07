import streamlit as st
import sqlite3
import pandas as pd
import streamlit_authenticator as stauth
import qrcode
from io import BytesIO
from datetime import datetime

# --- 1. CẤU HÌNH & DATABASE ---

def init_db():
    conn = sqlite3.connect('he_thong_quan_ly.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS assets 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  loai_tai_san TEXT, ma_tai_san TEXT, ten_tai_san TEXT, 
                  ngay_su_dung DATE, vi_tri TEXT, nguoi_quan_ly TEXT, 
                  tinh_trang TEXT, gia_tri REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (username TEXT PRIMARY KEY, name TEXT, password TEXT, role TEXT, 
                  email TEXT, don_vi TEXT, khu_nha TEXT, phong TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS asset_types 
                 (ma_loai TEXT PRIMARY KEY, ten_loai TEXT)''')
    c.execute("SELECT * FROM users WHERE username='admin'")
    if not c.fetchone():
        hp = stauth.Hasher.hash('admin123')
        c.execute("INSERT INTO users (username, name, password, role) VALUES ('admin', 'Quản trị viên', ?, 'admin')", (hp,))
    conn.commit()
    conn.close()

# --- 2. HÀM TẠO MÃ QR (CHỨA URL) ---

def generate_qr_code(ma_tai_san):
    # Lấy URL gốc của ứng dụng (Ví dụ: http://localhost:8501 hoặc domain của bạn)
    # Streamlit Cloud URL thường có dạng: https://your-app.streamlit.app/
    base_url = st.secrets.get("BASE_URL", "http://localhost:8501") 
    
    # Tạo URL kèm tham số truy vấn
    qr_url = f"{base_url}?view_asset={ma_tai_san}"
    
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(qr_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

# --- 3. GIAO DIỆN CHÍNH ---

def main():
    st.set_page_config(page_title="Hệ thống Quản lý Tài sản TV", layout="wide")
    init_db()
    config = fetch_users_config()
    
    # Kiểm tra nếu người dùng đang truy cập qua link quét mã QR
    query_params = st.query_params
    if "view_asset" in query_params:
        show_asset_details(query_params["view_asset"])
        st.stop() # Dừng lại chỉ hiển thị thông tin tài sản, không bắt đăng nhập ngay

    # Logic Đăng nhập bình thường
    if 'authenticator' not in st.session_state:
        st.session_state['authenticator'] = stauth.Authenticate(config, 'asset_cookie', 'auth_key', cookie_expiry_days=1)
    
    authenticator = st.session_state['authenticator']
    authenticator.login(location='main')

    if st.session_state["authentication_status"]:
        # ... (Phần menu và Dashboard giữ nguyên) ...
        render_main_app() 

# --- 4. HÀM HIỂN THỊ CHI TIẾT KHI QUÉT MÃ ---

def show_asset_details(ma_tai_san):
    st.title(f"🔍 Thông tin tài sản: {ma_tai_san}")
    conn = sqlite3.connect('he_thong_quan_ly.db')
    df = pd.read_sql_query("SELECT * FROM assets WHERE ma_tai_san=?", conn, params=(ma_tai_san,))
    conn.close()
    
    if not df.empty:
        asset = df.iloc[0]
        st.success(f"Đã tìm thấy tài sản: **{asset['ten_tai_san']}**")
        
        c1, c2 = st.columns(2)
        with c1:
            st.metric("Loại tài sản", asset['loai_tai_san'])
            st.metric("Ngày sử dụng", str(asset['ngay_su_dung']))
            st.metric("Vị trí", asset['vi_tri'])
        with c2:
            st.metric("Người quản lý", asset['nguoi_quan_ly'])
            st.metric("Tình trạng", asset['tinh_trang'])
            st.metric("Giá trị", f"{asset['gia_tri']:,.0f} VNĐ")
        
        if st.button("⬅️ Quay lại trang đăng nhập"):
            st.query_params.clear()
            st.rerun()
    else:
        st.error("Không tìm thấy thông tin tài sản này trong hệ thống!")

def render_main_app():
    # ... (Toàn bộ code menu choice == "📋 Danh sách tài sản" và "⚙️ Cấu hình" của bạn) ...
    pass
