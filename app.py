import streamlit as st
import sqlite3
import pandas as pd
import qrcode
import plotly.express as px
import streamlit_authenticator as stauth
from io import BytesIO
from datetime import datetime

# --- 1. CÁC HÀM TIỆN ÍCH & DATABASE ---

def init_db():
    conn = sqlite3.connect('he_thong_quan_ly.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS assets 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, ten_tai_san TEXT, loai_tai_san TEXT, 
                  gia_tri REAL, tinh_trang TEXT, nguoi_su_dung TEXT, vi_tri TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS maintenance 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, asset_id INTEGER, 
                  ngay_thuc_hien DATE, noi_dung TEXT, chi_phi REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (username TEXT PRIMARY KEY, name TEXT, password TEXT, role TEXT)''')
    
    c.execute("SELECT * FROM users WHERE username='admin'")
    if not c.fetchone():
        hashed_pw = stauth.Hasher.hash('admin123')
        c.execute("INSERT INTO users VALUES ('admin', 'Quản trị viên', ?, 'admin')", (hashed_pw,))
    conn.commit()
    conn.close()

def fetch_users_config():
    init_db()
    conn = sqlite3.connect('he_thong_quan_ly.db')
    df = pd.read_sql_query("SELECT * FROM users", conn)
    conn.close()
    config = {'usernames': {}} 
    for _, row in df.iterrows():
        config['usernames'][row['username']] = {
            'name': row['name'], 'password': row['password'], 'role': row['role']
        }
    return config

def generate_qr(url):
    qr = qrcode.make(url)
    buf = BytesIO()
    qr.save(buf, format="PNG")
    return buf.getvalue()

# --- 2. CÁC HÀM QUẢN LÝ NGƯỜI DÙNG (MỚI) ---

def add_user(username, name, password, role):
    try:
        conn = sqlite3.connect('he_thong_quan_ly.db')
        hashed_pw = stauth.Hasher.hash(password)
        conn.execute("INSERT INTO users VALUES (?, ?, ?, ?)", (username, name, hashed_pw, role))
        conn.commit()
        conn.close()
        return True
    except:
        return False

def delete_user(username):
    if username == 'admin': return False # Không cho xóa admin gốc
    conn = sqlite3.connect('he_thong_quan_ly.db')
    conn.execute("DELETE FROM users WHERE username=?", (username,))
    conn.commit()
    conn.close()
    return True

# --- 3. GIAO DIỆN CHÍNH ---

def main():
    st.set_page_config(page_title="Quản Lý Tài Sản Pro", layout="wide")
    
    if "id" in st.query_params:
        # Giữ nguyên hàm show_public_details... (bỏ qua để ngắn gọn)
        return

    init_db()
    config = fetch_users_config()
    
    if 'authenticator' not in st.session_state:
        st.session_state['authenticator'] = stauth.Authenticate(
            config, 'asset_cookie', 'auth_key', cookie_expiry_days=1
        )
    
    authenticator = st.session_state['authenticator']
    authenticator.login(location='main')

    if st.session_state["authentication_status"]:
        name = st.session_state["name"]
        username = st.session_state["username"]
        role = config['usernames'][username]['role']
        
        st.sidebar.title(f"Chào {name}")
        authenticator.logout('Đăng xuất', 'sidebar')
        
        if role == 'admin':
            menu = ["📊 Dashboard", "📋 Danh sách", "🔧 Bảo trì & QR", "⚙️ Hệ thống"]
        else:
            menu = ["📊 Dashboard", "📋 Danh sách"]
        choice = st.sidebar.radio("Chức năng", menu)

        conn = sqlite3.connect('he_thong_quan_ly.db')

        # ... (Dashboard & Danh sách giữ nguyên) ...

        if choice == "⚙️ Hệ thống":
            st.title("⚙️ Quản lý hệ thống")
            
            tab_asset, tab_user = st.tabs(["➕ Thêm tài sản", "👥 Quản lý người dùng"])
            
            with tab_asset:
                with st.form("add_asset"):
                    ten = st.text_input("Tên tài sản")
                    loai = st.selectbox("Loại", ["Điện tử", "Nội thất", "Khác"])
                    gia = st.number_input("Giá trị", min_value=0.0)
                    tt = st.selectbox("Tình trạng", ["Mới", "Tốt", "Cần bảo trì", "Hỏng"])
                    vt = st.text_input("Vị trí")
                    if st.form_submit_button("Lưu tài sản"):
                        conn.cursor().execute("INSERT INTO assets (ten_tai_san, loai_tai_san, gia_tri, tinh_trang, vi_tri) VALUES (?,?,?,?,?)",
                                              (ten, loai, gia, tt, vt))
                        conn.commit()
                        st.success("Đã thêm tài sản!")

            with tab_user:
                st.subheader("Tạo tài khoản mới")
                with st.form("new_user"):
                    u = st.text_input("Tên đăng nhập")
                    n = st.text_input("Họ tên")
                    p = st.text_input("Mật khẩu", type="password")
                    r = st.selectbox("Vai trò", ["user", "admin"])
                    if st.form_submit_button("Tạo người dùng"):
                        if add_user(u, n, p, r):
                            st.success("Đã tạo! Vui lòng tải lại trang để áp dụng.")
                            st.rerun()
                        else:
                            st.error("Lỗi: Trùng tên đăng nhập hoặc thiếu thông tin.")
                
                st.divider()
                st.subheader("Danh sách tài khoản")
                df_u = pd.read_sql_query("SELECT username, name, role FROM users", conn)
                st.table(df_u)
                
                user_del = st.selectbox("Chọn tài khoản cần xóa", df_u['username'])
                if st.button("Xóa tài khoản"):
                    if delete_user(user_del):
                        st.success("Đã xóa!")
                        st.rerun()
                    else:
                        st.error("Không thể xóa tài khoản này.")
        conn.close()

    elif st.session_state["authentication_status"] is False:
        st.error('Sai tài khoản hoặc mật khẩu')
    elif st.session_state["authentication_status"] is None:
        st.info('Vui lòng đăng nhập.')

if __name__ == '__main__':
    main()
