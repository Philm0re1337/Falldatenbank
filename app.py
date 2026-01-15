import streamlit as st
import pandas as pd
import sqlite3
import datetime
import os

# --- KONFIGURATION ---
DB_NAME = "fall_archiv_lokal.db"
TEAM_PASSWORD = "2180"

# --- DATENBANK FUNKTIONEN ---
def get_db_connection():
    conn = sqlite3.connect(DB_NAME, check_same_thread=False)
    return conn

def init_db():
    conn = get_db_connection()
    c = conn.cursor()
    # Tabelle für die Fälle
    c.execute('''CREATE TABLE IF NOT EXISTS falle 
                 (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                  fall_nummer TEXT, 
                  datum DATE, 
                  beschreibung TEXT, 
                  erledigt INTEGER DEFAULT 0)''')
    conn.commit()
    conn.close()

# Datenbank initialisieren
init_db()

# --- UI KONFIGURATION ---
st.set_page_config(page_title="Lokales Fall-Archiv", layout="wide")

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
st.sidebar.title("Navigation")
mode = st.sidebar.radio("Gehe zu:", ["Übersicht", "Neuanlage"])

# --- NEUANLAGE ---
if mode == "Neuanlage":
    st.header("➕ Neuen Fall anlegen")
    
    with st.form("neuer_fall", clear_on_submit=True):
        fnr = st.text_input("Fall-Nummer / Kennung")
        fdat = st.date_input("Datum", datetime.date.today())
        fbes = st.text_area("Fallbeschreibung")
        
        submit = st.form_submit_button("Speichern")
        
        if submit:
            if fnr and fbes:
                conn = get_db_connection()
                c = conn.cursor()
                c.execute("INSERT INTO falle (fall_nummer, datum, beschreibung) VALUES (?, ?, ?)", 
                          (fnr, fdat, fbes))
                conn.commit()
                conn.close()
                st.success(f"Fall {fnr} wurde lokal gespeichert!")
            else:
                st.warning("Bitte füllen Sie alle Felder aus.")

# --- ÜBERSICHT ---
elif mode == "Übersicht":
    st.header("📂 Archivierte Fälle")
    
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT * FROM falle ORDER BY datum DESC", conn)
    conn.close()
    
    if df.empty:
        st.info("Noch keine Fälle im Archiv vorhanden.")
    else:
        # Suche/Filter
        search = st.text_input("🔍 Fall suchen (Nummer oder Beschreibung)")
        if search:
            df = df[df['fall_nummer'].str.contains(search, case=False) | 
                    df['beschreibung'].str.contains(search, case=False)]

        # Anzeige der Fälle in Kartenform
        for _, row in df.iterrows():
            with st.container(border=True):
                st.subheader(f"Fall: {row['fall_nummer']}")
                st.write(f"📅 **Datum:** {row['datum']}")
                st.write(f"📝 **Beschreibung:** {row['beschreibung']}")
                
                # Button zum Löschen (Optional)
                if st.button(f"Löschen #{row['id']}", key=f"del_{row['id']}"):
                    conn = get_db_connection()
                    c = conn.cursor()
                    c.execute("DELETE FROM falle WHERE id = ?", (row['id'],))
                    conn.commit()
                    conn.close()
                    st.rerun()
