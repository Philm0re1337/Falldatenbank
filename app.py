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
    
    # Spalten-Check für Erweiterungen
    c.execute("PRAGMA table_info(falle)")
    columns = [column[1] for column in c.fetchall()]
    
    # medien_pfade hinzufügen falls fehlt
    if 'medien_pfade' not in columns:
        c.execute("ALTER TABLE falle ADD COLUMN medien_pfade TEXT")
    
    # status hinzufügen falls fehlt (Default: 'Offen')
    if 'status' not in columns:
        c.execute("ALTER TABLE falle ADD COLUMN status TEXT DEFAULT 'Offen'")
        
    # zahlbetrag hinzufügen falls fehlt
    if 'zahlbetrag' not in columns:
        c.execute("ALTER TABLE falle ADD COLUMN zahlbetrag REAL DEFAULT 0.0")
            
    conn.commit()
    conn.close()

init_db()

# --- UI SETTINGS ---
st.set_page_config(page_title="Fall-Archiv Pro", layout="wide")

# --- AUTHENTIFIZIERUNG ---
if "auth" not in st.session_state:
    st.title("🔒 Team Login")
    pwd = st.text_input("Passwort eingeben und Enter drücken", type="password")
    
    if pwd: 
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
                c.execute("INSERT INTO falle (fall_nummer, datum, beschreibung, medien_pfade, status) VALUES (?, ?, ?, ?, ?)", 
                          (fnr, fdat, fbes, m_pfade, "Offen"))
                conn.commit()
                conn.close()
                st.success(f"Fall {fnr} wurde angelegt!")
            else:
                st.warning("Bitte Pflichtfelder (Nummer & Beschreibung) ausfüllen.")

# --- ÜBERSICHT ---
elif mode == "Übersicht":
    st.header("📂 Archivierte Fälle")
    
    c_s1, c_s2 = st.columns([2, 1])
    with c_s1:
        search_query = st.text_input("🔍 Suche nach Fallnummer oder Stichworten", "").strip()
    with c_s2:
        filter_status = st.selectbox("Status filtern", ["Alle", "Offen", "Erledigt"])
    
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT * FROM falle ORDER BY datum DESC", conn)
    conn.close()

    if df.empty:
        st.info("Keine Fälle im Archiv vorhanden.")
    else:
        if search_query:
            df = df[df['fall_nummer'].str.contains(search_query, case=False, na=False) | 
                    df['beschreibung'].str.contains(search_query, case=False, na=False)]
        
        if filter_status != "Alle":
            df = df[df['status'] == filter_status]

        if df.empty:
            st.warning("Keine Treffer für deine Auswahl.")
        
        for index, row in df.iterrows():
            status_color = "🟢" if row['status'] == "Erledigt" else "🟡"
            
            with st.container(border=True):
                col_thumb, col_info, col_status = st.columns([1, 3, 1])
                
                with col_thumb:
                    first_img = None
                    if row['medien_pfade']:
                        all_files = row['medien_pfade'].split(",")
                        for f_name in all_files:
                            if f_name.lower().endswith(('.jpg', '.jpeg', '.png')):
                                p = os.path.join(UPLOAD_FOLDER, f_name)
                                if os.path.exists(p):
                                    first_img = p
                                    break
                    if first_img:
                        st.image(first_img, use_container_width=True)
                    else:
                        st.caption("Kein Bild")

                with col_info:
                    st.subheader(f"{status_color} Fall: {row['fall_nummer']}")
                    st.write(f"📅 **Datum:** {row['datum']}")
                    short_desc = row['beschreibung'][:150] + "..." if len(row['beschreibung']) > 150 else row['beschreibung']
                    st.write(f"📝 {short_desc}")
                    if row['status'] == "Erledigt":
                        st.write(f"💰 **Zahlbetrag:** {row['zahlbetrag']:.2f} €")

                with col_status:
                    st.write("**Status ändern:**")
                    new_status = st.selectbox("Status", ["Offen", "Erledigt"], 
                                             index=0 if row['status'] == "Offen" else 1, 
                                             key=f"stat_sel_{row['id']}")
                    
                    if new_status != row['status']:
                        conn = get_db_connection()
                        c = conn.cursor()
                        c.execute("UPDATE falle SET status = ? WHERE id = ?", (new_status, row['id']))
                        conn.commit()
                        conn.close()
                        st.rerun()

                with st.expander("Details, Medien & Bearbeitung"):
                    edit_key = f"edit_{row['id']}"
                    delete_confirm_key = f"delete_confirm_{row['id']}"

                    if edit_key not in st.session_state and delete_confirm_key not in st.session_state:
                        st.write(f"**Vollständige Beschreibung:**\n{row['beschreibung']}")
                        
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
                        
                        st.write("---")
                        c1, c2, _ = st.columns([1, 1, 4])
                        if c1.button("Bearbeiten", key=f"btn_ed_{row['id']}"):
                            st.session_state[edit_key] = True
                            st.rerun()
                        
                        if c2.button("Löschen", key=f"btn_del_{row['id']}", type="primary"):
                            st.session_state[delete_confirm_key] = True
                            st.rerun()
                    
                    elif delete_confirm_key in st.session_state:
                        st.warning(f"⚠️ Fall **{row['fall_nummer']}** wirklich löschen?")
                        dc1, dc2, _ = st.columns([1, 1, 4])
                        if dc1.button("Dauerhaft löschen", key=f"confirm_del_{row['id']}", type="primary"):
                            conn = get_db_connection()
                            c = conn.cursor()
                            c.execute("DELETE FROM falle WHERE id = ?", (row['id'],))
                            conn.commit()
                            conn.close()
                            del st.session_state[delete_confirm_key]
                            st.rerun()
                        if dc2.button("Abbrechen", key=f"cancel_del_{row['id']}"):
                            del st.session_state[delete_confirm_key]
                            st.rerun()

                    elif edit_key in st.session_state:
                        st.write("### 📝 Fall bearbeiten")
                        with st.form(key=f"edit_form_{row['id']}"):
                            e_fnr = st.text_input("Fall-Nummer", row['fall_nummer'])
                            e_dat = st.date_input("Datum", datetime.datetime.strptime(row['datum'], '%Y-%m-%d').date() if isinstance(row['datum'], str) else row['datum'])
                            e_bes = st.text_area("Beschreibung", row['beschreibung'])
                            e_sta = st.selectbox("Status", ["Offen", "Erledigt"], index=0 if row['status'] == "Offen" else 1)
                            e_betrag = st.number_input("Zahlbetrag (€)", value=float(row['zahlbetrag']) if row['zahlbetrag'] else 0.0, step=0.01)
                            
                            bc1, bc2, _ = st.columns([1, 1, 2])
                            if bc1.form_submit_button("Speichern"):
                                conn = get_db_connection()
                                c = conn.cursor()
                                c.execute("UPDATE falle SET fall_nummer = ?, datum = ?, beschreibung = ?, status = ?, zahlbetrag = ? WHERE id = ?", 
                                          (e_fnr, e_dat, e_bes, e_sta, e_betrag, row['id']))
                                conn.commit()
                                conn.close()
                                del st.session_state[edit_key]
                                st.rerun()
                            if bc2.form_submit_button("Abbrechen"):
                                del st.session_state[edit_key]
                                st.rerun()
