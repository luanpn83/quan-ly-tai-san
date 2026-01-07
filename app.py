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
    
    # 1.1. Tạo các bảng nếu chưa có
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

    # 1.2. KIỂM TRA VÀ TỰ ĐỘNG THÊM CỘT 'email' NẾU THIẾU (Sửa lỗi KeyError)
    c.execute("PRAGMA table_info(users)")
    columns = [column[1] for column in c.fetchall()]
    if 'email' not in columns:
        try:
            c.execute("ALTER TABLE users ADD COLUMN email TEXT DEFAULT ''")
            conn.commit()
        except Exception as e:
            st.error(f"Lỗi nâng cấp DB: {e}")

    # 1.3. Đảm bảo admin mặc định tồn tại
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
        # Dùng .get() để an toàn hơn hoặc truy cập trực tiếp vì init_db đã đảm bảo có cột
        config['usernames'][row['username']] = {
            'name': row['name'], 
            'password': row['password'], 
            'role': row['role'], 
            'email': row.get('email', '') 
        }
    return config

# --- 2. TIỆN ÍCH (EMAIL & QR) ---

def send_email_notification(asset_name, from_user, to_user, note):
    try:
        # Lấy thông tin từ Streamlit Secrets
        sender = st.secrets["SENDER_EMAIL"]
        pwd = st.secrets["SENDER_PASSWORD"]
        receiver = st.secrets["RECEIVER_EMAIL"]

        msg = MIMEMultipart()
        msg['From'] = sender
        msg['To'] = receiver
        msg['Subject'] = f"🔔 [Asset Management] Điều chuyển: {asset_name}"
        
        body = f"""
        <h3>Thông báo điều chuyển tài sản</h3>
        <p><b>Tài sản:</b> {asset_name}</p>
        <p><b>Bàn giao từ:</b> {from_user if from_user else 'Kho/Chưa xác định'}</p>
        <p><b>Người nhận mới:</b> {to_user}</p>
        <p><b>Ngày:</b> {datetime.now().strftime('%d/%m/%Y %H:%M')}</p>
        <p><b>Ghi chú:</b> {note}</p>
        """
        msg.attach(MIMEText(body, 'html'))
        
        server = smtplib.SMTP("smtp.gmail.com", 587)
        server.starttls()
        server.login(sender, pwd)
        server.sendmail(sender, receiver, msg.as_string())
        server.quit()
        return True
    except Exception:
        return False

def generate_qr(url):
    qr = qrcode.make(url)
    buf = BytesIO()
    qr.save(buf, format="PNG")
    return buf.getvalue()

# --- 3. GIAO DIỆN CHÍNH ---

def main():
    st.set_page_config(page_title="Asset Pro", layout="wide")
    
    # 3.1. Xem QR Code (Không cần login)
    if "id" in st.query_params:
        asset_id = st.query_params["id"]
        conn = sqlite3.connect('he_thong_quan_ly.db')
        asset = pd.read_sql_query(f"SELECT * FROM assets WHERE id={asset_id}", conn)
        conn.close()
        if not asset.empty:
            st.success(f"### Tài sản: {asset.iloc[0]['ten_tai_san']}")
            st.write(f"👤 Người sử dụng: **{asset.iloc[0]['nguoi_su_dung']}**")
            st.write(f"📍 Vị trí: {asset.iloc[0]['vi_tri']} | Trạng thái: {asset.iloc[0]['tinh_trang']}")
        if st.button("Đăng nhập hệ thống"):
            st.query_params.clear()
            st.rerun()
        return

    # 3.2. Đăng nhập
    init_db()
    config = fetch_users_config()
    
    if 'authenticator' not in st.session_state:
        st.session_state['authenticator'] = stauth.Authenticate(
            config, 'asset_cookie', 'auth_key', cookie_expiry_days=1
        )
    
    authenticator = st.session_state['authenticator']
    authenticator.login(location='main')

    if st.session_state["authentication_status"]:
        name = st.session_state["name"]
        username = st.session_state["username"]
        role = config['usernames'][username]['role']
        
        st.sidebar.title(f"Chào {name}")
        authenticator.logout('Đăng xuất', 'sidebar')
        
        menu = ["📊 Dashboard", "📋 Danh sách"]
        if role == 'admin':
            menu += ["🔧 Vận hành & Điều chuyển", "⚙️ Hệ thống"]
        choice = st.sidebar.radio("Menu", menu)

        conn = sqlite3.connect('he_thong_quan_ly.db')

        if choice == "📊 Dashboard":
            st.title("📈 Tổng quan tài sản")
            df = pd.read_sql_query("SELECT * FROM assets", conn)
            if not df.empty:
                c1, c2, c3 = st.columns(3)
                c1.metric("Tổng tài sản", len(df))
                c2.metric("Giá trị", f"{df['gia_tri'].sum():,.0f} đ")
                c3.metric("Cần bảo trì", len(df[df['tinh_trang']=="Cần bảo trì"]))
                st.plotly_chart(px.pie(df, names='tinh_trang', hole=0.3), use_container_width=True)

        elif choice == "📋 Danh sách":
            st.title("📋 Danh mục tài sản")
            df = pd.read_sql_query("SELECT id, ten_tai_san, nguoi_su_dung, vi_tri, tinh_trang FROM assets", conn)
            st.dataframe(df, use_container_width=True)

        elif choice == "🔧 Vận hành & Điều chuyển":
            st.title("🔧 Điều chuyển & Bảo trì")
            df_as = pd.read_sql_query("SELECT * FROM assets", conn)
            df_us = pd.read_sql_query("SELECT name FROM users", conn)
            
            tab_bt, tab_dc, tab_qr = st.tabs(["Bảo trì", "Điều chuyển", "Mã QR"])
            
            with tab_bt:
                sel = st.selectbox("Chọn tài sản", [f"{r['id']}-{r['ten_tai_san']}" for _,r in df_as.iterrows()])
                with st.form("f_bt"):
                    nd = st.text_area("Nội dung bảo trì")
                    if st.form_submit_button("Lưu"):
                        conn.execute("INSERT INTO maintenance (asset_id, ngay_thuc_hien, noi_dung) VALUES (?,?,?)",
                                     (sel.split('-')[0], datetime.now().date(), nd))
                        conn.commit()
                        st.success("Đã ghi nhận!")

            with tab_dc:
                sel_dc = st.selectbox("Tài sản cần chuyển", [f"{r['id']}-{r['ten_tai_san']} ({r['nguoi_su_dung'] or 'Trống'})" for _,r in df_as.iterrows()])
                aid = sel_dc.split('-')[0]
                old_u = next(r['nguoi_su_dung'] for _,r in df_as.iterrows() if str(r['id']) == aid)
                new_u = st.selectbox("Người nhận mới", df_us['name'].tolist())
                note = st.text_input("Ghi chú điều chuyển")
                
                if st.button("Xác nhận điều chuyển"):
                    conn.execute("UPDATE assets SET nguoi_su_dung = ? WHERE id = ?", (new_u, aid))
                    conn.execute("INSERT INTO transfer_history (asset_id, tu_nguoi, sang_nguoi, ngay_chuyen, ghi_chu) VALUES (?,?,?,?,?)",
                                (aid, old_u, new_u, datetime.now().date(), note))
                    conn.commit()
                    with st.spinner("Đang gửi mail..."):
                        send_email_notification(sel_dc.split('-')[1], old_u, new_u, note)
                    st.success("Điều chuyển thành công!")
                    st.rerun()

            with tab_qr:
                sel_qr = st.selectbox("In mã QR", [f"{r['id']}-{r['ten_tai_san']}" for _,r in df_as.iterrows()])
                # Thay URL bằng link thật sau khi deploy
                url = f"https://quan-ly-tai-san.streamlit.app/?id={sel_qr.split('-')[0]}"
                st.image(generate_qr(url), caption=f"ID: {sel_qr.split('-')[0]}")

        elif choice == "⚙️ Hệ thống":
            st.title("⚙️ Quản trị hệ thống")
            t1, t2 = st.tabs(["Thêm tài sản", "Quản lý nhân viên"])
            with t1:
                with st.form("f_as"):
                    ten = st.text_input("Tên tài sản")
                    gia = st.number_input("Giá trị", min_value=0.0)
                    vt = st.text_input("Vị trí")
                    if st.form_submit_button("Thêm"):
                        conn.execute("INSERT INTO assets (ten_tai_san, gia_tri, tinh_trang, vi_tri) VALUES (?,?,'Mới',?)", (ten, gia, vt))
                        conn.commit()
                        st.success("Đã thêm tài sản!")
            with t2:
                with st.form("f_us"):
                    un = st.text_input("Username")
                    nm = st.text_input("Họ tên")
                    pw = st.text_input("Mật khẩu", type="password")
                    em = st.text_input("Email nhân viên")
                    rl = st.selectbox("Quyền", ["user", "admin"])
                    if st.form_submit_button("Tạo tài khoản"):
                        hp = stauth.Hasher.hash(pw)
                        conn.execute("INSERT INTO users VALUES (?,?,?,?,?)", (un, nm, hp, rl, em))
                        conn.commit()
                        st.success("Đã tạo!")
                        st.rerun()
        conn.close()

    elif st.session_state["authentication_status"] is False:
        st.error('Tài khoản hoặc mật khẩu không đúng.')
    elif st.session_state["authentication_status"] is None:
        st.info('Vui lòng đăng nhập.')

if __name__ == '__main__':
    main()
