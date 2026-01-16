import streamlit as st
import pandas as pd
import sqlite3
import datetime
import os
import re

# --- KONFIGURATION ---
DB_NAME = "fall_archiv_lokal.db"
TEAM_PASSWORD = "2180"
UPLOAD_FOLDER = "uploads"

# Verzeichnis für Uploads erstellen, falls nicht vorhanden
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

# --- DATENBANK FUNKTIONEN ---
def get_db_connection():
    db_path = os.path.join(os.getcwd(), DB_NAME)
    return sqlite3.connect(db_path, check_same_thread=False)

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    # Basis-Tabelle erstellen
    c.execute('''CREATE TABLE IF NOT EXISTS falle 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  fall_nummer TEXT, 
                  datum DATE, 
                  beschreibung TEXT)''')
    
    # Spalten-Check für medien_pfade
    c.execute("PRAGMA table_info(falle)")
    columns = [column[1] for column in c.fetchall()]
    if 'medien_pfade' not in columns:
        try:
            c.execute("ALTER TABLE falle ADD COLUMN medien_pfade TEXT")
            conn.commit()
        except Exception as e:
            st.error(f"Fehler bei DB-Update: {e}")
            
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
mode = st.sidebar.radio("Navigation", ["Übersicht", "Neuanlage"])

# --- FUNKTION: DATEIEN SPEICHERN ---
def save_uploaded_files(files):
    filenames = []
    for f in files:
        # Dateiname säubern (Leerzeichen entfernen)
        clean_name = re.sub(r'[^a-zA-Z0-9.-]', '_', f.name)
        f_path = os.path.join(UPLOAD_FOLDER, clean_name)
        with open(f_path, "wb") as buffer:
            buffer.write(f.getbuffer())
        filenames.append(clean_name)
    return ",".join(filenames)

# --- NEUANLAGE ---
if mode == "Neuanlage":
    st.header("➕ Neuen Fall anlegen")
    with st.form("form_neu", clear_on_submit=True):
        fnr = st.text_input("Fall-Nummer")
        fdat = st.date_input("Datum", datetime.date.today())
        fbes = st.text_area("Beschreibung")
        files = st.file_uploader("Bilder & Videos hochladen", accept_multiple_files=True, type=["jpg","png","jpeg","mp4","mov"])
        
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
                st.warning("Bitte Pflichtfelder (Nummer & Beschreibung) ausfüllen.")

# --- ÜBERSICHT ---
elif mode == "Übersicht":
    st.header("📂 Archivierte Fälle")
    
    # Suchfunktion
    search_query = st.text_input("🔍 Suche nach Fallnummer oder Stichworten", "").strip()
    
    conn = get_db_connection()
    # Daten laden
    df = pd.read_sql_query("SELECT * FROM falle ORDER BY datum DESC", conn)
    conn.close()

    if df.empty:
        st.info("Keine Fälle im Archiv vorhanden.")
    else:
        # Filter anwenden, falls Suche aktiv
        if search_query:
            df = df[
                df['fall_nummer'].str.contains(search_query, case=False, na=False) | 
                df['beschreibung'].str.contains(search_query, case=False, na=False)
            ]

        if df.empty:
            st.warning("Keine Treffer für deine Suche.")
        
        for index, row in df.iterrows():
            # Container für jeden Fall
            with st.container(border=True):
                col_thumb, col_info = st.columns([1, 4])
                
                # --- SPALTE 1: VORSCHAU ---
                with col_thumb:
                    first_img = None
                    if row['medien_pfade']:
                        all_files = row['medien_pfade'].split(",")
                        # Suche das erste Bild in den Anhängen
                        for f_name in all_files:
                            if f_name.lower().endswith(('.jpg', '.jpeg', '.png')):
                                p = os.path.join(UPLOAD_FOLDER, f_name)
                                if os.path.exists(p):
                                    first_img = p
                                    break
                    
                    if first_img:
                        st.image(first_img, use_container_width=True)
                    else:
                        # Platzhalter, falls kein Bild vorhanden ist
                        st.info("Kein Bild")

                # --- SPALTE 2: INFO ---
                with col_info:
                    st.subheader(f"Fall: {row['fall_nummer']}")
                    st.write(f"📅 **Datum:** {row['datum']}")
                    st.write(f"📝 {row['beschreibung'][:200]}..." if len(row['beschreibung']) > 200 else f"📝 {row['beschreibung']}")
                    
                    # Details-Expander
                    with st.expander("Details & Verwaltung"):
                        if f"edit_{row['id']}" not in st.session_state:
                            st.write(f"**Vollständige Beschreibung:**\n{row['beschreibung']}")
                            
                            # Alle Medien anzeigen
                            if row['medien_pfade']:
                                st.write("---")
                                st.write("**Anhänge:**")
                                m_cols = st.columns(3)
                                files = row['medien_pfade'].split(",")
                                for i, f_name in enumerate(files):
                                    p = os.path.join(UPLOAD_FOLDER, f_name)
                                    if os.path.exists(p):
                                        with m_cols[i % 3]:
                                            if f_name.lower().endswith(('.mp4', '.mov')):
                                                st.video(p)
                                            else:
                                                st.image(p, caption=f_name)
                            
                            # Aktions-Buttons
                            st.write("---")
                            c1, c2, _ = st.columns([1, 1, 4])
                            if c1.button("Fall bearbeiten", key=f"btn_ed_{row['id']}"):
                                st.session_state[f"edit_{row['id']}"] = True
                                st.rerun()
                            
                            if c2.button("Fall löschen", key=f"btn_del_{row['id']}", type="primary"):
                                conn = get_db_connection()
                                c = conn.cursor()
                                c.execute("DELETE FROM falle WHERE id = ?", (row['id'],))
                                conn.commit()
                                conn.close()
                                st.success("Fall wurde dauerhaft gelöscht!")
                                st.rerun()
                        
                        # Bearbeiten Modus
                        else:
                            st.write("### 📝 Fall bearbeiten")
                            with st.form(key=f"edit_form_{row['id']}"):
                                new_fnr = st.text_input("Fall-Nummer", row['fall_nummer'])
                                new_dat = st.date_input("Datum", datetime.datetime.strptime(row['datum'], '%Y-%m-%d').date() if isinstance(row['datum'], str) else row['datum'])
                                new_bes = st.text_area("Beschreibung", row['beschreibung'])
                                
                                bc1, bc2, _ = st.columns([1, 1, 2])
                                if bc1.form_submit_button("Änderungen speichern"):
                                    conn = get_db_connection()
                                    c = conn.cursor()
                                    c.execute("UPDATE falle SET fall_nummer = ?, datum = ?, beschreibung = ? WHERE id = ?", 
                                              (new_fnr, new_dat, new_bes, row['id']))
                                    conn.commit()
                                    conn.close()
                                    del st.session_state[f"edit_{row['id']}"]
                                    st.success("Änderungen gespeichert!")
                                    st.rerun()
                                
                                if bc2.form_submit_button("Abbrechen"):
                                    del st.session_state[f"edit_{row['id']}"]
                                    st.rerun()
                                
