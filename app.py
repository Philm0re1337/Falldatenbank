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

# --- DEIN NEUER SCHLÜSSEL ---
NEW_KEY_DATA = {
  "type": "service_account",
  "project_id": "falldatenbank",
  "private_key_id": "bd26ff2b50cc2b3c7b5272de2895acd4db7e5ac9",
  "private_key": "-----BEGIN PRIVATE KEY-----\nMIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSjAgEAAoIBAQDDgrR+a2j9Z44N\nJ2zILf9oXq+nlBSWrbnhkC3TTDgcCdk9rpRiihvZGy1tyYIbQ6cOkbYGKT5x02Uo\nS6k3nURHo4LQziiVeCHgKBRHecYs1yuUyCE0OvWnCi7PtIJFXS4Rc4yZ8KLgZ45d\n+FvTU2kDqdqaD9AZ5wVQ0K5iwgiTW7RX0OY/lPEu2tu72pR1eMF8oOatr5lLuFPt\nB6YVxcnlktU8ANvTesvypcCxSTQDOXsBExgYZWDQ0N24hZrLnEOGfop0s9ffx8Tm\ne5z7mQo2ag81Dil36zUsGMHrV9aVe8yA+i0KmhsbXkESBW1h8Nm0k1c5aOFgWJYX\nigAfuVz9AgMBAAECggEAKHbY3IFmjWvtXpOWVCgRAIz4Vfqz+CukmSa6FU1lH4h6\nSeXkGDD1ao3RbTOTlgj+fmlx/vxyTCSwfxKJx1TpWNpirMy+YZEnkbk52UE+3vD5\nuCVjmefKB/R3k82MWMbcTghYRVQkocVNFe3dM3PD/FofQFuden7x/rPyI8Z89+Ja\nMED2+b8MXFvSt/riGvvg2fQD3x11/OK32lZDQtJhAsVU8H+hntRefK+1/DT21gca\nHBn/NDgH6cdRqtWGvwg1MahdKInZmXswtyRUsObvUO2p9aFaQcFJUEOV4DpG1Tql\nHgAOCv2N4E0ZcecboJBoFIHm+MBHywiRujBn4xt3EQKBgQDv11Cbm4TjcoikJSYr\nUHhUiw6CkJHwFyO9+OZbNdAQTeC5V+gL2h+epIuwdoRWuCl899uasK8nTj5K+27y\ntP31PvzfAJdCNQvfSLMrPK900QONISoXCtBuSSZJM5SfbfZOXB/FjMJWmHH+EtnR\nHac3G0CpnDIqIjZ30pHJ4zzCbwKBgQDQrst/gs6i2O4N2CC0hxs6oU4vgsf0WmO6\nK7qqgVXBphIkicueGgHrE7QYnGcLIxbvZ7uxYO6KZ8lka5H74EhQW6JOM5VCVY/X\nrnKJDNRKSD3DKrP8BXXDwxJdd9D5G5DFxooAnIBA90dGQwdrgPvwkSHX6oid0G8I\nP6UNx9xdUwKBgBOHHHEPAIrkUGvM+oacTq/TgqLu0nMR7z8QfPEAOKibLqjol2Qf\npmNsUlNT0wKcjAQ4yhCWQiyZGklQn3/zbJoDPuOJUMd7OjQ73xquHjsMqZVcFek6\nYC4alptvL7KraVqH9a5H/6q9Tsq5DjMQjwTVmzY0GYGEt5qZ8nTVo6TRAoGBALQM\nG8eINICMadfIAW/Aod2UDsEvNRW+ZwzZbdRugm7xufWMbgGars0D0v7o8n7JZ6Bm\n/6mq2CTSJxBdPzbx63JpnT+bgcwZxmFwQaG9T+xHKAKbdW6bx19/jvjVx5cmEWKS\nSb79SCrFLtmQO3alcrm8flasI/MFQsb7Io0hQx/BAoGANeswA6IW/b4TX/gTzJ0C\nnLroSVNX99ZfvG95ixPSq2lS35H5j8MBOyXB+ofSroBJCDd16M4rd9Uwnwcx/alJ\nXLNEoINskKm/2zN1FgsJhQeoONqOelxLPDPbn+tQu6NlY2w+4tsYD7s4RCXtQ+I3\n8ScNNZKYB0tVmjox6d5pII0=\n-----END PRIVATE KEY-----\n",
  "client_email": "falldatenbank@falldatenbank.iam.gserviceaccount.com",
  "client_id": "102942440306105394865",
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token",
  "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
  "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/falldatenbank%40falldatenbank.iam.gserviceaccount.com"
}

# --- GOOGLE DRIVE VERBINDUNG ---
@st.cache_resource
def get_gdrive_service():
    try:
        # Sicherstellen, dass \n als echte Zeilenumbrüche erkannt werden
        info = NEW_KEY_DATA.copy()
        info["private_key"] = info["private_key"].replace("\\n", "\n")
        
        creds = service_account.Credentials.from_service_account_info(
            info, 
            scopes=['https://www.googleapis.com/auth/drive']
        )
        
        # Zeit-Fix für Synchronität mit Google Servern
        creds._iat = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=30)
        
        return build('drive', 'v3', credentials=creds)
    except Exception as e:
        st.error(f"❌ Verbindungsfehler: {e}")
        return None

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
        # Berechtigung setzen für Anzeige in der App
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
                with st.spinner("Hochladen..."):
                    # 1. Hauptbild (Thumbnail)
                    hid = upload_to_gdrive(u_imgs[0], f"{fnr}_VORSCHAU.jpg")
                    c.execute("INSERT INTO falle (fall_nummer, datum, beschreibung, hauptbild_id) VALUES (?,?,?,?)",
                              (fnr, fdat, fbes, hid))
                    last_id = c.lastrowid
                    
                    # 2. Bilder hochladen
                    for img in u_imgs:
                        mid = upload_to_gdrive(img, f"{fnr}_BILD_{img.name}")
                        c.execute("INSERT INTO media (fall_id, file_id, file_type) VALUES (?,?,'image')", (last_id, mid))
                    
                    # 3. Videos hochladen
                    if u_vids:
                        for vid in u_vids:
                            vid_id = upload_to_gdrive(vid, f"{fnr}_VID_{vid.name}")
                            c.execute("INSERT INTO media (fall_id, file_id, file_type) VALUES (?,?,'video')", (last_id, vid_id))
                    
                    conn.commit()
                    st.success("✅ Fall erfolgreich in der Cloud gespeichert!")

# --- ÜBERSICHT ---
elif mode == "Übersicht":
    st.header("📂 Archiv Übersicht")
    df = pd.read_sql_query("SELECT * FROM falle ORDER BY datum DESC", conn)
    
    if df.empty:
        st.info("Noch keine Fälle vorhanden.")
    
    for _, row in df.iterrows():
        with st.container(border=True):
            col1, col2 = st.columns([1, 4])
            # Thumbnail Anzeige
            col1.image(f"https://drive.google.com/uc?id={row['hauptbild_id']}")
            with col2:
                st.subheader(f"Fall {row['fall_nummer']}")
                st.write(f"**Datum:** {row['datum']}")
                st.write(row['beschreibung'])
                with st.expander("Medien ansehen"):
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
    st.header("📝 Verwaltung")
    df = pd.read_sql_query("SELECT * FROM falle", conn)
    if not df.empty:
        target = st.selectbox("Fall auswählen zum Löschen", df['fall_nummer'].tolist())
        sel = df[df['fall_nummer'] == target].iloc[0]
        
        if st.button("Endgültig löschen", type="primary"):
            c.execute("DELETE FROM media WHERE fall_id=?", (sel['id'],))
            c.execute("DELETE FROM falle WHERE id=?", (sel['id'],))
            conn.commit()
            st.success("Gelöscht!")
            st.rerun()
