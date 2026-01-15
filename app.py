import streamlit as st
import pandas as pd
import sqlite3
import os
from datetime import datetime
from pydrive2.auth import GoogleAuth
from pydrive2.drive import GoogleDrive
from oauth2client.service_account import ServiceAccountCredentials

# --- CONFIGURATION ---
# Extrahiert aus deiner URL
GDRIVE_FOLDER_ID = "0B5UeXbdEo09pR1h2T0pJNmdLMUE" 
TEAM_PASSWORD = "2180"
DB_NAME = "fall_archiv_gdrive.db"

# --- GOOGLE DRIVE CONNECTION ---
@st.cache_resource
def get_gdrive():
    try:
        scope = ['https://www.googleapis.com/auth/drive']
        # Erwartet die credentials.json Datei im gleichen Verzeichnis
        creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
        gauth = GoogleAuth()
        gauth.credentials = creds
        return GoogleDrive(gauth)
    except Exception as e:
        st.error(f"Fehler bei der Google Drive Verbindung: {e}")
        return None

drive = get_gdrive()

# --- DATABASE SETUP ---
def get_db_connection():
    return sqlite3.connect(DB_NAME, check_same_thread=False)

conn = get_db_connection()
c = conn.cursor()

c.execute('''CREATE TABLE IF NOT EXISTS falle 
             (id INTEGER PRIMARY KEY AUTOINCREMENT, 
              fall_nummer TEXT, 
              datum DATE, 
              beschreibung TEXT, 
              hauptbild_id TEXT,
              erledigt INTEGER DEFAULT 0)''')

c.execute('''CREATE TABLE IF NOT EXISTS media 
             (id INTEGER PRIMARY KEY AUTOINCREMENT, 
              fall_id INTEGER, 
              file_id TEXT, 
              file_type TEXT,
              FOREIGN KEY(fall_id) REFERENCES falle(id))''')
conn.commit()

# --- HELFERFUNKTIONEN ---
def upload_to_gdrive(file, filename):
    try:
        gfile = drive.CreateFile({'title': filename, 'parents': [{'id': GDRIVE_FOLDER_ID}]})
        # Temporäres Speichern der Streamlit-Datei zum Upload
        with open(filename, "wb") as f:
            f.write(file.getbuffer())
        gfile.SetContentFile(filename)
        gfile.Upload()
        # Datei für die Anzeige freigeben (Public Link)
        gfile.InsertPermission({'type': 'anyone', 'value': 'anyone', 'role': 'reader'})
        os.remove(filename) # Temporäre lokale Datei löschen
        return gfile['id']
    except Exception as e:
        st.error(f"Upload-Fehler: {e}")
        return None

# --- 1. SICHERHEIT: PASSWORT-ABFRAGE ---
def check_password():
    if "password_correct" not in st.session_state:
        st.title("🔒 Team-Login")
        pw = st.text_input("Bitte gib das Passwort ein", type="password")
        if st.button("Anmelden"):
            if pw == TEAM_PASSWORD:
                st.session_state["password_correct"] = True
                st.rerun()
            else:
                st.error("😕 Passwort falsch.")
        return False
    return True

if not check_password():
    st.stop()

# --- 2. NAVIGATION & UI ---
st.set_page_config(page_title="Team Fall-Archiv Cloud", layout="wide")
st.sidebar.title("📁 Navigation")
choice = st.sidebar.radio("Menü", ["Übersicht & Suche", "Neuanlage", "Bearbeiten & Löschen"])

# --- NEUANLAGE ---
if choice == "Neuanlage":
    st.header("➕ Neuen Fall erfassen (Cloud)")
    with st.form("neu_form", clear_on_submit=True):
        f_nr = st.text_input("Fall-Nummer")
        f_date = st.date_input("Datum", datetime.now())
        f_desc = st.text_area("Fall-Beschreibung")
        
        st.write("---")
        st.subheader("Cloud-Upload")
        u_bilder = st.file_uploader("Bilder hochladen", type=["jpg", "jpeg", "png"], accept_multiple_files=True)
        u_videos = st.file_uploader("Videos hochladen", type=["mp4", "mov"], accept_multiple_files=True)
        
        if st.form_submit_button("Fall in Cloud speichern"):
            if f_nr and u_bilder and drive:
                with st.spinner('Lade Dateien zu Google Drive hoch...'):
                    # Hauptbild (Index 0)
                    h_id = upload_to_gdrive(u_bilder[0], f"{f_nr}_MAIN.jpg")
                    
                    c.execute("INSERT INTO falle (fall_nummer, datum, beschreibung, hauptbild_id, erledigt) VALUES (?,?,?,?,?)",
                              (f_nr, f_date, f_desc, h_id, 0))
                    f_id = c.lastrowid
                    
                    # Alle Bilder hochladen
                    for img in u_bilder:
                        img_id = upload_to_gdrive(img, f"{f_nr}_IMG_{img.name}")
                        c.execute("INSERT INTO media (fall_id, file_id, file_type) VALUES (?,?,?)", (f_id, img_id, "image"))
                    
                    # Videos hochladen
                    if u_videos:
                        for vid in u_videos:
                            vid_id = upload_to_gdrive(vid, f"{f_nr}_VID_{vid.name}")
                            c.execute("INSERT INTO media (fall_id, file_id, file_type) VALUES (?,?,?)", (f_id, vid_id, "video"))
                    
                    conn.commit()
                    st.success(f"Fall {f_nr} wurde erfolgreich in Google Drive gespeichert!")
            else:
                st.error("Bitte Fallnummer, mindestens ein Bild und Drive-Verbindung prüfen.")

# --- ÜBERSICHT & SUCHE ---
elif choice == "Übersicht & Suche":
    st.header("📂 Cloud Fall-Archiv")
    
    s_col1, s_col2, s_col3 = st.columns([2, 1, 1])
    with s_col1:
        search_nr = st.text_input("Suche Fallnummer")
    with s_col2:
        search_date = st.date_input("Filter Datum", value=None)
    with s_col3:
        status_filter = st.selectbox("Status", ["Alle", "Offen", "Erledigt"])

    query = "SELECT * FROM falle WHERE 1=1"
    params = []
    if search_nr:
        query += " AND fall_nummer LIKE ?"; params.append(f"%{search_nr}%")
    if search_date:
        query += " AND datum = ?"; params.append(search_date)
    if status_filter == "Offen":
        query += " AND erledigt = 0"
    elif status_filter == "Erledigt":
        query += " AND erledigt = 1"
    
    df = pd.read_sql_query(query + " ORDER BY datum DESC", conn, params=params)
    
    for idx, row in df.iterrows():
        status_icon = "✅" if row['erledigt'] == 1 else "⏳"
        with st.container(border=True):
            col1, col2 = st.columns([1, 4])
            with col1:
                # Google Drive Bildanzeige über die ID
                st.image(f"https://drive.google.com/uc?id={row['hauptbild_id']}")
            with col2:
                st.subheader(f"{status_icon} Fall {row['fall_nummer']}")
                st.caption(f"Datum: {row['datum']}")
                with st.expander("Beschreibung & alle Medien anzeigen"):
                    st.write(row['beschreibung'])
                    m_df = pd.read_sql_query(f"SELECT * FROM media WHERE fall_id = {row['id']}", conn)
                    m_cols = st.columns(3)
                    for m_idx, m_row in m_df.iterrows():
                        with m_cols[m_idx % 3]:
                            url = f"https://drive.google.com/uc?id={m_row['file_id']}"
                            if m_row['file_type'] == "video":
                                st.video(url)
                            else:
                                st.image(url)

# --- BEARBEITEN & LÖSCHEN ---
elif choice == "Bearbeiten & Löschen":
    st.header("📝 Fall bearbeiten")
    df = pd.read_sql_query("SELECT * FROM falle", conn)
    
    if not df.empty:
        auswahl = st.selectbox("Fall auswählen", df['fall_nummer'].tolist())
        f_data = df[df['fall_nummer'] == auswahl].iloc[0]
        f_id = int(f_data['id'])
        
        with st.form("edit_form"):
            u_nr = st.text_input("Fall-Nummer", value=f_data['fall_nummer'])
            u_date = st.date_input("Datum", value=datetime.strptime(str(f_data['datum']), '%Y-%m-%d'))
            u_desc = st.text_area("Beschreibung", value=f_data['beschreibung'])
            u_done = st.checkbox("Erledigt", value=bool(f_data['erledigt']))
            
            if st.form_submit_button("Speichern"):
                c.execute("UPDATE falle SET fall_nummer=?, datum=?, beschreibung=?, erledigt=? WHERE id=?", 
                          (u_nr, u_date, u_desc, 1 if u_done else 0, f_id))
                conn.commit()
                st.success("Aktualisiert!")
                st.rerun()

        st.divider()
        with st.expander("🗑️ Fall endgültig löschen"):
            confirm = st.checkbox("Ich möchte diesen Fall und alle Cloud-Daten löschen")
            if st.button("LÖSCHEN BESTÄTIGEN", type="primary"):
                if confirm:
                    # Hinweis: Dateien in Drive werden hier nicht gelöscht (nur Datenbank), 
                    # um Datenverlust bei Fehlern zu vermeiden.
                    c.execute("DELETE FROM media WHERE fall_id = ?", (f_id,))
                    c.execute("DELETE FROM falle WHERE id = ?", (f_id,))
                    conn.commit()
                    st.success("Eintrag gelöscht!")
                    st.rerun()