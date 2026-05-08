"""
CesareOrchestrator — nuovo design.

Cesare è l'unico cervello: pianifica, delega, sintetizza, valida.
I MiniCesare (programmer, researcher, worker) sono agenti COMPLETI con
tutti i tool disponibili. La loro specializzazione emerge dall'esperienza
accumulata (Tier 3) e dall'LLM scelto, non da limitazioni di capacità.

Flusso:
  1. Cesare analizza il task con logica leggera (niente JSON esterno fragile)
  2. Delega ai MiniCesare necessari in parallelo
  3. Raccoglie i risultati
  4. Sintetizza e valida internamente (niente agenti Synthesizer/Audit separati)
  5. Presenta la risposta finale
"""
import os
import uuid
import logging
import time
import copy
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime
from typing import Dict, List, Optional, Any

from langchain_ollama import ChatOllama
from langchain_core.tools import StructuredTool
from langgraph.prebuilt import ToolNode

from .base_agent import MiniCesare, AgentTask, AgentResult
from .researcher import ResearcherAgent
from .programmer import ProgrammerAgent
from .worker import WorkerAgent
from core.security import audit_log
from core.memory import CesareMemory
from tools.filesystem import get_fs_tools
from tools.web_tools import search_web_tool, browse_web_tool


class DebugLogger:
    """Classe di supporto per memorizzare i log di comunicazione tra agenti per la GUI."""
    def __init__(self):
        self._messages = []
        self._enabled = True

    def is_enabled(self) -> bool:
        return self._enabled

    def log_event(self, direction: str, agent_id: str, content: Any, 
                  task_desc: str = "", status: str = "success", 
                  exec_time: float = 0):
        event = {
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "direction": direction, # TO_AGENT, FROM_AGENT, ERROR
            "agent_id": agent_id,
            "message_content": content if direction == "TO_AGENT" else None,
            "response_content": content if direction == "FROM_AGENT" else None,
            "task_description": task_desc,
            "status": status,
            "execution_time_ms": exec_time
        }
        self._messages.append(event)
        # Mantieni solo gli ultimi 100 messaggi per non saturare la RAM
        if len(self._messages) > 100:
            self._messages.pop(0)

    def get_messages(self) -> List[Dict]:
        return self._messages

    def clear(self):
        self._messages = []

    def to_dict(self) -> Dict:
        return {
            "total_messages": len(self._messages),
            "messages": self._messages
        }


class CesareOrchestrator:
    """
    Cesare come orchestratore, sintetizzatore e garante della qualità.

    Non usa un piano JSON esterno per decidere gli agenti — usa una logica
    interna semplice e robusta. Sintesi e audit sono fasi interne di Cesare,
    non agenti separati che possono allucinare.
    """

    # Soglia: messaggi brevi/conversazionali → risposta diretta senza delegare
    CONVERSATIONAL_TRIGGERS = [
        "ciao", "salve", "buongiorno", "buonasera", "buonanotte",
        "come stai", "come va", "grazie", "prego", "arrivederci",
        "ok", "perfetto", "capito", "bene", "ottimo", "esatto",
        "chi sei", "cosa sei", "presentati", "dimmi di te"
    ]

    def __init__(self, config: dict):
        self.config = config
        self.logger = logging.getLogger("CESARE.Orchestrator")
        
        # Inizializza il logger per la GUI
        self.debug_logger = DebugLogger()

        # LLM principale di Cesare (per pianificazione, sintesi, risposta diretta)
        self.llm = ChatOllama(
            model=config.get("agent", {}).get("model", "gemma4:26b"),
            temperature=config.get("agent", {}).get("temperature", 0.1),
            base_url=config["agent"]["base_url"]
        )

        # Memoria di Cesare
        # Utilizza i percorsi isolati specifici dell'orchestratore definiti nel config
        paths = config.get('paths', {})
        mem_paths = paths.copy()
        if 'memory_isolated' in paths and 'orchestrator' in paths['memory_isolated']:
            mem_paths.update(paths['memory_isolated']['orchestrator'])
        self.memory = CesareMemory(mem_paths)

        # Inizializza i MiniCesare con memoria isolata e tool completi per agente
        self.mini: Dict[str, MiniCesare] = {
            "researcher": ResearcherAgent(self._build_agent_config("researcher")),
            "programmer": ProgrammerAgent(self._build_agent_config("programmer")),
            "worker":     WorkerAgent(self._build_agent_config("worker")),
        }
        for agent_name, agent in self.mini.items():
            agent_mem_cfg = self._build_agent_config(agent_name)
            agent_mem = CesareMemory(agent_mem_cfg["paths"])
            agent_tools = self._build_tools(agent_mem)
            agent.setup_tools(agent_tools)

    def _build_agent_config(self, agent_name: str) -> dict:
        """Ritorna una config derivata con percorsi memoria isolati per l'agente."""
        cfg = copy.deepcopy(self.config)
        paths = cfg.get("paths", {})
        isolated = paths.get("memory_isolated", {}).get(agent_name, {})
        paths.update(isolated)
        cfg["paths"] = paths
        return cfg

    def _build_tools(self, memory_backend: CesareMemory) -> list:
        """Costruisce la lista tool completa — identica a quella del singolo agente."""
        workspace = self.config['paths']['workspace']
        fs_tools = get_fs_tools(workspace)

        memory_tools = [
            StructuredTool.from_function(
                name="memorize_fact",
                func=lambda fact: memory_backend.dispatch_memory(2, fact, {"type": "fact"}),
                description="Memorizza un fatto importante nella ROM (TIER 2)."
            ),
            StructuredTool.from_function(
                name="manage_calendar",
                func=lambda action, task_id=None, data=None: memory_backend.manage_calendar_db(action, task_id, data),
                description="Gestisce agenda/calendario (Chronos). Azioni: 'list', 'create', 'delete'."
            ),
        ]

        web_tools = [
            StructuredTool.from_function(
                name="search_web",
                func=search_web_tool,
                description="Cerca su internet. Restituisce titoli, URL e snippet."
            ),
            StructuredTool.from_function(
                name="browse_web",
                func=browse_web_tool,
                description="Legge il contenuto di un URL specifico."
            ),
        ]

        try:
            from tools.video_tools import get_video_tools
            video_tools = get_video_tools(self.config)
        except Exception:
            video_tools = []

        return fs_tools + memory_tools + web_tools + video_tools

    # -----------------------------------------------------------------------
    # Logica di routing — semplice, senza JSON esterno
    # -----------------------------------------------------------------------

    def _is_conversational(self, text: str) -> bool:
        text_lower = text.lower().strip()
        if len(text_lower.split()) <= 5:
            for trigger in self.CONVERSATIONAL_TRIGGERS:
                if trigger in text_lower:
                    return True
        return False

    def _select_agents(self, user_request: str) -> List[str]:
        """
        Cesare decide quali MiniCesare attivare.

        Usa keyword matching come prima linea (veloce, zero allucinazioni).
        Solo se il task è ambiguo, fa una breve chiamata LLM con output
        vincolato a una lista di nomi — niente JSON complesso.
        """
        text = user_request.lower()

        # Segnali forti → routing diretto senza chiamare l'LLM
        code_signals = ["codice", "script", "funzione", "bug", "debug", "programm",
                        "python", "javascript", "classe", "refactor", "implementa",
                        "scrivi un", "crea un programma", "sviluppa"]
        research_signals = ["cerca", "trova informazioni", "ricerca", "notizie",
                            "aggiorna", "recente", "internet", "web", "analizza",
                            "studia", "cosa è", "spiega", "confronta"]
        work_signals = ["crea un documento", "genera un report", "excel", "xlsx",
                        "docx", "pdf", "converti", "trasforma", "elabora",
                        "tabella", "foglio", "presentazione", "pptx"]

        has_code = any(s in text for s in code_signals)
        has_research = any(s in text for s in research_signals)
        has_work = any(s in text for s in work_signals)

        if has_code or has_research or has_work:
            selected = []
            if has_code:
                selected.append("programmer")
            if has_research:
                selected.append("researcher")
            if has_work:
                selected.append("worker")
            return selected

        # Task ambiguo → chiediamo a Cesare con output vincolato
        try:
            prompt = (
                "Sei CESARE. Analizza il task e rispondi SOLO con i nomi degli agenti necessari, "
                "separati da virgola, senza nient'altro.\n"
                "Agenti disponibili: programmer, researcher, worker\n"
                "Regola: usa il minimo necessario. Se basta uno, usa solo uno.\n\n"
                f"TASK: {user_request}\n\n"
                "Risposta (solo nomi separati da virgola):"
            )
            response = self.llm.invoke(prompt)
            raw = response.content.strip().lower()
            selected = [
                name.strip()
                for name in raw.replace("\n", ",").split(",")
                if name.strip() in self.mini
            ]
            if selected:
                return selected
        except Exception as e:
            self.logger.warning(f"Selezione agenti LLM fallita: {e}")

        # Fallback: worker generico
        return ["worker"]

    # -----------------------------------------------------------------------
    # Risposta diretta di Cesare (senza delegare)
    # -----------------------------------------------------------------------

    def _direct_response(self, user_request: str, reason: str = "") -> str:
        """Cesare risponde direttamente, senza delegare ai MiniCesare."""
        bible_path = self.config['paths'].get('bible', '')
        bible = ""
        if bible_path and os.path.exists(bible_path):
            with open(bible_path, 'r', encoding='utf-8') as f:
                bible = f.read()

        now = datetime.now().strftime("%A, %d %B %Y, %H:%M:%S")
        system = (
            f"[BIBBIA]\n{bible}\n[FINE BIBBIA]\n\n"
            f"DATA E ORA: {now}\n\n"
            "Sei CESARE, l'agente autonomo locale. Rispondi in modo naturale, conciso e preciso."
        )
        if reason:
            system += f"\n\nNota: {reason}"

        try:
            resp = self.llm.invoke([
                {"role": "system", "content": system},
                {"role": "user", "content": user_request}
            ])
            return resp.content
        except Exception as e:
            return f"Errore risposta diretta: {e}"

    # -----------------------------------------------------------------------
    # Sintesi interna — Cesare elabora e presenta gli output dei MiniCesare
    # -----------------------------------------------------------------------

    def _synthesize(self, user_request: str, results: Dict[str, AgentResult]) -> str:
        """
        Cesare sintetizza i risultati dei MiniCesare in una risposta coerente.
        Niente agente Synthesizer separato — è logica interna di Cesare.
        """
        # Costruisce il contesto degli output
        parts = []
        for agent_name, result in results.items():
            status_icon = "✅" if result["status"] == "success" else "❌"
            parts.append(
                f"[{status_icon} OUTPUT {agent_name.upper()}]\n{result['output']}"
            )

        combined = "\n\n".join(parts)

        bible_path = self.config['paths'].get('bible', '')
        bible = ""
        if bible_path and os.path.exists(bible_path):
            with open(bible_path, 'r', encoding='utf-8') as f:
                bible = f.read()

        system = (
            f"[BIBBIA]\n{bible}\n[FINE BIBBIA]\n\n"
            "Sei CESARE. Hai delegato parti di un task ai tuoi agenti e hai ricevuto i loro output.\n"
            "Il tuo compito ora è sintetizzare tutto in una risposta unica, coerente e completa per l'utente.\n"
            "Elimina ridondanze, unifica le informazioni, mantieni ciò che è rilevante.\n"
            "Parla in prima persona come CESARE — non menzionare i nomi degli agenti interni.\n"
            "Se qualcosa non è andato a buon fine, segnalalo con trasparenza."
        )

        user_msg = (
            f"RICHIESTA ORIGINALE: {user_request}\n\n"
            f"OUTPUT DEGLI AGENTI:\n{combined}\n\n"
            "Produci la risposta finale."
        )

        try:
            resp = self.llm.invoke([
                {"role": "system", "content": system},
                {"role": "user", "content": user_msg}
            ])
            return resp.content
        except Exception as e:
            self.logger.error(f"Errore sintesi: {e}")
            # Fallback: restituisce gli output concatenati grezzi
            return combined

    # -----------------------------------------------------------------------
    # Audit interno — Cesare valida la propria risposta
    # -----------------------------------------------------------------------

    def _audit(self, user_request: str, response: str) -> str:
        """
        Cesare esegue un rapido audit interno sulla risposta sintetizzata.
        Non è un agente separato — è Cesare che rilegge il proprio lavoro.
        Se non trova problemi, restituisce la risposta invariata.
        """
        prompt = (
            f"Richiesta utente: {user_request}\n\n"
            f"Risposta prodotta:\n{response}\n\n"
            "Verifica rapidamente:\n"
            "1. La risposta è completa rispetto alla richiesta?\n"
            "2. Ci sono contraddizioni o errori evidenti?\n"
            "3. Il tono è appropriato?\n\n"
            "Se tutto è corretto, rispondi SOLO con: OK\n"
            "Se ci sono problemi, rispondi con la versione corretta della risposta."
        )

        try:
            resp = self.llm.invoke([
                {"role": "system", "content": "Sei CESARE in modalità revisione. Sii rapido e preciso."},
                {"role": "user", "content": prompt}
            ])
            result = resp.content.strip()
            if result.upper() == "OK" or result.upper().startswith("OK"):
                return response  # Nessuna modifica necessaria
            return result  # Versione corretta
        except Exception as e:
            self.logger.warning(f"Audit interno fallito: {e}")
            return response  # In caso di errore, mantieni la risposta originale

    # -----------------------------------------------------------------------
    # Entry point principale
    # -----------------------------------------------------------------------

    def run(self, user_request: str, override_active: bool = False,
            status_callback=None) -> str:
        start_time_global = time.time()

        def notify(msg: str):
            if status_callback:
                status_callback(msg)

        audit_log("ORCHESTRATOR | START", f"Task: {user_request[:60]}...")

        # 1. Conversazionale → risposta diretta
        if self._is_conversational(user_request):
            notify("💬 Risposta diretta.")
            return self._direct_response(user_request)

        # 2. Seleziona MiniCesare
        notify("🔍 Analisi task...")
        selected = self._select_agents(user_request)
        notify(f"📋 Agenti selezionati: {', '.join(selected)}")
        audit_log("ORCHESTRATOR | ROUTING", f"Agenti: {selected}")

        task_id = str(uuid.uuid4())[:8]
        timeout = self.config.get('team', {}).get('agent_timeout_seconds', 180)

        # 3. Esecuzione parallela dei MiniCesare
        notify("⚙️ Elaborazione parallela avviata...")
        results: Dict[str, AgentResult] = {}

        with ThreadPoolExecutor(max_workers=len(selected)) as executor:
            futures = {}
            for name in selected:
                task: AgentTask = {
                    "task_id": task_id,
                    "instruction": user_request,
                    "context": "",
                    "workspace_path": self.config["paths"]["workspace"]
                }
                
                # Log debug invio
                self.debug_logger.log_event(
                    "TO_AGENT", name, task, task_desc=user_request[:50]+"...", status="sent"
                )
                self.logger.info(f"Delegato task a {name} (ID: {task_id})")
                audit_log("ORCHESTRATOR | DELEGATE", f"Inviato task a {name}")
                
                future = executor.submit(self.mini[name].run, task)
                futures[future] = name

            for future in as_completed(futures, timeout=timeout):
                name = futures[future]
                agent_start = time.time()
                try:
                    result = future.result()
                    exec_time = (time.time() - agent_start) * 1000
                    results[name] = result
                    
                    icon = "✅" if result["status"] == "success" else "❌"
                    notify(f"{icon} {name} completato.")
                    
                    # Log debug ricezione
                    self.debug_logger.log_event(
                        "FROM_AGENT", name, result["output"], 
                        status=result["status"], exec_time=exec_time
                    )
                    audit_log("ORCHESTRATOR | AGENT_RESULT", f"Agente {name} ha terminato con status {result['status']}")

                except Exception as e:
                    self.logger.error(f"Timeout/errore {name}: {e}")
                    error_res = {
                        "agent_name": name,
                        "task_id": task_id,
                        "output": f"[{name} non ha risposto in tempo]",
                        "status": "error",
                        "error_detail": str(e)
                    }
                    results[name] = error_res
                    self.debug_logger.log_event("ERROR", name, {"error": str(e)}, status="error")
                    audit_log("ORCHESTRATOR | ERROR", f"Fallimento agente {name}: {str(e)}")

        # 4. Se c'è un solo agente e ha risposto bene, no sintesi necessaria
        if len(selected) == 1:
            only = selected[0]
            result = results.get(only, {})
            if result.get("status") == "success":
                notify("✅ Completato.")
                audit_log("ORCHESTRATOR | DONE", f"Task {task_id} — singolo agente.")
                return result.get("output", "Nessun output.")
            else:
                # L'agente ha fallito → Cesare interviene direttamente
                notify("⚠️ Agente in difficoltà — CESARE interviene.")
                return self._direct_response(
                    user_request,
                    reason=f"Il MiniCesare {only} ha riportato: {result.get('error_detail', '')}"
                )

        # 5. Sintesi multi-agente
        notify("🔗 Sintesi degli output...")
        synthesized = self._synthesize(user_request, results)

        # 6. Audit interno
        notify("🛡️ Revisione finale...")
        final = self._audit(user_request, synthesized)

        notify("✅ Completato.")
        audit_log("ORCHESTRATOR | DONE", f"Task {task_id} — multi-agente.")
        return final
