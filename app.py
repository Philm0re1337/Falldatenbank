import streamlit as st
import pandas as pd
import sqlite3
import os
from datetime import datetime
from pydrive2.auth import GoogleAuth
from pydrive2.drive import GoogleDrive
from oauth2client.service_account import ServiceAccountCredentials

# --- KONFIGURATION ---
GDRIVE_FOLDER_ID = "0B5UeXbdEo09pR1h2T0pJNmdLMUE" 
TEAM_PASSWORD = "2180"
DB_NAME = "fall_archiv_gdrive.db"

# --- GOOGLE DRIVE VERBINDUNG (Service Account Modus) ---
@st.cache_resource
def get_gdrive():
    try:
        key_file = 'credentials.json'
        if not os.path.exists(key_file):
            st.error(f"⚠️ Datei '{key_file}' nicht gefunden!")
            return None
            
        scope = ['https://www.googleapis.com/auth/drive']
        creds = ServiceAccountCredentials.from_json_keyfile_name(key_file, scope)
        
        # --- KORREKTUR HIER ---
        gauth = GoogleAuth()
        # Diese Zeile verhindert, dass PyDrive2 nach client_secrets.json sucht:
        gauth.settings['client_config_backend'] = 'settings' 
        gauth.credentials = creds
        # ----------------------
        
        return GoogleDrive(gauth)
    except Exception as e:
        st.error(f"❌ Fehler bei der Google Drive Verbindung: {e}")
        return None

drive = get_gdrive()

# --- DATENBANK SETUP ---
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
              file_type TEXT)''')
conn.commit()

# --- HELFERFUNKTION: UPLOAD ---
def upload_to_gdrive(file, filename):
    try:
        # Lokale temporäre Datei erstellen, da PyDrive2 einen Pfad benötigt
        temp_path = f"temp_{filename}"
        with open(temp_path, "wb") as f:
            f.write(file.getbuffer())
            
        gfile = drive.CreateFile({'title': filename, 'parents': [{'id': GDRIVE_FOLDER_ID}]})
        gfile.SetContentFile(temp_path)
        gfile.Upload()
        
        # Berechtigung setzen, damit das Bild per URL angezeigt werden kann
        gfile.InsertPermission({'type': 'anyone', 'value': 'anyone', 'role': 'reader'})
        
        os.remove(temp_path) # Temp-Datei löschen
        return gfile['id']
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
        
        st.write("---")
        u_bilder = st.file_uploader("Bilder (Erstes = Vorschau)", type=["jpg", "jpeg", "png"], accept_multiple_files=True)
        u_vids = st.file_uploader("Videos", type=["mp4", "mov"], accept_multiple_files=True)
        
        if st.form_submit_button("In Cloud speichern"):
            if f_nr and u_bilder and drive:
                with st.spinner('Daten werden hochgeladen...'):
                    # Hauptbild
                    h_id = upload_to_gdrive(u_bilder[0], f"{f_nr}_VORSCHAU.jpg")
                    
                    c.execute("INSERT INTO falle (fall_nummer, datum, beschreibung, hauptbild_id, erledigt) VALUES (?,?,?,?,0)",
                              (f_nr, f_date, f_desc, h_id))
                    f_id = c.lastrowid
                    
                    # Alle Bilder
                    for img in u_bilder:
                        img_id = upload_to_gdrive(img, f"{f_nr}_BILD_{img.name}")
                        c.execute("INSERT INTO media (fall_id, file_id, file_type) VALUES (?,?,'image')", (f_id, img_id))
                    
                    # Videos
                    if u_vids:
                        for vid in u_vids:
                            vid_id = upload_to_gdrive(vid, f"{f_nr}_VIDEO_{vid.name}")
                            c.execute("INSERT INTO media (fall_id, file_id, file_type) VALUES (?,?,'video')", (f_id, vid_id))
                    
                    conn.commit()
                    st.success(f"Fall {f_nr} erfolgreich gespeichert!")
            else:
                st.error("Bitte Fall-Nr und mindestens ein Bild angeben.")

# --- ÜBERSICHT ---
elif choice == "Übersicht & Suche":
    st.header("📂 Fall-Archiv")
    
    # Filter
    s1, s2, s3 = st.columns([2,1,1])
    search_nr = s1.text_input("Suche Nummer")
    search_date = s2.date_input("Filter Datum", value=None)
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
            col_a, col_b = st.columns([1, 4])
            col_a.image(f"https://drive.google.com/uc?id={row['hauptbild_id']}")
            with col_b:
                st.subheader(f"{badge} Fall {row['fall_nummer']}")
                st.caption(f"Datum: {row['datum']}")
                with st.expander("Details & Medien"):
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
    st.header("📝 Bearbeiten")
    df = pd.read_sql_query("SELECT * FROM falle", conn)
    if not df.empty:
        auswahl = st.selectbox("Fall wählen", df['fall_nummer'].tolist())
        f_data = df[df['fall_nummer'] == auswahl].iloc[0]
        f_id = int(f_data['id'])
        
        with st.form("edit"):
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

        st.write("---")
        with st.expander("🗑️ Fall löschen"):
            confirm = st.checkbox("Bestätige das Löschen")
            if st.button("LÖSCHEN", type="primary") and confirm:
                c.execute("DELETE FROM media WHERE fall_id = ?", (f_id,))
                c.execute("DELETE FROM falle WHERE id = ?", (f_id,))
                conn.commit()
                st.success("Gelöscht!")
                st.rerun()

