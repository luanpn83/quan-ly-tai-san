import streamlit as st
import sqlite3
import pandas as pd
import qrcode
import plotly.express as px
import streamlit_authenticator as stauth
from io import BytesIO
from datetime import datetime

# --- 1. KHỞI TẠO CƠ SỞ DỮ LIỆU ---
def init_db():
    conn = sqlite3.connect('he_thong_quan_ly_v2.db')
    c = conn.cursor()
    # Bảng tài sản
    c.execute('''CREATE TABLE IF NOT EXISTS assets 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, ten_tai_san TEXT, loai_tai_san TEXT, 
                  gia_tri REAL, tinh_trang TEXT, nguoi_su_dung TEXT, vi_tri TEXT)''')
    # Bảng lịch sử bảo trì
    c.execute('''CREATE TABLE IF NOT EXISTS maintenance 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, asset_id INTEGER, 
                  ngay_thuc_hien DATE, noi_dung TEXT, chi_phi REAL)''')
    # Bảng người dùng
    c.execute('''CREATE TABLE IF NOT EXISTS users 
                 (username TEXT PRIMARY KEY, name TEXT, password TEXT, role TEXT)''')
    
    # Tạo admin mặc định nếu chưa có (Pass: admin123)
    c.execute("SELECT * FROM users WHERE username='admin'")
    if not c.fetchone():
        hashed_pw = stauth.Hasher.hash('admin123')
        c.execute("INSERT INTO users VALUES ('admin', 'Quản trị viên', ?, 'admin')", (hashed_pw,))
    conn.commit()
    conn.close()

# --- 2. CÁC HÀM TIỆN ÍCH ---
def fetch_users_config():
    conn = sqlite3.connect('he_thong_quan_ly.db')
    df = pd.read_sql_query("SELECT * FROM users", conn)
    conn.close()
    
    # Cấu trúc phải có key 'usernames' ở ngoài cùng
    config = {'usernames': {}} 
    
    for _, row in df.iterrows():
        config['usernames'][row['username']] = {
            'name': row['name'],
            'password': row['password'],
            'role': row['role']
        }
    return config

def generate_qr(url):
    qr = qrcode.make(url)
    buf = BytesIO()
    qr.save(buf, format="PNG")
    return buf.getvalue()

# --- 3. GIAO DIỆN CHI TIẾT (KHI QUÉT QR) ---
def show_public_details(asset_id):
    conn = sqlite3.connect('he_thong_quan_ly.db')
    asset = pd.read_sql_query(f"SELECT * FROM assets WHERE id={asset_id}", conn)
    history = pd.read_sql_query(f"SELECT * FROM maintenance WHERE asset_id={asset_id}", conn)
    conn.close()
    if not asset.empty:
        st.success(f"### Tài sản: {asset.iloc[0]['ten_tai_san']}")
        st.write(f"**Trạng thái:** {asset.iloc[0]['tinh_trang']} | **Vị trí:** {asset.iloc[0]['vi_tri']}")
        st.subheader("📜 Lịch sử bảo trì")
        st.table(history[['ngay_thuc_hien', 'noi_dung', 'chi_phi']])
    else:
        st.error("Không tìm thấy tài sản.")

# --- 4. GIAO DIỆN CHÍNH ---
def main():
    st.set_page_config(page_title="Quản Lý Tài Sản Pro", layout="wide")
    init_db()

    # 1. Khởi tạo bộ xác thực
    config = fetch_users_config()
    authenticator = stauth.Authenticate(
        credentials=config,          # config chứa 'usernames'
        cookie_name='asset_cookie',
        cookie_key='auth_key',
        cookie_expiry_days=1,
        key='unique_auth_key'        # Khắc phục lỗi Duplicate Element Key
    )

    # 2. Gọi hàm login (Cấu trúc mới của bản 0.3.0+)
    authenticator.login(location='main')

    # 3. Kiểm tra trạng thái từ session_state
    if st.session_state["authentication_status"]:
        name = st.session_state["name"]
        username = st.session_state["username"]
        role = config['usernames'][username]['role']
        
        st.sidebar.title(f"Chào {name}")
        authenticator.logout('Đăng xuất', 'sidebar')
        
        # ... (Phần menu và các tính năng khác giữ nguyên) ...

    elif st.session_state["authentication_status"] is False:
        st.error('Sai tài khoản hoặc mật khẩu')
    elif st.session_state["authentication_status"] is None:
        st.warning('Vui lòng đăng nhập để sử dụng hệ thống.')

    # Kiểm tra truy cập qua QR (không cần login)
    if "id" in st.query_params:
        show_public_details(st.query_params["id"])
        if st.button("Trang chủ"): st.query_params.clear(); st.rerun()
        return

    # Hệ thống Đăng nhập
    config = fetch_users_config()
    authenticator = stauth.Authenticate(config, 'asset_cookie', 'auth_key', cookie_expiry_days=1)
    # Phiên bản mới chỉ cần gọi login(). 
    # Kết quả trả về có thể khác nhau tùy bản, nhưng an toàn nhất là lấy từ session_state
    authenticator.login(location='main')
    
    if st.session_state["authentication_status"]:
        name = st.session_state["name"]
        username = st.session_state["username"]
        # Tiếp tục code khi đăng nhập thành công...

    if status:
        role = config['usernames'][username]['role']
        st.sidebar.title(f"Chào {name}")
        authenticator.logout('Đăng xuất', 'sidebar')

        # Menu phân quyền
        if role == 'admin':
            menu = ["📊 Dashboard", "📋 Danh sách", "🔧 Bảo trì & QR", "⚙️ Hệ thống"]
        else:
            menu = ["📊 Dashboard", "📋 Danh sách"]
        choice = st.sidebar.radio("Chức năng", menu)

        # --- XỬ LÝ CÁC TAB ---
        conn = sqlite3.connect('he_thong_quan_ly.db')
        
        if choice == "📊 Dashboard":
            st.title("Báo cáo tài sản")
            df_assets = pd.read_sql_query("SELECT * FROM assets", conn)
            if not df_assets.empty:
                c1, c2, c3 = st.columns(3)
                c1.metric("Tổng tài sản", len(df_assets))
                c2.metric("Tổng giá trị", f"{df_assets['gia_tri'].sum():,.0f} đ")
                c3.metric("Cần bảo trì", len(df_assets[df_assets['tinh_trang']=="Cần bảo trì"]))
                
                fig = px.pie(df_assets, names='tinh_trang', title="Tỷ lệ tình trạng")
                st.plotly_chart(fig, use_container_width=True)
            else: st.info("Chưa có dữ liệu.")

        elif choice == "📋 Danh sách":
            st.title("Danh mục tài sản")
            df_assets = pd.read_sql_query("SELECT * FROM assets", conn)
            st.dataframe(df_assets, use_container_width=True)
            
            if role == 'admin' and not df_assets.empty:
                if st.button("🗑️ Xóa tài sản đã chọn"):
                    st.warning("Tính năng này cần chọn ID cụ thể.")

        elif choice == "🔧 Bảo trì & QR":
            df_assets = pd.read_sql_query("SELECT id, ten_tai_san FROM assets", conn)
            t1, t2 = st.tabs(["Ghi chú bảo trì", "In mã QR"])
            with t1:
                sel = st.selectbox("Chọn tài sản", [f"{r['id']}-{r['ten_tai_san']}" for _,r in df_assets.iterrows()])
                with st.form("maint"):
                    nd = st.text_area("Nội dung sửa chữa")
                    cp = st.number_input("Chi phí", min_value=0.0)
                    if st.form_submit_button("Lưu"):
                        conn.cursor().execute("INSERT INTO maintenance (asset_id, ngay_thuc_hien, noi_dung, chi_phi) VALUES (?,?,?,?)",
                                              (sel.split('-')[0], datetime.now().date(), nd, cp))
                        conn.commit()
                        st.success("Đã lưu!")
            with t2:
                sel_qr = st.selectbox("Chọn tài sản in mã", [f"{r['id']}-{r['ten_tai_san']}" for _,r in df_assets.iterrows()])
                url = f"https://your-app.streamlit.app/?id={sel_qr.split('-')[0]}" # Thay URL thật
                st.image(generate_qr(url), caption=f"QR ID: {sel_qr.split('-')[0]}")

        elif choice == "⚙️ Hệ thống":
            st.subheader("Thêm tài sản mới")
            with st.form("add_asset"):
                ten = st.text_input("Tên tài sản")
                loai = st.selectbox("Loại", ["Điện tử", "Nội thất", "Khác"])
                gia = st.number_input("Giá trị", min_value=0.0)
                tt = st.selectbox("Tình trạng", ["Mới", "Tốt", "Cần bảo trì", "Hỏng"])
                vt = st.text_input("Vị trí")
                if st.form_submit_button("Thêm"):
                    conn.cursor().execute("INSERT INTO assets (ten_tai_san, loai_tai_san, gia_tri, tinh_trang, vi_tri) VALUES (?,?,?,?,?)",
                                          (ten, loai, gia, tt, vt))
                    conn.commit()
                    st.success("Đã thêm!")
        conn.close()

    elif status == False: st.error('Sai tài khoản.')
    elif status == None: st.warning('Hãy đăng nhập.')

if __name__ == '__main__':

    main()









