import streamlit as st
import qrcode
from PIL import Image
import io, os, uuid, sqlite3, tempfile, base64
from datetime import datetime, timedelta
import pandas as pd
import base64
from pathlib import Path

# ========================
# CONFIG
# ========================
DB_FILE = "database.db"
TEMP_DIR = tempfile.gettempdir()
BANNER_PATH = "assets/banner.png"

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
conn.commit()

# ========================
# CLEANUP EXPIRED FILES
# ========================
def cleanup_expired_files():
    now = datetime.now()
    c.execute("SELECT uuid, local_path, expires_at FROM files")
    rows = c.fetchall()

    for uuid_val, local_path, expires_at in rows:
        if expires_at:
            expires_at = datetime.fromisoformat(expires_at)
            if expires_at < now:
                if local_path and os.path.exists(local_path):
                    try:
                        os.remove(local_path)
                    except:
                        pass
                c.execute("DELETE FROM files WHERE uuid=?", (uuid_val,))
    conn.commit()

cleanup_expired_files()

# ========================
# BANNER RENDERER (SLIM)
# ========================
def render_banner(image_path, height_px=210):
    if not Path(image_path).exists():
        return

    with open(image_path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode()

    st.markdown("""
<style>
/* --- Premium SaaS Header --- */
.premium-shell {
    width: 100%;
    padding: 36px 42px;
    margin: 18px 0 34px 0;
    border-radius: 20px;
    background: linear-gradient(180deg, #0f172a, #020617);
    box-shadow:
        0 20px 40px rgba(0,0,0,0.35),
        inset 0 1px 0 rgba(255,255,255,0.04);
}

.premium-title {
    font-size: 44px;
    font-weight: 700;
    letter-spacing: 1.8px;
    text-transform: uppercase;
    color: #f8fafc;
    margin: 0;
}

.premium-divider {
    width: 530px;
    height: 3px;
    margin: 14px 0;
    background: linear-gradient(90deg, #6366f1, #8b5cf6);
    border-radius: 6px;
}

.premium-subtitle {
    font-size: 15px;
    color: #94a3b8;
    letter-spacing: 0.4px;
    max-width: 640px;
}
</style>

<div class="premium-shell">
    <div class="premium-title">Premium QR Generator</div>
    <div class="premium-divider"></div>
    <div class="premium-subtitle">
        Secure QR creation with expiring files, scan analytics,
        and embedded branding — built for modern professionals.
    </div>
</div>
""", unsafe_allow_html=True)

# ========================
# QR GENERATION
# ========================
def generate_qr(data, fill_color, back_color, box_size, border, logo_file=None):
    qr = qrcode.QRCode(
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
        wpercent = basewidth / float(logo.size[0])
        hsize = int(float(logo.size[1]) * wpercent)

        try:
            from PIL import ImageResampling
            resample = ImageResampling.LANCZOS
        except:
            resample = Image.LANCZOS

        logo = logo.resize((basewidth, hsize), resample)
        pos = ((img.size[0] - logo.size[0]) // 2,
               (img.size[1] - logo.size[1]) // 2)

        img.paste(logo, pos, mask=logo if logo.mode == "RGBA" else None)

    return img

# ========================
# PAGE CONFIG
# ========================
st.set_page_config(
    page_title="Premium QR Generator",
    page_icon="🔳",
    layout="wide"
)

# ========================
# GLOBAL CSS (MODERN)
# ========================
st.markdown("""
<style>
body {
    background: linear-gradient(135deg,#f0f4f8,#d9e2ec);
    font-family: 'Segoe UI', sans-serif;
}
.stButton>button {
    background-color: #4f46e5;
    color: white;
    border-radius: 8px;
    padding: 8px 16px;
}
.stDownloadButton>button {
    background-color: #10b981;
    color: white;
    border-radius: 8px;
    padding: 8px 16px;
}
.stFileUploader>div {
    border-radius: 8px;
    border: 2px dashed #4f46e5;
    padding: 15px;
}
</style>
""", unsafe_allow_html=True)

# ========================
# HEADER (LOGO BANNER ONLY)
# ========================
render_banner(BANNER_PATH, height_px=70)

# ========================
# SIDEBAR SETTINGS
# ========================
with st.sidebar:
    st.header("QR Settings")
    fill_color = st.color_picker("QR Color", "#000000")
    back_color = st.color_picker("Background Color", "#FFFFFF")
    box_size = st.slider("Box Size", 5, 20, 12)
    border = st.slider("Border", 2, 10, 4)
    expire_days = st.slider("Expire in Days", 1, 30, 7)

# ========================
# MAIN UI
# ========================
col1, col2 = st.columns([2, 1])

with col1:
    qr_mode = st.radio("QR Type", ["URL / Text", "Upload File"])
    user_logo = st.file_uploader(
        "Upload your logo (optional)",
        type=["png", "jpg", "jpeg"]
    )

    qr_data = None

    if qr_mode == "URL / Text":
        qr_data = st.text_input("Enter URL or text")

        if qr_data:
            uid = str(uuid.uuid4())
            expires_at = datetime.now() + timedelta(days=expire_days)
            c.execute(
                "INSERT INTO files VALUES(?,?,?,?,?,?,0)",
                (uid, qr_data, None,
                 datetime.now().isoformat(),
                 expires_at.isoformat(),
                 qr_data)
            )
            conn.commit()

    else:
        uploaded_file = st.file_uploader("Upload any file")

        if uploaded_file:
            uid = str(uuid.uuid4())
            path = os.path.join(TEMP_DIR, f"{uid}_{uploaded_file.name}")

            with open(path, "wb") as f:
                f.write(uploaded_file.getbuffer())

            qr_data = f"file://{path}"
            expires_at = datetime.now() + timedelta(days=expire_days)

            c.execute(
                "INSERT INTO files VALUES(?,?,?,?,?,?,0)",
                (uid, uploaded_file.name, path,
                 datetime.now().isoformat(),
                 expires_at.isoformat(),
                 qr_data)
            )
            conn.commit()

            st.success("File stored in temporary demo storage")

with col2:
    st.subheader("Generated QR")

    if qr_data:
        qr_img = generate_qr(
            qr_data,
            fill_color,
            back_color,
            box_size,
            border,
            user_logo
        )

        st.image(qr_img, width=300)

        buf = io.BytesIO()
        qr_img.save(buf, format="PNG")

        st.download_button(
            "⬇ Download QR",
            data=buf.getvalue(),
            file_name="qr_code.png",
            mime="image/png"
        )

# ========================
# ANALYTICS
# ========================
st.divider()
st.header("Scan Analytics")

df = pd.read_sql_query("SELECT * FROM files", conn)

if df.empty:
    st.info("No QR codes generated yet.")
else:
    for _, row in df.iterrows():
        st.markdown(f"**{row['file_name']}**")
        st.markdown(f"- Expires: `{row['expires_at']}`")
        st.markdown(f"- QR Data: `{row['qr_url']}`")
        st.markdown("---")

st.caption(
    "Premium QR Generator • Demo Edition • No Paid Services • Streamlit Cloud Ready"
)
