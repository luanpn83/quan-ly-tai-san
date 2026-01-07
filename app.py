import streamlit as st
import sqlite3
import pandas as pd
import qrcode
import plotly.express as px
import streamlit_authenticator as stauth
from io import BytesIO
from datetime import datetime

# --- 1. CÁC HÀM TIỆN ÍCH & DATABASE ---

def init_db():
    """Khởi tạo cơ sở dữ liệu và bảng"""
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
        # Sử dụng phương thức hash mới nhất của bản 0.3.x
        hashed_pw = stauth.Hasher.hash('admin123')
        c.execute("INSERT INTO users VALUES ('admin', 'Quản trị viên', ?, 'admin')", (hashed_pw,))
    conn.commit()
    conn.close()

def fetch_users_config():
    """Lấy cấu hình người dùng từ DB"""
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
    """Tạo ảnh QR Code"""
    qr = qrcode.make(url)
    buf = BytesIO()
    qr.save(buf, format="PNG")
    return buf.getvalue()

def show_public_details(asset_id):
    """Hiển thị chi tiết tài sản cho khách quét QR"""
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
    
    # Kiểm tra truy cập qua QR (Xử lý ưu tiên trước khi đăng nhập)
    if "id" in st.query_params:
        show_public_details(st.query_params["id"])
        if st.button("Quay lại trang chủ"):
            st.query_params.clear()
            st.rerun()
        return

    # Khởi tạo DB và lấy cấu hình
    init_db()
    config = fetch_users_config()
    
    # KHỞI TẠO AUTHENTICATOR QUA SESSION STATE (Để tránh lỗi Duplicate Key và Cache Warning)
    if 'authenticator' not in st.session_state:
        st.session_state['authenticator'] = stauth.Authenticate(
            config,
            'asset_cookie',
            'auth_key',
            cookie_expiry_days=1
        )
    
    authenticator = st.session_state['authenticator']

    # Thực hiện login
    authenticator.login(location='main')

    # Kiểm tra trạng thái đăng nhập
    if st.session_state["authentication_status"]:
        name = st.session_state["name"]
        username = st.session_state["username"]
        role = config['usernames'][username]['role']
        
        st.sidebar.title(f"Chào {name}")
        st.sidebar.write(f"Quyền hạn: **{role.upper()}**")
        authenticator.logout('Đăng xuất', 'sidebar')
        
        # Menu phân quyền
        if role == 'admin':
            menu = ["📊 Dashboard", "📋 Danh sách", "🔧 Bảo trì & QR", "⚙️ Hệ thống"]
        else:
            menu = ["📊 Dashboard", "📋 Danh sách"]
        choice = st.sidebar.radio("Chức năng", menu)

        # Kết nối DB cho các chức năng
        conn = sqlite3.connect('he_thong_quan_ly.db')
        
        if choice == "📊 Dashboard":
            st.title("📈 Dashboard Báo Cáo")
            df_assets = pd.read_sql_query("SELECT * FROM assets", conn)
            if not df_assets.empty:
                c1, c2, c3 = st.columns(3)
                c1.metric("Tổng tài sản", len(df_assets))
                c2.metric("Tổng giá trị", f"{df_assets['gia_tri'].sum():,.0f} đ")
                c3.metric("Cần bảo trì", len(df_assets[df_assets['tinh_trang']=="Cần bảo trì"]))
                
                fig = px.pie(df_assets, names='tinh_trang', title="Phân bổ tình trạng tài sản", hole=0.3)
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.info("Chưa có dữ liệu để thống kê.")

        elif choice == "📋 Danh sách":
            st.title("📋 Danh mục tài sản")
            df_assets = pd.read_sql_query("SELECT * FROM assets", conn)
            st.dataframe(df_assets, use_container_width=True)

        elif choice == "🔧 Bảo trì & QR":
            st.title("🔧 Quản lý Bảo trì & QR Code")
            df_assets = pd.read_sql_query("SELECT id, ten_tai_san FROM assets", conn)
            if not df_assets.empty:
                t1, t2 = st.tabs(["Ghi chú bảo trì", "Tạo mã QR"])
                with t1:
                    sel = st.selectbox("Chọn tài sản", [f"{r['id']}-{r['ten_tai_san']}" for _,r in df_assets.iterrows()])
                    with st.form("maint_form"):
                        nd = st.text_area("Nội dung sửa chữa/bảo trì")
                        cp = st.number_input("Chi phí (VNĐ)", min_value=0.0)
                        if st.form_submit_button("Lưu lịch sử"):
                            conn.cursor().execute("INSERT INTO maintenance (asset_id, ngay_thuc_hien, noi_dung, chi_phi) VALUES (?,?,?,?)",
                                                  (sel.split('-')[0], datetime.now().date(), nd, cp))
                            conn.commit()
                            st.success("Đã ghi nhận lịch sử bảo trì!")
                with t2:
                    sel_qr = st.selectbox("Chọn tài sản cần in mã", [f"{r['id']}-{r['ten_tai_san']}" for _,r in df_assets.iterrows()])
                    # URL này sẽ tự động nhận diện khi deploy lên Streamlit Cloud
                    url = f"https://quan-ly-tai-san.streamlit.app/?id={sel_qr.split('-')[0]}"
                    st.image(generate_qr(url), caption=f"QR Code ID: {sel_qr.split('-')[0]}")
                    st.info("Mẹo: Bạn có thể chuột phải vào ảnh QR để lưu về máy và in dán lên tài sản.")
            else:
                st.warning("Vui lòng thêm tài sản trước.")

        elif choice == "⚙️ Hệ thống":
            st.title("⚙️ Quản lý hệ thống")
            st.subheader("Thêm tài sản mới")
            with st.form("add_asset"):
                col1, col2 = st.columns(2)
                with col1:
                    ten = st.text_input("Tên tài sản")
                    loai = st.selectbox("Loại tài sản", ["Điện tử", "Nội thất", "Văn phòng phẩm", "Khác"])
                    gia = st.number_input("Giá trị (VNĐ)", min_value=0.0)
                with col2:
                    tt = st.selectbox("Tình trạng", ["Mới", "Tốt", "Cần bảo trì", "Hỏng"])
                    vt = st.text_input("Vị trí/Phòng ban")
                if st.form_submit_button("Thêm tài sản"):
                    conn.cursor().execute("INSERT INTO assets (ten_tai_san, loai_tai_san, gia_tri, tinh_trang, vi_tri) VALUES (?,?,?,?,?)",
                                          (ten, loai, gia, tt, vt))
                    conn.commit()
                    st.success("Đã thêm tài sản mới vào hệ thống!")
        
        conn.close()

    elif st.session_state["authentication_status"] is False:
        st.error('Tên đăng nhập hoặc mật khẩu không chính xác.')
    elif st.session_state["authentication_status"] is None:
        st.info('Vui lòng nhập thông tin đăng nhập để tiếp tục.')

if __name__ == '__main__':
    main()
