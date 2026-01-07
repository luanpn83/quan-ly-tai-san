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
    
    # Bảng người dùng (Lưu ý các trường email, don_vi, khu_nha, phong)
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (username TEXT PRIMARY KEY, name TEXT, password TEXT, role TEXT, 
                  email TEXT, don_vi TEXT, khu_nha TEXT, phong TEXT)''')
    
    # Bảng danh mục Loại tài sản
    c.execute('''CREATE TABLE IF NOT EXISTS asset_types 
                 (ma_loai TEXT PRIMARY KEY, ten_loai TEXT)''')

    # Tạo Admin mặc định nếu hệ thống mới tinh
    c.execute("SELECT * FROM users WHERE username='admin'")
    if not c.fetchone():
        hp = stauth.Hasher.hash('admin123')
        c.execute('''INSERT INTO users (username, name, password, role, email) 
                     VALUES ('admin', 'Quản trị viên', ?, 'admin', 'admin@example.com')''', (hp,))
    
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
    st.set_page_config(page_title="Hệ thống Quản lý Tài sản TV", layout="wide")
    init_db()
    config = fetch_users_config()
    
    # Khởi tạo xác thực
    if 'authenticator' not in st.session_state:
        st.session_state['authenticator'] = stauth.Authenticate(config, 'asset_cookie', 'auth_key', cookie_expiry_days=1)
    
    authenticator = st.session_state['authenticator']
    authenticator.login(location='main')

    if st.session_state["authentication_status"]:
        username_logged = st.session_state["username"]
        role = config['usernames'].get(username_logged, {}).get('role')
        
        st.sidebar.title(f"Chào {st.session_state['name']}")
        st.sidebar.write(f"Vai trò: **{role.upper()}**")
        authenticator.logout('Đăng xuất', 'sidebar')
        
        # Phân quyền menu: User thường không thấy mục "Cấu hình hệ thống"
        menu = ["📊 Dashboard", "📋 Danh sách tài sản"]
        if role == 'admin':
            menu += ["⚙️ Cấu hình hệ thống"]
        
        choice = st.sidebar.radio("Menu chính", menu)
        conn = sqlite3.connect('he_thong_quan_ly.db')

        if choice == "📋 Danh sách tài sản":
            st.title("📋 Danh mục tài sản")
            df = pd.read_sql_query("SELECT ma_tai_san, ten_tai_san, loai_tai_san, vi_tri, nguoi_quan_ly, tinh_trang FROM assets", conn)
            st.dataframe(df, use_container_width=True)

        elif choice == "⚙️ Cấu hình hệ thống":
            st.title("⚙️ Quản trị hệ thống")
            t1, t2, t3 = st.tabs(["📦 Nhập tài sản", "📑 Danh mục Loại", "👥 Quản lý nhân viên"])
            
            with t1:
                # Giao diện thêm tài sản (giữ nguyên các trường đã cập nhật)
                st.subheader("Thêm tài sản mới")
                suggested_code = get_next_asset_code()
                df_types = pd.read_sql_query("SELECT ten_loai FROM asset_types", conn)
                list_types = df_types['ten_loai'].tolist()
                list_users = pd.read_sql_query("SELECT name FROM users", conn)['name'].tolist()
                
                with st.form("f_asset", clear_on_submit=True):
                    c1, c2 = st.columns(2)
                    with c1:
                        st.text_input("Mã tài sản", value=suggested_code, disabled=True)
                        ten_ts = st.text_input("Tên tài sản *")
                        loai_ts = st.selectbox("Loại tài sản", list_types if list_types else ["N/A"])
                    with c2:
                        vi_tri = st.text_input("Vị trí đặt *")
                        nguoi_ql = st.selectbox("Người quản lý", list_users)
                        tt = st.selectbox("Tình trạng", ["Mới", "Tốt", "Cần bảo trì"])
                    if st.form_submit_button("Lưu tài sản"):
                        conn.execute("INSERT INTO assets (loai_tai_san, ma_tai_san, ten_tai_san, vi_tri, nguoi_quan_ly, tinh_trang) VALUES (?,?,?,?,?,?)",
                                    (loai_ts, suggested_code, ten_ts, vi_tri, nguoi_ql, tt))
                        conn.commit()
                        st.success("Đã thêm!"); st.rerun()

            with t2:
                # Quản lý Loại tài sản
                st.subheader("Danh mục loại tài sản")
                with st.form("f_type"):
                    ml, tl = st.columns(2)
                    m_val = ml.text_input("Mã loại")
                    t_val = tl.text_input("Tên loại")
                    if st.form_submit_button("Thêm loại"):
                        conn.execute("INSERT INTO asset_types VALUES (?,?)", (m_val, t_val))
                        conn.commit(); st.rerun()
                st.dataframe(pd.read_sql_query("SELECT * FROM asset_types", conn), use_container_width=True)

            with t3:
                # CHỨC NĂNG QUẢN LÝ NHÂN VIÊN & PHÂN QUYỀN
                st.subheader("Quản lý tài khoản nhân viên")
                col_form, col_list = st.columns([1, 2])
                
                with col_form:
                    st.write("**Thêm nhân viên mới**")
                    with st.form("f_add_user", clear_on_submit=True):
                        new_un = st.text_input("Tên đăng nhập *")
                        new_nm = st.text_input("Họ và tên *")
                        new_pw = st.text_input("Mật khẩu *", type="password")
                        new_dv = st.text_input("Đơn vị (Phòng/Ban)")
                        new_kn = st.text_input("Khu nhà")
                        new_ph = st.text_input("Phòng")
                        # PHÂN QUYỀN
                        new_rl = st.selectbox("Quyền hạn", ["user", "admin"])
                        
                        if st.form_submit_button("Đăng ký"):
                            if new_un and new_pw and new_nm:
                                try:
                                    hp = stauth.Hasher.hash(new_pw)
                                    conn.execute('''INSERT INTO users (username, name, password, role, don_vi, khu_nha, phong) 
                                                 VALUES (?,?,?,?,?,?,?)''', (new_un, new_nm, hp, new_rl, new_dv, new_kn, new_ph))
                                    conn.commit()
                                    st.success(f"Đã tạo user {new_un}")
                                    st.rerun()
                                except:
                                    st.error("Tên đăng nhập đã tồn tại!")
                            else:
                                st.warning("Vui lòng nhập đủ các trường có dấu *")

                with col_list:
                    st.write("**Danh sách nhân viên**")
                    df_u = pd.read_sql_query("SELECT username, name, role, don_vi, khu_nha, phong FROM users", conn)
                    st.dataframe(df_u, use_container_width=True)
                    
                    # Tính năng xóa
                    user_del = st.selectbox("Chọn user để xóa", [""] + df_u['username'].tolist())
                    if st.button("Xóa nhân viên"):
                        if user_del == 'admin':
                            st.error("Không thể xóa admin hệ thống!")
                        elif user_del == username_logged:
                            st.error("Bạn không thể tự xóa chính mình!")
                        elif user_del:
                            conn.execute("DELETE FROM users WHERE username=?", (user_del,))
                            conn.commit()
                            st.success(f"Đã xóa {user_del}")
                            st.rerun()

        conn.close()
    
    elif st.session_state["authentication_status"] is False:
        st.error('Sai tài khoản hoặc mật khẩu')
    elif st.session_state["authentication_status"] is None:
        st.info('Vui lòng đăng nhập.')

if __name__ == '__main__':
    main()
