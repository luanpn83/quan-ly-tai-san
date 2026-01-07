import streamlit as st
import sqlite3
import pandas as pd
import qrcode
from io import BytesIO
from datetime import datetime
import streamlit_authenticator as stauth

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
    
    # Khởi tạo Admin mặc định
    c.execute("SELECT * FROM users WHERE username='admin'")
    if not c.fetchone():
        hp = stauth.Hasher.hash('admin123')
        c.execute("INSERT INTO users (username, name, password, role) VALUES ('admin', 'Quản trị viên', ?, 'admin')", (hp,))
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
            'name': row['name'], 'password': row['password'], 'role': row['role']
        }
    return config

# --- 2. HÀM TẠO MÃ QR ---

def generate_asset_qr(data_dict):
    # Tạo chuỗi thông tin để mã hóa vào QR
    qr_content = f"MA TS: {data_dict['ma_tai_san']}\nTEN: {data_dict['ten_tai_san']}\nLOAI: {data_dict['loai_tai_san']}\nVI TRI: {data_dict['vi_tri']}\nQL: {data_dict['nguoi_quan_ly']}"
    
    qr = qrcode.QRCode(version=1, box_size=10, border=5)
    qr.add_data(qr_content)
    qr.make(fit=True)
    
    img = qr.make_image(fill_color="black", back_color="white")
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()

# --- 3. GIAO DIỆN CHÍNH ---

def main():
    st.set_page_config(page_title="Asset Pro QR", layout="wide")
    init_db()
    config = fetch_users_config()
    
    if 'authenticator' not in st.session_state:
        st.session_state['authenticator'] = stauth.Authenticate(config, 'asset_cookie', 'auth_key', cookie_expiry_days=1)
    
    authenticator = st.session_state['authenticator']
    authenticator.login(location='main')

    if st.session_state["authentication_status"]:
        role = config['usernames'].get(st.session_state["username"], {}).get('role')
        st.sidebar.title(f"Chào {st.session_state['name']}")
        authenticator.logout('Đăng xuất', 'sidebar')
        
        menu = ["📊 Dashboard", "📋 Danh sách tài sản"]
        if role == 'admin': menu += ["⚙️ Cấu hình hệ thống"]
        choice = st.sidebar.radio("Chức năng", menu)

        conn = sqlite3.connect('he_thong_quan_ly.db')

        if choice == "📋 Danh sách tài sản":
            st.title("📋 Danh mục tài sản & QR Code")
            
            df = pd.read_sql_query("SELECT * FROM assets", conn)
            
            if df.empty:
                st.info("Chưa có tài sản nào để hiển thị.")
            else:
                # Hiển thị bảng danh sách
                st.dataframe(df[['ma_tai_san', 'ten_tai_san', 'loai_tai_san', 'vi_tri', 'nguoi_quan_ly', 'tinh_trang']], use_container_width=True)
                
                st.markdown("---")
                st.subheader("🔍 Tạo mã QR truy xuất")
                
                # Cho phép chọn tài sản để tạo mã QR
                asset_list = [f"{row['ma_tai_san']} - {row['ten_tai_san']}" for _, row in df.iterrows()]
                selected_asset_str = st.selectbox("Chọn tài sản để xuất mã QR:", asset_list)
                
                if selected_asset_str:
                    selected_ma = selected_asset_str.split(" - ")[0]
                    asset_data = df[df['ma_tai_san'] == selected_ma].iloc[0].to_dict()
                    
                    col1, col2 = st.columns([1, 2])
                    with col1:
                        qr_img = generate_asset_qr(asset_data)
                        st.image(qr_img, caption=f"QR Code: {selected_ma}", width=250)
                        st.download_button(
                            label="📥 Tải mã QR về máy",
                            data=qr_img,
                            file_name=f"QR_{selected_ma}.png",
                            mime="image/png"
                        )
                    with col2:
                        st.write("**Thông tin mã hóa trong QR:**")
                        st.info(f"""
                        - **Mã:** {asset_data['ma_tai_san']}
                        - **Tên:** {asset_data['ten_tai_san']}
                        - **Loại:** {asset_data['loai_tai_san']}
                        - **Vị trí:** {asset_data['vi_tri']}
                        - **Người quản lý:** {asset_data['nguoi_quan_ly']}
                        """)

        elif choice == "⚙️ Cấu hình hệ thống":
            # (Giữ nguyên logic các Tab Thêm tài sản, Loại tài sản, Nhân viên như cũ)
            st.title("⚙️ Cấu hình hệ thống")
            # ... [Phần code quản trị giữ nguyên] ...

        conn.close()

    elif st.session_state["authentication_status"] is False:
        st.error('Sai tài khoản hoặc mật khẩu')
    elif st.session_state["authentication_status"] is None:
        st.info('Vui lòng đăng nhập.')

if __name__ == '__main__':
    main()
