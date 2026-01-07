import streamlit as st
import sqlite3
import pandas as pd
import streamlit_authenticator as stauth
import qrcode
from io import BytesIO
from datetime import datetime

# --- 1. CẤU HÌNH & DATABASE ---

def init_db():
    conn = sqlite3.connect('he_thong_quan_ly.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS assets 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  loai_tai_san TEXT, ma_tai_san TEXT, ten_tai_san TEXT, 
                  ngay_su_dung DATE, vi_tri TEXT, nguoi_quan_ly TEXT, 
                  tinh_trang TEXT, gia_tri REAL)''')
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (username TEXT PRIMARY KEY, name TEXT, password TEXT, role TEXT, 
                  email TEXT, don_vi TEXT, khu_nha TEXT, phong TEXT)''')
    c.execute('''CREATE TABLE IF NOT EXISTS asset_types 
                 (ma_loai TEXT PRIMARY KEY, ten_loai TEXT)''')
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
    except: return f"TV001"

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

# --- 2. HÀM TẠO MÃ QR ---

def generate_qr_code(asset_info):
    qr_data = f"Mã TS: {asset_info['ma_tai_san']}\nTên: {asset_info['ten_tai_san']}\nVị trí: {asset_info['vi_tri']}\nNgười QL: {asset_info['nguoi_quan_ly']}"
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(qr_data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

# --- 3. GIAO DIỆN CHÍNH ---

def main():
    st.set_page_config(page_title="Hệ thống Quản lý Tài sản TV", layout="wide")
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
        authenticator.logout('Đăng xuất', 'sidebar')
        
        menu = ["📊 Dashboard", "📋 Danh sách tài sản"]
        if role == 'admin': menu += ["⚙️ Cấu hình hệ thống"]
        choice = st.sidebar.radio("Chức năng", menu)

        conn = sqlite3.connect('he_thong_quan_ly.db')

        if choice == "📋 Danh sách tài sản":
            st.title("📋 Danh mục tài sản & QR Code")
            df = pd.read_sql_query("SELECT * FROM assets", conn)
            
            if not df.empty:
                st.dataframe(df[['ma_tai_san', 'ten_tai_san', 'loai_tai_san', 'vi_tri', 'nguoi_quan_ly', 'tinh_trang']], use_container_width=True)
                st.markdown("---")
                st.subheader("🖼️ Tạo mã QR truy xuất")
                
                selected_code = st.selectbox("Chọn mã tài sản để tạo QR", df['ma_tai_san'].tolist())
                
                # KHẮC PHỤC LỖI INDEXERROR TẠI ĐÂY
                df_selected = df[df['ma_tai_san'] == selected_code]
                
                if not df_selected.empty:
                    asset_row = df_selected.iloc[0]
                    c1, c2 = st.columns([1, 2])
                    with c1:
                        qr_img = generate_qr_code(asset_row)
                        st.image(qr_img, width=250)
                        st.download_button("📥 Tải QR về", data=qr_img, file_name=f"QR_{selected_code}.png", mime="image/png")
                    with c2:
                        st.info(f"**Thông tin mã hóa:**\n\n- Mã: {asset_row['ma_tai_san']}\n- Tên: {asset_row['ten_tai_san']}\n- Vị trí: {asset_row['vi_tri']}")
                else:
                    st.warning("Không tìm thấy dữ liệu cho mã tài sản đã chọn.")
            else:
                st.info("Chưa có tài sản nào trong hệ thống.")

        elif choice == "⚙️ Cấu hình hệ thống":
            st.title("⚙️ Quản trị hệ thống")
            t1, t2, t3 = st.tabs(["📦 Thêm tài sản mới", "📑 Loại tài sản", "👥 Quản lý nhân viên"])
            
            with t1:
                st.subheader("Nhập tài sản mới")
                suggested_code = get_next_asset_code()
                list_types = pd.read_sql_query("SELECT ten_loai FROM asset_types", conn)['ten_loai'].tolist()
                list_users = pd.read_sql_query("SELECT name FROM users", conn)['name'].tolist()
                
                with st.form("f_add_asset", clear_on_submit=True):
                    c1, c2 = st.columns(2)
                    with c1:
                        st.text_input("Mã tài sản", value=suggested_code, disabled=True)
                        ten_ts = st.text_input("Tên tài sản *")
                        loai_ts = st.selectbox("Loại tài sản", list_types if list_types else ["N/A"])
                    with c2:
                        vi_tri = st.text_input("Vị trí *")
                        nguoi_ql = st.selectbox("Người quản lý", list_users)
                        ngay_sd = st.date_input("Ngày sử dụng", datetime.now())
                    
                    if st.form_submit_button("Lưu tài sản"):
                        if ten_ts and vi_tri:
                            conn.execute("INSERT INTO assets (loai_tai_san, ma_tai_san, ten_tai_san, ngay_su_dung, vi_tri, nguoi_quan_ly) VALUES (?,?,?,?,?,?)",
                                        (loai_ts, suggested_code, ten_ts, ngay_sd, vi_tri, nguoi_ql))
                            conn.commit()
                            st.success("Đã thêm!"); st.rerun()

            with t2:
                st.subheader("Danh mục loại")
                with st.form("f_type"):
                    ml, tl = st.text_input("Mã loại"), st.text_input("Tên loại")
                    if st.form_submit_button("Thêm loại"):
                        conn.execute("INSERT INTO asset_types VALUES (?,?)", (ml, tl))
                        conn.commit(); st.rerun()
                st.dataframe(pd.read_sql_query("SELECT * FROM asset_types", conn), use_container_width=True)

            with t3:
                st.subheader("Quản lý nhân viên")
                with st.form("f_user"):
                    u, n, p = st.text_input("User"), st.text_input("Tên"), st.text_input("Pass", type="password")
                    r = st.selectbox("Quyền", ["user", "admin"])
                    if st.form_submit_button("Tạo"):
                        hp = stauth.Hasher.hash(p)
                        conn.execute("INSERT INTO users (username, name, password, role) VALUES (?,?,?,?)", (u, n, hp, r))
                        conn.commit(); st.rerun()

        conn.close()
    
    elif st.session_state["authentication_status"] is False:
        st.error('Sai tài khoản hoặc mật khẩu')
    elif st.session_state["authentication_status"] is None:
        st.info('Vui lòng đăng nhập.')

if __name__ == '__main__':
    main()
