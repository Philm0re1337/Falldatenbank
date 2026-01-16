import streamlit as st
import pandas as pd
import datetime
import json
import base64
from PIL import Image
import io
import urllib.parse

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
# Hier kannst du die Telefonnummer der Firma oder Gruppe hinterlegen
WHATSAPP_TARGET = "491234567890" 

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

# --- HILFSFUNKTIONEN ---
def process_file(file):
    """Verarbeitet Bilder für Firestore (Base64) oder erkennt zu große Videos."""
    file_type = file.type
    
    if "image" in file_type:
        try:
            img = Image.open(file)
            img.thumbnail((1000, 1000))
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=70)
            base64_str = base64.b64encode(buffer.getvalue()).decode()
            return {"data": f"data:image/jpeg;base64,{base64_str}", "status": "stored"}
        except:
            return None
    else:
        # Videos werden in Firestore oft zu groß (>1MB)
        file_bytes = file.read()
        if len(file_bytes) > 950000:
            # Zu groß für Firestore -> Markierung für externen Versand
            return {"data": file.name, "status": "external", "size": len(file_bytes)}
        else:
            base64_str = base64.b64encode(file_bytes).decode()
            return {"data": f"data:{file_type};base64,{base64_str}", "status": "stored"}

def create_whatsapp_link(text):
    encoded_text = urllib.parse.quote(text)
    return f"https://wa.me/{WHATSAPP_TARGET}?text={encoded_text}"

# --- UI ---
st.set_page_config(page_title="Fall-Archiv & Video-Manager", layout="wide")

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
        files = st.file_uploader("Medien (Bilder landen in Cloud, große Videos per WA)", accept_multiple_files=True)
        
        if st.form_submit_button("Speichern"):
            if fnr and fbes:
                media_list = []
                external_videos = []
                
                with st.spinner("Verarbeite Medien..."):
                    for f in files:
                        res = process_file(f)
                        if res:
                            if res["status"] == "stored":
                                media_list.append({"name": f.name, "data": res["data"], "type": f.type, "stored": True})
                            else:
                                media_list.append({"name": f.name, "data": "Extern gespeichert (WhatsApp/Server)", "type": f.type, "stored": False})
                                external_videos.append(f.name)
                
                try:
                    db.collection("falle").add({
                        "fall_nummer": fnr,
                        "datum": fdat.isoformat(),
                        "beschreibung": fbes,
                        "medien": media_list,
                        "status": "Offen",
                        "created_at": firestore.SERVER_TIMESTAMP
                    })
                    
                    st.success(f"Fall {fnr} in Datenbank angelegt!")
                    
                    if external_videos:
                        st.warning(f"⚠️ {len(external_videos)} Videos sind zu groß für die Cloud.")
                        wa_text = f"Neuer Fall: {fnr}\nDatum: {fdat}\nVideos: {', '.join(external_videos)}\n\nBitte hier hochladen/senden!"
                        wa_url = create_whatsapp_link(wa_text)
                        st.markdown(f'<a href="{wa_url}" target="_blank" style="text-decoration:none;"><div style="background-color:#25D366;color:white;padding:10px;text-align:center;border-radius:5px;">Jetzt Videos per WhatsApp senden</div></a>', unsafe_allow_html=True)
                        
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
            st.write(f"**Beschreibung:** {row['beschreibung']}")
            
            if row.get('medien'):
                st.write("---")
                cols = st.columns(3)
                for i, m in enumerate(row['medien']):
                    with cols[i % 3]:
                        if m.get("stored", True):
                            if "image" in m['type']:
                                st.image(m['data'], caption=m['name'])
                            else:
                                st.video(m['data'])
                        else:
                            st.info(f"🎥 {m['name']}\n(Video wurde extern gesendet)")
