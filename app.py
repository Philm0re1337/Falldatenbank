import streamlit as st
import pandas as pd
import datetime

# --- KONFIGURATION ---
# Das Passwort für den Zugang zur App
TEAM_PASSWORD = "2180"

# --- LOGGING FUNKTION ---
def log_fall_to_console(fnr, fdat, fbes, bilder_anzahl):
    """
    Schreibt die Falldaten in die Streamlit Cloud Logs.
    Diese sind im Dashboard unter 'Manage App' -> 'Logs' einsehbar.
    """
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"\n--- NEUER FALL-EINTRAG [{timestamp}] ---\n"
    log_entry += f"FALL-NUMMER: {fnr}\n"
    log_entry += f"DATUM: {fdat}\n"
    log_entry += f"BESCHREIBUNG: {fbes}\n"
    log_entry += f"ANZAHL BILDER: {bilder_anzahl}\n"
    log_entry += "--------------------------------------\n"
    
    # Der print-Befehl leitet die Daten in die Streamlit-Konsole um
    print(log_entry)
    return True

# --- UI KONFIGURATION ---
st.set_page_config(page_title="Fall-Archiv Log-System", layout="centered")

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

# --- HAUPTSEITE ---
st.title("📂 Fall-Protokollierung")
st.info("Eingegebene Daten werden direkt in den System-Logs archiviert.")

# Eingabe-Formular
with st.form("fall_form", clear_on_submit=True):
    col1, col2 = st.columns(2)
    with col1:
        fall_nummer = st.text_input("Fall-Nummer / Aktenzeichen")
    with col2:
        datum = st.date_input("Datum des Vorfalls", datetime.date.today())
    
    beschreibung = st.text_area("Detaillierte Fallbeschreibung")
    
    upload_files = st.file_uploader(
        "Bilder/Dokumente (werden im Log vermerkt)", 
        type=["jpg", "png", "pdf"], 
        accept_multiple_files=True
    )
    
    submit = st.form_submit_button("Fall final archivieren")

    if submit:
        if fall_nummer and beschreibung:
            anzahl_anhange = len(upload_files) if upload_files else 0
            
            # Daten in Logs schreiben
            if log_fall_to_console(fall_nummer, datum, beschreibung, anzahl_anhange):
                st.success(f"✅ Fall {fall_nummer} wurde erfolgreich im System-Log protokolliert.")
                st.balloons()
        else:
            st.warning("Bitte füllen Sie mindestens die Fall-Nummer und die Beschreibung aus.")

# --- FOOTER / INFO ---
st.sidebar.markdown("---")
st.sidebar.write("### 🛠 Admin-Info")
st.sidebar.write("Um die gespeicherten Fälle einzusehen:")
st.sidebar.write("1. Öffne das Streamlit Dashboard.")
st.sidebar.write("2. Klicke auf deine App.")
st.sidebar.write("3. Wähle rechts unten 'Manage App'.")
st.sidebar.write("4. Klicke auf den Tab 'Logs'.")
