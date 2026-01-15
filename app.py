import streamlit as st
import pandas as pd
import sqlite3
import os
import io
import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

# --- KONFIGURATION ---
GDRIVE_FOLDER_ID = "0B5UeXbdEo09pR1h2T0pJNmdLMUE" 
TEAM_PASSWORD = "2180"
DB_NAME = "fall_archiv_cloud.db"

# --- GOOGLE DRIVE VERBINDUNG (FEHLERTOLERANT) ---
@st.cache_resource
def get_gdrive_service():
    try:
        # Wir laden die Werte einzeln und bereinigen sie radikal
        def clean(key):
            return str(st.secrets[key]).strip().replace('"', '').replace("'", "")

        creds_info = {
            "type": clean("GCP_TYPE"),
            "project_id": clean("GCP_PROJECT_ID"),
            "private_key_id": clean("GCP_PRIVATE_KEY_ID"),
            "private_key": clean("GCP_PRIVATE_KEY").replace("\\n", "\n"),
            "client_email": clean("GCP_CLIENT_EMAIL"),
            "client_id": clean("GCP_CLIENT_ID"),
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_x509_cert_url": f"https://www.googleapis.com/robot/v1/metadata/x509/{clean('GCP_CLIENT_EMAIL').replace('@', '%40')}"
        }

        creds = service_account.Credentials.from_service_account_info(
            creds_info, 
            scopes=['https://www.googleapis.com/auth/drive']
        )
        
        creds._iat = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=30)
        return build('drive', 'v3', credentials=creds)
    except Exception as e:
        st.error(f"❌ Kritischer Verbindungsfehler: {e}")
        return None

# GLOBAL DEFINIEREN
drive_service = get_gdrive_service()

# --- DATENBANK SETUP ---
def get_db_connection():
    return sqlite3.connect(DB_NAME, check_same_thread=False)

conn = get_db_connection()
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS falle 
             (id INTEGER PRIMARY KEY AUTOINCREMENT, fall_nummer TEXT, datum DATE, 
              beschreibung TEXT, hauptbild_id TEXT, erledigt INTEGER DEFAULT 0)''')
c.execute('''CREATE TABLE IF NOT EXISTS media 
             (id INTEGER PRIMARY KEY AUTOINCREMENT, fall_id INTEGER, 
              file_id TEXT, file_type TEXT)''')
conn.commit()

# --- HELFERFUNKTION: UPLOAD ---
def upload_to_gdrive(file, filename):
    try:
        if drive_service is None:
            st.error("Keine Verbindung zu Google Drive.")
            return None
            
        file_metadata = {'name': filename, 'parents': [GDRIVE_FOLDER_ID]}
        file.seek(0)
        fh = io.BytesIO(file.read())
        media = MediaIoBaseUpload(fh, mimetype='application/octet-stream', resumable=True)
        
        gfile = drive_service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id'
        ).execute()
        
        f_id = gfile.get('id')
        drive_service.permissions().create(fileId=f_id, body={'type': 'anyone', 'role': 'reader'}).execute()
        return f_id
    except Exception as e:
        st.error(f"❗ Upload-Fehler ({filename}): {e}")
        return None

# --- AUTHENTIFIZIERUNG ---
if "auth" not in st.session_state:
    st.title("🔒 Team Login")
    pwd = st.text_input("Passwort eingeben", type="password")
    if st.button("Anmelden"):
        if pwd == TEAM_PASSWORD:
            st.session_state["auth"] = True
            st.rerun()
        else:
            st.error("Falsches Passwort")
    st.stop()

# --- UI NAVIGATION ---
st.set_page_config(page_title="Team Cloud Archiv", layout="wide")
st.sidebar.title("Menü")
mode = st.sidebar.radio("Navigation", ["Übersicht", "Neuanlage", "Verwalten"])

# --- NEUANLAGE ---
if mode == "Neuanlage":
    st.header("➕ Neuen Fall anlegen")
    with st.form("neu", clear_on_submit=True):
        fnr = st.text_input("Fall-Nummer")
        fdat = st.date_input("Datum", datetime.date.today())
        fbes = st.text_area("Beschreibung")
        u_imgs = st.file_uploader("Bilder", type=["jpg", "png", "jpeg"], accept_multiple_files=True)
        u_vids = st.file_uploader("Videos", type=["mp4", "mov"], accept_multiple_files=True)
        
        if st.form_submit_button("Speichern"):
            # HIER WAR DER FEHLER: drive_service muss existieren
            if fnr and u_imgs and drive_service:
                with st.spinner("Hochladen..."):
                    hid = upload_to_gdrive(u_imgs[0], f"{fnr}_MAIN.jpg")
                    if hid:
                        c.execute("INSERT INTO falle (fall_nummer, datum, beschreibung, hauptbild_id) VALUES (?,?,?,?)",
                                  (fnr, fdat, fbes, hid))
                        last_id = c.lastrowid
                        for img in u_imgs:
                            mid = upload_to_gdrive(img, f"{fnr}_IMG_{img.name}")
                            c.execute("INSERT INTO media (fall_id, file_id, file_type) VALUES (?,?,'image')", (last_id, mid))
                        if u_vids:
                            for vid in u_vids:
                                vid_id = upload_to_gdrive(vid, f"{fnr}_VID_{vid.name}")
                                c.execute("INSERT INTO media (fall_id, file_id, file_type) VALUES (?,?,'video')", (last_id, vid_id))
                        conn.commit()
                        st.success("✅ Fall erfolgreich gespeichert!")
            else:
                st.warning("Bitte Fall-Nummer und Bilder angeben (oder Drive-Verbindung prüfen).")

# --- ÜBERSICHT ---
elif mode == "Übersicht":
    st.header("📂 Archiv Übersicht")
    df = pd.read_sql_query("SELECT * FROM falle ORDER BY datum DESC", conn)
    for _, row in df.iterrows():
        with st.container(border=True):
            c1, c2 = st.columns([1, 4])
            c1.image(f"https://drive.google.com/uc?id={row['hauptbild_id']}")
            with c2:
                st.subheader(f"Fall {row['fall_nummer']}")
                st.write(row['beschreibung'])
                with st.expander("Medien anzeigen"):
                    m_df = pd.read_sql_query(f"SELECT * FROM media WHERE fall_id = {row['id']}", conn)
                    cols = st.columns(3)
                    for i, m_row in m_df.iterrows():
                        url = f"https://drive.google.com/uc?id={m_row['file_id']}"
                        with cols[i % 3]:
                            if m_row['file_type'] == "video": st.video(url)
                            else: st.image(url)

# --- VERWALTEN ---
elif mode == "Verwalten":
    st.header("⚙️ Verwalten")
    df = pd.read_sql_query("SELECT * FROM falle", conn)
    if not df.empty:
        target = st.selectbox("Fall wählen", df['fall_nummer'].tolist())
        if st.button("FALL LÖSCHEN", type="primary"):
            sel = df[df['fall_nummer'] == target].iloc[0]
            c.execute("DELETE FROM media WHERE fall_id=?", (sel['id'],))
            c.execute("DELETE FROM falle WHERE id=?", (sel['id'],))
            conn.commit()
            st.rerun()




