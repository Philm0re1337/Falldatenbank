import streamlit as st
import pandas as pd
import sqlite3
import datetime
import os

# --- KONFIGURATION ---
DB_NAME = "fall_archiv_lokal.db"
TEAM_PASSWORD = "2180"
UPLOAD_FOLDER = "uploads"

# Verzeichnis für Uploads erstellen, falls nicht vorhanden
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# --- DATENBANK FUNKTIONEN ---
def get_db_connection():
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    return conn

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    # Erweitert um Spalten für Medien (als Text-Pfade)
    c.execute('''CREATE TABLE IF NOT EXISTS falle 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  fall_nummer TEXT, 
                  datum DATE, 
                  beschreibung TEXT, 
                  medien_pfade TEXT)''')
    conn.commit()
    conn.close()

init_db()

# --- UI SETTINGS ---
st.set_page_config(page_title="Fall-Archiv Pro", layout="wide")

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

# --- NAVIGATION ---
mode = st.sidebar.radio("Navigation", ["Übersicht", "Neuanlage", "Daten-Backup"])

# --- FUNKTION: DATEIEN SPEICHERN ---
def save_uploaded_files(files):
    filenames = []
    for f in files:
        f_path = os.path.join(UPLOAD_FOLDER, f.name)
        with open(f_path, "wb") as buffer:
            buffer.write(f.getbuffer())
        filenames.append(f.name)
    return ",".join(filenames)

# --- NEUANLAGE ---
if mode == "Neuanlage":
    st.header("➕ Neuen Fall anlegen")
    with st.form("form_neu", clear_on_submit=True):
        fnr = st.text_input("Fall-Nummer")
        fdat = st.date_input("Datum", datetime.date.today())
        fbes = st.text_area("Beschreibung")
        files = st.file_uploader("Bilder & Videos hochladen", accept_multiple_files=True, type=["jpg","png","mp4","mov"])
        
        if st.form_submit_button("Speichern"):
            if fnr and fbes:
                m_pfade = save_uploaded_files(files) if files else ""
                conn = get_db_connection()
                c = conn.cursor()
                c.execute("INSERT INTO falle (fall_nummer, datum, beschreibung, medien_pfade) VALUES (?, ?, ?, ?)", 
                          (fnr, fdat, fbes, m_pfade))
                conn.commit()
                conn.close()
                st.success(f"Fall {fnr} wurde angelegt!")
            else:
                st.warning("Bitte Pflichtfelder ausfüllen.")

# --- ÜBERSICHT (MIT EDIT & DELETE) ---
elif mode == "Übersicht":
    st.header("📂 Archivierte Fälle")
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT * FROM falle ORDER BY datum DESC", conn)
    conn.close()

    if df.empty:
        st.info("Keine Fälle vorhanden.")
    else:
        for index, row in df.iterrows():
            with st.expander(f"📌 Fall: {row['fall_nummer']} ({row['datum']})"):
                # Anzeige Modus
                if f"edit_{row['id']}" not in st.session_state:
                    st.write(f"**Beschreibung:** {row['beschreibung']}")
                    
                    # Medien anzeigen
                    if row['medien_pfade']:
                        st.write("---")
                        st.write("**Anhänge:**")
                        cols = st.columns(3)
                        files = row['medien_pfade'].split(",")
                        for i, f_name in enumerate(files):
                            p = os.path.join(UPLOAD_FOLDER, f_name)
                            if os.path.exists(p):
                                with cols[i % 3]:
                                    if f_name.lower().endswith(('.mp4', '.mov')):
                                        st.video(p)
                                    else:
                                        st.image(p, caption=f_name)

                    # Buttons für Aktionen
                    c1, c2, _ = st.columns([1,1,4])
                    if c1.button("Bearbeiten", key=f"btn_ed_{row['id']}"):
                        st.session_state[f"edit_{row['id']}"] = True
                        st.rerun()
                    
                    if c2.button("Löschen", key=f"btn_del_{row['id']}", type="primary"):
                        conn = get_db_connection()
                        c = conn.cursor()
                        c.execute("DELETE FROM falle WHERE id = ?", (row['id'],))
                        conn.commit()
                        conn.close()
                        st.success("Gelöscht!")
                        st.rerun()

                # Bearbeiten Modus
                else:
                    st.write("### Fall bearbeiten")
                    new_fnr = st.text_input("Fall-Nummer", row['fall_nummer'], key=f"inf_{row['id']}")
                    new_bes = st.text_area("Beschreibung", row['beschreibung'], key=f"ibes_{row['id']}")
                    
                    bc1, bc2 = st.columns(2)
                    if bc1.button("Änderungen speichern", key=f"save_{row['id']}"):
                        conn = get_db_connection()
                        c = conn.cursor()
                        c.execute("UPDATE falle SET fall_nummer = ?, beschreibung = ? WHERE id = ?", 
                                  (new_fnr, new_bes, row['id']))
                        conn.commit()
                        conn.close()
                        del st.session_state[f"edit_{row['id']}"]
                        st.rerun()
                    
                    if bc2.button("Abbrechen", key=f"can_{row['id']}"):
                        del st.session_state[f"edit_{row['id']}"]
                        st.rerun()

# --- BACKUP ---
elif mode == "Daten-Backup":
    st.header("💾 Datensicherung")
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT * FROM falle", conn)
    conn.close()
    
    csv = df.to_csv(index=False).encode('utf-8')
    st.download_button("Als CSV (Excel) exportieren", data=csv, file_name="fall_archiv_backup.csv", mime="text/csv")
    st.write("Nutze diesen Button regelmäßig, um deine Daten lokal zu sichern.")
