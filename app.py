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
    
    # Bảng tài sản
    c.execute('''CREATE TABLE IF NOT EXISTS assets 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, ten_tai_san TEXT, loai_tai_san TEXT, 
                  gia_tri REAL, tinh_trang TEXT, nguoi_su_dung TEXT, vi_tri TEXT)''')
    
    # Bảng người dùng (Thêm các trường đơn vị, khu nhà, phòng)
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (username TEXT PRIMARY KEY, name TEXT, password TEXT, role TEXT, 
                  email TEXT, don_vi TEXT, khu_nha TEXT, phong TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS transfer_history 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, asset_id INTEGER, 
                  tu_nguoi TEXT, sang_nguoi TEXT, ngay_chuyen DATE, ghi_chu TEXT)''')

    # TỰ ĐỘNG CẬP NHẬT CẤU TRÚC BẢNG (MIGRATE)
    c.execute("PRAGMA table_info(users)")
    columns = [column[1] for column in c.fetchall()]
    for col in ['email', 'don_vi', 'khu_nha', 'phong']:
        if col not in columns:
            c.execute(f"ALTER TABLE users ADD COLUMN {col} TEXT DEFAULT ''")

    # Admin mặc định
    c.execute("SELECT * FROM users WHERE username='admin'")
    if not c.fetchone():
        hashed_pw = stauth.Hasher.hash('admin123')
        c.execute("INSERT INTO users (username, name, password, role, email) VALUES ('admin', 'Quản trị viên', ?, 'admin', 'admin@example.com')", (hashed_pw,))
    
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
            'name': row['name'], 'password': row['password'], 'role': row['role'], 
            'email': row['email'], 'don_vi': row['don_vi'], 'khu_nha': row['khu_nha'], 'phong': row['phong']
        }
    return config

# --- 2. TIỆN ÍCH ---

def send_email_notification(asset_name, from_user, to_user, note):
    try:
        sender = st.secrets["SENDER_EMAIL"]
        pwd = st.secrets["SENDER_PASSWORD"]
        receiver = st.secrets["RECEIVER_EMAIL"]
        msg = MIMEMultipart()
        msg['From'] = sender
        msg['To'] = receiver
        msg['Subject'] = f"🔔 Điều chuyển tài sản: {asset_name}"
        body = f"Tài sản {asset_name} chuyển sang {to_user}. Ghi chú: {note}"
        msg.attach(MIMEText(body, 'html'))
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(sender, pwd)
        server.sendmail(sender, receiver, msg.as_string())
        server.quit()
        return True
    except: return False

def generate_qr(url):
    qr = qrcode.make(url)
    buf = BytesIO()
    qr.save(buf, format="PNG")
    return buf.getvalue()

# --- 3. GIAO DIỆN CHÍNH ---

def main():
    st.set_page_config(page_title="Asset Pro Management", layout="wide")
    
    # Xử lý Query Params (QR Code)
    if "id" in st.query_params:
        # Giữ nguyên phần hiển thị công khai như trước
        pass

    init_db()
    config = fetch_users_config()
    
    if 'authenticator' not in st.session_state:
        st.session_state['authenticator'] = stauth.Authenticate(
            config, 'asset_cookie', 'auth_key', cookie_expiry_days=1
        )
    
    authenticator = st.session_state['authenticator']
    authenticator.login(location='main')

    if st.session_state["authentication_status"]:
        username = st.session_state["username"]
        role = config['usernames'][username]['role']
        st.sidebar.title(f"Chào {st.session_state['name']}")
        authenticator.logout('Đăng xuất', 'sidebar')
        
        menu = ["📊 Dashboard", "📋 Danh sách"]
        if role == 'admin':
            menu += ["🔧 Vận hành & Điều chuyển", "⚙️ Hệ thống"]
        choice = st.sidebar.radio("Menu chính", menu)

        conn = sqlite3.connect('he_thong_quan_ly.db')

        if choice == "⚙️ Hệ thống":
            st.title("⚙️ Cấu hình hệ thống")
            t1, t2 = st.tabs(["📦 Tài sản", "👥 Nhân viên & Vị trí"])
            
            with t1:
                st.subheader("Thêm tài sản")
                with st.form("f_asset"):
                    ten = st.text_input("Tên tài sản")
                    gia = st.number_input("Giá trị", min_value=0.0)
                    if st.form_submit_button("Lưu"):
                        conn.execute("INSERT INTO assets (ten_tai_san, gia_tri, tinh_trang) VALUES (?,?,'Mới')", (ten, gia))
                        conn.commit()
                        st.success("Đã thêm!")

            with t2:
                col1, col2 = st.columns([1, 2])
                with col1:
                    st.subheader("Tạo tài khoản mới")
                    with st.form("f_user"):
                        u_un = st.text_input("Username")
                        u_nm = st.text_input("Họ tên")
                        u_pw = st.text_input("Mật khẩu", type="password")
                        u_em = st.text_input("Email")
                        st.markdown("---")
                        u_dv = st.text_input("Đơn vị (Phòng/Ban)")
                        u_kn = st.text_input("Khu nhà")
                        u_ph = st.text_input("Số phòng")
                        u_rl = st.selectbox("Vai trò", ["user", "admin"])
                        
                        if st.form_submit_button("Đăng ký nhân viên"):
                            if u_un and u_pw:
                                hp = stauth.Hasher.hash(u_pw)
                                try:
                                    conn.execute("INSERT INTO users VALUES (?,?,?,?,?,?,?,?)", 
                                               (u_un, u_nm, hp, u_rl, u_em, u_dv, u_kn, u_ph))
                                    conn.commit()
                                    st.success("Đã tạo nhân viên!")
                                    st.rerun()
                                except: st.error("Lỗi: Username đã tồn tại!")

                with col2:
                    st.subheader("Danh sách nhân viên & Vị trí công tác")
                    df_u = pd.read_sql_query("SELECT username, name, don_vi, khu_nha, phong, role FROM users", conn)
                    st.dataframe(df_u, use_container_width=True)
                    
                    user_del = st.selectbox("Chọn nhân viên để xóa", [""] + df_u['username'].tolist())
                    if st.button("Xóa tài khoản này"):
                        if user_del and user_del != 'admin':
                            conn.execute("DELETE FROM users WHERE username=?", (user_del,))
                            conn.commit()
                            st.rerun()

        # (Các chức năng Dashboard, Danh sách, Điều chuyển giữ nguyên cấu trúc)
        conn.close()

    elif st.session_state["authentication_status"] is False:
        st.error('Sai thông tin đăng nhập.')
    elif st.session_state["authentication_status"] is None:
        st.info('Vui lòng đăng nhập.')

if __name__ == '__main__':
    main()
