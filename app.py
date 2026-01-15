import streamlit as st
import pandas as pd
import sqlite3
import os
import io
from datetime import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

# --- KONFIGURATION ---
GDRIVE_FOLDER_ID = "0B5UeXbdEo09pR1h2T0pJNmdLMUE" 
TEAM_PASSWORD = "2180"
DB_NAME = "fall_archiv_gdrive.db"

# --- GOOGLE DRIVE VERBINDUNG ÜBER SECRETS ---
@st.cache_resource
@st.cache_resource
def get_gdrive_service():
    try:
        # Wir laden die Secrets in ein Dictionary
        creds_dict = {
            "type": st.secrets["gcp_service_account"]["type"],
            "project_id": st.secrets["gcp_service_account"]["project_id"],
            "private_key_id": st.secrets["gcp_service_account"]["private_key_id"],
            # Hier ist die wichtige Reparatur:
            "private_key": st.secrets["gcp_service_account"]["private_key"].replace("\\n", "\n"),
            "client_email": st.secrets["gcp_service_account"]["client_email"],
            "client_id": st.secrets["gcp_service_account"]["client_id"],
            "auth_uri": st.secrets["gcp_service_account"]["auth_uri"],
            "token_uri": st.secrets["gcp_service_account"]["token_uri"],
            "auth_provider_x509_cert_url": st.secrets["gcp_service_account"]["auth_provider_x509_cert_url"],
            "client_x509_cert_url": st.secrets["gcp_service_account"]["client_x509_cert_url"],
        }
        
        creds = service_account.Credentials.from_service_account_info(
            creds_dict, 
            scopes=['https://www.googleapis.com/auth/drive']
        )
        service = build('drive', 'v3', credentials=creds)
        return service
    except Exception as e:
        st.error(f"❌ Fehler bei der Google Verbindung: {e}")
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
        file_metadata = {'name': filename, 'parents': [GDRIVE_FOLDER_ID]}
        
        # Sicherstellen, dass der Stream am Anfang steht
        file.seek(0)
        fh = io.BytesIO(file.read())
        media = MediaIoBaseUpload(fh, mimetype='application/octet-stream', resumable=True)
        
        # Erstellen der Datei in Google Drive
        gfile = drive_service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id'
        ).execute()
        
        file_id = gfile.get('id')
        
        # Berechtigung: Jeder mit Link kann lesen (für die Anzeige in der App)
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
        else:
            st.error("Falsches Passwort.")
    st.stop()

# --- UI & NAVIGATION ---
st.set_page_config(page_title="Cloud Fall-Archiv", layout="wide")
st.sidebar.title("📁 Navigation")
choice = st.sidebar.radio("Menü", ["Übersicht & Suche", "Neuanlage", "Bearbeiten & Löschen"])

# --- NEUANLAGE ---
if choice == "Neuanlage":
    st.header("➕ Neuen Fall erfassen")
    with st.form("neu_form", clear_on_submit=True):
        f_nr = st.text_input("Fall-Nummer")
        f_date = st.date_input("Datum", datetime.now())
        f_desc = st.text_area("Beschreibung")
        u_bilder = st.file_uploader("Bilder (Erstes = Vorschau)", type=["jpg", "jpeg", "png"], accept_multiple_files=True)
        u_vids = st.file_uploader("Videos", type=["mp4", "mov"], accept_multiple_files=True)
        
        if st.form_submit_button("In Google Drive speichern"):
            if f_nr and u_bilder and drive_service:
                with st.spinner('Upload läuft...'):
                    # 1. Hauptbild hochladen
                    h_id = upload_to_gdrive(u_bilder[0], f"{f_nr}_VORSCHAU.jpg")
                    
                    c.execute("INSERT INTO falle (fall_nummer, datum, beschreibung, hauptbild_id, erledigt) VALUES (?,?,?,?,0)",
                              (f_nr, f_date, f_desc, h_id))
                    f_id = c.lastrowid
                    
                    # 2. Alle Bilder hochladen
                    for img in u_bilder:
                        img_id = upload_to_gdrive(img, f"{f_nr}_BILD_{img.name}")
                        c.execute("INSERT INTO media (fall_id, file_id, file_type) VALUES (?,?,'image')", (f_id, img_id))
                    
                    # 3. Videos hochladen
                    if u_vids:
                        for vid in u_vids:
                            vid_id = upload_to_gdrive(vid, f"{f_nr}_VIDEO_{vid.name}")
                            c.execute("INSERT INTO media (fall_id, file_id, file_type) VALUES (?,?,'video')", (f_id, vid_id))
                    
                    conn.commit()
                    st.success(f"Fall {f_nr} wurde erfolgreich gespeichert!")

# --- ÜBERSICHT & SUCHE ---
elif choice == "Übersicht & Suche":
    st.header("📂 Archiv")
    s1, s2, s3 = st.columns([2,1,1])
    search_nr = s1.text_input("Suche Nummer")
    search_date = s2.date_input("Datum filtern", value=None)
    status_f = s3.selectbox("Status", ["Alle", "Offen", "Erledigt"])

    query = "SELECT * FROM falle WHERE 1=1"
    params = []
    if search_nr:
        query += " AND fall_nummer LIKE ?"; params.append(f"%{search_nr}%")
    if search_date:
        query += " AND datum = ?"; params.append(search_date)
    if status_f == "Offen": query += " AND erledigt = 0"
    elif status_f == "Erledigt": query += " AND erledigt = 1"

    df = pd.read_sql_query(query + " ORDER BY datum DESC", conn, params=params)

    for _, row in df.iterrows():
        badge = "✅" if row['erledigt'] == 1 else "⏳"
        with st.container(border=True):
            col_img, col_txt = st.columns([1, 4])
            col_img.image(f"https://drive.google.com/uc?id={row['hauptbild_id']}")
            with col_txt:
                st.subheader(f"{badge} Fall {row['fall_nummer']}")
                st.caption(f"Datum: {row['datum']}")
                with st.expander("Ansehen"):
                    st.write(row['beschreibung'])
                    m_df = pd.read_sql_query(f"SELECT * FROM media WHERE fall_id = {row['id']}", conn)
                    m_cols = st.columns(3)
                    for i, m_row in m_df.iterrows():
                        url = f"https://drive.google.com/uc?id={m_row['file_id']}"
                        with m_cols[i % 3]:
                            if m_row['file_type'] == "video": st.video(url)
                            else: st.image(url)

# --- BEARBEITEN & LÖSCHEN ---
elif choice == "Bearbeiten & Löschen":
    st.header("📝 Verwalten")
    df = pd.read_sql_query("SELECT * FROM falle", conn)
    if not df.empty:
        auswahl = st.selectbox("Fall wählen", df['fall_nummer'].tolist())
        f_data = df[df['fall_nummer'] == auswahl].iloc[0]
        f_id = int(f_data['id'])
        
        with st.form("edit"):
            u_nr = st.text_input("Nummer", value=f_data['fall_nummer'])
            u_date = st.date_input("Datum", value=datetime.strptime(str(f_data['datum']), '%Y-%m-%d'))
            u_desc = st.text_area("Beschreibung", value=f_data['beschreibung'])
            u_done = st.checkbox("Erledigt", value=bool(f_data['erledigt']))
            if st.form_submit_button("Speichern"):
                c.execute("UPDATE falle SET fall_nummer=?, datum=?, beschreibung=?, erledigt=? WHERE id=?", 
                          (u_nr, u_date, u_desc, 1 if u_done else 0, f_id))
                conn.commit()
                st.success("Aktualisiert!")
                st.rerun()

        with st.expander("🗑️ Fall löschen"):
            if st.button("Endgültig aus Datenbank löschen", type="primary") and st.checkbox("Bestätigen"):
                c.execute("DELETE FROM media WHERE fall_id = ?", (f_id,))
                c.execute("DELETE FROM falle WHERE id = ?", (f_id,))
                conn.commit()
                st.success("Gelöscht!")
                st.rerun()

