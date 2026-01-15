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

# --- GOOGLE DRIVE VERBINDUNG (Direkt-Key Methode) ---
@st.cache_resource
def get_gdrive_service():
    try:
        # Wir fügen den Key als Multi-Line String ein, exakt wie in der JSON
        # Das r vor dem String sorgt dafür, dass Backslashes (\n) richtig interpretiert werden
        private_key = r"-----BEGIN PRIVATE KEY-----\nMIIEvAIBADANBgkqhkiG9w0BAQEFAASCBKYwggSiAgEAAoIBAQDYewPQIsMaAReC\nX2pDzPnXDnIxvrKkUqa+FarCFdZRXETjqG9aeIsBK9h8Ath+YEgf6JoUmUEWov1l\nnKTnxSPwFnrESy0oBw/KVMeZhdN7eqbMhg03tsSlvL6wNlUk8JheJTO5cojCqoHW\nI6pe6ke5XvGpiA6zjwmH/zU8JkmoIFceh1qfkEN5+pV7X64k5Cbh4qpF9cajAHV2\nbaeZXiFzMcPP1Es4pPn/LS+cIw1h2Fqq89sdeb0y0ZiU0xVvTRmek5ULmdGYkQlx\nKvYv0ugex95fJeqtGKX8Ti9Vq6qOTOEjquWeakd48o3MWW4uCGOOgdZzZEIqwGcm\nyJZiWJGZAgMBAAECggEAH6OA9+kwtwr8Tt1XmE+rnxr5JRyQGtSKkqLziTisUUlJ\nNzWdiq0t8a6hDeTTk8rKF8HEzShl2yNYogJuFoKZQURjzm8HSz+W9vUDlAQ7V6Ni\nH+eipGcln+xxOStDr+mq9y18PQkIhFzrq2qcgpE+iNDfxG2CaotH8xShSOh2oOfO\nLosD46iLbSPqKvTZ2mPHqxAI3tXkS9XDJrU405CvdqsB/ABNJ/rgxn5Tkzexm6u+\nLuY0f5HFT26+Q+0CaH+BtcnBCNd/jlYmBBI+gic8eOEFQC6RsCVNZn8cRjn92Ulk\nH0PtQ4a7aDiFZV+NciYqle3VOJ9JKQW9QmMo2eMGJQKBgQD5YpPM2Kxx2uTmZYDz\nYfNYEMTuQDfhat9yrcVaosMt0SzIzjDvQMwOc7517fdKpUVeeqfp4ncsCLZlX3Lj\nYouw5KxwSa7U53qt7sVmoN5xI0u2hzlw+f3ZKklEeRHm96c/buiMof19CIlXt0xa\nDYWMFj15suMbbHtv+IUk3v0HBQKBgQDeOQC2TCPm2ewYRhsBJ5Cpbf/gEUtWyKlY\nx4nMGovgdA5bkJ8BVCD7tGcSpAcHXnpwp8ie785I/tw0kuFaQQlF5IpbrDU2F8ZH\nrAEJniEkhOWBEtQjFZaLvrcWUxT85BAKtpGR1FPbJsyo/feCBiDaeVu86TkluCiB\nw8A/GP/8hQKBgGTepoGYskdrDmLSc5H98HuSbNUhTHj0zWSJPOYoJ2IE1WRzYf+j\n6eV+k28HzZp3ttM8MWa8nw9EhuIB9Wpblbz7AXR5mSmsZ0aq6VVVhCOm7xzpHSbB\nNxf7rp7viXoueYuCxLT9YJaOOV8tWMij53x+EmeDH7Eb8+GaV+BOAXIxAoGAYbL0\nAjG1cxAKQZ3Iz5gifKr03QEde1kbQwHvLkHZj2PW0CDkF0Ryf9cPnd1pja7W6+KI\nTIAn1GXgUGjnFLQVLJpOzgEHH/IR5X7UsfLIpXKcKEQr6gTavDOr8O+0AX8PInaj\nx1ZvS6FiR0Xo5Exnc0X5tDNhQZkWjf6O7e7C1LUCgYBygV2iKSslCtViFTztNhxv\nyLFT95jNlESDnUR12oI86D0ri5WZtn9+D3WyIKjg4sV/OyWqywcYd6aOOAp9iT0k\nlSVe25cMEXSi5WDtdi6DDhXphUaOdkFiavgdvkINrPgQ2EAqMGQspoPuv7PCTXXO\nDWOORiinO+KNlVsLoDdThQ==\n-----END PRIVATE KEY-----\n".replace(r"\n", "\n")

        creds_info = {
            "type": "service_account",
            "project_id": "falldatenbank",
            "private_key_id": "eb9219c2f4b417433e68d54baa8ed80c759169a5",
            "private_key": private_key,
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
        
        # Zeitstempel-Fix für Google
        creds._iat = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=20)
        
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

