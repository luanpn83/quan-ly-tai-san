import streamlit as st
import sqlite3
import pandas as pd
import qrcode
import plotly.express as px
import streamlit_authenticator as stauth
from io import BytesIO
from datetime import datetime

# --- 1. CÁC HÀM KHỞI TẠO (Đặt ở ngoài cùng để tránh lỗi NameError) ---

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
                 (username TEXT PRIMARY KEY, name TEXT, password TEXT, role TEXT)''')
    
    c.execute("SELECT * FROM users WHERE username='admin'")
    if not c.fetchone():
        # Sử dụng cú pháp hash mới nhất
        hashed_pw = stauth.Hasher.hash('admin123')
        c.execute("INSERT INTO users VALUES ('admin', 'Quản trị viên', ?, 'admin')", (hashed_pw,))
    conn.commit()
    conn.close()

@st.cache_resource
def get_authenticator(config):
    # Dùng cache_resource để tránh lỗi DuplicateElementKey (CookieManager)
    return stauth.Authenticate(
        config,
        'asset_cookie',
        'auth_key',
        cookie_expiry_days=1
    )

def fetch_users_config():
    # Đảm bảo bảng tồn tại trước khi đọc
    init_db() 
    conn = sqlite3.connect('he_thong_quan_ly.db')
    df = pd.read_sql_query("SELECT * FROM users", conn)
    conn.close()
    
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

def show_public_details(asset_id):
    conn = sqlite3.connect('he_thong_quan_ly.db')
    asset = pd.read_sql_query(f"SELECT * FROM assets WHERE id={asset_id}", conn)
    history = pd.read_sql_query(f"SELECT * FROM maintenance WHERE asset_id={asset_id}", conn)
    conn.close()
    if not asset.empty:
        st.success(f"### Tài sản: {asset.iloc[0]['ten_tai_san']}")
        st.write(f"**Trạng thái:** {asset.iloc[0]['tinh_trang']} | **Vị trí:** {asset.iloc[0]['vi_tri']}")
        st.subheader("📜 Lịch sử bảo trì")
        if not history.empty:
            st.table(history[['ngay_thuc_hien', 'noi_dung', 'chi_phi']])
        else:
            st.info("Chưa có lịch sử bảo trì.")
    else:
        st.error("Không tìm thấy tài sản.")

# --- 2. GIAO DIỆN CHÍNH ---

def main():
    st.set_page_config(page_title="Quản Lý Tài Sản Pro", layout="wide")
    
    # Kiểm tra truy cập qua QR (Không cần đăng nhập)
    if "id" in st.query_params:
        show_public_details(st.query_params["id"])
        if st.button("Quay lại trang chủ"):
            st.query_params.clear()
            st.rerun()
        return

    # Khởi tạo DB và lấy cấu hình người dùng
    init_db()
    config = fetch_users_config()
    
    # Khởi tạo Authenticator
    authenticator = get_authenticator(config)

    # Hiển thị form đăng nhập (Chỉ gọi 1 lần duy nhất)
    authenticator.login(location='main')

    # Kiểm tra trạng thái đăng nhập từ session_state
    if st.session_state["authentication_status"]:
        name = st.session_state["name"]
        username = st.session_state["username"]
        role = config['usernames'][username]['role']
        
        st.sidebar.title(f"Chào {name}")
        st.sidebar.write(f"Quyền: {role}")
        authenticator.logout('Đăng xuất', 'sidebar')
        
        # Menu điều hướng
        if role == 'admin':
            menu = ["📊 Dashboard", "📋 Danh sách", "🔧 Bảo trì & QR", "⚙️ Hệ thống"]
        else:
            menu = ["📊 Dashboard", "📋 Danh sách"]
        
        choice = st.sidebar.radio("Chức năng", menu)

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
            else:
                st.info("Chưa có dữ liệu.")

        elif choice == "📋 Danh sách":
            st.title("Danh mục tài sản")
            df_assets = pd.read_sql_query("SELECT * FROM assets", conn)
            st.dataframe(df_assets, use_container_width=True)

        elif choice == "🔧 Bảo trì & QR":
            df_assets = pd.read_sql_query("SELECT id, ten_tai_san FROM assets", conn)
            if not df_assets.empty:
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
                    # Thay URL bằng địa chỉ thực tế khi deploy
                    url = f"https://quan-ly-tai-san.streamlit.app/?id={sel_qr.split('-')[0]}"
                    st.image(generate_qr(url), caption=f"Mã QR của tài sản ID: {sel_qr.split('-')[0]}")
            else:
                st.warning("Chưa có tài sản nào.")

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
                    st.success("Đã thêm thành công!")
        
        conn.close()

    elif st.session_state["authentication_status"] is False:
        st.error('Sai tài khoản hoặc mật khẩu')
    elif st.session_state["authentication_status"] is None:
        st.warning('Vui lòng đăng nhập để sử dụng hệ thống.')

if __name__ == '__main__':
    main()
