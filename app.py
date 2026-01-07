import streamlit as st
import sqlite3
import pandas as pd
import qrcode
import plotly.express as px
import streamlit_authenticator as stauth
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
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
    
    # Migrate: Đảm bảo có cột ma_tai_san
    c.execute("PRAGMA table_info(assets)")
    cols = [col[1] for col in c.fetchall()]
    if 'ma_tai_san' not in cols:
        c.execute("ALTER TABLE assets ADD COLUMN ma_tai_san TEXT")
        
    # Tạo admin mặc định
    c.execute("SELECT * FROM users WHERE username='admin'")
    if not c.fetchone():
        hp = stauth.Hasher.hash('admin123')
        c.execute("INSERT INTO users (username, name, password, role) VALUES ('admin', 'Quản trị viên', ?, 'admin')", (hp,))
    conn.commit()
    conn.close()

def get_next_asset_code():
    """Hàm tự động sinh mã TV00x"""
    conn = sqlite3.connect('he_thong_quan_ly.db')
    df = pd.read_sql_query("SELECT ma_tai_san FROM assets WHERE ma_tai_san LIKE 'TV%'", conn)
    conn.close()
    if df.empty:
        return "TV001"
    else:
        # Lấy phần số từ mã, chuyển sang int, tìm max và +1
        try:
            numbers = df['ma_tai_san'].str.extract('(\\dd+)').dropna().astype(int)
            if numbers.empty: # Trường hợp mã không có số
                return f"TV{len(df)+1:03d}"
            next_num = numbers.max().item() + 1
            return f"TV{next_num:03d}"
        except:
            return f"TV{len(df)+1:03d}"

def fetch_users_config():
    init_db()
    conn = sqlite3.connect('he_thong_quan_ly.db')
    df = pd.read_sql_query("SELECT * FROM users", conn)
    conn.close()
    config = {'usernames': {}} 
    for _, row in df.iterrows():
        config['usernames'][row['username']] = {
            'name': row['name'], 'password': row['password'], 'role': row['role'], 
            'email': row.get('email', ''), 'don_vi': row.get('don_vi',''), 
            'khu_nha': row.get('khu_nha',''), 'phong': row.get('phong','')
        }
    return config

# --- 2. GIAO DIỆN CHÍNH ---

def main():
    st.set_page_config(page_title="Asset Pro Management", layout="wide")
    init_db()
    config = fetch_users_config()
    
    if 'authenticator' not in st.session_state:
        st.session_state['authenticator'] = stauth.Authenticate(config, 'asset_cookie', 'auth_key', cookie_expiry_days=1)
    
    authenticator = st.session_state['authenticator']
    authenticator.login(location='main')

    if st.session_state["authentication_status"]:
        user_info = config['usernames'].get(st.session_state["username"])
        if not user_info: st.stop()
        
        role = user_info['role']
        st.sidebar.title(f"Chào {st.session_state['name']}")
        authenticator.logout('Đăng xuất', 'sidebar')
        
        menu = ["📊 Dashboard", "📋 Danh sách"]
        if role == 'admin': menu += ["🔧 Điều chuyển", "⚙️ Hệ thống"]
        choice = st.sidebar.radio("Chức năng", menu)

        conn = sqlite3.connect('he_thong_quan_ly.db')

        if choice == "📋 Danh sách":
            st.title("📋 Danh mục tài sản")
            df = pd.read_sql_query("SELECT ma_tai_san, ten_tai_san, loai_tai_san, ngay_su_dung, vi_tri, nguoi_quan_ly, tinh_trang FROM assets", conn)
            st.dataframe(df, use_container_width=True)

        elif choice == "⚙️ Hệ thống":
            st.title("⚙️ Cấu hình hệ thống")
            t1, t2 = st.tabs(["📦 Thêm tài sản mới", "👥 Quản lý nhân viên"])
            
            with t1:
                st.subheader("Nhập thông tin tài sản")
                # Lấy mã tự động sinh
                suggested_code = get_next_asset_code()
                
                with st.form("f_new_asset", clear_on_submit=True):
                    c1, c2 = st.columns(2)
                    with c1:
                        # Hiển thị mã nhưng không cho sửa để tránh sai quy tắc
                        ma_ts = st.text_input("Mã tài sản (Tự động)", value=suggested_code, disabled=True)
                        ten_ts = st.text_input("Tên tài sản *")
                        loai_ts = st.selectbox("Loại tài sản", ["Máy tính", "Thiết bị văn phòng", "Nội thất", "Khác"])
                        ngay_sd = st.date_input("Ngày đưa vào sử dụng", datetime.now())
                    with c2:
                        vi_tri = st.text_input("Vị trí đặt")
                        users_list = pd.read_sql_query("SELECT name FROM users", conn)['name'].tolist()
                        nguoi_ql = st.selectbox("Người quản lý/Sử dụng", users_list)
                        tinh_trang = st.selectbox("Tình trạng", ["Mới", "Đang dùng tốt", "Cần bảo trì", "Hỏng"])
                        gia_tri = st.number_input("Giá trị (VNĐ)", min_value=0.0)
                    
                    if st.form_submit_button("Thêm tài sản"):
                        if ten_ts:
                            conn.execute('''INSERT INTO assets 
                                (loai_tai_san, ma_tai_san, ten_tai_san, ngay_su_dung, vi_tri, nguoi_quan_ly, tinh_trang, gia_tri) 
                                VALUES (?,?,?,?,?,?,?,?)''', 
                                (loai_ts, suggested_code, ten_ts, ngay_sd, vi_tri, nguoi_ql, tinh_trang, gia_tri))
                            conn.commit()
                            st.success(f"Đã thêm tài sản với mã: {suggested_code}")
                            st.rerun()
                        else:
                            st.error("Vui lòng nhập tên tài sản!")

            with t2:
                # Giao diện quản lý nhân viên (Giữ nguyên các trường Đơn vị, Khu nhà, Phòng)
                st.subheader("Danh sách nhân viên")
                df_u = pd.read_sql_query("SELECT username, name, don_vi, khu_nha, phong FROM users", conn)
                st.dataframe(df_u, use_container_width=True)
                
                with st.expander("Thêm tài khoản nhân viên mới"):
                    with st.form("add_user_new"):
                        u_un = st.text_input("Username")
                        u_nm = st.text_input("Họ tên")
                        u_pw = st.text_input("Mật khẩu", type="password")
                        u_dv = st.text_input("Đơn vị")
                        u_kn = st.text_input("Khu nhà")
                        u_ph = st.text_input("Phòng")
                        if st.form_submit_button("Tạo tài khoản"):
                            hp = stauth.Hasher.hash(u_pw)
                            conn.execute("INSERT INTO users (username, name, password, role, don_vi, khu_nha, phong) VALUES (?,?,?,'user',?,?,?)",
                                        (u_un, u_nm, hp, u_dv, u_kn, u_ph))
                            conn.commit()
                            st.success("Đã tạo!")
                            st.rerun()

        conn.close()
    
    elif st.session_state["authentication_status"] is False:
        st.error('Sai thông tin đăng nhập.')
    elif st.session_state["authentication_status"] is None:
        st.info('Vui lòng đăng nhập.')

if __name__ == '__main__':
    main()
