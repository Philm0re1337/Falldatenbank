import streamlit as st
import pandas as pd
import datetime
import json
import base64
from PIL import Image
import io

# --- PRÜFUNG DER ABHÄNGIGKEITEN ---
try:
    from google.cloud import firestore
    from google.oauth2 import service_account
except ImportError as e:
    st.error(f"🚨 Fehler beim Laden der Bibliotheken: {e}")
    st.info("Bitte stelle sicher, dass `google-cloud-firestore` in deiner requirements.txt steht.")
    st.stop()

# --- KONFIGURATION ---
firebase_info = st.secrets.get("FIREBASE_JSON")
TEAM_PASSWORD = "2180"

@st.cache_resource
def get_db():
    if not firebase_info:
        st.error("Google Credentials fehlen!")
        st.stop()
    try:
        info = json.loads(firebase_info)
        credentials = service_account.Credentials.from_service_account_info(info)
        db = firestore.Client(
            credentials=credentials, 
            project=info.get("project_id"),
            database="falldatenbank"
        )
        return db
    except Exception as e:
        st.error(f"Datenbankfehler: {e}")
        st.stop()

db = get_db()

# --- HILFSFUNKTIONEN (BASE64) ---
def process_file(file):
    """Konvertiert Dateien in Base64 und verkleinert Bilder falls nötig."""
    file_type = file.type
    
    if "image" in file_type:
        # Bild verkleinern, um unter dem 1MB Firestore Limit zu bleiben
        img = Image.open(file)
        # Maximal 1200px Breite/Höhe
        img.thumbnail((1200, 1200))
        buffer = io.BytesIO()
        # Als JPEG speichern für bessere Kompression
        img.save(buffer, format="JPEG", quality=75)
        base64_str = base64.b64encode(buffer.getvalue()).decode()
        return f"data:image/jpeg;base64,{base64_str}"
    else:
        # Für Videos/andere Dateien (Vorsicht: Darf nicht > 1MB sein!)
        file_bytes = file.read()
        if len(file_bytes) > 900000: # ~0.9 MB Sicherheitsgrenze
            st.error(f"Datei {file.name} ist zu groß (max. 1MB erlaubt in Firestore).")
            return None
        base64_str = base64.b64encode(file_bytes).decode()
        return f"data:{file_type};base64,{base64_str}"

# --- UI ---
st.set_page_config(page_title="Fall-Archiv Lokal-Cloud", layout="wide")

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

mode = st.sidebar.radio("Navigation", ["Übersicht", "Neuanlage"])

if mode == "Neuanlage":
    st.header("➕ Neuen Fall anlegen")
    with st.form("form_neu", clear_on_submit=True):
        fnr = st.text_input("Fall-Nummer")
        fdat = st.date_input("Datum", datetime.date.today())
        fbes = st.text_area("Beschreibung")
        files = st.file_uploader("Bilder/Videos (max. 1MB pro Datei)", accept_multiple_files=True)
        
        if st.form_submit_button("Speichern"):
            if fnr and fbes:
                media_list = []
                with st.spinner("Verarbeite Medien..."):
                    for f in files:
                        b64 = process_file(f)
                        if b64:
                            media_list.append({"name": f.name, "data": b64, "type": f.type})
                
                try:
                    db.collection("falle").add({
                        "fall_nummer": fnr,
                        "datum": fdat.isoformat(),
                        "beschreibung": fbes,
                        "medien": media_list,
                        "status": "Offen",
                        "created_at": firestore.SERVER_TIMESTAMP
                    })
                    st.success("Fall wurde gespeichert!")
                except Exception as e:
                    st.error(f"Fehler: {e}")

elif mode == "Übersicht":
    st.header("📂 Fall-Archiv")
    search = st.text_input("Suche...")
    
    docs = db.collection("falle").order_by("datum", direction=firestore.Query.DESCENDING).stream()
    
    for doc in docs:
        row = doc.to_dict()
        if search and search.lower() not in row['fall_nummer'].lower():
            continue
            
        with st.expander(f"Fall {row['fall_nummer']} - {row['datum']}"):
            st.write(row['beschreibung'])
            if row.get('medien'):
                cols = st.columns(3)
                for i, m in enumerate(row['medien']):
                    with cols[i % 3]:
                        if "image" in m['type']:
                            st.image(m['data'], caption=m['name'])
                        else:
                            st.video(m['data'])
