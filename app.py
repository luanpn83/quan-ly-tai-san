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
    conn = sqlite3.connect('he_thong_quan_ly_v2.db') # Sử dụng tên mới để đảm bảo sạch lỗi
    c = conn.cursor()
    # Bảng tài sản
    c.execute('''CREATE TABLE IF NOT EXISTS assets 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, ten_tai_san TEXT, loai_tai_san TEXT, 
                  gia_tri REAL, tinh_trang TEXT, nguoi_su_dung TEXT, vi_tri TEXT)''')
    # Bảng bảo trì
    c.execute('''CREATE TABLE IF NOT EXISTS maintenance 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, asset_id INTEGER, 
                  ngay_thuc_hien DATE, noi_dung TEXT, chi_phi REAL)''')
    # Bảng người dùng
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (username TEXT PRIMARY KEY, name TEXT, password TEXT, role TEXT, email TEXT)''')
    # Bảng lịch sử điều chuyển
    c.execute('''CREATE TABLE IF NOT EXISTS transfer_history 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, asset_id INTEGER, 
                  tu_nguoi TEXT, sang_nguoi TEXT, ngay_chuyen DATE, ghi_chu TEXT)''')
    
    # Đảm bảo admin mặc định tồn tại
    c.execute("SELECT * FROM users WHERE username='admin'")
    if not c.fetchone():
        hashed_pw = stauth.Hasher.hash('admin123')
        c.execute("INSERT INTO users VALUES ('admin', 'Quản trị viên', ?, 'admin', 'admin@example.com')", (hashed_pw,))
    
    conn.commit()
    conn.close()

def fetch_users_config():
    init_db()
    conn = sqlite3.connect('he_thong_quan_ly_v2.db')
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
        msg['Subject'] = f"🔔 [Thông báo] Điều chuyển tài sản: {asset_name}"
        
        body = f"""
        <h3>Hệ thống Quản lý Tài sản</h3>
        <p>Ghi nhận giao dịch điều chuyển mới:</p>
        <ul>
            <li><b>Tài sản:</b> {asset_name}</li>
            <li><b>Từ:</b> {from_user if from_user else 'Kho'}</li>
            <li><b>Sang:</b> {to_user}</li>
            <li><b>Ghi chú:</b> {note}</li>
        </ul>
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
    conn = sqlite3.connect('he_thong_quan_ly_v2.db')
    asset = pd.read_sql_query(f"SELECT * FROM assets WHERE id={asset_id}", conn)
    conn.close()
    if not asset.empty:
        st.success(f"### Thông tin tài sản: {asset.iloc[0]['ten_tai_san']}")
        st.info(f"👤 Người giữ: {asset.iloc[0]['nguoi_su_dung'] or 'N/A'}")
        st.write(f"📍 Vị trí: {asset.iloc[0]['vi_tri']} | 🛠 Trạng thái: {asset.iloc[0]['tinh_trang']}")
    else:
        st.error("Không tìm thấy dữ liệu.")

# --- 3. GIAO DIỆN CHÍNH ---

def main():
    st.set_page_config(page_title="Hệ thống Quản lý Tài sản Pro", layout="wide")
    
    # 3.1. Truy cập qua QR (Không cần Login)
    if "id" in st.query_params:
        show_public_details(st.query_params["id"])
        if st.button("Về trang đăng nhập"):
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
        st.sidebar.write(f"Quyền: {role.upper()}")
        authenticator.logout('Đăng xuất', 'sidebar')
        
        # Menu phân quyền
        menu = ["📊 Dashboard", "📋 Danh sách"]
        if role == 'admin':
            menu += ["🔧 Vận hành & Điều chuyển", "⚙️ Hệ thống"]
        choice = st.sidebar.radio("Chức năng chính", menu)

        conn = sqlite3.connect('he_thong_quan_ly_v2.db')

        if choice == "📊 Dashboard":
            st.title("📈 Báo cáo tổng quan")
            df = pd.read_sql_query("SELECT * FROM assets", conn)
            if not df.empty:
                c1, c2, c3 = st.columns(3)
                c1.metric("Tổng tài sản", len(df))
                c2.metric("Tổng giá trị", f"{df['gia_tri'].sum():,.0f} đ")
                c3.metric("Cần bảo trì", len(df[df['tinh_trang']=="Cần bảo trì"]))
                st.plotly_chart(px.pie(df, names='tinh_trang', title="Tỷ lệ tình trạng"), use_container_width=True)
            else:
                st.info("Chưa có dữ liệu.")

        elif choice == "📋 Danh sách":
            st.title("📋 Danh mục tài sản")
            df = pd.read_sql_query("SELECT id, ten_tai_san, loai_tai_san, nguoi_su_dung, vi_tri, tinh_trang FROM assets", conn)
            st.dataframe(df, use_container_width=True)

        elif choice == "🔧 Vận hành & Điều chuyển":
            st.title("🔧 Quản lý tài sản")
            df_as = pd.read_sql_query("SELECT * FROM assets", conn)
            df_us = pd.read_sql_query("SELECT name FROM users", conn)
            
            t1, t2, t3 = st.tabs(["Ghi chú bảo trì", "Điều chuyển nhân sự", "In mã QR"])
            
            with t1:
                sel = st.selectbox("Chọn tài sản", [f"{r['id']}-{r['ten_tai_san']}" for _,r in df_as.iterrows()])
                with st.form("bt_form"):
                    nd = st.text_area("Nội dung thực hiện")
                    if st.form_submit_button("Lưu bảo trì"):
                        conn.execute("INSERT INTO maintenance (asset_id, ngay_thuc_hien, noi_dung) VALUES (?,?,?)",
                                     (sel.split('-')[0], datetime.now().date(), nd))
                        conn.commit()
                        st.success("Đã ghi sổ bảo trì!")

            with t2:
                st.subheader("Bàn giao cho người khác")
                sel_dc = st.selectbox("Chọn tài sản điều chuyển", 
                                     [f"{r['id']}-{r['ten_tai_san']} ({r['nguoi_su_dung'] or 'Kho'})" for _,r in df_as.iterrows()])
                aid = sel_dc.split('-')[0]
                # Lấy tên tài sản và người cũ
                row_as = df_as[df_as['id']==int(aid)].iloc[0]
                old_u = row_as['nguoi_su_dung']
                t_ten = row_as['ten_tai_san']
                
                new_u = st.selectbox("Nhân viên nhận bàn giao", df_us['name'].tolist())
                note = st.text_input("Ghi chú điều chuyển")
                
                if st.button("Xác nhận điều chuyển"):
                    conn.execute("UPDATE assets SET nguoi_su_dung = ? WHERE id = ?", (new_u, aid))
                    conn.execute("INSERT INTO transfer_history (asset_id, tu_nguoi, sang_nguoi, ngay_chuyen, ghi_chu) VALUES (?,?,?,?,?)",
                                (aid, old_u, new_u, datetime.now().date(), note))
                    conn.commit()
                    
                    with st.spinner("Đang gửi email thông báo..."):
                        send_email_notification(t_ten, old_u, new_u, note)
                    
                    st.success("Điều chuyển thành công!")
                    st.rerun()

            with t3:
                sel_qr = st.selectbox("In mã QR", [f"{r['id']}-{r['ten_tai_san']}" for _,r in df_as.iterrows()])
                # LƯU Ý: Thay URL bên dưới bằng link thật sau khi deploy
                url = f"https://quan-ly-tai-san.streamlit.app/?id={sel_qr.split('-')[0]}"
                st.image(generate_qr(url), caption=f"Quét để xem ID: {sel_qr.split('-')[0]}")

        elif choice == "⚙️ Hệ thống":
            st.title("⚙️ Cấu hình hệ thống")
            tab_a, tab_u = st.tabs(["Thêm tài sản", "Thêm người dùng"])
            with tab_a:
                with st.form("add_a"):
                    ten = st.text_input("Tên tài sản")
                    gia = st.number_input("Giá trị", min_value=0.0)
                    vt = st.text_input("Vị trí")
                    if st.form_submit_button("Thêm tài sản"):
                        conn.execute("INSERT INTO assets (ten_tai_san, gia_tri, tinh_trang, vi_tri) VALUES (?,?,'Mới',?)", (ten, gia, vt))
                        conn.commit()
                        st.success("Đã thêm!")
            with tab_u:
                with st.form("add_u"):
                    un = st.text_input("Username")
                    nm = st.text_input("Họ tên")
                    pw = st.text_input("Mật khẩu", type="password")
                    em = st.text_input("Email nhân viên")
                    rl = st.selectbox("Vai trò", ["user", "admin"])
                    if st.form_submit_button("Tạo tài khoản"):
                        hp = stauth.Hasher.hash(pw)
                        conn.execute("INSERT INTO users VALUES (?,?,?,?,?)", (un, nm, hp, rl, em))
                        conn.commit()
                        st.success("Đã tạo người dùng!")
        conn.close()
        
    elif st.session_state["authentication_status"] is False:
        st.error('Sai tài khoản hoặc mật khẩu!')
    elif st.session_state["authentication_status"] is None:
        st.info('Vui lòng đăng nhập để vào hệ thống.')

if __name__ == '__main__':
    main()
