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
    
    # Bảng tài sản (Cập nhật các trường thông tin mới)
    c.execute('''CREATE TABLE IF NOT EXISTS assets 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  loai_tai_san TEXT, 
                  ma_tai_san TEXT, 
                  ten_tai_san TEXT, 
                  ngay_su_dung DATE, 
                  vi_tri TEXT, 
                  nguoi_quan_ly TEXT, 
                  tinh_trang TEXT,
                  gia_tri REAL)''')
    
    # Bảng người dùng (Đơn vị, Khu nhà, Phòng)
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (username TEXT PRIMARY KEY, name TEXT, password TEXT, role TEXT, 
                  email TEXT, don_vi TEXT, khu_nha TEXT, phong TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS transfer_history 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, asset_id INTEGER, 
                  tu_nguoi TEXT, sang_nguoi TEXT, ngay_chuyen DATE, ghi_chu TEXT)''')

    # Migrate: Tự động thêm các cột mới vào bảng assets nếu đang dùng DB cũ
    c.execute("PRAGMA table_info(assets)")
    cols = [column[1] for column in c.fetchall()]
    new_cols = {
        'loai_tai_san': 'TEXT', 'ma_tai_san': 'TEXT', 'ngay_su_dung': 'DATE', 'nguoi_quan_ly': 'TEXT'
    }
    for col, type in new_cols.items():
        if col not in cols:
            c.execute(f"ALTER TABLE assets ADD COLUMN {col} {type}")

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
        server = smtplib.SMTP("smtp.gmail.com", 587); server.starttls()
        server.login(sender, pwd); server.sendmail(sender, receiver, msg.as_string()); server.quit()
        return True
    except: return False

def generate_qr(url):
    qr = qrcode.make(url)
    buf = BytesIO(); qr.save(buf, format="PNG")
    return buf.getvalue()

# --- 3. GIAO DIỆN CHÍNH ---

def main():
    st.set_page_config(page_title="Asset Pro Management", layout="wide")
    init_db()
    config = fetch_users_config()
    
    if 'authenticator' not in st.session_state:
        st.session_state['authenticator'] = stauth.Authenticate(config, 'asset_cookie', 'auth_key', cookie_expiry_days=1)
    
    authenticator = st.session_state['authenticator']
    authenticator.login(location='main')

    if st.session_state["authentication_status"]:
        role = config[st.session_state["username"]]['role']
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
                st.subheader("Thông tin tài sản mới")
                df_users = pd.read_sql_query("SELECT name FROM users", conn)
                with st.form("f_new_asset"):
                    c1, c2 = st.columns(2)
                    with c1:
                        loai = st.selectbox("Loại tài sản", ["Máy tính", "Thiết bị VP", "Nội thất", "Công cụ dụng cụ"])
                        ma = st.text_input("Mã tài sản (Ví dụ: MT-001)")
                        ten = st.text_input("Tên tài sản")
                        ngay = st.date_input("Ngày đưa vào sử dụng", datetime.now())
                    with c2:
                        vt = st.text_input("Vị trí đặt tài sản")
                        ql = st.selectbox("Người quản lý/Sử dụng", df_users['name'].tolist())
                        tt = st.selectbox("Tình trạng", ["Mới", "Đang dùng tốt", "Cần bảo trì", "Hỏng"])
                        gia = st.number_input("Giá trị (VNĐ)", min_value=0.0)
                    
                    if st.form_submit_button("Thêm tài sản vào hệ thống"):
                        conn.execute('''INSERT INTO assets 
                            (loai_tai_san, ma_tai_san, ten_tai_san, ngay_su_dung, vi_tri, nguoi_quan_ly, tinh_trang, gia_tri) 
                            VALUES (?,?,?,?,?,?,?,?)''', (loai, ma, ten, ngay, vt, ql, tt, gia))
                        conn.commit()
                        st.success(f"Đã thêm tài sản {ma} thành công!")

            with t2:
                # (Phần Quản lý nhân viên giữ nguyên như bản cập nhật trước)
                st.subheader("Danh sách nhân viên")
                df_u = pd.read_sql_query("SELECT username, name, don_vi, khu_nha, phong FROM users", conn)
                st.dataframe(df_u, use_container_width=True)
                # Form thêm User...
        
        conn.close()
    
    elif st.session_state["authentication_status"] is False:
        st.error('Sai thông tin đăng nhập.')
    elif st.session_state["authentication_status"] is None:
        st.info('Vui lòng đăng nhập.')

if __name__ == '__main__':
    main()
