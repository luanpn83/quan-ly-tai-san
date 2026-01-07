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
    
    # Bảng tài sản (Đã bao gồm cột vi_tri)
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
        c.execute("INSERT INTO users (username, name, password, role, email) VALUES ('admin', 'Quản trị viên', ?, 'admin', 'admin@example.com')", (hp,))
    
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

def get_next_asset_code():
    conn = sqlite3.connect('he_thong_quan_ly.db')
    df = pd.read_sql_query("SELECT ma_tai_san FROM assets WHERE ma_tai_san LIKE 'TV%'", conn)
    conn.close()
    if df.empty: return "TV001"
    try:
        numbers = df['ma_tai_san'].str.extract('(\d+)').dropna().astype(int)
        next_num = numbers.max().item() + 1
        return f"TV{next_num:03d}"
    except: return f"TV001"

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
        username_logged = st.session_state["username"]
        role = config['usernames'].get(username_logged, {}).get('role')
        
        st.sidebar.title(f"Chào {st.session_state['name']}")
        authenticator.logout('Đăng xuất', 'sidebar')
        
        menu = ["📊 Dashboard", "📋 Danh sách tài sản"]
        if role == 'admin': menu += ["⚙️ Cấu hình hệ thống"]
        choice = st.sidebar.radio("Chức năng chính", menu)

        conn = sqlite3.connect('he_thong_quan_ly.db')

        if choice == "📋 Danh sách tài sản":
            st.title("📋 Danh mục tài sản hệ thống")
            # Hiển thị thêm cột Vị trí trong bảng danh sách
            df = pd.read_sql_query("SELECT ma_tai_san as 'Mã', ten_tai_san as 'Tên', loai_tai_san as 'Loại', vi_tri as 'Vị trí', nguoi_quan_ly as 'Người giữ', tinh_trang as 'Trạng thái' FROM assets", conn)
            st.dataframe(df, use_container_width=True)

        elif choice == "⚙️ Cấu hình hệ thống":
            st.title("⚙️ Quản trị hệ thống")
            t1, t2, t3 = st.tabs(["📦 Thêm tài sản mới", "📑 Loại tài sản", "👥 Nhân viên"])
            
            with t1:
                st.subheader("Nhập thông tin tài sản")
                suggested_code = get_next_asset_code()
                
                # Lấy danh sách Loại tài sản và Nhân viên cho Selectbox
                df_types = pd.read_sql_query("SELECT ten_loai FROM asset_types", conn)
                list_types = df_types['ten_loai'].tolist()
                list_users = pd.read_sql_query("SELECT name FROM users", conn)['name'].tolist()
                
                with st.form("f_add_asset", clear_on_submit=True):
                    c1, c2 = st.columns(2)
                    with c1:
                        st.text_input("Mã tài sản (Tự động)", value=suggested_code, disabled=True)
                        ten_ts = st.text_input("Tên tài sản *")
                        loai_ts = st.selectbox("Chọn loại tài sản *", list_types if list_types else ["Chưa có loại"])
                        ngay_sd = st.date_input("Ngày đưa vào sử dụng", datetime.now())
                    with c2:
                        # TRƯỜNG VỊ TRÍ MỚI BỔ SUNG Ở ĐÂY
                        vi_tri_ts = st.text_input("Vị trí đặt tài sản (VD: Tầng 2, Phòng KT) *")
                        nguoi_ql = st.selectbox("Người quản lý/Sử dụng", list_users)
                        tt = st.selectbox("Tình trạng", ["Mới", "Đang dùng tốt", "Cần bảo trì", "Hỏng"])
                        gia_tri = st.number_input("Giá trị (VNĐ)", min_value=0.0)
                    
                    if st.form_submit_button("Lưu tài sản"):
                        if ten_ts and vi_tri_ts and list_types:
                            conn.execute('''INSERT INTO assets 
                                (loai_tai_san, ma_tai_san, ten_tai_san, ngay_su_dung, vi_tri, nguoi_quan_ly, tinh_trang, gia_tri) 
                                VALUES (?,?,?,?,?,?,?,?)''', 
                                (loai_ts, suggested_code, ten_ts, ngay_sd, vi_tri_ts, nguoi_ql, tt, gia_tri))
                            conn.commit()
                            st.success(f"Đã lưu tài sản {ten_ts} tại vị trí {vi_tri_ts}!")
                            st.rerun()
                        elif not ten_ts or not vi_tri_ts:
                            st.error("Vui lòng nhập đầy đủ Tên và Vị trí tài sản.")
                        else:
                            st.error("Vui lòng cấu hình 'Loại tài sản' trước.")

            with t2:
                # (Code quản lý Loại tài sản giữ nguyên)
                st.subheader("Danh mục loại")
                with st.form("f_type"):
                    ml, tl = st.columns(2)
                    m_val = ml.text_input("Mã loại")
                    t_val = tl.text_input("Tên loại")
                    if st.form_submit_button("Thêm loại"):
                        conn.execute("INSERT INTO asset_types VALUES (?,?)", (m_val, t_val))
                        conn.commit(); st.rerun()
                st.dataframe(pd.read_sql_query("SELECT * FROM asset_types", conn), use_container_width=True)

            with t3:
                # (Code quản lý Nhân viên giữ nguyên)
                st.subheader("Quản lý nhân viên & Phân quyền")
                # ... (Phần thêm nhân viên đã có từ yêu cầu trước)

        conn.close()
    
    elif st.session_state["authentication_status"] is False:
        st.error('Sai tài khoản hoặc mật khẩu')
    elif st.session_state["authentication_status"] is None:
        st.info('Vui lòng đăng nhập.')

if __name__ == '__main__':
    main()
