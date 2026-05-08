from typing import Literal, Annotated, Sequence
from langchain_ollama import ChatOllama
from langgraph.graph import StateGraph, END, START
from langgraph.prebuilt import ToolNode
from core.state import AgentState
from core.memory import CesareMemory
from tools.filesystem import get_fs_tools
from langchain_core.tools import StructuredTool
from tools.web_tools import search_web_tool, browse_web_tool
from tools.video_tools import get_video_tools
import os
import time
import atexit
from datetime import datetime
import logging
from agents import CesareOrchestrator
from tools.web_tools import cleanup_browser

logger = logging.getLogger("CESARE.Wrapper")


class DebugMessage:
    """Rappresenta un messaggio di debug per il tracciamento delle comunicazioni."""
    def __init__(self, timestamp: datetime = None, direction: str = "",
                 agent_id: str = "", task_description: str = "",
                 message_content: dict = None, response_content: dict = None,
                 status: str = "", execution_time_ms: float = 0.0):
        self.timestamp = timestamp or datetime.now()
        self.direction = direction
        self.agent_id = agent_id
        self.task_description = task_description
        self.message_content = message_content or {}
        self.response_content = response_content or {}
        self.status = status
        self.execution_time_ms = execution_time_ms


class DebugLogger:
    """Logger di debug per tracciare le comunicazioni tra Cesare e gli agenti."""
    
    def __init__(self, enabled: bool = False):
        self.enabled = enabled
        self.messages = []
    
    def enable(self):
        """Abilita il logging di debug."""
        self.enabled = True
        logger.info("Debug logging enabled")
    
    def disable(self):
        """Disabilita il logging di debug."""
        self.enabled = False
        logger.info("Debug logging disabled")
    
    def is_enabled(self) -> bool:
        """Restituisce lo stato del debug logging."""
        return self.enabled
    
    def log_message_to_agent(self, agent_id: str, task_description: str, 
                             message: dict) -> None:
        """Registra un messaggio inviato a un agente."""
        if not self.enabled:
            return
        
        debug_msg = DebugMessage(
            direction="TO_AGENT",
            agent_id=agent_id,
            task_description=task_description,
            message_content=message,
            status="sent"
        )
        self.messages.append(debug_msg)
        logger.debug(f"[DEBUG] TO_AGENT[{agent_id}]: {task_description}")
    
    def log_response_from_agent(self, agent_id: str, task_description: str,
                                response: dict, execution_time_ms: float,
                                status: str = "success") -> None:
        """Registra una risposta ricevuta da un agente."""
        if not self.enabled:
            return
        
        # Trova il messaggio corrispondente e aggiornalo
        for msg in reversed(self.messages):
            if msg.direction == "TO_AGENT" and msg.agent_id == agent_id and msg.status == "sent":
                msg.response_content = response
                msg.status = status
                msg.execution_time_ms = execution_time_ms
                break
        
        logger.debug(f"[DEBUG] FROM_AGENT[{agent_id}]: Status={status}, Time={execution_time_ms:.2f}ms")
    
    def log_error(self, agent_id: str, task_description: str, 
                  error: str, execution_time_ms: float) -> None:
        """Registra un errore nella comunicazione con un agente."""
        if not self.enabled:
            return
        
        debug_msg = DebugMessage(
            direction="ERROR",
            agent_id=agent_id,
            task_description=task_description,
            message_content={"error": error},
            status="error",
            execution_time_ms=execution_time_ms
        )
        self.messages.append(debug_msg)
        logger.error(f"[DEBUG] ERROR[{agent_id}]: {error}")
    
    def get_messages(self) -> list:
        """Restituisce tutti i messaggi di debug registrati."""
        return self.messages.copy()
    
    def clear(self) -> None:
        """Pulisce tutti i messaggi di debug registrati."""
        self.messages.clear()
    
    def to_dict(self) -> dict:
        """Converte i messaggi di debug in formato dictionary per serializzazione."""
        return {
            "enabled": self.enabled,
            "total_messages": len(self.messages),
            "messages": [
                {
                    "timestamp": msg.timestamp.isoformat(),
                    "direction": msg.direction,
                    "agent_id": msg.agent_id,
                    "task_description": msg.task_description,
                    "message_content": msg.message_content,
                    "response_content": msg.response_content,
                    "status": msg.status,
                    "execution_time_ms": msg.execution_time_ms
                }
                for msg in self.messages
            ]
        }


class CesareGraph:
    def __init__(self, config, context_folder=None, debug_enabled: bool = False):
        # Prende tutto dal dizionario config passato all'avvio (Single Source of Truth)
        self.config = config
        paths = config['paths']
        self.workspace_path = paths['workspace']
        self.bible_path = paths['bible']
        
        # Inizializza il debug logger
        self.debug_logger = DebugLogger(enabled=debug_enabled)

        # Inizializza i tool passando il percorso workspace corretto
        fs_tools = get_fs_tools(self.workspace_path, context_folder)

        # Inizializza la memoria con i percorsi del config
        # Forza l'uso della memoria isolata dell'orchestratore per coerenza tra modalità singolo e team
        mem_paths = paths.copy()
        if 'memory_isolated' in paths and 'orchestrator' in paths['memory_isolated']:
            mem_paths.update(paths['memory_isolated']['orchestrator'])
        self.memory = CesareMemory(mem_paths)

        # Tool per la memoria a lungo termine
        memory_tools = [
            StructuredTool.from_function(
                name="memorize_fact",
                func=lambda fact: self.memory.dispatch_memory(2, fact, {"type": "fact"}),
                description="Memorizza un fatto o un'informazione importante nella ROM (TIER 2). Usa questo per preferenze permanenti o dati immutabili."
            ),
            StructuredTool.from_function(
                name="manage_calendar",
                func=lambda action, task_id=None, data=None: self.memory.manage_calendar_db(action, task_id, data),
                description="Gestisce l'agenda/calendario condiviso di CESARE (Modulo Chronos). Azioni: 'list', 'create' (richiede dict 'data'), 'delete' (richiede 'task_id'). Usa SEMPRE questo per impegni, scadenze e task temporali invece della memoria ROM/Esperienza."
            )
        ]

        # Tool per la navigazione web
        web_tools = [
            StructuredTool.from_function(
                name="search_web",
                func=search_web_tool,
                description="Cerca su internet informazioni aggiornate. Restituisce una lista di titoli, URL e snippet."
            ),
            StructuredTool.from_function(
                name="browse_web",
                func=browse_web_tool,
                description="Legge il contenuto testuale di un URL specifico. Usa questo dopo 'search_web' per approfondire un risultato."
            )
        ]

        # Tool per il video
        video_tools = get_video_tools(self.config)

        self.tools = fs_tools + memory_tools + web_tools + video_tools

        llm_base = ChatOllama(
            model=self.config['agent']['model'],
            temperature=self.config['agent']['temperature'],
            base_url=self.config['agent']['base_url']
        )
        self.llm = llm_base.bind_tools(self.tools)
        
    def _get_bible_content(self):
        if os.path.exists(self.bible_path):
            with open(self.bible_path, 'r', encoding='utf-8') as f:
                return f.read()
        return "Bibbia non trovata."

    def call_model(self, state: AgentState):
        bible_content = self._get_bible_content()
        
        # --- Informazioni Temporali e Spaziali ---
        now = datetime.now().strftime("%A, %d %B %Y, %H:%M:%S")
        location = self.config.get('agent', {}).get('location', 'Fiorano Modenese, Italia')

        # --- TIER 3: EXPERIENCE SEARCH (Learning from Seeds) ---
        last_user_query = next((m.content for m in reversed(state['messages']) if m.type == 'human'), "")
        exp_context = ""
        if last_user_query:
            seeds = self.memory.search_experience(str(last_user_query))
            if seeds:
                exp_context = "\n".join([f"• SEME: {s}" for s in seeds])

        # --- TIER 2: ROM SEARCH (Absolute Truths) ---
        rom_docs_context = ""
        if last_user_query:
            rom_docs = self.memory.search_rom(str(last_user_query))
            if rom_docs:
                rom_docs_context = "\n".join(rom_docs)

        # Rafforziamo le istruzioni per il monitoraggio file
        system_message = (
            f"[BIBBIA - ROM TIER 2]\n{bible_content}\n"
            f"DATI AGGIUNTIVI ROM: {rom_docs_context}\n[FINE ROM]\n\n"
            f"DATA E ORA: {now}\n"
            f"POSIZIONE: {location}\n\n"
            f"[ESPERIENZA ACQUISITA - TIER 3]\n{exp_context}\n"
            "Se un'esperienza passata contraddice la tua tendenza attuale, segui l'ESPERIENZA.\n\n"
            "Sei CESARE, l'agente autonomo locale.\n"
            "Il tuo workspace operativo è la cartella ./workspace/. Tutti i file creati o gestiti devono trovarsi lì.\n"
            "I file config.yaml, bible.md e i log di audit sono all'esterno del workspace e NON sono accessibili via tool.\n"
            "La cronologia esecuzioni di Chronos è in 'chronos/task_history.md' dentro il workspace.\n"
            "NON provare MAI a leggere file binari come .db o indici vettoriali usando 'read_file'.\n"
            "MANTRA: Ogni comodità è un limite.\n"
            "\n--- PROTOCOLLO CALENDARIO (CHRONOS) ---\n"
            "1. Ogni impegno, scadenza o task temporale DEVE essere gestito tramite 'manage_calendar'.\n"
            "2. NON usare 'memorize_fact' per dati che hanno una scadenza o natura di calendario.\n"
            "3. L'agenda esterna in chronos/ è la priorità assoluta per la tua pianificazione.\n"
            "\n--- PROTOCOLLO OPERATIVO CHAT-FILE ---\n"
            "1. Se il compito è monitorare un file o usarlo come chat, NON dare mai per scontato il contenuto.\n"
            "2. Chiama SEMPRE 'read_file' prima di rispondere.\n"
            "\n--- PROTOCOLLO DI CRESCITA ---\n"
            "Se la tua azione fallisce, il sistema registrerà un errore. Nella sessione successiva, quel fallimento sarà un Seme nel tuo contesto Esperienza."
        )

        # Gestione Protocollo Override
        if state.get('override_active'):
            system_message += "\nATTENZIONE: Il Protocollo BIBBIA OVERRIDE è attivo. Hai il permesso temporaneo del Creatore di derogare alla sandbox."
        
        messages = [{"role": "system", "content": system_message}] + list(state['messages'])
        response = self.llm.invoke(messages)
        
        # TIER 1: Ephemeral memory update
        if not response.tool_calls and response.content:
            self.memory.dispatch_memory(1, str(last_user_query), {"role": "user"})
            self.memory.dispatch_memory(1, response.content, {"role": "assistant"})
        
        return {"messages": [response]}

    def reflect(self, state: AgentState):
        """Analisi post-interazione per Tier 3 (Distillazione Esperienza)."""
        messages = state['messages']
        last_assistant_msg = next((m.content for m in reversed(messages) if m.type == 'ai'), "")
        last_user_msg = next((m.content for m in reversed(messages) if m.type == 'human'), "").lower()
        
        # 1. Trigger da Errore (Autocorrezione)
        error_keywords = ["errore", "fallito", "error", "failed", "denied"]
        if any(kw in last_assistant_msg.lower() for kw in error_keywords):
            seed = f"FALLIMENTO: L'azione precedente è fallita. Contesto: {last_assistant_msg[:150]}. Lezione: Adatta la strategia evitando l'approccio che ha causato l'errore."
            self.memory.dispatch_memory(3, seed, {"category": "error_recovery"})
            return {"reflection_log": "Seme di fallimento distillato."}
        
        # 2. Trigger da Creatore ("Ricorda", "Ottimo", "Plauso")
        praise_keywords = ["ricorda", "memorizza questo", "ottimo lavoro", "perfetto così"]
        if any(kw in last_user_msg for kw in praise_keywords):
            # Distilla l'essenza dell'ultima risposta positiva
            seed = f"PATTERN SUCCESSO: L'utente ha approvato questa logica: {last_assistant_msg[:200]}."
            self.memory.dispatch_memory(3, seed, {"category": "user_preference"})
            return {"reflection_log": "Pattern di successo salvato nel Tier 3."}

        return {"reflection_log": "Interazione nominale."}

    def should_continue(self, state: AgentState) -> Literal["tools", "reflect", "__end__"]:
        messages = state['messages']
        last_message = messages[-1]
        if last_message.tool_calls:
            return "tools"
        return "reflect"

    def build(self):
        workflow = StateGraph(AgentState)
        
        # Aggiungiamo i nodi
        workflow.add_node("agent", self.call_model)
        workflow.add_node("tools", ToolNode(self.tools))
        workflow.add_node("reflect", self.reflect)
        
        # Definiamo i flussi
        workflow.add_edge(START, "agent")
        workflow.add_conditional_edges("agent", self.should_continue)
        workflow.add_edge("tools", "agent")
        workflow.add_edge("reflect", END)
        
        app = workflow.compile()
        
        # Registriamo il cleanup del browser all'uscita del processo
        atexit.register(cleanup_browser)
        
        return app

def get_cesare_app(config, context_folder=None, team_mode: bool = False, debug_enabled: bool = False):
    if not team_mode:
        # Modalità esistente (inglese per non rompere retrocompatibilità)
        builder = CesareGraph(config, context_folder, debug_enabled=debug_enabled)
        return builder.build()
    
    # --- NUOVA MODALITÀ TEAM ---
    orchestrator = CesareOrchestrator(config)
    
    class OrchestratorWrapper:
        class AIMsg:
            def __init__(self, content):
                self.content = content
                self.type = "ai"

        def __init__(self, orch):
            self.orch = orch
        
        @property
        def debug_logger(self):
            return self.orch.debug_logger
        
        def invoke(self, inputs: dict) -> dict:
            user_request = ""
            
            # Estrazione robusta: supporta sia dict {"role":..., "content":...}
            # che oggetti LangChain con attributo .type
            for m in reversed(inputs.get("messages", [])):
                if isinstance(m, dict):
                    if m.get("role") == "user":
                        user_request = m.get("content", "")
                        break
                elif getattr(m, "type", "") == "human":
                    user_request = m.content
                    break
            
            if not user_request:
                logger.warning("OrchestratorWrapper: nessun messaggio utente trovato nell'input.")
                return {"messages": [self.AIMsg("Nessun input ricevuto.")]}
            
            status_callback = inputs.get("status_callback", None)
            output_text = self.orch.run(
                user_request, 
                override_active=inputs.get("override_active", False),
                status_callback=status_callback
            )
            return {"messages": [self.AIMsg(output_text)]}

    return OrchestratorWrapper(orchestrator)