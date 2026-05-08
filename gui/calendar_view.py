import streamlit as st
import pandas as pd
from core.memory import CesareMemory
from core.helpers import save_config
import os

def calendar_page(config):
    st.title("⏳ Chronos - Pianificazione Missioni")
    
    memory = CesareMemory(config['paths'])
    
    # --- Master Switch ---
    is_active = config.get('scheduler', {}).get('active', True)
    col_sw, _ = st.columns([2, 8])
    if col_sw.button("⏸️ PAUSE" if is_active else "▶️ PLAY"):
        config['scheduler']['active'] = not is_active
        save_config(os.path.dirname(config['paths']['bible']), config)
        st.rerun()
        
    st.divider()

    # --- Task Creator ---
    with st.expander("➕ Nuova Missione Programmata", expanded=False):
        with st.form("new_task"):
            title = st.text_input("Titolo Missione")
            prompt = st.text_area("Mini-Prompt (Cosa deve fare?)")
            t_time = st.text_input("Data/Ora Trigger (YYYY-MM-DD HH:MM)", value="2024-01-01 12:00")
            folder = st.text_input("Cartella Context (relativa a workspace/)")
            
            if st.form_submit_button("Programma"):
                res = memory.manage_calendar_db("create", data={
                    "title": title,
                    "description": prompt,
                    "trigger_time": t_time,
                    "target_folder": folder
                })
                st.success(res)
                st.rerun()

    # --- Task Monitor ---
    st.subheader("📋 Missioni Attive")
    conn = memory._get_conn('calendar_db')
    df = pd.read_sql_query("SELECT id, title, trigger_time, target_folder, status, last_run_log FROM calendar_tasks ORDER BY trigger_time DESC", conn)
    
    if not df.empty:
        edited_df = st.data_editor(df, num_rows="dynamic", width="stretch", key="task_editor")
        
        if len(edited_df) < len(df):
            deleted_ids = set(df['id']) - set(edited_df['id'])
            for d_id in deleted_ids:
                memory.manage_calendar_db("delete", task_id=int(d_id))
            st.rerun()
    else:
        st.info("Nessuna missione programmata.")

    # --- Real-time Logs ---
    st.divider()
    st.subheader("📜 Cronologia Esecuzioni")
    history_path = os.path.join(os.path.dirname(config['paths']['calendar_db']), "task_history.md")
    if os.path.exists(history_path):
        with open(history_path, "r", encoding="utf-8") as f:
            st.markdown(f.read()[-2000:])