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
    """Gửi thông báo qua Email sử dụng Streamlit Secrets"""
    try:
        sender = st.secrets["SENDER_EMAIL"]
        pwd = st.secrets["SENDER_PASSWORD"]
        receiver = st.secrets["RECEIVER_EMAIL"]

        msg = MIMEMultipart()
        msg['From'] = sender
        msg['To'] = receiver
        msg['Subject'] = f"🔔 Điều chuyển tài sản: {asset_name}"
        
        body = f"""
        <h3>Thông báo điều chuyển</h3>
        <p><b>Tài sản:</b> {asset_name}</p>
        <p><b>Từ:</b> {from_user if from_user else 'Kho'}</p>
        <p><b>Sang:</b> {to_user}</p>
        <p><b>Ghi chú:</b> {note}</p>
        <p>Thời gian: {datetime.now().strftime('%d/%m/%Y %H:%M')}</p>
        """
        msg.attach(MIMEText(body, 'html'))
        
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(sender, pwd)
        server.sendmail(sender, receiver, msg.as_string())
        server.quit()
        return True
    except Exception as e:
        return False

def generate_qr(url):
    qr = qrcode.make(url)
    buf = BytesIO()
    qr.save(buf, format="PNG")
    return buf.getvalue()

def show_public_details(asset_id):
    conn = sqlite3.connect('he_thong_quan_ly.db')
    asset = pd.read_sql_query(f"SELECT * FROM assets WHERE id={asset_id}", conn)
    conn.close()
    if not asset.empty:
        st.success(f"### Tài sản: {asset.iloc[0]['ten_tai_san']}")
        st.info(f"👤 Người sử dụng: {asset.iloc[0]['nguoi_su_dung'] or 'N/A'}")
        st.write(f"📍 Vị trí: {asset.iloc[0]['vi_tri']} | Trạng thái: {asset.iloc[0]['tinh_trang']}")
    else:
        st.error("Không tìm thấy tài sản.")

# --- 3. GIAO DIỆN CHÍNH ---

def main():
    st.set_page_config(page_title="Asset Pro Management", layout="wide")
    
    # Xử lý QR không cần login
    if "id" in st.query_params:
        show_public_details(st.query_params["id"])
        if st.button("Trở về"):
            st.query_params.clear()
            st.rerun()
        return

    init_db()
    config = fetch_users_config()
    
    # Khởi tạo Authenticator qua session_state
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

        if choice == "📊 Dashboard":
            st.title("📈 Thống kê tài sản")
            df = pd.read_sql_query("SELECT * FROM assets", conn)
            if not df.empty:
                c1, c2, c3 = st.columns(3)
                c1.metric("Tổng tài sản", len(df))
                c2.metric("Tổng giá trị", f"{df['gia_tri'].sum():,.0f} đ")
                c3.metric("Cần bảo trì", len(df[df['tinh_trang']=="Cần bảo trì"]))
                st.plotly_chart(px.pie(df, names='tinh_trang', hole=0.4), use_container_width=True)

        elif choice == "📋 Danh sách":
            st.title("📋 Danh mục tài sản")
            df = pd.read_sql_query("SELECT id, ten_tai_san, loai_tai_san, nguoi_su_dung, vi_tri, tinh_trang FROM assets", conn)
            st.dataframe(df, use_container_width=True)

        elif choice == "🔧 Vận hành & Điều chuyển":
            st.title("🔧 Quản lý tài sản")
            df_as = pd.read_sql_query("SELECT * FROM assets", conn)
            df_us = pd.read_sql_query("SELECT name FROM users", conn)
            
            t1, t2, t3 = st.tabs(["Bảo trì", "Điều chuyển", "Mã QR"])
            
            with t1:
                sel = st.selectbox("Chọn tài sản", [f"{r['id']}-{r['ten_tai_san']}" for _,r in df_as.iterrows()])
                with st.form("bt"):
                    nd = st.text_area("Nội dung bảo trì")
                    if st.form_submit_button("Lưu"):
                        conn.execute("INSERT INTO maintenance (asset_id, ngay_thuc_hien, noi_dung) VALUES (?,?,?)",
                                     (sel.split('-')[0], datetime.now().date(), nd))
                        conn.commit()
                        st.success("Đã ghi nhận!")

            with t2:
                sel_dc = st.selectbox("Chọn tài sản chuyển", [f"{r['id']}-{r['ten_tai_san']} ({r['nguoi_su_dung']})" for _,r in df_as.iterrows()])
                aid = sel_dc.split('-')[0]
                old_u = next(r['nguoi_su_dung'] for _,r in df_as.iterrows() if str(r['id']) == aid)
                new_u = st.selectbox("Người nhận", df_us['name'].tolist())
                note = st.text_input("Ghi chú")
                if st.button("Xác nhận điều chuyển"):
                    conn.execute("UPDATE assets SET nguoi_su_dung = ? WHERE id = ?", (new_user, aid))
                    conn.execute("INSERT INTO transfer_history (asset_id, tu_nguoi, sang_nguoi, ngay_chuyen, ghi_chu) VALUES (?,?,?,?,?)",
                                (aid, old_u, new_u, datetime.now().date(), note))
                    conn.commit()
                    # Gửi Email
                    with st.spinner("Đang gửi mail..."):
                        send_email_notification(sel_dc.split('-')[1], old_u, new_u, note)
                    st.success("Thành công!")
                    st.rerun()

            with t3:
                sel_qr = st.selectbox("In mã QR", [f"{r['id']}-{r['ten_tai_san']}" for _,r in df_as.iterrows()])
                # Thay link-cua-ban.streamlit.app bằng link thật sau khi deploy
                url = f"https://link-cua-ban.streamlit.app/?id={sel_qr.split('-')[0]}"
                st.image(generate_qr(url), caption=f"Mã QR ID: {sel_qr.split('-')[0]}")

        elif choice == "⚙️ Hệ thống":
            st.title("⚙️ Cấu hình hệ thống")
            tab1, tab2 = st.tabs(["Tài sản", "Người dùng"])
            with tab1:
                with st.form("add_as"):
                    t = st.text_input("Tên tài sản")
                    g = st.number_input("Giá trị", min_value=0.0)
                    v = st.text_input("Vị trí")
                    if st.form_submit_button("Thêm"):
                        conn.execute("INSERT INTO assets (ten_tai_san, gia_tri, tinh_trang, vi_tri) VALUES (?,?,'Mới',?)", (t,g,v))
                        conn.commit()
                        st.success("Đã thêm!")
            with tab2:
                with st.form("add_us"):
                    un = st.text_input("Username")
                    nm = st.text_input("Họ tên")
                    pw = st.text_input("Mật khẩu", type="password")
                    em = st.text_input("Email")
                    rl = st.selectbox("Quyền", ["user", "admin"])
                    if st.form_submit_button("Tạo"):
                        hp = stauth.Hasher.hash(pw)
                        conn.execute("INSERT INTO users VALUES (?,?,?,?,?)", (un, nm, hp, rl, em))
                        conn.commit()
                        st.success("Đã tạo!")
        conn.close()
    elif st.session_state["authentication_status"] is False:
        st.error('Sai thông tin!')
    elif st.session_state["authentication_status"] is None:
        st.warning('Vui lòng đăng nhập.')

if __name__ == '__main__':
    main()
