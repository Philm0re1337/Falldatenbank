import streamlit as st
import pandas as pd
import sqlite3
import os
from datetime import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseUpload

# --- KONFIGURATION ---
GDRIVE_FOLDER_ID = "0B5UeXbdEo09pR1h2T0pJNmdLMUE" 
TEAM_PASSWORD = "2180"
DB_NAME = "fall_archiv_gdrive.db"

# --- GOOGLE DRIVE VERBINDUNG (Offizieller Google Client) ---
@st.cache_resource
def get_gdrive_service():
    try:
        key_file = 'credentials.json'
        if not os.path.exists(key_file):
            st.error(f"⚠️ Datei '{key_file}' nicht gefunden!")
            return None
            
        creds = service_account.Credentials.from_service_account_file(
            key_file, scopes=['https://www.googleapis.com/auth/drive']
        )
        service = build('drive', 'v3', credentials=creds)
        return service
    except Exception as e:
        st.error(f"❌ Fehler bei der Google Verbindung: {e}")
        return None

drive_service = get_gdrive_service()

# --- DATENBANK SETUP ---
conn = sqlite3.connect(DB_NAME, check_same_thread=False)
c = conn.cursor()
c.execute('''CREATE TABLE IF NOT EXISTS falle 
             (id INTEGER PRIMARY KEY AUTOINCREMENT, fall_nummer TEXT, datum DATE, 
              beschreibung TEXT, hauptbild_id TEXT, erledigt INTEGER DEFAULT 0)''')
c.execute('''CREATE TABLE IF NOT EXISTS media 
             (id INTEGER PRIMARY KEY AUTOINCREMENT, fall_id INTEGER, 
              file_id TEXT, file_type TEXT)''')
conn.commit()

# --- HELFERFUNKTION: UPLOAD ---
import io

def upload_to_gdrive(file, filename):
    try:
        file_metadata = {
            'name': filename,
            'parents': [GDRIVE_FOLDER_ID]
        }
        
        # Sicherstellen, dass wir am Anfang der Datei lesen
        file.seek(0)
        
        # Wir nutzen BytesIO, um den Stream für Google vorzubereiten
        fh = io.BytesIO(file.read())
        media = MediaIoBaseUpload(fh, mimetype='application/octet-stream', resumable=True)
        
        gfile = drive_service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id'
        ).execute()
        
        file_id = gfile.get('id')
        
        # Berechtigung setzen
        drive_service.permissions().create(
            fileId=file_id,
            body={'type': 'anyone', 'role': 'reader'}
        ).execute()
        
        return file_id
    except Exception as e:
        st.error(f"❗ Upload-Fehler für {filename}: {e}")
        return None

# --- LOGIN ---
if "password_correct" not in st.session_state:
    st.title("🔒 Team-Login")
    pw = st.text_input("Bitte gib das Passwort ein", type="password")
    if st.button("Anmelden"):
        if pw == TEAM_PASSWORD:
            st.session_state["password_correct"] = True
            st.rerun()
        else: st.error("Falsches Passwort.")
    st.stop()

# --- UI & NAVIGATION ---
st.set_page_config(page_title="Team Cloud-Archiv", layout="wide")
st.sidebar.title("📁 Navigation")
choice = st.sidebar.radio("Menü", ["Übersicht & Suche", "Neuanlage", "Bearbeiten & Löschen"])

# --- NEUANLAGE ---
if choice == "Neuanlage":
    st.header("➕ Neuen Fall erfassen")
    with st.form("neu_form", clear_on_submit=True):
        f_nr = st.text_input("Fall-Nummer")
        f_date = st.date_input("Datum", datetime.now())
        f_desc = st.text_area("Beschreibung")
        u_bilder = st.file_uploader("Bilder", type=["jpg", "jpeg", "png"], accept_multiple_files=True)
        u_vids = st.file_uploader("Videos", type=["mp4", "mov"], accept_multiple_files=True)
        
        if st.form_submit_button("In Cloud speichern"):
            if f_nr and u_bilder and drive_service:
                with st.spinner('Lade zu Google Drive hoch...'):
                    # Hauptbild
                    h_id = upload_to_gdrive(u_bilder[0], f"{f_nr}_VORSCHAU.jpg")
                    
                    c.execute("INSERT INTO falle (fall_nummer, datum, beschreibung, hauptbild_id, erledigt) VALUES (?,?,?,?,0)",
                              (f_nr, f_date, f_desc, h_id))
                    f_id = c.lastrowid
                    
                    for img in u_bilder:
                        img_id = upload_to_gdrive(img, f"{f_nr}_BILD_{img.name}")
                        c.execute("INSERT INTO media (fall_id, file_id, file_type) VALUES (?,?,'image')", (f_id, img_id))
                    
                    if u_vids:
                        for vid in u_vids:
                            vid_id = upload_to_gdrive(vid, f"{f_nr}_VIDEO_{vid.name}")
                            c.execute("INSERT INTO media (fall_id, file_id, file_type) VALUES (?,?,'video')", (f_id, vid_id))
                    
                    conn.commit()
                    st.success(f"Fall {f_nr} erfolgreich gespeichert!")

# --- ÜBERSICHT ---
elif choice == "Übersicht & Suche":
    st.header("📂 Fall-Archiv")
    # (Suche und Anzeige wie vorher, nutzt die file_id URLs)
    df = pd.read_sql_query("SELECT * FROM falle ORDER BY datum DESC", conn)
    for _, row in df.iterrows():
        with st.container(border=True):
            col_a, col_b = st.columns([1, 4])
            col_a.image(f"https://drive.google.com/uc?id={row['hauptbild_id']}")
            with col_b:
                st.subheader(f"Fall {row['fall_nummer']}")
                with st.expander("Medien"):
                    m_df = pd.read_sql_query(f"SELECT * FROM media WHERE fall_id = {row['id']}", conn)
                    for _, m_row in m_df.iterrows():
                        url = f"https://drive.google.com/uc?id={m_row['file_id']}"
                        if m_row['file_type'] == "video": st.video(url)
                        else: st.image(url)

# --- BEARBEITEN & LÖSCHEN ---
elif choice == "Bearbeiten & Löschen":
    # (Löschfunktion wie vorher...)
    st.write("Bearbeiten-Modus aktiv.")

