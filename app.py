import streamlit as st
import pandas as pd
import datetime
import json
import base64
from PIL import Image
import io
import requests

# --- PRÜFUNG DER ABHÄNGIGKEITEN ---
try:
    from google.cloud import firestore
    from google.oauth2 import service_account
except ImportError as e:
    st.error(f"🚨 Fehler beim Laden der Bibliotheken: {e}")
    st.info("Bitte stelle sicher, dass `google-cloud-firestore`, `Pillow` und `requests` in deiner requirements.txt stehen.")
    st.stop()

# --- KONFIGURATION AUS SECRETS ---
firebase_info = st.secrets.get("FIREBASE_JSON")
TEAM_PASSWORD = "2180"

# Die ngrok-URL von deinem Firmen-PC
NGROK_URL = st.secrets.get("LOCAL_SERVER_URL", "HIER_DEINE_NGROK_URL_EINTRAGEN")

@st.cache_resource
def get_db():
    if not firebase_info:
        st.error("Google Credentials (FIREBASE_JSON) fehlen in den Secrets!")
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

# --- HILFSFUNKTIONEN ---
def process_file(file, fall_nummer):
    """Verarbeitet Bilder für Firestore oder sendet große Videos an den Firmen-PC via ngrok."""
    file_type = file.type
    
    # 1. BILDER (Werden komprimiert und in Firestore gespeichert)
    if "image" in file_type:
        try:
            img = Image.open(file)
            # Bild verkleinern für Firestore (Limit pro Dokument 1MB)
            img.thumbnail((1000, 1000))
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=70)
            base64_str = base64.b64encode(buffer.getvalue()).decode()
            return {"data": f"data:image/jpeg;base64,{base64_str}", "status": "stored", "method": "firestore"}
        except Exception:
            return None
            
    # 2. VIDEOS ODER ANDERE DATEIEN
    else:
        file_content = file.read()
        # Wenn Datei > 0.95 MB, sende sie an den lokalen Server (Firmen-PC)
        if len(file_content) > 950000:
            if NGROK_URL == "HIER_DEINE_NGROK_URL_EINTRAGEN" or not NGROK_URL:
                return {"data": file.name, "status": "error", "msg": "Keine Server-URL konfiguriert"}
            
            try:
                clean_url = NGROK_URL.rstrip('/')
                # Sende Datei per POST an das server.py Skript auf dem PC
                response = requests.post(
                    f"{clean_url}/upload",
                    files={"file": (file.name, file_content, file_type)},
                    data={"fall_nummer": fall_nummer},
                    timeout=120 # Langer Timeout für große Video-Uploads
                )
                if response.status_code == 200:
                    return {"data": file.name, "status": "stored", "method": "local_server"}
                else:
                    return {"data": file.name, "status": "error", "msg": f"Server-Fehler: {response.status_code}"}
            except Exception as e:
                return {"data": file.name, "status": "error", "msg": f"Verbindung fehlgeschlagen: {str(e)}"}
        else:
            # Kleines Video (< 1MB) direkt in Firestore speichern
            base64_str = base64.b64encode(file_content).decode()
            return {"data": f"data:{file_type};base64,{base64_str}", "status": "stored", "method": "firestore"}

# --- UI LAYOUT ---
st.set_page_config(page_title="Fall-Archiv & Firmen-Server", layout="wide")

# LOGIN CHECK
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

# NAVIGATION
mode = st.sidebar.radio("Menü", ["Übersicht", "Neuanlage"])

# --- MODUS: NEUANLAGE ---
if mode == "Neuanlage":
    st.header("➕ Neuen Fall anlegen")
    with st.form("form_neu", clear_on_submit=True):
        fnr = st.text_input("Fall-Nummer (z.B. F-2024-001)")
        fdat = st.date_input("Datum", datetime.date.today())
        fbes = st.text_area("Beschreibung des Vorfalls")
        files = st.file_uploader("Medien hochladen (Fotos & Videos)", accept_multiple_files=True)
        
        if st.form_submit_button("Fall in Cloud speichern"):
            if fnr and fbes:
                media_list = []
                upload_errors = []
                
                with st.spinner("Dateien werden verarbeitet und übertragen..."):
                    for f in files:
                        res = process_file(f, fnr)
                        if res:
                            if res["status"] == "stored":
                                media_list.append({
                                    "name": f.name, 
                                    "data": res["data"] if res["method"] == "firestore" else f"Gespeichert auf Firmen-PC ({f.name})", 
                                    "type": f.type, 
                                    "method": res["method"]
                                })
                            else:
                                upload_errors.append(f"{f.name}: {res.get('msg', 'Fehler')}")
                
                try:
                    # Daten in die Cloud (Firestore) schreiben
                    db.collection("falle").add({
                        "fall_nummer": fnr,
                        "datum": fdat.isoformat(),
                        "beschreibung": fbes,
                        "medien": media_list,
                        "status": "Offen",
                        "created_at": firestore.SERVER_TIMESTAMP
                    })
                    
                    st.success(f"✅ Fall {fnr} wurde erfolgreich im Archiv gespeichert!")
                    if upload_errors:
                        st.error("⚠️ Einige Videos konnten nicht an den Firmen-PC übertragen werden (siehe unten).")
                        for err in upload_errors: st.write(f"- {err}")
                except Exception as e:
                    st.error(f"Datenbankfehler: {e}")
            else:
                st.warning("Bitte gib mindestens eine Fall-Nummer und eine Beschreibung an.")

# --- MODUS: ÜBERSICHT ---
elif mode == "Übersicht":
    st.header("📂 Archiviertes Fallregister")
    search = st.text_input("🔍 Suche nach Fall-Nummer...")
    
    try:
        # Fälle aus der Cloud laden
        docs = db.collection("falle").order_by("datum", direction=firestore.Query.DESCENDING).stream()
        
        found = False
        for doc in docs:
            row = doc.to_dict()
            if search and search.lower() not in row.get('fall_nummer', '').lower():
                continue
            
            found = True
            with st.expander(f"📦 Fall: {row.get('fall_nummer', 'Unbekannt')} | Datum: {row.get('datum', 'Ohne Datum')}"):
                st.write(f"**Vorgang:** {row.get('beschreibung', '-')}")
                
                if row.get('medien'):
                    st.write("---")
                    st.write("**Anhänge:**")
                    cols = st.columns(3)
                    for i, m in enumerate(row['medien']):
                        method = m.get("method", "firestore")
                        with cols[i % 3]:
                            if method == "firestore":
                                if "image" in m['type']:
                                    st.image(m['data'], caption=m['name'], use_container_width=True)
                                else:
                                    st.video(m['data'])
                            else:
                                # Info-Box für Dateien, die auf der lokalen Festplatte liegen
                                st.info(f"🖥️ **{m['name']}**\nDiese Datei ist zu groß für die Cloud und wurde direkt auf dem Firmen-PC gesichert.")
        
        if not found:
            st.info("Keine passenden Fälle gefunden.")
            
    except Exception as e:
        st.error(f"Fehler beim Laden der Cloud-Daten: {e}")
