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
    
    # Bảng tài sản với đầy đủ thông tin mới
    c.execute('''CREATE TABLE IF NOT EXISTS assets 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  loai_tai_san TEXT, ma_tai_san TEXT, ten_tai_san TEXT, 
                  ngay_su_dung DATE, vi_tri TEXT, nguoi_quan_ly TEXT, 
                  tinh_trang TEXT, gia_tri REAL)''')
    
    # Bảng người dùng với thông tin Đơn vị, Khu nhà, Phòng
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (username TEXT PRIMARY KEY, name TEXT, password TEXT, role TEXT, 
                  email TEXT, don_vi TEXT, khu_nha TEXT, phong TEXT)''')
    
    c.execute('''CREATE TABLE IF NOT EXISTS transfer_history 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, asset_id INTEGER, 
                  tu_nguoi TEXT, sang_nguoi TEXT, ngay_chuyen DATE, ghi_chu TEXT)''')

    # Tự động nâng cấp cấu trúc bảng nếu thiếu cột (Migrate)
    c.execute("PRAGMA table_info(assets)")
    asset_cols = [col[1] for col in c.fetchall()]
    for col in ['loai_tai_san', 'ma_tai_san', 'ngay_su_dung', 'nguoi_quan_ly']:
        if col not in asset_cols:
            c.execute(f"ALTER TABLE assets ADD COLUMN {col} TEXT")

    c.execute("PRAGMA table_info(users)")
    user_cols = [col[1] for col in c.fetchall()]
    for col in ['email', 'don_vi', 'khu_nha', 'phong']:
        if col not in user_cols:
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
        body = f"Tài sản {asset_name} đã được chuyển từ {from_user} sang {to_user}. Ghi chú: {note}"
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
    
    # Sửa lỗi KeyError: Lấy config mới nhất mỗi khi trang load
    config = fetch_users_config()
    
    if 'authenticator' not in st.session_state:
        st.session_state['authenticator'] = stauth.Authenticate(config, 'asset_cookie', 'auth_key', cookie_expiry_days=1)
    
    authenticator = st.session_state['authenticator']
    authenticator.login(location='main')

    if st.session_state["authentication_status"]:
        # Kiểm tra an toàn để lấy Role
        user_info = config['usernames'].get(st.session_state["username"])
        if not user_info:
            st.error("Tài khoản không tồn tại trong hệ thống. Vui lòng đăng xuất.")
            st.stop()
        
        role = user_info['role']
        st.sidebar.title(f"Chào {st.session_state['name']}")
        authenticator.logout('Đăng xuất', 'sidebar')
        
        menu = ["📊 Dashboard", "📋 Danh sách"]
        if role == 'admin': menu += ["🔧 Điều chuyển", "⚙️ Hệ thống"]
        choice = st.sidebar.radio("Chức năng chính", menu)

        conn = sqlite3.connect('he_thong_quan_ly.db')

        if choice == "📊 Dashboard":
            st.title("📈 Tổng quan tài sản")
            df = pd.read_sql_query("SELECT * FROM assets", conn)
            if not df.empty:
                c1, c2 = st.columns(2)
                c1.metric("Tổng tài sản", len(df))
                c2.metric("Tổng giá trị", f"{df['gia_tri'].sum():,.0f} đ")
                st.plotly_chart(px.pie(df, names='tinh_trang', title="Tình trạng tài sản"), use_container_width=True)

        elif choice == "📋 Danh sách":
            st.title("📋 Danh mục tài sản")
            df = pd.read_sql_query("SELECT ma_tai_san, ten_tai_san, loai_tai_san, ngay_su_dung, vi_tri, nguoi_quan_ly, tinh_trang FROM assets", conn)
            st.dataframe(df, use_container_width=True)

        elif choice == "🔧 Điều chuyển":
            st.title("🔧 Điều chuyển nhân sự sử dụng")
            df_as = pd.read_sql_query("SELECT id, ma_tai_san, ten_tai_san, nguoi_quan_ly FROM assets", conn)
            df_us = pd.read_sql_query("SELECT name FROM users", conn)
            
            sel_dc = st.selectbox("Chọn tài sản", [f"{r['id']}-{r['ma_tai_san']}-{r['ten_tai_san']}" for _,r in df_as.iterrows()])
            aid = sel_dc.split('-')[0]
            old_u = next(r['nguoi_quan_ly'] for _,r in df_as.iterrows() if str(r['id']) == aid)
            new_u = st.selectbox("Bàn giao sang nhân viên", df_us['name'].tolist())
            note = st.text_input("Ghi chú")
            
            if st.button("Xác nhận bàn giao"):
                conn.execute("UPDATE assets SET nguoi_quan_ly = ? WHERE id = ?", (new_u, aid))
                conn.execute("INSERT INTO transfer_history (asset_id, tu_nguoi, sang_nguoi, ngay_chuyen, ghi_chu) VALUES (?,?,?,?,?)",
                            (aid, old_u, new_u, datetime.now().date(), note))
                conn.commit()
                st.success("Đã điều chuyển trên hệ thống!")
                st.rerun()

        elif choice == "⚙️ Hệ thống":
            st.title("⚙️ Cấu hình hệ thống")
            t1, t2 = st.tabs(["📦 Thêm tài sản mới", "👥 Quản lý nhân viên"])
            
            with t1:
                with st.form("f_asset"):
                    c1, c2 = st.columns(2)
                    with c1:
                        loai = st.selectbox("Loại", ["Máy tính", "VP Phẩm", "Nội thất"])
                        ma = st.text_input("Mã tài sản")
                        ten = st.text_input("Tên tài sản")
                    with c2:
                        ngay = st.date_input("Ngày sử dụng")
                        vt = st.text_input("Vị trí")
                        ql = st.selectbox("Người quản lý", pd.read_sql_query("SELECT name FROM users", conn)['name'].tolist())
                        tt = st.selectbox("Tình trạng", ["Mới", "Tốt", "Cần sửa"])
                        gia = st.number_input("Giá trị", min_value=0.0)
                    if st.form_submit_button("Thêm tài sản"):
                        conn.execute("INSERT INTO assets (loai_tai_san, ma_tai_san, ten_tai_san, ngay_su_dung, vi_tri, nguoi_quan_ly, tinh_trang, gia_tri) VALUES (?,?,?,?,?,?,?,?)",
                                    (loai, ma, ten, ngay, vt, ql, tt, gia))
                        conn.commit()
                        st.success("Đã thêm!")

            with t2:
                col_a, col_b = st.columns([1, 2])
                with col_a:
                    with st.form("f_u"):
                        u = st.text_input("User")
                        n = st.text_input("Họ tên")
                        p = st.text_input("Pass", type="password")
                        dv = st.text_input("Đơn vị")
                        kn = st.text_input("Khu")
                        ph = st.text_input("Phòng")
                        if st.form_submit_button("Tạo nhân viên"):
                            hp = stauth.Hasher.hash(p)
                            conn.execute("INSERT INTO users (username, name, password, role, don_vi, khu_nha, phong) VALUES (?,?,?,'user',?,?,?)", (u,n,hp,dv,kn,ph))
                            conn.commit()
                            st.rerun()
                with col_b:
                    st.dataframe(pd.read_sql_query("SELECT username, name, don_vi, khu_nha, phong FROM users", conn))

        conn.close()
    
    elif st.session_state["authentication_status"] is False:
        st.error('Sai tài khoản hoặc mật khẩu')
    elif st.session_state["authentication_status"] is None:
        st.info('Hệ thống Quản lý Tài sản - Vui lòng đăng nhập.')

if __name__ == '__main__':
    main()
