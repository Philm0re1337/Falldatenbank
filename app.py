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

# --- GOOGLE DRIVE VERBINDUNG (SICHER ÜBER SECRETS) ---
@st.cache_resource
def get_gdrive_service():
    try:
        # 1. Daten aus Secrets laden
        creds_info = dict(st.secrets["gcp_service_account"])
        
        # 2. Fehlerkorrektur: Alle IDs von versteckten Leerzeichen befreien
        # Das löst den "number of data characters cannot be 1 more than a multiple of 4" Fehler
        for key in ["project_id", "private_key_id", "client_id", "client_email"]:
            if key in creds_info:
                creds_info[key] = str(creds_info[key]).strip()

        # 3. Private Key säubern (entfernt versehentliche Leerzeichen am Anfang/Ende)
        if "private_key" in creds_info:
            creds_info["private_key"] = creds_info["private_key"].strip()

        # 4. Credentials erstellen
        creds = service_account.Credentials.from_service_account_info(
            creds_info, 
            scopes=['https://www.googleapis.com/auth/drive']
        )
        
        # Zeit-Fix für Google Server
        creds._iat = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=30)
        
        return build('drive', 'v3', credentials=creds)
    except Exception as e:
        st.error(f"❌ Verbindungsfehler: {e}")
        return None


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
        if not drive_service:
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
        # Berechtigung auf 'jeder mit dem Link' setzen für die Anzeige in der App
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
            if fnr and u_imgs and drive_service:
                with st.spinner("Hochladen in die Cloud..."):
                    # 1. Hauptbild (Thumbnail) hochladen
                    hid = upload_to_gdrive(u_imgs[0], f"{fnr}_VORSCHAU.jpg")
                    c.execute("INSERT INTO falle (fall_nummer, datum, beschreibung, hauptbild_id) VALUES (?,?,?,?)",
                              (fnr, fdat, fbes, hid))
                    last_id = c.lastrowid
                    
                    # 2. Alle Bilder hochladen
                    for img in u_imgs:
                        mid = upload_to_gdrive(img, f"{fnr}_BILD_{img.name}")
                        c.execute("INSERT INTO media (fall_id, file_id, file_type) VALUES (?,?,'image')", (last_id, mid))
                    
                    # 3. Videos hochladen
                    if u_vids:
                        for vid in u_vids:
                            vid_id = upload_to_gdrive(vid, f"{fnr}_VID_{vid.name}")
                            c.execute("INSERT INTO media (fall_id, file_id, file_type) VALUES (?,?,'video')", (last_id, vid_id))
                    
                    conn.commit()
                    st.success(f"✅ Fall {fnr} wurde erfolgreich gespeichert!")

# --- ÜBERSICHT ---
elif mode == "Übersicht":
    st.header("📂 Archiv Übersicht")
    df = pd.read_sql_query("SELECT * FROM falle ORDER BY datum DESC", conn)
    
    if df.empty:
        st.info("Das Archiv ist noch leer.")
    
    for _, row in df.iterrows():
        with st.container(border=True):
            col1, col2 = st.columns([1, 4])
            # Thumbnail Anzeige direkt aus G-Drive
            col1.image(f"https://drive.google.com/uc?id={row['hauptbild_id']}")
            with col2:
                st.subheader(f"Fall {row['fall_nummer']}")
                st.write(f"📅 **Datum:** {row['datum']}")
                st.write(row['beschreibung'])
                with st.expander("📸 Medien anzeigen"):
                    m_df = pd.read_sql_query(f"SELECT * FROM media WHERE fall_id = {row['id']}", conn)
                    m_cols = st.columns(3)
                    for i, m_row in m_df.iterrows():
                        url = f"https://drive.google.com/uc?id={m_row['file_id']}"
                        with m_cols[i % 3]:
                            if m_row['file_type'] == "video":
                                st.video(url)
                            else:
                                st.image(url)

# --- VERWALTEN ---
elif mode == "Verwalten":
    st.header("⚙️ Verwaltung")
    df = pd.read_sql_query("SELECT * FROM falle", conn)
    if not df.empty:
        target = st.selectbox("Fall auswählen", df['fall_nummer'].tolist())
        sel = df[df['fall_nummer'] == target].iloc[0]
        
        st.warning(f"Soll der Fall {target} wirklich gelöscht werden?")
        if st.button("Endgültig löschen", type="primary"):
            c.execute("DELETE FROM media WHERE fall_id=?", (sel['id'],))
            c.execute("DELETE FROM falle WHERE id=?", (sel['id'],))
            conn.commit()
            st.success("Daten wurden gelöscht.")
            st.rerun()



