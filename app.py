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

    # Admin mặc định nếu DB trống
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
        st.sidebar.info(f"Quyền: {role.upper()}")
        authenticator.logout('Đăng xuất', 'sidebar')
        
        menu = ["📊 Dashboard", "📋 Danh sách tài sản"]
        if role == 'admin': menu += ["⚙️ Cấu hình hệ thống"]
        choice = st.sidebar.radio("Chức năng chính", menu)

        conn = sqlite3.connect('he_thong_quan_ly.db')

        if choice == "📋 Danh sách tài sản":
            st.title("📋 Danh mục tài sản hệ thống")
            df = pd.read_sql_query("SELECT ma_tai_san, ten_tai_san, loai_tai_san, vi_tri, nguoi_quan_ly, tinh_trang FROM assets", conn)
            st.dataframe(df, use_container_width=True)

        elif choice == "⚙️ Cấu hình hệ thống":
            st.title("⚙️ Quản trị & Phân quyền")
            t1, t2, t3 = st.tabs(["📦 Thêm tài sản", "📑 Loại tài sản", "👥 Quản lý nhân viên"])
            
            # --- TAB 1 & 2 giữ nguyên logic cũ ---
            with t1:
                # (Code thêm tài sản...)
                st.subheader("Nhập tài sản mới")
                df_types = pd.read_sql_query("SELECT ten_loai FROM asset_types", conn)
                list_type_names = df_types['ten_loai'].tolist()
                suggested_code = get_next_asset_code()
                with st.form("f_add_asset", clear_on_submit=True):
                    c1, c2 = st.columns(2)
                    with c1:
                        st.text_input("Mã tài sản (Tự động)", value=suggested_code, disabled=True)
                        ten_ts = st.text_input("Tên tài sản *")
                        loai_ts = st.selectbox("Chọn loại tài sản *", list_type_names if list_type_names else ["Chưa có"])
                    with c2:
                        ngay_sd = st.date_input("Ngày sử dụng", datetime.now())
                        users_names = pd.read_sql_query("SELECT name FROM users", conn)['name'].tolist()
                        nguoi_ql = st.selectbox("Người quản lý", users_names)
                        tt = st.selectbox("Tình trạng", ["Mới", "Tốt", "Cần bảo trì"])
                    if st.form_submit_button("Lưu"):
                        conn.execute("INSERT INTO assets (loai_tai_san, ma_tai_san, ten_tai_san, ngay_su_dung, nguoi_quan_ly, tinh_trang) VALUES (?,?,?,?,?,?)",
                                    (loai_ts, suggested_code, ten_ts, ngay_sd, nguoi_ql, tt))
                        conn.commit()
                        st.success("Đã thêm!")
                        st.rerun()

            with t2:
                # (Code thêm loại tài sản...)
                st.subheader("Danh mục loại")
                with st.form("f_type"):
                    ml = st.text_input("Mã loại")
                    tl = st.text_input("Tên loại")
                    if st.form_submit_button("Thêm loại"):
                        conn.execute("INSERT INTO asset_types VALUES (?,?)", (ml, tl))
                        conn.commit(); st.rerun()
                st.dataframe(pd.read_sql_query("SELECT * FROM asset_types", conn), use_container_width=True)

            # --- TAB 3: QUẢN LÝ NHÂN VIÊN & PHÂN QUYỀN (MỚI) ---
            with t3:
                st.subheader("Quản lý tài khoản & Phân quyền")
                col_add, col_list = st.columns([1, 2])
                
                with col_add:
                    st.write("**Tạo nhân viên mới**")
                    with st.form("f_add_user", clear_on_submit=True):
                        new_username = st.text_input("Username (viết liền, không dấu) *")
                        new_name = st.text_input("Họ và tên *")
                        new_password = st.text_input("Mật khẩu *", type="password")
                        new_email = st.text_input("Email")
                        
                        st.markdown("---")
                        new_dv = st.text_input("Đơn vị (Phòng/Ban)")
                        new_kn = st.text_input("Khu nhà")
                        new_phong = st.text_input("Số phòng")
                        
                        # PHÂN QUYỀN Ở ĐÂY
                        new_role = st.selectbox("Phân quyền hệ thống", ["user", "admin"], 
                                                help="Admin: Toàn quyền | User: Chỉ được xem danh sách")
                        
                        if st.form_submit_button("Đăng ký tài khoản"):
                            if new_username and new_name and new_password:
                                try:
                                    hashed_password = stauth.Hasher.hash(new_password)
                                    conn.execute('''INSERT INTO users 
                                        (username, name, password, role, email, don_vi, khu_nha, phong) 
                                        VALUES (?,?,?,?,?,?,?,?)''',
                                        (new_username, new_name, hashed_password, new_role, new_email, new_dv, new_kn, new_phong))
                                    conn.commit()
                                    st.success(f"Đã tạo tài khoản {new_username} thành công!")
                                    st.rerun()
                                except sqlite3.IntegrityError:
                                    st.error("Lỗi: Username này đã tồn tại trên hệ thống!")
                            else:
                                st.warning("Vui lòng nhập đủ các trường có dấu (*)")

                with col_list:
                    st.write("**Danh sách nhân sự hiện có**")
                    df_users_display = pd.read_sql_query('''
                        SELECT username as 'Tên đăng nhập', 
                               name as 'Họ tên', 
                               role as 'Quyền', 
                               don_vi as 'Đơn vị', 
                               khu_nha as 'Khu', 
                               phong as 'Phòng' 
                        FROM users
                    ''', conn)
                    st.dataframe(df_users_display, use_container_width=True)
                    
                    # Tính năng xóa nhân viên
                    user_to_delete = st.selectbox("Chọn nhân viên cần xóa", [""] + df_users_display['Tên đăng nhập'].tolist())
                    if st.button("Xóa nhân viên này"):
                        if user_to_delete == "admin":
                            st.error("Không thể xóa tài khoản Admin gốc!")
                        elif user_to_delete == username_logged:
                            st.error("Bạn không thể tự xóa chính mình khi đang đăng nhập!")
                        elif user_to_delete:
                            conn.execute("DELETE FROM users WHERE username=?", (user_to_delete,))
                            conn.commit()
                            st.success(f"Đã xóa tài khoản {user_to_delete}")
                            st.rerun()

        conn.close()
    
    elif st.session_state["authentication_status"] is False:
        st.error('Sai tài khoản hoặc mật khẩu')
    elif st.session_state["authentication_status"] is None:
        st.info('Vui lòng đăng nhập để quản lý tài sản.')

if __name__ == '__main__':
    main()
