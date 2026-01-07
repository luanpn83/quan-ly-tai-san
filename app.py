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
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, ten_tai_san TEXT, loai_tai_san TEXT, 
                  gia_tri REAL, tinh_trang TEXT, nguoi_su_dung TEXT, vi_tri TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS maintenance 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, asset_id INTEGER, 
                  ngay_thuc_hien DATE, noi_dung TEXT, chi_phi REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (username TEXT PRIMARY KEY, name TEXT, password TEXT, role TEXT, email TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS transfer_history 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, asset_id INTEGER, 
                  tu_nguoi TEXT, sang_nguoi TEXT, ngay_chuyen DATE, ghi_chu TEXT)''')

    # Tự động sửa lỗi thiếu cột email nếu dùng DB cũ
    c.execute("PRAGMA table_info(users)")
    columns = [column[1] for column in c.fetchall()]
    if 'email' not in columns:
        c.execute("ALTER TABLE users ADD COLUMN email TEXT DEFAULT ''")

    c.execute("SELECT * FROM users WHERE username='admin'")
    if not c.fetchone():
        hashed_pw = stauth.Hasher.hash('admin123')
        c.execute("INSERT INTO users VALUES ('admin', 'Quản trị viên', ?, 'admin', 'admin@example.com')", (hashed_pw,))
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
            'name': row['name'], 'password': row['password'], 'role': row['role'], 'email': row['email']
        }
    return config

# --- 2. TIỆN ÍCH (EMAIL & QR) ---

def send_email_notification(asset_name, from_user, to_user, note):
    try:
        sender = st.secrets["SENDER_EMAIL"]
        pwd = st.secrets["SENDER_PASSWORD"]
        receiver = st.secrets["RECEIVER_EMAIL"]
        msg = MIMEMultipart()
        msg['From'] = sender
        msg['To'] = receiver
        msg['Subject'] = f"🔔 Điều chuyển tài sản: {asset_name}"
        body = f"Tài sản {asset_name} đã được chuyển từ {from_user} sang {to_user}. Ghi chú: {note}"
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
    st.set_page_config(page_title="Asset Pro", layout="wide")
    
    if "id" in st.query_params:
        # (Phần hiển thị QR công khai giữ nguyên như cũ)
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
        choice = st.sidebar.radio("Menu", menu)

        conn = sqlite3.connect('he_thong_quan_ly.db')

        # ... (Dashboard & Danh sách giữ nguyên) ...

        if choice == "🔧 Vận hành & Điều chuyển":
            # (Phần Điều chuyển giữ nguyên)
            pass

        elif choice == "⚙️ Hệ thống":
            st.title("⚙️ Quản trị hệ thống")
            t1, t2 = st.tabs(["📦 Quản lý tài sản", "👥 Quản lý nhân viên"])
            
            with t1:
                st.subheader("Thêm tài sản mới")
                with st.form("f_add_asset"):
                    ten = st.text_input("Tên tài sản")
                    gia = st.number_input("Giá trị", min_value=0.0)
                    vt = st.text_input("Vị trí")
                    if st.form_submit_button("Lưu tài sản"):
                        conn.execute("INSERT INTO assets (ten_tai_san, gia_tri, tinh_trang, vi_tri) VALUES (?,?,'Mới',?)", (ten, gia, vt))
                        conn.commit()
                        st.success("Đã thêm tài sản!")

            with t2:
                col_left, col_right = st.columns([1, 2])
                
                with col_left:
                    st.subheader("Tạo tài khoản")
                    with st.form("f_add_user"):
                        un = st.text_input("Username (viết liền)")
                        nm = st.text_input("Họ tên nhân viên")
                        pw = st.text_input("Mật khẩu", type="password")
                        em = st.text_input("Email")
                        rl = st.selectbox("Quyền hạn", ["user", "admin"])
                        if st.form_submit_button("Tạo tài khoản"):
                            if un and pw:
                                hp = stauth.Hasher.hash(pw)
                                try:
                                    conn.execute("INSERT INTO users VALUES (?,?,?,?,?)", (un, nm, hp, rl, em))
                                    conn.commit()
                                    st.success("Đã tạo thành công!")
                                    st.rerun()
                                except:
                                    st.error("Username đã tồn tại!")
                            else:
                                st.warning("Vui lòng nhập đủ Username/Mật khẩu")

                with col_right:
                    st.subheader("Danh sách nhân viên hiện có")
                    df_users = pd.read_sql_query("SELECT username, name, email, role FROM users", conn)
                    # Hiển thị bảng danh sách nhân viên
                    st.dataframe(df_users, use_container_width=True)
                    
                    # Tính năng xóa nhân viên
                    user_to_del = st.selectbox("Chọn Username để xóa", [""] + df_users['username'].tolist())
                    if st.button("Xóa nhân viên này"):
                        if user_to_del == 'admin':
                            st.error("Không thể xóa tài khoản Admin gốc!")
                        elif user_to_del:
                            conn.execute("DELETE FROM users WHERE username=?", (user_to_del,))
                            conn.commit()
                            st.success(f"Đã xóa tài khoản {user_to_del}")
                            st.rerun()
        
        conn.close()
    
    elif st.session_state["authentication_status"] is False:
        st.error('Sai tài khoản hoặc mật khẩu')
    elif st.session_state["authentication_status"] is None:
        st.info('Vui lòng đăng nhập.')

if __name__ == '__main__':
    main()
