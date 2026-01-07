import streamlit as st
import sqlite3
import pandas as pd
import qrcode
import plotly.express as px
import streamlit_authenticator as stauth
from io import BytesIO
from datetime import datetime

# --- 1. CẤU HÌNH & DATABASE ---

def init_db():
    conn = sqlite3.connect('he_thong_quan_ly.db')
    c = conn.cursor()
    
    # Bảng tài sản
    c.execute('''CREATE TABLE IF NOT EXISTS assets 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  loai_tai_san TEXT, ma_tai_san TEXT, ten_tai_san TEXT, 
                  ngay_su_dung DATE, vi_tri TEXT, nguoi_quan_ly TEXT, 
                  tinh_trang TEXT, gia_tri REAL)''')
    
    # Bảng người dùng
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (username TEXT PRIMARY KEY, name TEXT, password TEXT, role TEXT, 
                  email TEXT, don_vi TEXT, khu_nha TEXT, phong TEXT)''')
    
    # Bảng danh mục Loại tài sản
    c.execute('''CREATE TABLE IF NOT EXISTS asset_types 
                 (ma_loai TEXT PRIMARY KEY, ten_loai TEXT)''')

    # Admin mặc định
    c.execute("SELECT * FROM users WHERE username='admin'")
    if not c.fetchone():
        hp = stauth.Hasher.hash('admin123')
        c.execute("INSERT INTO users (username, name, password, role) VALUES ('admin', 'Quản trị viên', ?, 'admin')", (hp,))
    
    conn.commit()
    conn.close()

def get_next_asset_code():
    conn = sqlite3.connect('he_thong_quan_ly.db')
    df = pd.read_sql_query("SELECT ma_tai_san FROM assets WHERE ma_tai_san LIKE 'TV%'", conn)
    conn.close()
    if df.empty: return "TV001"
    try:
        # Tìm số lớn nhất từ các mã hiện có
        numbers = df['ma_tai_san'].str.extract('(\d+)').dropna().astype(int)
        next_num = numbers.max().item() + 1
        return f"TV{next_num:03d}"
    except: return f"TV001"

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

# --- 2. GIAO DIỆN CHÍNH ---

def main():
    st.set_page_config(page_title="Quản lý Tài sản TV", layout="wide")
    init_db()
    config = fetch_users_config()
    
    if 'authenticator' not in st.session_state:
        st.session_state['authenticator'] = stauth.Authenticate(config, 'asset_cookie', 'auth_key', cookie_expiry_days=1)
    
    authenticator = st.session_state['authenticator']
    authenticator.login(location='main')

    if st.session_state["authentication_status"]:
        role = config['usernames'].get(st.session_state["username"], {}).get('role')
        st.sidebar.title(f"Chào {st.session_state['name']}")
        authenticator.logout('Đăng xuất', 'sidebar')
        
        menu = ["📊 Dashboard", "📋 Danh sách tài sản"]
        if role == 'admin': menu += ["⚙️ Cấu hình hệ thống"]
        choice = st.sidebar.radio("Chức năng", menu)

        conn = sqlite3.connect('he_thong_quan_ly.db')

        if choice == "📋 Danh sách tài sản":
            st.title("📋 Danh mục tài sản hệ thống")
            df = pd.read_sql_query("SELECT ma_tai_san, ten_tai_san, loai_tai_san, vi_tri, nguoi_quan_ly, tinh_trang FROM assets", conn)
            st.dataframe(df, use_container_width=True)

        elif choice == "⚙️ Cấu hình hệ thống":
            st.title("⚙️ Quản trị hệ thống")
            t1, t2, t3 = st.tabs(["📦 Thêm tài sản", "📑 Danh mục Loại tài sản", "👥 Nhân viên"])
            
            # --- TAB 1: THÊM TÀI SẢN (Dữ liệu loại lấy từ Tab 2) ---
            with t1:
                st.subheader("Nhập tài sản mới")
                suggested_code = get_next_asset_code()
                
                # LẤY TỰ ĐỘNG DANH SÁCH TÊN LOẠI TỪ DATABASE
                df_types = pd.read_sql_query("SELECT ten_loai FROM asset_types", conn)
                list_type_names = df_types['ten_loai'].tolist()
                
                if not list_type_names:
                    st.warning("⚠️ Chưa có loại tài sản nào trong hệ thống. Vui lòng thêm tại tab 'Danh mục Loại tài sản' trước.")
                
                with st.form("f_add_asset", clear_on_submit=True):
                    c1, c2 = st.columns(2)
                    with c1:
                        st.text_input("Mã tài sản (Tự động)", value=suggested_code, disabled=True)
                        ten_ts = st.text_input("Tên tài sản *")
                        # Hộp thoại loại tài sản lấy dữ liệu tự động ở đây
                        loai_ts = st.selectbox("Chọn loại tài sản *", list_type_names if list_type_names else ["N/A"])
                    with c2:
                        ngay_sd = st.date_input("Ngày sử dụng", datetime.now())
                        users_df = pd.read_sql_query("SELECT name FROM users", conn)
                        nguoi_ql = st.selectbox("Người quản lý", users_df['name'].tolist())
                        tt = st.selectbox("Tình trạng", ["Mới", "Đang dùng tốt", "Cần bảo trì", "Hỏng"])
                    
                    if st.form_submit_button("Lưu tài sản"):
                        if ten_ts and list_type_names:
                            conn.execute("INSERT INTO assets (loai_tai_san, ma_tai_san, ten_tai_san, ngay_su_dung, nguoi_quan_ly, tinh_trang) VALUES (?,?,?,?,?,?)",
                                        (loai_ts, suggested_code, ten_ts, ngay_sd, nguoi_ql, tt))
                            conn.commit()
                            st.success(f"Đã lưu tài sản {ten_ts} với mã {suggested_code}")
                            st.rerun()
                        elif not list_type_names:
                            st.error("Không thể lưu vì chưa có loại tài sản.")
                        else:
                            st.error("Vui lòng nhập tên tài sản.")

            # --- TAB 2: DANH MỤC LOẠI TÀI SẢN ---
            with t2:
                st.subheader("Quản lý danh mục loại tài sản")
                c_f, c_l = st.columns([1, 2])
                with c_f:
                    with st.form("f_add_type", clear_on_submit=True):
                        m_l = st.text_input("Mã loại (VD: MT)")
                        t_l = st.text_input("Tên loại tài sản (VD: Máy tính)")
                        if st.form_submit_button("Thêm loại"):
                            if m_l and t_l:
                                try:
                                    conn.execute("INSERT INTO asset_types VALUES (?,?)", (m_l, t_l))
                                    conn.commit()
                                    st.success("Đã thêm loại mới!")
                                    st.rerun()
                                except: st.error("Mã loại đã tồn tại!")
                with c_l:
                    df_all_t = pd.read_sql_query("SELECT ma_loai as 'Mã loại', ten_loai as 'Tên loại' FROM asset_types", conn)
                    st.dataframe(df_all_t, use_container_width=True)

            # --- TAB 3: NHÂN VIÊN ---
            with t3:
                # (Phần nhân viên giữ nguyên như các bản trước)
                st.subheader("Danh sách nhân sự")
                df_u = pd.read_sql_query("SELECT username, name, don_vi, khu_nha, phong FROM users", conn)
                st.dataframe(df_u, use_container_width=True)

        conn.close()
    
    elif st.session_state["authentication_status"] is False:
        st.error('Sai tài khoản hoặc mật khẩu')
    elif st.session_state["authentication_status"] is None:
        st.info('Vui lòng đăng nhập.')

if __name__ == '__main__':
    main()
