import streamlit as st
import pandas as pd
import sqlite3
import os
import io
import base64
import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseUpload

# --- KONFIGURATION ---
GDRIVE_FOLDER_ID = "0B5UeXbdEo09pR1h2T0pJNmdLMUE" 
TEAM_PASSWORD = "2180"
DB_NAME = "fall_archiv_cloud.db"

# Dein Private Key als Base64 (sicher gegen Formatierungsfehler)
B64_KEY = "LS0tLS1CRUdJTiBQUklWQVRFIEtFWS0tLS0tCk1JSUV2QUlCQURBTkJna3Foa2lHOXcwQkFRRUZBQVNDQktZd2dnU2lBZ0VBQW9JQkFRRFlld1BRSXNNYUFSZUMKWDJwRHpQblhEbklycktLUnFhK0ZhckNGZFpSWEVUanFHOWFlSXNCSzl2OEF0aCtZR2dmNkpvVW1VRVdvdjFsCm5LVG54U1B3Rm5yRVN5MG9Cdy9LVk1lWmhkTjdlcWJNaGcwM3RzU2x2TDZ3TmxVazhKaGVKVE81Y29qQ3FvSFcKSTZwZTZrZTVYdkdwaUE2emp3bUgvekU4Smttb0lGY2VoMXFma0VONSVwVjdYNjRrNUM2aDRxcEY5Y2FqQUhWMgpiYWVaWGlGek1jUFAxRXM0cFBuL0xTK2NJdzFoMkZxcTg5c2RlYjB5MFppVTExeHdUUm1lazVVTG1kR1lrUWx4Ckt2WXYwdWdleDk1ZkplcXRHS1g4VGk5VnE2cU9UT0VqcXVXZWFrZDQ4bzNNV1c0dUNHT09nZFpaWkVJcXdHY20KeUpaaVdKR1pBZ01CQUFFQ2dnRUFIOE9BOTVrd3R3cjhUdDFYbUUrcW54cjVKUnlRR3RTS2txTHppVGlzVVVsSgpOeldkaXEwdDhhNmhEZVRUazhyS0Y4SEV6U2hsMnlOWW9ndUp1Rm9LWlFVUmp6bThIU3orVzl2VURsQVE3VjZNaQpIK2VpcEdjbG4reHhPU3REcittcTl5MThQUWtJaEZ6cnEycWNncEUraU5EZnhHMkNhb3RIOHhTaFNPaDJvT2ZPCkxvc0Q0NmlMYlNQcUt2VFoybVBIcXhBSTN0WGtTOVRES3JVNDA1Q3ZkcXNCL0FCTkovcmd4bjVUa3pleG02dSsKTHVZMGY1SEZUMjYrUSswQ2FIK0J0Y25CQ05kL2psWW1CQkkrZ2ljOGVPRUZRQzZSc0NWTm5uOGNSam45MlVsawpIMFB0UTRBN2FkaUZaVitOY2lZcWxlM1ZPSjlKS1FXOVFmTW8yZU1HSlFLQmdRRDVZwFBNMkt4eDJ1VG1aWUR6CllmTllFTVR1UURmaGF0OXlyY1Zhb3NNdDBTekl6akR2UU13T2M3NTE3ZmRLcFVWZWVxZnA0bmNzQ0xa bFgzTGpZb3d2S3h3U2E3VTUzcXQ3c1Ztb041eEkwdTJoemx3K2YzWktsa0VlUkhtOWVjL2J1aU1vZjE5Q0lsWHRMnhhCkRZV01GajE1c3VNYmJIdHYrSVVrM3YwSEJRS0JnUURlT1FDMlRDUG0yZXdZUmhzQko1Q3BiZi9nRVV0V3lLbFkKeDRuTUdvdmdkQTVia0o4QlZDRDd0R2NTcEFjSFhucHA4aWU3ODVJL3R3MGt1RmFRUWxGNUlQYnJEVTJGOVpIclFFSm5pRWtoT1dCRXRRakZabEx2cmNXVXhUODVCQUt0cEdSMUZQYkpzeW8vZmVDQmlEYWVWdTg2VGtsdUNpQgp3OEEvR1AvOGhRS0JnR1RlcG9HWXNrZHJEbUxTYzVIOThIdVNiTlVoVEhqMHpXU0pQT1lvSjJJRTFXUnpZZitqCjZlVisayjhIelozdHRNOE1XYThudzlFaHVJQjlXcGJsYno3QVhSNW1TbXNaMGFxNlZWVmhDT203eHpwSFNiQgpOeGY3cnA3dmlYb3VlWXVDeExUOVlKYU9PVjh0V01pajUzK0VtZURIN0ViOCtHYVYrQk9BWEh4QW9HQUZiTDAKQWpHMWN4QUtRWjNJejVnaWZLcjAzUUVkZTF rYlF3SHZMa0haajJQVzBDRGtGMFJ5ZitjUG5kMXBqYTdXNitLSQpUSWFuMUdYZ1VHam5GTFFWTEpwb3pnRUhIL0lSNVg3VXNmTElwWEtjS0VRUjZnVGF2RE9yOE8rdEFYOFBJbmFqCngxWnZTNkZpUjBYbzVFeG5jMFg1dEROaFFaa1dqZjZPN2U3QzFMVUNnWUJ5Z1YyaUtzc2xDdFZpRlR6dE5oeHYKeUxGVDk1ak5sRVNEblVSMTJvSThkNkQwcmk1V3p0bjkrRDM1eUlLZWc0c1YvT3lXcXl3Y1lkNmFPT0FwOWlUMGsKbFNWZTkyY01FWFNpNVd0ZGk2RERoWHBoVWFPZGtGaWF2Z2R2a0lOclBnUTJFQXFNR1FzcG9QdXY3UENUWFhPCkRXT09SaWluTytLTmxWc0xvRGRUaFE9PQotLS0tLUVORCBQUklWQVRFIEtFWS0tLS0tCg=="

# --- GOOGLE DRIVE VERBINDUNG ---
@st.cache_resource
def get_gdrive_service():
    try:
        # Key aus Base64 dekodieren
        decoded_key = base64.b64decode(B64_KEY).decode('utf-8')
        
        # Credential-Info direkt im Code
        creds_info = {
            "type": "service_account",
            "project_id": "falldatenbank",
            "private_key_id": "eb9219c2f4b417433e68d54baa8ed80c759169a5",
            "private_key": decoded_key,
            "client_email": "falldatenbank@falldatenbank.iam.gserviceaccount.com",
            "client_id": "102942440306105394865",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
            "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/falldatenbank%40falldatenbank.iam.gserviceaccount.com"
        }
        
        creds = service_account.Credentials.from_service_account_info(
            creds_info, 
            scopes=['https://www.googleapis.com/auth/drive']
        )
        
        # ZEIT-FIX: Verhindert 'invalid_grant' durch Serverzeit-Unterschiede
        creds._iat = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=20)
        
        service = build('drive', 'v3', credentials=creds)
        return service
    except Exception as e:
        st.error(f"❌ Kritischer Verbindungsfehler: {e}")
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

# --- UI ---
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
                    hid = upload_to_gdrive(u_imgs[0], f"{fnr}_MAIN.jpg")
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
                    st.success("Erfolgreich gespeichert!")

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
    st.header("📝 Fälle bearbeiten / löschen")
    df = pd.read_sql_query("SELECT * FROM falle", conn)
    if not df.empty:
        target = st.selectbox("Fall wählen", df['fall_nummer'].tolist())
        sel = df[df['fall_nummer'] == target].iloc[0]
        with st.form("edit"):
            new_nr = st.text_input("Nummer", value=sel['fall_nummer'])
            new_done = st.checkbox("Erledigt", value=bool(sel['erledigt']))
            if st.form_submit_button("Update"):
                c.execute("UPDATE falle SET fall_nummer=?, erledigt=? WHERE id=?", (new_nr, 1 if new_done else 0, sel['id']))
                conn.commit()
                st.rerun()
        if st.button("FALL LÖSCHEN", type="primary"):
            c.execute("DELETE FROM media WHERE fall_id=?", (sel['id'],))
            c.execute("DELETE FROM falle WHERE id=?", (sel['id'],))
            conn.commit()
            st.rerun()
