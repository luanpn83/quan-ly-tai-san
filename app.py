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

# --- 2. HÀM TẠO MÃ QR (CHỨA URL TRUY XUẤT INTERNET) ---

def generate_qr_code(ma_tai_san):
    # Lấy URL của ứng dụng. Khi chạy local là localhost, khi triển khai lên mạng hãy thay bằng domain thực tế.
    # Bạn có thể cấu hình BASE_URL trong Streamlit Secrets
    base_url = st.secrets.get("BASE_URL", "http://localhost:8501")
    
    # Tạo URL kèm tham số để truy xuất trực tiếp
    qr_url = f"{base_url}?view_asset={ma_tai_san}"
    
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(qr_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

# --- 3. HÀM HIỂN THỊ THÔNG TIN CHI TIẾT KHI QUÉT MÃ ---

def show_asset_details(ma_tai_san):
    conn = sqlite3.connect('he_thong_quan_ly.db')
    df = pd.read_sql_query("SELECT * FROM assets WHERE ma_tai_san=?", conn, params=(ma_tai_san,))
    conn.close()
    
    if not df.empty:
        asset = df.iloc[0]
        st.title(f"🔍 Tra cứu nguồn gốc tài sản: {asset['ten_tai_san']}")
        st.info(f"Mã định danh hệ thống: **{asset['ma_tai_san']}**")
        
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("📦 Thông tin cơ bản")
            st.write(f"- **Loại tài sản:** {asset['loai_tai_san']}")
            st.write(f"- **Tình trạng hiện tại:** {asset['tinh_trang']}")
            st.write(f"- **Giá trị tài sản:** {asset['gia_tri']:,.0f} VNĐ")
        
        with col2:
            st.subheader("📍 Nguồn gốc & Vị trí")
            st.write(f"- **Ngày đưa vào sử dụng:** {asset['ngay_su_dung']}")
            st.write(f"- **Vị trí lắp đặt/lưu trữ:** {asset['vi_tri']}")
            st.write(f"- **Cán bộ quản lý:** {asset['nguoi_quan_ly']}")
        
        st.markdown("---")
        if st.button("⬅️ Quay lại trang đăng nhập"):
            st.query_params.clear()
            st.rerun()
    else:
        st.error("❌ Không tìm thấy thông tin cho mã tài sản này!")

# --- 4. GIAO DIỆN CHÍNH ---

def main():
    st.set_page_config(page_title="Hệ thống Quản lý Tài sản TV", layout="wide")
    init_db()

    # KIỂM TRA NẾU TRUY CẬP QUA MÃ QR (URL PARAMS)
    query_params = st.query_params
    if "view_asset" in query_params:
        show_asset_details(query_params["view_asset"])
        return # Dừng chương trình tại đây để chỉ hiện thông tin tra cứu

    # LOGIC ĐĂNG NHẬP VÀ CÁC CHỨC NĂNG CŨ
    config = fetch_users_config()
    if 'authenticator' not in st.session_state:
        st.session_state['authenticator'] = stauth.Authenticate(config, 'asset_cookie', 'auth_key', cookie_expiry_days=1)
    
    authenticator = st.session_state['authenticator']
    authenticator.login(location='main')

    if st.session_state["authentication_status"]:
        # ... (Toàn bộ logic Dashboard, Danh sách, Cấu hình giữ nguyên như file của bạn) ...
        render_main_app(config)
    elif st.session_state["authentication_status"] is False:
        st.error('Sai tài khoản hoặc mật khẩu')
    elif st.session_state["authentication_status"] is None:
        st.info('Vui lòng đăng nhập để quản lý.')

def render_main_app(config):
    username_logged = st.session_state["username"]
    role = config['usernames'].get(username_logged, {}).get('role')
    
    st.sidebar.title(f"Chào {st.session_state['name']}")
    st.session_state['authenticator'].logout('Đăng xuất', 'sidebar')
    
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
            st.subheader("🖼️ Tạo mã QR truy xuất qua Internet")
            
            selected_code = st.selectbox("Chọn mã tài sản để tạo QR", df['ma_tai_san'].tolist())
            df_selected = df[df['ma_tai_san'] == selected_code]
            
            if not df_selected.empty:
                asset_row = df_selected.iloc[0]
                c1, c2 = st.columns([1, 2])
                with c1:
                    qr_img = generate_qr_code(selected_code) # Sử dụng hàm tạo QR URL mới
                    st.image(qr_img, width=250)
                    st.download_button("📥 Tải QR về", data=qr_img, file_name=f"QR_{selected_code}.png", mime="image/png")
                with c2:
                    st.success("Mã QR này cho phép quét để xem thông tin qua Internet.")
                    st.info(f"**Thông tin:** {asset_row['ten_tai_san']} - {asset_row['vi_tri']}")
        else:
            st.info("Chưa có tài sản nào.")

    elif choice == "⚙️ Cấu hình hệ thống":
        # (Giữ nguyên code phần Tab 1, 2, 3 từ file cũ của bạn)
        pass

    conn.close()

# Giữ nguyên các hàm bổ trợ của bạn
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

if __name__ == '__main__':
    main()
