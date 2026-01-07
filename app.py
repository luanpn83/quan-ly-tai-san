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
    
    # Bảng danh mục Loại tài sản (MỚI)
    c.execute('''CREATE TABLE IF NOT EXISTS asset_types 
                 (ma_loai TEXT PRIMARY KEY, ten_loai TEXT)''')

    # Thêm dữ liệu mẫu cho Loại tài sản nếu chưa có
    c.execute("SELECT COUNT(*) FROM asset_types")
    if c.fetchone()[0] == 0:
        sample_types = [('MT', 'Máy tính'), ('TBVP', 'Thiết bị văn phòng'), ('NT', 'Nội thất')]
        c.executemany("INSERT INTO asset_types VALUES (?,?)", sample_types)

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
        numbers = df['ma_tai_san'].str.extract('(\d+)').dropna().astype(int)
        next_num = numbers.max().item() + 1
        return f"TV{next_num:03d}"
    except: return f"TV{len(df)+1:03d}"

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
    st.set_page_config(page_title="Quản lý Tài sản Pro", layout="wide")
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
            
            # --- TAB 1: THÊM TÀI SẢN ---
            with t1:
                st.subheader("Nhập tài sản mới")
                suggested_code = get_next_asset_code()
                # Lấy danh sách loại tài sản từ DB
                df_types = pd.read_sql_query("SELECT ten_loai FROM asset_types", conn)
                list_types = df_types['ten_loai'].tolist() if not df_types.empty else ["Chưa có loại"]
                
                with st.form("f_add_asset", clear_on_submit=True):
                    c1, c2 = st.columns(2)
                    with c1:
                        ma_ts = st.text_input("Mã tài sản (Tự động)", value=suggested_code, disabled=True)
                        ten_ts = st.text_input("Tên tài sản *")
                        loai_ts = st.selectbox("Chọn loại tài sản", list_types)
                    with c2:
                        ngay_sd = st.date_input("Ngày sử dụng", datetime.now())
                        users_list = pd.read_sql_query("SELECT name FROM users", conn)['name'].tolist()
                        nguoi_ql = st.selectbox("Người quản lý", users_list)
                        tt = st.selectbox("Tình trạng", ["Mới", "Tốt", "Cần bảo trì"])
                    
                    if st.form_submit_button("Lưu tài sản"):
                        if ten_ts:
                            conn.execute("INSERT INTO assets (loai_tai_san, ma_tai_san, ten_tai_san, ngay_su_dung, nguoi_quan_ly, tinh_trang) VALUES (?,?,?,?,?,?)",
                                        (loai_ts, suggested_code, ten_ts, ngay_sd, nguoi_ql, tt))
                            conn.commit()
                            st.success(f"Đã thêm thành công mã {suggested_code}")
                            st.rerun()

            # --- TAB 2: DANH MỤC LOẠI TÀI SẢN (YÊU CẦU MỚI) ---
            with t2:
                st.subheader("Quản lý danh mục loại tài sản")
                col_form, col_list = st.columns([1, 2])
                
                with col_form:
                    with st.form("f_add_type", clear_on_submit=True):
                        st.write("**Thêm loại mới**")
                        m_loai = st.text_input("Mã loại (ví dụ: MT)")
                        t_loai = st.text_input("Tên loại (ví dụ: Máy tính)")
                        if st.form_submit_button("Thêm danh mục"):
                            if m_loai and t_loai:
                                try:
                                    conn.execute("INSERT INTO asset_types VALUES (?,?)", (m_loai, t_loai))
                                    conn.commit()
                                    st.success("Đã thêm loại tài sản!")
                                    st.rerun()
                                except: st.error("Mã loại đã tồn tại!")
                            else: st.warning("Vui lòng nhập đủ thông tin")

                with col_list:
                    st.write("**Danh sách loại tài sản hiện có**")
                    df_all_types = pd.read_sql_query("SELECT ma_loai as 'Mã loại', ten_loai as 'Tên loại tài sản' FROM asset_types", conn)
                    st.dataframe(df_all_types, use_container_width=True)
                    
                    # Tính năng xóa loại
                    del_type = st.selectbox("Chọn loại muốn xóa", [""] + df_all_types['Mã loại'].tolist())
                    if st.button("Xóa loại tài sản"):
                        if del_type:
                            conn.execute("DELETE FROM asset_types WHERE ma_loai=?", (del_type,))
                            conn.commit()
                            st.rerun()

            # --- TAB 3: NHÂN VIÊN ---
            with t3:
                st.subheader("Danh sách nhân sự")
                df_u = pd.read_sql_query("SELECT username, name, don_vi, khu_nha, phong FROM users", conn)
                st.dataframe(df_u, use_container_width=True)
                # (Code form thêm nhân viên giữ nguyên như các bản trước...)

        conn.close()
    
    elif st.session_state["authentication_status"] is False:
        st.error('Sai tài khoản hoặc mật khẩu')
    elif st.session_state["authentication_status"] is None:
        st.info('Vui lòng đăng nhập.')

if __name__ == '__main__':
    main()
