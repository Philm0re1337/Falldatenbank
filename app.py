import streamlit as st
import pandas as pd
import sqlite3
import os
from datetime import datetime

# --- SETUP ---
UPLOAD_DIR = "fall_medien"
DB_NAME = "fall_archiv_v2.db"

if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

def get_db_connection():
    return sqlite3.connect(DB_NAME, check_same_thread=False)

conn = get_db_connection()
c = conn.cursor()

# Tabellen erstellen
c.execute('''CREATE TABLE IF NOT EXISTS falle 
             (id INTEGER PRIMARY KEY AUTOINCREMENT, 
              fall_nummer TEXT, 
              datum DATE, 
              beschreibung TEXT, 
              hauptbild_pfad TEXT,
              erledigt INTEGER DEFAULT 0)''')

c.execute('''CREATE TABLE IF NOT EXISTS media 
             (id INTEGER PRIMARY KEY AUTOINCREMENT, 
              fall_id INTEGER, 
              file_path TEXT,
              file_type TEXT,
              FOREIGN KEY(fall_id) REFERENCES falle(id))''')
conn.commit()

# --- HELFERFUNKTION ---
def save_files(files, fall_nr, suffix=""):
    paths = []
    for f in files:
        path = os.path.join(UPLOAD_DIR, f"{fall_nr}_{suffix}_{f.name}")
        with open(path, "wb") as out:
            out.write(f.getbuffer())
        paths.append(path)
    return paths

# --- UI ---
st.set_page_config(page_title="Fall-Datenbank Pro", layout="wide")
st.sidebar.title("📁 Navigation")
choice = st.sidebar.radio("Menü", ["Übersicht & Suche", "Neuanlage", "Bearbeiten"])

# --- NEUANLAGE ---
if choice == "Neuanlage":
    st.header("➕ Neuen Fall erfassen")
    with st.form("neu_form", clear_on_submit=True):
        f_nr = st.text_input("Fall-Nummer")
        f_date = st.date_input("Datum", datetime.now())
        f_desc = st.text_area("Fall-Beschreibung")
        
        st.write("---")
        st.subheader("Medien-Upload")
        u_bilder = st.file_uploader("Bilder hochladen (Mehrfachauswahl)", type=["jpg", "jpeg", "png"], accept_multiple_files=True)
        u_videos = st.file_uploader("Videos hochladen (Mehrfachauswahl)", type=["mp4", "mov"], accept_multiple_files=True)
        
        if st.form_submit_button("Fall speichern"):
            if f_nr and u_bilder:
                # Das erste Bild als Hauptbild/Vorschau nehmen
                b_paths = save_files(u_bilder, f_nr, "IMG")
                h_path = b_paths[0]
                
                c.execute("INSERT INTO falle (fall_nummer, datum, beschreibung, hauptbild_pfad, erledigt) VALUES (?,?,?,?,?)",
                          (f_nr, f_date, f_desc, h_path, 0))
                f_id = c.lastrowid
                
                # Alle Bilder in die Mediatabelle (auch das Hauptbild für die Galerie)
                for p in b_paths:
                    c.execute("INSERT INTO media (fall_id, file_path, file_type) VALUES (?,?,?)", (f_id, p, "image"))
                
                # Videos speichern
                if u_videos:
                    v_paths = save_files(u_videos, f_nr, "VID")
                    for p in v_paths:
                        c.execute("INSERT INTO media (fall_id, file_path, file_type) VALUES (?,?,?)", (f_id, p, "video"))
                
                conn.commit()
                st.success(f"Fall {f_nr} erfolgreich angelegt!")
            else:
                st.error("Bitte mindestens die Fallnummer und ein Bild hochladen.")

# --- ÜBERSICHT & SUCHE ---
elif choice == "Übersicht & Suche":
    st.header("📂 Fall-Archiv")
    
    # Suchfilter oben
    s_col1, s_col2, s_col3 = st.columns([2, 1, 1])
    with s_col1:
        search_nr = st.text_input("Suche nach Fallnummer")
    with s_col2:
        search_date = st.date_input("Filter nach Datum", value=None)
    with s_col3:
        status_filter = st.selectbox("Status", ["Alle", "Offen", "Erledigt"])

    # Query zusammenbauen
    query = "SELECT * FROM falle WHERE 1=1"
    params = []
    if search_nr:
        query += " AND fall_nummer LIKE ?"
        params.append(f"%{search_nr}%")
    if search_date:
        query += " AND datum = ?"
        params.append(search_date)
    if status_filter == "Offen":
        query += " AND erledigt = 0"
    elif status_filter == "Erledigt":
        query += " AND erledigt = 1"
    
    query += " ORDER BY datum DESC"
    df = pd.read_sql_query(query, conn, params=params)
    
    if not df.empty:
        for idx, row in df.iterrows():
            # Status-Badge Styling
            status_label = "✅ Erledigt" if row['erledigt'] == 1 else "⏳ Offen"
            
            with st.container(border=True):
                col1, col2 = st.columns([1, 4])
                with col1:
                    st.image(row['hauptbild_pfad'], caption=f"Vorschau: {row['fall_nummer']}")
                with col2:
                    st.subheader(f"Fall: {row['fall_nummer']} ({status_label})")
                    st.write(f"📅 **Datum:** {row['datum']}")
                    with st.expander("Details, Bilder & Videos"):
                        st.write(row['beschreibung'])
                        st.divider()
                        # Medien anzeigen
                        m_df = pd.read_sql_query(f"SELECT * FROM media WHERE fall_id = {row['id']}", conn)
                        img_cols = st.columns(4)
                        for m_idx, m_row in m_df.iterrows():
                            with img_cols[m_idx % 4]:
                                if m_row['file_type'] == "video":
                                    st.video(m_row['file_path'])
                                else:
                                    st.image(m_row['file_path'])
    else:
        st.info("Keine passenden Fälle gefunden.")

# --- BEARBEITEN ---
elif choice == "Bearbeiten":
    st.header("📝 Fall bearbeiten & abschließen")
    df = pd.read_sql_query("SELECT * FROM falle", conn)
    
    if not df.empty:
        auswahl = st.selectbox("Wähle einen Fall", df['fall_nummer'].tolist())
        f_data = df[df['fall_nummer'] == auswahl].iloc[0]
        
        with st.form("edit_form"):
            u_nr = st.text_input("Fall-Nummer", value=f_data['fall_nummer'])
            u_date = st.date_input("Datum", value=datetime.strptime(str(f_data['datum']), '%Y-%m-%d'))
            u_desc = st.text_area("Beschreibung", value=f_data['beschreibung'])
            u_done = st.checkbox("Als erledigt markieren", value=bool(f_data['erledigt']))
            
            st.write("---")
            add_imgs = st.file_uploader("Weitere Bilder hinzufügen", type=["jpg", "png"], accept_multiple_files=True)
            add_vids = st.file_uploader("Weitere Videos hinzufügen", type=["mp4"], accept_multiple_files=True)
            
            if st.form_submit_button("Änderungen speichern"):
                c.execute("UPDATE falle SET fall_nummer=?, datum=?, beschreibung=?, erledigt=? WHERE id=?", 
                          (u_nr, u_date, u_desc, 1 if u_done else 0, int(f_data['id'])))
                
                # Neue Medien hinzufügen
                if add_imgs:
                    for p in save_files(add_imgs, u_nr, "ADD_IMG"):
                        c.execute("INSERT INTO media (fall_id, file_path, file_type) VALUES (?,?,?)", (int(f_data['id']), p, "image"))
                if add_vids:
                    for p in save_files(add_vids, u_nr, "ADD_VID"):
                        c.execute("INSERT INTO media (fall_id, file_path, file_type) VALUES (?,?,?)", (int(f_data['id']), p, "video"))
                
                conn.commit()
                st.success("Aktualisiert!")
                st.rerun()