import sys
import os
import asyncio

# Fix per Windows: forziamo l'uso di ProactorEventLoop per supportare i sottoprocessi (Playwright, Shell, ecc.)
# Necessario per evitare il NotImplementedError in asyncio.
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# Compatibilità PyInstaller: aggiunge la root del progetto al path
# In modalità frozen (eseguibile), _MEIPASS è la cartella temporanea
# dove PyInstaller estrae i file. In modalità normale è la cartella del file.
if getattr(sys, 'frozen', False):
    _ROOT = sys._MEIPASS
else:
    _ROOT = os.path.dirname(os.path.abspath(__file__))

# Aggiunge la root al sys.path se non già presente
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import hashlib
import yaml
import logging
import threading
from pathlib import Path
import streamlit as st
import streamlit.web.cli as stcli

# Import aggiornati secondo la mappa di ristrutturazione
from core.helpers import init_cesare_workspace, get_validated_config, save_config, ensure_config_paths_exist
from core.security import check_override, audit_log
from core.graph import get_cesare_app
from scheduler.scheduler_engine import start_scheduler
from gui.calendar_view import calendar_page
from gui.memory_repository import MemoryRepository
from gui.models import MemoryEntry, MemoryTier
from gui.ui import render_memory_card, render_detail_panel
from gui.styles import get_custom_css

def run_cesare_gui():
    """
    Contiene tutta la logica dell'interfaccia Streamlit di CESARE.
    Questa funzione viene eseguita all'interno del runtime di Streamlit.
    """
    st.set_page_config(page_title="CESARE GUI", layout="wide", initial_sidebar_state="expanded")

    # --- DETERMINAZIONE WORKDIR ---
    if "workdir" not in st.session_state:
        if getattr(sys, 'frozen', False):
            st.session_state.workdir = os.path.dirname(sys.executable)
        else:
            st.session_state.workdir = os.getcwd()

    # --- INIZIALIZZAZIONE WORKSPACE ---
    # Assicura la struttura base prima di validare il config
    init_cesare_workspace(st.session_state.workdir)

    config = get_validated_config(st.session_state.workdir)

    # --- FORZATURA LOG NEL WORKSPACE ---
    # Come richiesto, i log devono risiedere all'interno del workspace
    ws_path_str = config.get('paths', {}).get('workspace', 'workspace')
    ws_path = Path(ws_path_str)
    if not ws_path.is_absolute():
        ws_path = Path(st.session_state.workdir) / ws_path
    
    logs_dir = ws_path / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    log_file_path = str(logs_dir / "audit.log")
    config['paths']['logs'] = log_file_path

    # --- ASSICURA CHE TUTTI I PERCORSI ESISTANO ---
    # Questo deve avvenire dopo aver caricato la configurazione
    # e dopo aver risolto il percorso dei log, prima di qualsiasi operazione
    # che dipenda da questi percorsi (es. inizializzazione memoria).
    ensure_config_paths_exist(config.get('paths', {}), Path(st.session_state.workdir))


    # --- INIZIALIZZAZIONE LOGGING SU FILE ---
    cesare_logger = logging.getLogger("CESARE")
    cesare_logger.setLevel(logging.INFO)
    # Evitiamo di aggiungere più volte l'handler se la pagina Streamlit viene ricaricata
    if not any(isinstance(h, logging.FileHandler) for h in cesare_logger.handlers):
        fh = logging.FileHandler(log_file_path, encoding='utf-8')
        fh.setFormatter(logging.Formatter('%(asctime)s | %(levelname)s | %(name)s | %(message)s'))
        cesare_logger.addHandler(fh)

    # --- STATO DELLA SESSIONE ---
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False

    # --- AUTENTICAZIONE ---
    if not st.session_state.authenticated:
        st.title("🛡️ Accesso Protetto - CESARE")
        st.write("Inserisci il codice segreto per sbloccare l'interfaccia.")
        password = st.text_input("Codice Segreto:", type="password")
        if st.button("Accedi"):
            target_hash = "309768a5e701223f4259fdebba24db009f70c73c9c5149deade9f36c188c7871"
            if hashlib.sha256(password.encode()).hexdigest() == target_hash:
                st.session_state.authenticated = True
                audit_log("GUI_ACCESS", "Accesso autorizzato.")
                st.rerun()
            else:
                st.error("Codice non valido.")
        st.stop()

    # --- LOGICA APPLICATIVA ---
    @st.cache_resource
    def load_agent(conf, debug_enabled=False):
        # Legge la modalità corrente dal config (singolo o team)
        team_mode = conf.get('team', {}).get('enabled', False)
        return get_cesare_app(conf, team_mode=team_mode, debug_enabled=debug_enabled)

    # Controlla se il debug è abilitato nella sessione
    debug_enabled = st.session_state.get('debug_enabled', False)
    
    # Forza la ricreazione dell'agente se lo stato del debug cambia
    if 'last_debug_state' not in st.session_state:
        st.session_state.last_debug_state = debug_enabled
    
    if st.session_state.last_debug_state != debug_enabled:
        st.session_state.last_debug_state = debug_enabled
        st.cache_resource.clear()
    
    cesare = load_agent(config, debug_enabled=debug_enabled)

    # --- SWITCH MODALITÀ (SINGOLO / TEAM) ---
    team_mode = config.get('team', {}).get('enabled', False)
    col_tg1, col_tg2 = st.columns([3, 7])
    with col_tg1:
        new_mode = st.toggle(
            "🧠 Modalità Team" if team_mode else "🤖 Modalità Singolo",
            value=team_mode,
            help="Attiva il sistema multi-agente"
        )
        if new_mode != team_mode:
            config.setdefault('team', {})['enabled'] = new_mode
            save_config(st.session_state.workdir, config)
            st.cache_resource.clear()
            st.rerun()

    # --- SIDEBAR ---
    st.sidebar.title("🛡️ CESARE CONTROL")
    
    # Debug controls nella sidebar
    st.sidebar.markdown("---")
    st.sidebar.subheader("🐛 Debug Options")
    
    debug_enabled = st.session_state.get('debug_enabled', False)
    
    if not debug_enabled:
        if st.sidebar.button("🐛 Enable Debug", use_container_width=True):
            st.session_state.debug_enabled = True
            st.cache_resource.clear()
            st.success("Debug logging abilitato! Ricarica la pagina per applicare.")
            st.rerun()
    else:
        st.sidebar.success("✅ Debug Enabled")
        
        if st.sidebar.button("🗑️ Clear Debug Log", use_container_width=True):
            # Pulisce i messaggi di debug se disponibili
            if hasattr(cesare, 'debug_logger'):
                cesare.debug_logger.clear()
            st.success("Debug log pulito")
        
        # Mostra conteggio messaggi
        if hasattr(cesare, 'debug_logger'):
            msg_count = len(cesare.debug_logger.get_messages())
            st.sidebar.text(f"📋 Messaggi: {msg_count}")
    
    st.sidebar.markdown("---")
    
    page = st.sidebar.radio("Navigazione", [
        "Dashboard",
        "Chat",
        "Chronos (Calendario)",
        "🧠 Memoria",           # ← NUOVA PAGINA
        "Editor Bibbia",
        "Configurazione",
        "Workspace Explorer",
        "🐛 Debug Log"          # ← NUOVA PAGINA DEBUG
    ])

    if st.sidebar.button("🔄 Ricarica Agente"):
        st.cache_resource.clear()
        st.rerun()

    # ===================================================================
    # PAGINE
    # ===================================================================

    if page == "Dashboard":
        st.title("📊 Stato di CESARE")
        st.write(f"**Cartella di lavoro:** `{st.session_state.workdir}`")
        col1, col2 = st.columns(2)
        with col1:
            st.info(f"Status Agente: 🟢 Online | Modello: `{config['agent']['model']}`")
            if st.button("🧹 Pulisci Log Audit"):
                with open(config['paths']['logs'], "w") as f:
                    f.write("")
                st.rerun()
        with col2:
            st.write("**Audit Log Recenti:**")
            log_path = Path(config['paths']['logs'])
            if log_path.exists():
                with open(log_path, "r") as f:
                    st.code(f.read()[-1000:])

        st.divider()
        st.subheader("🔍 Stato Sistema")

        col_a, col_b, col_c = st.columns(3)

        with col_a:
            st.metric(label="Modalità", value="🧠 Team" if team_mode else "🤖 Singolo")

        with col_b:
            try:
                from memory import CesareMemory
                mem = CesareMemory(config['paths'])
                pending = mem.get_due_tasks()
                st.metric(label="Task Chronos in coda", value=len(pending))
            except Exception:
                st.metric(label="Task Chronos in coda", value="N/D")

        with col_c:
            st.metric(
                label="Modello principale",
                value=config.get('agent', {}).get('model', 'N/D')
            )

        if team_mode:
            st.markdown("**Configurazione agenti:**")
            agents_cfg = config.get('team', {}).get('agents', {})
            agent_data = [
                {
                    "Agente": name,
                    "Modello": cfg.get('model', 'default'),
                    "Temperatura": cfg.get('temperature', 0.1)
                }
                for name, cfg in agents_cfg.items()
            ]
            if agent_data:
                import pandas as pd
                st.dataframe(
                    pd.DataFrame(agent_data),
                    use_container_width=True,
                    hide_index=True
                )

    elif page == "Chat":
        st.title("🤖 Chat con CESARE")

        if "messages" not in st.session_state:
            st.session_state.messages = []
        if "pending_response" not in st.session_state:
            st.session_state.pending_response = None
        if "is_processing" not in st.session_state:
            st.session_state.is_processing = False

        # Se c'è una risposta pendente non ancora visualizzata, aggiungila ora
        if st.session_state.pending_response is not None:
            st.session_state.messages.append({
                "role": "assistant",
                "content": st.session_state.pending_response
            })
            st.session_state.pending_response = None
            st.session_state.is_processing = False

        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])

        if st.session_state.is_processing:
            st.info("⏳ CESARE sta elaborando... Torna qui per vedere la risposta.")

        if prompt := st.chat_input(
            "Cosa deve fare CESARE?",
            disabled=st.session_state.is_processing
        ):
            st.session_state.messages.append({"role": "user", "content": prompt})
            st.session_state.is_processing = True

            with st.chat_message("user"):
                st.markdown(prompt)

            override = check_override(
                prompt,
                os.getenv("CESARE_SECRET_CODE", "CESARE_2024")
            )
            team_mode = config.get('team', {}).get('enabled', False)

            with st.chat_message("assistant"):
                with st.status("CESARE sta elaborando...", expanded=True) as status:

                    if team_mode:
                        step_container = st.empty()
                        steps_log = []

                        def on_step(msg: str):
                            steps_log.append(msg)
                            step_container.markdown("\n\n".join(steps_log))

                        output = cesare.invoke({
                            "messages": st.session_state.messages,
                            "override_active": override,
                            "status_callback": on_step
                        })
                    else:
                        output = cesare.invoke({
                            "messages": st.session_state.messages,
                            "override_active": override
                        })

                    response = output["messages"][-1].content
                    status.update(label="✅ Risposta generata!", state="complete")

                st.markdown(response)

            # Salva risposta in pending prima di rerun
            # così sopravvive al cambio pagina
            st.session_state.pending_response = response
            st.rerun()

    elif page == "Chronos (Calendario)":
        calendar_page(config)

    elif page == "🧠 Memoria":
        # ---------------------------------------------------------------
        # PAGINA MEMORIA — usa i moduli già presenti nel progetto
        # ---------------------------------------------------------------
        st.title("🧠 Memoria di CESARE")
        st.markdown(get_custom_css(), unsafe_allow_html=True)

        if "selected_entry" not in st.session_state:
            st.session_state.selected_entry = None

        # Selettore Agente per la Memoria (Punto 1: Replicazione)
        team_mode = config.get('team', {}).get('enabled', False)
        available_agents = ["orchestrator"]
        if team_mode:
            available_agents += ["researcher", "programmer", "worker"]
        
        target_agent = st.selectbox(
            "Seleziona l'entità di cui esplorare la memoria:",
            available_agents,
            format_func=lambda x: x.upper()
        )

        # Ogni agente ha ora il suo path dedicato nel config
        agent_mem_paths = config.get('paths', {}).get('memory_isolated', {}).get(target_agent, config.get('paths', {}))
        repo = MemoryRepository(agent_mem_paths)

        # Se un'entry è selezionata mostra il dettaglio
        if st.session_state.selected_entry:
            render_detail_panel(st.session_state.selected_entry)
        else:
            # Barra di ricerca e filtro
            col_search, col_filter, col_refresh = st.columns([3, 1, 1])
            with col_search:
                query = st.text_input(
                    "🔍 Cerca nei ricordi di CESARE...",
                    placeholder="Es: sandbox, errori, preferenze..."
                )
            with col_filter:
                view_mode = st.selectbox("Filtra per Tier", [
                    "Tutti",
                    "Tier 1 — Temporale",
                    "Tier 2 — ROM",
                    "Tier 3 — Esperienza"
                ])
            with col_refresh:
                st.write("")  # spacer
                if st.button("🔄 Aggiorna"):
                    st.cache_data.clear()
                    st.rerun()

            # Recupero dati per tier selezionato
            if view_mode == "Tier 1 — Temporale":
                data = repo.get_tier1()
            elif view_mode == "Tier 2 — ROM":
                data = repo.get_tier2()
            elif view_mode == "Tier 3 — Esperienza":
                data = repo.get_tier3()
            else:
                data = repo.get_all()

            # Dati mock se DB vuoti
            if not data and not query:
                st.warning(
                    "⚠️ Nessun dato trovato nei database. "
                    "Visualizzazione dati di esempio (MOCK)."
                )
                data = repo.get_mock_data()

            # Filtro ricerca testuale
            if query:
                data = [
                    e for e in data
                    if query.lower() in e.content.lower()
                    or query.lower() in e.summary.lower()
                ]

            # Ordinamento per data
            data.sort(key=lambda x: x.timestamp, reverse=True)

            # Statistiche rapide
            col_s1, col_s2, col_s3 = st.columns(3)
            col_s1.metric("Tier 1 — Temporale", len([e for e in data if e.tier == MemoryTier.TIER_1]))
            col_s2.metric("Tier 2 — ROM", len([e for e in data if e.tier == MemoryTier.TIER_2]))
            col_s3.metric("Tier 3 — Esperienza", len([e for e in data if e.tier == MemoryTier.TIER_3]))

            st.divider()
            st.subheader(f"Risultati: {len(data)} voci")

            if not data:
                st.info("Nessuna memoria corrisponde ai criteri di ricerca.")
            else:
                # Visualizzazione a griglia (2 colonne)
                cols = st.columns(2)
                for idx, entry in enumerate(data):
                    with cols[idx % 2]:
                        render_memory_card(entry)

    elif page == "Editor Bibbia":
        st.title("📖 Editor bible.md")
        bible_path = config['paths']['bible']
        with open(bible_path, "r", encoding="utf-8") as f:
            bible_content = f.read()
        new_bible = st.text_area("La Legge Suprema", bible_content, height=600)
        if st.button("💾 Salva Nuova Legge"):
            with open(bible_path, "w", encoding="utf-8") as f:
                f.write(new_bible)
            audit_log("BIBLE_EDIT", "Modifica Bibbia via GUI.")
            st.success("Bibbia aggiornata.")

    elif page == "Configurazione":
        st.title("⚙️ Impostazioni config.yaml")
        new_conf = st.text_area(
            "YAML",
            yaml.dump(config, default_flow_style=False),
            height=400
        )
        if st.button("💾 Salva Configurazione"):
            save_config(st.session_state.workdir, yaml.safe_load(new_conf))
            st.success("Configurazione salvata!")

    elif page == "Workspace Explorer":
        st.title("📁 Workspace Explorer")
        ws_path = config['paths']['workspace']
        if not os.path.exists(ws_path):
            os.makedirs(ws_path)
        for file in os.listdir(ws_path):
            col_f, col_del = st.columns([8, 2])
            col_f.text(f"📄 {file}")
            if col_del.button("🗑️", key=f"del_{file}"):
                os.remove(os.path.join(ws_path, file))
                st.rerun()

    elif page == "🐛 Debug Log":
        st.title("🐛 Debug Log - Agent Communications")
        st.markdown("""
        Questa sezione mostra tutti i messaggi scambiati tra **Cesare** (l'orchestratore) 
        e gli **agenti**. Utile per il debugging e capire dove si verificano eventuali problemi.
        """)
        
        import time
        
        # Check if debug is enabled
        if not st.session_state.get('debug_enabled', False):
            st.warning("""
            ⚠️ **Debug non abilitato!**
            
            Per visualizzare i messaggi tra Cesare e gli agenti:
            1. Clicca su **🐛 Enable Debug** nella sidebar
            2. Esegui un task e torna a questa pagina per vedere i messaggi
            """)
        else:
            # Feedback sulla modalità
            team_mode = config.get('team', {}).get('enabled', False)
            if not team_mode:
                st.info("💡 Sei in **Modalità Singolo**. I log di comunicazione tra agenti sono disponibili solo in **Modalità Team**.")
            else:
                # Get debug messages from cesare
                if hasattr(cesare, 'debug_logger') and cesare.debug_logger.is_enabled():
                    debug_data = cesare.debug_logger.to_dict()
                    
                    # Mostra il percorso del log per trasparenza
                    st.caption(f"📂 Percorso log attivo: `{config['paths']['logs']}`")

                    if debug_data['total_messages'] == 0:
                        st.info("Nessun messaggio registrato dal logger in memoria. Prova a consultare l'Audit Log sotto.")
                    else:
                        # Summary statistics
                        col1, col2, col3 = st.columns(3)
                        
                        to_agent_count = len([m for m in debug_data['messages'] if m['direction'] == 'TO_AGENT'])
                        from_agent_count = len([m for m in debug_data['messages'] if m.get('response_content')])
                        error_count = len([m for m in debug_data['messages'] if m['status'] == 'error'])
                        
                        with col1:
                            st.metric("Messaggi inviati", to_agent_count)
                        with col2:
                            st.metric("Risposte ricevute", from_agent_count)
                        with col3:
                            st.metric("Errori", error_count, delta="⚠️" if error_count > 0 else "✅")
                        
                        st.markdown("---")
                        
                        # Display messages in chronological order
                        for msg in debug_data['messages']:
                            timestamp = msg['timestamp']
                            direction = msg['direction']
                            agent_id = msg['agent_id']
                            status = msg['status']
                            
                            if direction == "TO_AGENT":
                                st.markdown(f"**📤 A {agent_id}:** {msg['task_description']}")
                            elif direction == "FROM_AGENT":
                                with st.expander(f"📥 Risposta da {agent_id} ({status})"):
                                    st.write(msg.get('response_content', 'Nessun contenuto'))
                            st.divider()
                else:
                    st.warning("⚠️ Il Logger in memoria non è inizializzato. I dettagli completi sono però disponibili nell'Audit Log qui sotto.")
            
            # --- FALLBACK AVANZATO: ANALISI AUDIT LOG ---
            st.divider()
            st.subheader("📄 Analisi Flusso Orchestrazione (Audit Log)")
            log_path = Path(config['paths']['logs'])
            if log_path.exists():
                with open(log_path, "r", encoding="utf-8") as f:
                    lines = f.readlines()
                    # Filtriamo solo i log dell'orchestratore per pulizia
                    orch_logs = [l for l in lines if "ORCHESTRATOR" in l or "AGENT" in l]
                    
                    if orch_logs:
                        # Mostriamo gli ultimi 20 step di orchestrazione in modo leggibile
                        for l in orch_logs[-20:]:
                            if "STEP" in l:
                                st.markdown(f"🔹 {l.strip()}")
                            elif "ERROR" in l:
                                st.error(f"🚨 {l.strip()}")
                            else:
                                st.text(l.strip())
                    else:
                        st.info("Nessuna attività di orchestrazione rilevata nel file di log.")
                        
                with st.expander("Vedi Audit Log grezzo (ultime 50 righe)"):
                    st.code("".join(lines[-50:]), language="log")
            else:
                st.info("Il file di log non è ancora stato creato nel workspace.")


def main():
    """
    Punto di ingresso principale che gestisce il bootstrap di Streamlit.
    Necessario per il corretto funzionamento dell'eseguibile PyInstaller.
    """
    if getattr(sys, 'frozen', False):
        base_path = sys._MEIPASS
        work_dir = os.path.dirname(sys.executable)
    else:
        base_path = os.path.dirname(os.path.abspath(__file__))
        work_dir = base_path

    os.chdir(work_dir)

    if st.runtime.exists():
        run_cesare_gui()
    else:
        # --- BOOTSTRAP DI CESARE ---
        init_cesare_workspace(work_dir)
        config = get_validated_config(work_dir)

        # 1. Configurazione e creazione cartella LOGS nel workspace
        ws_path_str = config.get('paths', {}).get('workspace', 'workspace')
        ws_path = Path(ws_path_str)
        if not ws_path.is_absolute():
            ws_path = Path(work_dir) / ws_path
        
        logs_dir = ws_path / "logs"
        logs_dir.mkdir(parents=True, exist_ok=True)
        
        # Assicuriamo che il path dei log nel config sia aggiornato e assoluto
        config.setdefault('paths', {})['logs'] = str(logs_dir / "audit.log")

        # 2. CREAZIONE DI TUTTI I PERCORSI DEFINITI (Memoria, Agenti, Chronos)
        # Questo garantisce che SQLite e ChromaDB trovino le cartelle pronte.
        ensure_config_paths_exist(config.get('paths', {}), Path(work_dir))

        start_scheduler(config)

        print("--- 🛡️ CESARE: Centro di Controllo in Avvio ---")

        app_path = os.path.join(base_path, "main.py")
        sys.argv = ["streamlit", "run", app_path, "--global.developmentMode=false"]

        sys.exit(stcli.main())


if __name__ == "__main__":
    main()
