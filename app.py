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
    # Nội dung mã QR bao gồm thông tin cơ bản của tài sản
    qr_data = f"Mã TS: {asset_info['ma_tai_san']}\nTên: {asset_info['ten_tai_san']}\nVị trí: {asset_info['vi_tri']}\nNgười QL: {asset_info['nguoi_quan_ly']}"
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(qr_data)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Chuyển ảnh sang dạng Bytes để Streamlit có thể hiển thị/tải về
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
            st.title("📋 Danh mục tài sản & Tạo mã QR")
            
            # Hiển thị bảng danh sách
            df = pd.read_sql_query('''SELECT ma_tai_san, ten_tai_san, loai_tai_san, 
                                      ngay_su_dung, vi_tri, nguoi_quan_ly, tinh_trang 
                                      FROM assets''', conn)
            
            if not df.empty:
                st.dataframe(df, use_container_width=True)
                
                st.write("---")
                st.subheader("🖼️ Tạo mã QR truy xuất tài sản")
                
                # Chọn tài sản để tạo mã QR
                col_sel, col_qr = st.columns([1, 1])
                
                with col_sel:
                    selected_asset_code = st.selectbox(
                        "Chọn mã tài sản để tạo QR", 
                        df['ma_tai_san'].tolist()
                    )
                    asset_row = df[df['ma_tai_san'] == selected_asset_code].iloc[0]
                    
                    st.info(f"**Tên tài sản:** {asset_row['ten_tai_san']}\n\n"
                            f"**Vị trí:** {asset_row['vi_tri']}\n\n"
                            f"**Người giữ:** {asset_row['nguoi_quan_ly']}")
                
                with col_qr:
                    # Tạo và hiển thị mã QR
                    qr_img = generate_qr_code(asset_row)
                    st.image(qr_img, caption=f"Mã QR của {selected_asset_code}", width=250)
                    
                    # Nút tải mã QR về
                    st.download_button(
                        label="📥 Tải mã QR về máy",
                        data=qr_img,
                        file_name=f"QR_{selected_asset_code}.png",
                        mime="image/png"
                    )
            else:
                st.info("Chưa có tài sản nào trong hệ thống.")

        elif choice == "⚙️ Cấu hình hệ thống":
            st.title("⚙️ Quản trị hệ thống")
            t1, t2, t3 = st.tabs(["📦 Thêm tài sản mới", "📑 Loại tài sản", "👥 Quản lý nhân viên"])
            
            with t1:
                st.subheader("Nhập thông tin tài sản")
                suggested_code = get_next_asset_code()
                list_types = pd.read_sql_query("SELECT ten_loai FROM asset_types", conn)['ten_loai'].tolist()
                list_users = pd.read_sql_query("SELECT name FROM users", conn)['name'].tolist()
                
                with st.form("f_add_asset", clear_on_submit=True):
                    c1, c2 = st.columns(2)
                    with c1:
                        st.text_input("Mã tài sản (Tự động)", value=suggested_code, disabled=True)
                        ten_ts = st.text_input("Tên tài sản *")
                        loai_ts = st.selectbox("Chọn loại tài sản *", list_types if list_types else ["Chưa có loại"])
                        ngay_sd = st.date_input("Ngày đưa vào sử dụng", datetime.now())
                    with c2:
                        vi_tri_ts = st.text_input("Vị trí đặt tài sản *")
                        nguoi_ql = st.selectbox("Người quản lý/Sử dụng", list_users)
                        tt = st.selectbox("Tình trạng", ["Mới", "Đang dùng tốt", "Cần bảo trì", "Hỏng"])
                        gia_tri = st.number_input("Giá trị (VNĐ)", min_value=0.0)
                    
                    if st.form_submit_button("Lưu tài sản"):
                        if ten_ts and vi_tri_ts and list_types:
                            conn.execute('''INSERT INTO assets 
                                (loai_tai_san, ma_tai_san, ten_tai_san, ngay_su_dung, vi_tri, nguoi_quan_ly, tinh_trang, gia_tri) 
                                VALUES (?,?,?,?,?,?,?,?)''', 
                                (loai_ts, suggested_code, ten_ts, ngay_sd, vi_tri_ts, nguoi_ql, tt, gia_tri))
                            conn.commit()
                            st.success(f"Đã thêm tài sản {suggested_code} thành công!")
                            st.rerun()
                        else:
                            st.error("Vui lòng điền đủ Tên, Vị trí và cấu hình Loại tài sản.")

            # Tab Loại tài sản & Nhân viên (Giữ nguyên)
            with t2:
                st.subheader("Quản lý danh mục loại")
                with st.form("f_type"):
                    m_val = st.text_input("Mã loại")
                    t_val = st.text_input("Tên loại")
                    if st.form_submit_button("Thêm loại"):
                        conn.execute("INSERT INTO asset_types VALUES (?,?)", (m_val, t_val))
                        conn.commit(); st.rerun()
                st.dataframe(pd.read_sql_query("SELECT * FROM asset_types", conn), use_container_width=True)

            with t3:
                st.subheader("Quản lý nhân viên & Phân quyền")
                col_f, col_l = st.columns([1, 2])
                with col_f:
                    with st.form("f_u"):
                        u = st.text_input("Username")
                        n = st.text_input("Họ tên")
                        p = st.text_input("Password", type="password")
                        r = st.selectbox("Quyền", ["user", "admin"])
                        if st.form_submit_button("Tạo nhân viên"):
                            hp = stauth.Hasher.hash(p)
                            conn.execute("INSERT INTO users (username, name, password, role) VALUES (?,?,?,?)", (u, n, hp, r))
                            conn.commit(); st.rerun()
                with col_l:
                    st.dataframe(pd.read_sql_query("SELECT username, name, role FROM users", conn), use_container_width=True)

        conn.close()
    
    elif st.session_state["authentication_status"] is False:
        st.error('Sai tài khoản hoặc mật khẩu')
    elif st.session_state["authentication_status"] is None:
        st.info('Vui lòng đăng nhập.')

if __name__ == '__main__':
    main()
