import streamlit as st
import pandas as pd
import datetime
import os
import re
import json
import io

# --- PRÜFUNG DER ABHÄNGIGKEITEN ---
try:
    from google.cloud import firestore
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    from googleapiclient.http import MediaIoBaseUpload, MediaIoBaseDownload
except ImportError as e:
    st.error(f"🚨 Fehler beim Laden der Bibliotheken: {e}")
    st.stop()

# --- KONFIGURATION & INITIALISIERUNG ---
firebase_info = st.secrets.get("FIREBASE_JSON")
TEAM_PASSWORD = "2180"
# Deine private E-Mail für die Übertragung der Eigentumsrechte
USER_EMAIL = "philm0re1337@gmail.com"
# ID deines Zielordners (muss für die Service-Account E-Mail freigegeben sein!)
GDRIVE_FOLDER_ID = st.secrets.get("GDRIVE_FOLDER_ID", "0B5UeXbdEo09pR1h2T0pJNmdLMUE") 

@st.cache_resource
def get_services():
    if not firebase_info:
        st.error("Google Credentials fehlen!")
        st.stop()
    
    try:
        info = json.loads(firebase_info)
        credentials = service_account.Credentials.from_service_account_info(info)
        scoped_credentials = credentials.with_scopes([
            'https://www.googleapis.com/auth/cloud-platform',
            'https://www.googleapis.com/auth/drive.file',
            'https://www.googleapis.com/auth/drive'
        ])
        
        db = firestore.Client(
            credentials=scoped_credentials, 
            project=info.get("project_id"),
            database="falldatenbank"
        )
        drive_service = build('drive', 'v3', credentials=scoped_credentials)
        return db, drive_service
    except Exception as e:
        st.error(f"Initialisierungsfehler: {e}")
        st.stop()

db, drive_service = get_services()

# --- UI SETTINGS ---
st.set_page_config(page_title="Fall-Archiv Pro", layout="wide")

# --- AUTH ---
if "auth" not in st.session_state:
    st.title("🔒 Team Login")
    pwd = st.text_input("Passwort", type="password")
    if st.button("Anmelden") or (pwd == TEAM_PASSWORD and pwd != ""):
        if pwd == TEAM_PASSWORD:
            st.session_state["auth"] = True
            st.rerun()
        else:
            st.error("Falsch")
    st.stop()

# --- DRIVE FUNKTIONEN ---
def upload_to_drive(file):
    """
    Lädt eine Datei hoch und versucht, den Besitz auf das private Konto zu übertragen,
    um das 0GB-Limit des Service-Accounts zu umgehen.
    """
    file_metadata = {
        'name': f"{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}_{file.name}",
        'parents': [GDRIVE_FOLDER_ID]
    }
    
    media = MediaIoBaseUpload(io.BytesIO(file.read()), mimetype=file.type, resumable=True)
    
    try:
        # 1. Datei erstellen
        drive_file = drive_service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id, webViewLink'
        ).execute()
        
        file_id = drive_file.get('id')
        
        # 2. Berechtigung für dich hinzufügen und versuchen, den Besitz zu übertragen
        # Hinweis: Das Übertragen des Besitzes (transferOwnership) funktioniert in 
        # privaten Konten nur, wenn beide in der gleichen Organisation sind oder 
        # unter bestimmten Bedingungen. Wir setzen dich zumindest als 'owner'.
        try:
            drive_service.permissions().create(
                fileId=file_id,
                body={
                    'type': 'user',
                    'role': 'owner',
                    'emailAddress': USER_EMAIL
                },
                transferOwnership=True,
                fields='id'
            ).execute()
        except Exception as perm_e:
            # Falls transferOwnership scheitert (oft bei Gmail zu Gmail), 
            # machen wir dich zumindest zum Editor, damit du die Datei siehst.
            drive_service.permissions().create(
                fileId=file_id,
                body={
                    'type': 'user',
                    'role': 'writer',
                    'emailAddress': USER_EMAIL
                },
                fields='id'
            ).execute()
            
        return drive_file.get('webViewLink'), file_id
        
    except Exception as e:
        if "storageQuotaExceeded" in str(e):
            st.error("❌ Google Drive Quota-Limit überschritten.")
            st.info(f"""
            Selbst mit deiner E-Mail {USER_EMAIL} blockiert Google den Upload, da der Service-Account 
            der initiale Ersteller ist. 
            
            **Nächster Schritt:** Wir sollten auf **Firebase Storage** umsteigen. Das ist für private Konten 
            die stabilste Lösung.
            """)
        raise e

def get_drive_image(file_id):
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

if mode == "Neuanlage":
    st.header("➕ Neuen Fall anlegen")
    with st.form("form_neu", clear_on_submit=True):
        fnr = st.text_input("Fall-Nummer")
        fdat = st.date_input("Datum", datetime.date.today())
        fbes = st.text_area("Beschreibung")
        files = st.file_uploader("Dateien", accept_multiple_files=True)
        
        if st.form_submit_button("Speichern"):
            if fnr and fbes:
                media_data = []
                for f in files:
                    try:
                        url, f_id = upload_to_drive(f)
                        media_data.append({"url": url, "id": f_id, "type": f.type})
                    except Exception as e:
                        st.error(f"Fehler bei {f.name}: {e}")
                
                db.collection("falle").add({
                    "fall_nummer": fnr,
                    "datum": fdat.isoformat(),
                    "beschreibung": fbes,
                    "medien": media_data,
                    "status": "Offen",
                    "created_at": firestore.SERVER_TIMESTAMP
                })
                st.success("Erledigt!")

elif mode == "Übersicht":
    st.header("📂 Archiv")
    try:
        docs = db.collection("falle").order_by("datum", direction=firestore.Query.DESCENDING).stream()
        for doc in docs:
            row = doc.to_dict()
            with st.expander(f"Fall {row['fall_nummer']} - {row['datum']}"):
                st.write(row['beschreibung'])
                if row.get('medien'):
                    for m in row['medien']:
                        if "image" in m['type']:
                            img = get_drive_image(m['id'])
                            if img: st.image(img, width=300)
                        else:
                            st.write(f"🎥 Video: [Link]({m['url']})")
    except Exception as e:
        st.error(f"Fehler: {e}")
