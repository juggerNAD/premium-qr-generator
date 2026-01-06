import streamlit as st
import qrcode
from PIL import Image
import io, os, uuid, sqlite3, time
from datetime import datetime, timedelta
import pandas as pd
import tempfile

# ========================
# CONFIG
# ========================
DB_FILE = "database.db"
TEMP_DIR = tempfile.gettempdir()  # temporary folder for demo purposes

# ========================
# DATABASE SETUP
# ========================
conn = sqlite3.connect(DB_FILE, check_same_thread=False)
c = conn.cursor()

c.execute("""
CREATE TABLE IF NOT EXISTS files(
    uuid TEXT PRIMARY KEY,
    file_name TEXT,
    local_path TEXT,
    uploaded_at TEXT,
    expires_at TEXT,
    qr_url TEXT,
    scans INTEGER DEFAULT 0
)
""")
c.execute("""
CREATE TABLE IF NOT EXISTS scans(
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    file_uuid TEXT,
    scan_time TEXT,
    user_agent TEXT,
    ip TEXT
)
""")
conn.commit()

# ========================
# CLEANUP EXPIRED FILES
# ========================
def cleanup_expired_files():
    now = datetime.now()
    c.execute("SELECT uuid, local_path FROM files")
    rows = c.fetchall()
    for uuid_val, local_path in rows:
        if local_path and os.path.exists(local_path):
            # Check expiration
            c.execute("SELECT expires_at FROM files WHERE uuid=?", (uuid_val,))
            expires_at_str = c.fetchone()[0]
            expires_at = datetime.fromisoformat(expires_at_str)
            if expires_at < now:
                os.remove(local_path)
                c.execute("DELETE FROM files WHERE uuid=?", (uuid_val,))
    conn.commit()

cleanup_expired_files()

# ========================
# QR GENERATION
# ========================
def generate_qr(data, fill_color="#000000", back_color="#FFFFFF", box_size=12, border=4, logo_file=None):
    qr = qrcode.QRCode(
        version=None,
        error_correction=qrcode.constants.ERROR_CORRECT_Q,
        box_size=box_size,
        border=border
    )
    qr.add_data(data)
    qr.make(fit=True)
    img = qr.make_image(fill_color=fill_color, back_color=back_color).convert("RGB")
    
    if logo_file:
        logo = Image.open(logo_file)
        basewidth = img.size[0] // 4
        wpercent = (basewidth / float(logo.size[0]))
        hsize = int((float(logo.size[1]) * float(wpercent)))
        try:
            from PIL import ImageResampling
            resample_method = ImageResampling.LANCZOS
        except ImportError:
            resample_method = Image.LANCZOS  # fallback

        logo = logo.resize((basewidth, hsize), resample=resample_method)
        pos = ((img.size[0]-logo.size[0])//2, (img.size[1]-logo.size[1])//2)
        img.paste(logo, pos, mask=logo if logo.mode=="RGBA" else None)
    
    return img

# ========================
# APP LAYOUT
# ========================
st.set_page_config(page_title="Premium QR Generator", page_icon="🔳", layout="wide")

# CSS for modern premium look
st.markdown("""
<style>
body { background: linear-gradient(135deg,#f0f4f8,#d9e2ec); font-family: 'Segoe UI', sans-serif;}
h1,h2,h3 { color: #111; }
.stButton>button { background-color: #4f46e5; color:white; border-radius:8px; padding:8px 15px;}
.stDownloadButton>button { background-color:#10b981; color:white; border-radius:8px; padding:8px 15px;}
.stFileUploader>div { border-radius:8px; border:2px dashed #4f46e5; padding:15px;}
</style>
""", unsafe_allow_html=True)

col_logo, col_title = st.columns([1,5])
with col_logo:
    st.image("assets/logo.png", width=80) if os.path.exists("assets/logo.png") else None
with col_title:
    st.markdown("<h1>Premium QR Generator</h1>", unsafe_allow_html=True)
st.markdown("Upload files or URLs/text and generate QR codes with analytics, expiring links, and embedded branding.")
st.divider()

# -------------------------
# Sidebar for QR Settings
# -------------------------
with st.sidebar:
    st.header("QR Settings")
    fill_color = st.color_picker("QR Color", "#000000")
    back_color = st.color_picker("Background Color", "#FFFFFF")
    box_size = st.slider("Box Size", 5, 20, 12)
    border = st.slider("Border Size", 2, 10, 4)
    expire_days = st.slider("Expire in Days", 1, 30, 7)
    st.markdown("---")
    st.markdown("### Analytics")
    if st.button("Refresh Analytics"):
        st.rerun()

# -------------------------
# Main UI
# -------------------------
col1, col2 = st.columns([2,1])
with col1:
    qr_mode = st.radio("QR Type", ["URL / Text", "Upload Document"])
    qr_data = None
    qr_uuid = None
    user_logo = st.file_uploader("Upload your logo for QR (optional)", type=["png","jpg","jpeg"])

    if qr_mode=="URL / Text":
        qr_data = st.text_input("Enter URL or Text", placeholder="https://example.com or any text")
        if qr_data:
            qr_uuid = str(uuid.uuid4())
            uploaded_at = datetime.now()
            expires_at = uploaded_at + timedelta(days=expire_days)
            c.execute("INSERT INTO files(uuid,file_name,local_path,uploaded_at,expires_at,qr_url) VALUES(?,?,?,?,?,?)",
                      (qr_uuid, qr_data, None, uploaded_at.isoformat(), expires_at.isoformat(), qr_data))
            conn.commit()

    if qr_mode=="Upload Document":
        uploaded_file = st.file_uploader("Upload any file (PDF, DOCX, XLSX, images, ZIP, etc.)", type=None)
        if uploaded_file:
            qr_uuid = str(uuid.uuid4())
            file_ext = os.path.splitext(uploaded_file.name)[1]
            temp_path = os.path.join(TEMP_DIR, f"{qr_uuid}_{uploaded_file.name}")
            with open(temp_path, "wb") as f:
                f.write(uploaded_file.getbuffer())
            uploaded_at = datetime.now()
            expires_at = uploaded_at + timedelta(days=expire_days)
            qr_data = f"file://{temp_path}"  # local file link for demo
            c.execute("INSERT INTO files(uuid,file_name,local_path,uploaded_at,expires_at,qr_url) VALUES(?,?,?,?,?,?)",
                      (qr_uuid, uploaded_file.name, temp_path, uploaded_at.isoformat(), expires_at.isoformat(), qr_data))
            conn.commit()
            st.success("File saved to temporary demo storage!")
            st.code(qr_data)

with col2:
    st.subheader("Generated QR")
    if qr_data:
        qr_img = generate_qr(qr_data, fill_color, back_color, box_size, border, logo_file=user_logo)
        st.image(qr_img, width=300)
        buffer = io.BytesIO()
        qr_img.save(buffer, format="PNG")
        st.download_button("⬇ Download QR Code", data=buffer.getvalue(), file_name="qr_code.png", mime="image/png")

# -------------------------
# Analytics Dashboard
# -------------------------
st.divider()
st.header("Scan Analytics Dashboard")
files_df = pd.read_sql_query("SELECT * FROM files", conn)
if not files_df.empty:
    for idx, row in files_df.iterrows():
        st.markdown(f"**File:** {row['file_name']}")
        st.markdown(f"- UUID: {row['uuid']}")
        st.markdown(f"- Scans: {row['scans']}")
        st.markdown(f"- Expires At: {row['expires_at']}")
        st.markdown(f"- QR URL: {row['qr_url']}")
        st.markdown("---")
else:
    st.info("No files uploaded yet.")

st.caption("Premium SaaS-style QR Generator • Expiring Files • Analytics • Branding • Modern UX")
