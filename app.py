import streamlit as st
import pandas as pd
import datetime
import os
import re
import json
import io

# Wir versuchen die Bibliotheken zu importieren. 
# Falls sie fehlen, geben wir eine klare Anweisung für die requirements.txt aus.
try:
    from google.cloud import firestore
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseUpload, MediaIoBaseDownload
except ImportError:
    st.error("🚨 Fehlende Bibliotheken erkannt!")
    st.info("""
    Bitte stelle sicher, dass eine Datei namens **requirements.txt** in deinem GitHub-Repository liegt, die folgenden Inhalt hat:
    
    ```
    google-cloud-firestore
    google-api-python-client
    google-auth
    pandas
    ```
    """)
    st.stop()

# --- KONFIGURATION & INITIALISIERUNG ---
firebase_info = st.secrets.get("FIREBASE_JSON")
TEAM_PASSWORD = "2180"
GDRIVE_FOLDER_ID = st.secrets.get("GDRIVE_FOLDER_ID", "0B5UeXbdEo09pR1h2T0pJNmdLMUE") 

@st.cache_resource
def get_services():
    if not firebase_info:
        st.error("Google Credentials (JSON) fehlen in den Streamlit Secrets!")
        st.stop()
    
    try:
        info = json.loads(firebase_info)
        credentials = service_account.Credentials.from_service_account_info(info)
        
        scoped_credentials = credentials.with_scopes([
            'https://www.googleapis.com/auth/cloud-platform',
            'https://www.googleapis.com/auth/drive.file',
            'https://www.googleapis.com/auth/drive.readonly'
        ])
        
        db = firestore.Client(credentials=scoped_credentials)
        drive_service = build('drive', 'v3', credentials=scoped_credentials)
        
        return db, drive_service
    except Exception as e:
        st.error(f"Fehler bei der Initialisierung der Google Dienste: {e}")
        st.stop()

db, drive_service = get_services()

# --- UI SETTINGS ---
st.set_page_config(page_title="Fall-Archiv Pro (Google Drive Cloud)", layout="wide")

# --- AUTHENTIFIZIERUNG ---
if "auth" not in st.session_state:
    st.title("🔒 Team Login")
    pwd = st.text_input("Passwort eingeben", type="password")
    if st.button("Anmelden") or (pwd == TEAM_PASSWORD and pwd != ""):
        if pwd == TEAM_PASSWORD:
            st.session_state["auth"] = True
            st.rerun()
        else:
            st.error("Falsches Passwort")
    st.stop()

# --- GOOGLE DRIVE FUNKTIONEN ---
def upload_to_drive(file):
    """Lädt eine Datei in Google Drive hoch."""
    file_metadata = {
        'name': f"{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.name}",
        'parents': [GDRIVE_FOLDER_ID]
    }
    
    media = MediaIoBaseUpload(io.BytesIO(file.read()), mimetype=file.type, resumable=True)
    
    drive_file = drive_service.files().create(
        body=file_metadata,
        media_body=media,
        fields='id, webViewLink'
    ).execute()
    
    return drive_file.get('webViewLink'), drive_file.get('id')

def get_drive_image(file_id):
    """Lädt ein Bild aus Drive in den Speicher, um es in Streamlit anzuzeigen."""
    try:
        request = drive_service.files().get_media(fileId=file_id)
        fh = io.BytesIO()
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while done is False:
            status, done = downloader.next_chunk()
        return fh.getvalue()
    except:
        return None

# --- NAVIGATION ---
mode = st.sidebar.radio("Navigation", ["Übersicht", "Neuanlage"])

# --- NEUANLAGE ---
if mode == "Neuanlage":
    st.header("➕ Neuen Fall anlegen")
    with st.form("form_neu", clear_on_submit=True):
        fnr = st.text_input("Fall-Nummer")
        fdat = st.date_input("Datum", datetime.date.today())
        fbes = st.text_area("Beschreibung")
        files = st.file_uploader("Bilder & Videos auswählen", accept_multiple_files=True, type=["jpg","png","jpeg","mp4","mov"])
        
        if st.form_submit_button("Fall speichern"):
            if fnr and fbes:
                media_data = []
                with st.spinner("Dateien werden in Google Drive gesichert..."):
                    for f in files:
                        url, file_id = upload_to_drive(f)
                        media_data.append({"url": url, "id": file_id, "type": f.type})
                
                # In Firestore speichern
                doc_ref = db.collection("falle").document()
                doc_ref.set({
                    "fall_nummer": fnr,
                    "datum": fdat.isoformat(),
                    "beschreibung": fbes,
                    "medien": media_data,
                    "status": "Offen",
                    "zahlbetrag": 0.0,
                    "created_at": firestore.SERVER_TIMESTAMP
                })
                st.success(f"Fall {fnr} wurde erfolgreich angelegt!")
            else:
                st.warning("Bitte Fall-Nummer und Beschreibung ausfüllen.")

# --- ÜBERSICHT ---
elif mode == "Übersicht":
    st.header("📂 Fall-Archiv (Cloud)")
    
    search_query = st.text_input("🔍 Suche nach Fallnummer...", "").strip()
    
    # Daten abrufen
    try:
        docs = db.collection("falle").order_by("datum", direction=firestore.Query.DESCENDING).stream()
        data = []
        for doc in docs:
            d = doc.to_dict()
            d['id'] = doc.id
            data.append(d)
        
        if not data:
            st.info("Noch keine Fälle im Archiv.")
        else:
            df = pd.DataFrame(data)
            if search_query:
                df = df[df['fall_nummer'].str.contains(search_query, case=False, na=False)]

            for _, row in df.iterrows():
                with st.container(border=True):
                    c1, c2, c3 = st.columns([2, 4, 1])
                    
                    with c1:
                        medien = row.get('medien', [])
                        if medien and "image" in medien[0]['type']:
                            img_data = get_drive_image(medien[0]['id'])
                            if img_data:
                                st.image(img_data, use_container_width=True)
                        else:
                            st.write("📁 Keine Vorschau")

                    with c2:
                        st.subheader(f"Fall {row['fall_nummer']}")
                        st.write(f"📅 {row['datum']} | Status: **{row['status']}**")
                        st.write(row['beschreibung'][:150] + "...")

                    with c3:
                        if st.button("Details", key=f"btn_{row['id']}"):
                            st.session_state[f"detail_{row['id']}"] = True

                    if st.session_state.get(f"detail_{row['id']}", False):
                        with st.expander("Vollständige Falldaten", expanded=True):
                            st.write(f"**Beschreibung:**\n{row['beschreibung']}")
                            if medien:
                                st.write("---")
                                m_cols = st.columns(3)
                                for i, m in enumerate(medien):
                                    with m_cols[i % 3]:
                                        if "image" in m['type']:
                                            img = get_drive_image(m['id'])
                                            if img: st.image(img)
                                        else:
                                            st.video(m['url'])
                                        st.markdown(f"[In Drive öffnen]({m['url']})")
                            
                            if st.button("Schließen", key=f"close_{row['id']}"):
                                del st.session_state[f"detail_{row['id']}"]
                                st.rerun()
    except Exception as e:
        st.error(f"Fehler beim Abrufen der Daten: {e}")
