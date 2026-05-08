"""
BaseAgent: la classe madre di ogni MiniCesare.

Ogni MiniCesare è un agente COMPLETO: ha accesso a tutti i tool
(filesystem, web, memoria, video), alla Bibbia, e al proprio Tier 3.
La specializzazione emerge dall'esperienza accumulata, non da limitazioni imposte.
"""
import os
import uuid
import logging
import chromadb
import sqlite3
from abc import ABC, abstractmethod
from typing import TypedDict, Optional
from datetime import datetime
from langchain_ollama import ChatOllama
from langchain_core.tools import StructuredTool
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage
from langgraph.prebuilt import ToolNode  # Mantenuto per compatibilità se servisse altrove

logger = logging.getLogger("CESARE.BaseAgent")


class AgentTask(TypedDict):
    task_id: str
    instruction: str
    context: str
    workspace_path: str


class AgentResult(TypedDict):
    agent_name: str
    task_id: str
    output: str
    status: str            # "success" | "error" | "partial"
    error_detail: str


class MiniCesare(ABC):
    """
    Agente autonomo completo — un clone funzionale di CESARE.

    NON è un agente castrato con capacità limitate.
    Ha accesso a tutti gli stessi tool di Cesare principale.
    La specializzazione avviene bottom-up:
      - LLM configurabile per ruolo (più adatto al tipo di compiti)
      - Memoria Tier 3 separata (esperienza accumulata per ruolo)
      - Identity prompt che orienta il tono e l'approccio, non i permessi
    """

    def __init__(self, config: dict, agent_name: str):
        self.agent_name = agent_name
        self.config = config
        self.logger = logging.getLogger(f"CESARE.{agent_name}")

        # --- LLM: specifico per agente, fallback a quello principale ---
        agent_cfg = config.get('team', {}).get('agents', {}).get(agent_name, {})
        self.llm_model = agent_cfg.get('model', config['agent']['model'])
        self.llm_temperature = agent_cfg.get('temperature', 0.1)
        self.base_url = config['agent']['base_url']

        self.llm_raw = ChatOllama(
            model=self.llm_model,
            temperature=self.llm_temperature,
            base_url=self.base_url
        )

        # --- Memoria vettoriale: Tier 3 isolato per agente ---
        self.vector_client = chromadb.PersistentClient(path=config['paths']['vector_db'])
        self.exp_collection = self.vector_client.get_or_create_collection(
            name=f"cesare_exp_{agent_name}"
        )
        self.rom_collection = self.vector_client.get_or_create_collection(
            name=f"cesare_rom_{agent_name}"
        )

        # --- Identity prompt: orienta il ruolo, non limita i tool ---
        prompt_path = os.path.join(os.path.dirname(__file__), "prompts", f"{agent_name}.md")
        if os.path.exists(prompt_path):
            with open(prompt_path, "r", encoding="utf-8") as f:
                self.identity_prompt = f.read()
        else:
            self.identity_prompt = (
                f"Sei CESARE {agent_name.capitalize()}, un agente autonomo locale. "
                f"Opera con precisione, rigore e piena autonomia."
            )

        # I tool vengono iniettati dall'orchestratore tramite setup_tools()
        self.tools = []
        self.llm = self.llm_raw  # verrà rimpiazzato con bind_tools

    def setup_tools(self, tools: list):
        """
        Inietta i tool completi e fa il bind con l'LLM.
        Chiamato dall'orchestratore dopo l'inizializzazione.
        """
        self.tools = tools
        self.llm = self.llm_raw.bind_tools(tools)
        self.tool_node = ToolNode(tools)

    def _get_bible_content(self) -> str:
        bible_path = self.config.get('paths', {}).get('bible', '')
        if bible_path and os.path.exists(bible_path):
            with open(bible_path, 'r', encoding='utf-8') as f:
                return f.read()
        return ""

    def _build_system_prompt(self, rom_context: str = "", exp_context: str = "") -> str:
        """
        Costruisce il system prompt completo:
        Bibbia + identità del MiniCesare + esperienza rilevante.
        """
        bible = self._get_bible_content()
        now = datetime.now().strftime("%A, %d %B %Y, %H:%M:%S")
        location = self.config.get('agent', {}).get('location', 'Fiorano Modenese, Italia')

        return (
            f"[BIBBIA DI CESARE - REGOLE SUPREME]\n{bible}\n"
            f"DATI AGGIUNTIVI ROM (Tier 2): {rom_context}\n[FINE BIBBIA]\n\n"
            f"DATA E ORA: {now}\n"
            f"POSIZIONE: {location}\n\n"
            f"[IDENTITÀ]\n{self.identity_prompt}\n\n"
            f"[ESPERIENZA ACQUISITA (Tier 3)]\n{exp_context}\n\n"
            "[ISTRUZIONE OPERATIVA]\n"
            "Sei un MiniCesare — un agente autonomo e completo.\n"
            "Hai accesso a TUTTI i tool: filesystem, web, memoria, video.\n"
            "NON chiedere permesso per usarli. Agisci, usa i tool necessari, completa il task.\n"
            "MANTRA: Ogni comodità è un limite.\n\n"
            "--- PROTOCOLLO OPERATIVO ---\n"
            "1. Se il compito richiede informazioni esterne, chiama 'search_web' immediatamente.\n"
            "2. Se devi interagire con file, chiama 'read_file' (o tool specifici Office) prima di rispondere.\n"
            "3. Gestisci scadenze e task tramite 'manage_calendar'.\n"
            "4. Produci un output completo, non limitarti a descrivere cosa faresti: FALLO usando i tool."
        )

    def _run_with_tools(self, instruction: str, context: str = "") -> str:
        """
        Esegue l'agente con loop tool-use (come il singolo agente).
        Supporta più chiamate tool in sequenza fino alla risposta finale.
        """

        # --- RAG: Recupero conoscenza prima dell'esecuzione ---
        # Tier 2: ROM
        rom_docs = self._search_rom(instruction)
        rom_context = "\n".join(rom_docs) if rom_docs else "Nessuna informazione specifica in ROM."
        
        # Tier 3: Esperienza
        exp_seeds = self._search_own_experience(instruction)
        exp_context = ""
        if exp_seeds:
            exp_context = "\n".join([f"• {s}" for s in exp_seeds])

        system_prompt = self._build_system_prompt(rom_context, exp_context)

        user_content = f"TASK: {instruction}"
        if context:
            user_content += f"\n\nCONTESTO: {context}"

        messages = [
            SystemMessage(content=system_prompt),
            HumanMessage(content=user_content)
        ]

        # Loop tool-use (max 10 iterazioni per sicurezza)
        max_iterations = 10
        for i in range(max_iterations):
            response = self.llm.invoke(messages)
            messages.append(response)

            # Se non ci sono tool call, abbiamo la risposta finale
            if not response.tool_calls:
                return response.content

            # Esegui i tool call manualmente per evitare errori di configurazione del ToolNode
            # e garantire il passaggio corretto dei parametri.
            for tool_call in response.tool_calls:
                tool_name = tool_call["name"]
                tool_args = tool_call["args"]
                tool_id = tool_call["id"]
                
                # Cerca l'oggetto tool corrispondente
                tool = next((t for t in self.tools if t.name == tool_name), None)
                if tool:
                    try:
                        self.logger.info(f"[{self.agent_name}] Esecuzione tool: {tool_name} con args: {tool_args}")
                        observation = tool.invoke(tool_args)
                        messages.append(ToolMessage(content=str(observation), tool_call_id=tool_id))
                    except Exception as e:
                        err_msg = f"Errore esecuzione tool '{tool_name}': {str(e)}"
                        self.logger.error(err_msg)
                        messages.append(ToolMessage(content=err_msg, tool_call_id=tool_id))
                else:
                    err_msg = f"Tool '{tool_name}' non trovato."
                    self.logger.warning(err_msg)
                    messages.append(ToolMessage(content=err_msg, tool_call_id=tool_id))

        # Fallback: se esauriamo le iterazioni, restituiamo l'ultimo contenuto
        last = messages[-1]
        if hasattr(last, 'content'):
            return last.content
        return "[Iterazioni tool esaurite senza risposta finale]"

    def run(self, task: AgentTask) -> AgentResult:
        """
        Entry point standard. Esegue il task con piena autonomia e tool.
        """
        try:
            output = self._run_with_tools(
                instruction=task['instruction'],
                context=task.get('context', '')
            )

            # Distilla esperienza se il task è andato bene
            if output and "errore" not in output.lower()[:50]:
                seed = f"TASK COMPLETATO [{self.agent_name}]: {task['instruction'][:100]} → {output[:120]}"
                self._store_experience(seed, "success")

            return {
                "agent_name": self.agent_name,
                "task_id": task["task_id"],
                "output": output,
                "status": "success",
                "error_detail": ""
            }

        except Exception as e:
            error_msg = str(e)
            self.logger.error(f"Errore {self.agent_name}: {error_msg}")
            seed = f"FALLIMENTO [{self.agent_name}]: {task['instruction'][:100]} → {error_msg[:150]}"
            self._store_experience(seed, "failure")
            return {
                "agent_name": self.agent_name,
                "task_id": task["task_id"],
                "output": "",
                "status": "error",
                "error_detail": error_msg
            }

    def _search_own_experience(self, query: str, n: int = 3) -> list[str]:
        try:
            results = self.exp_collection.query(query_texts=[query], n_results=n)
            return results['documents'][0] if results['documents'] else []
        except Exception:
            return []

    def _search_rom(self, query: str, n: int = 3) -> list[str]:
        try:
            results = self.rom_collection.query(query_texts=[query], n_results=n)
            return results['documents'][0] if results['documents'] else []
        except Exception:
            return []

    def _store_experience(self, seed: str, category: str = "general"):
        import time
        try:
            seed_id = f"exp_{self.agent_name}_{uuid.uuid4().hex}"
            self.exp_collection.add(
                documents=[seed],
                metadatas=[{"category": category, "timestamp": time.time()}],
                ids=[seed_id]
            )
            tier3_db = self.config.get("paths", {}).get("tier3_db")
            if tier3_db:
                os.makedirs(os.path.dirname(tier3_db), exist_ok=True)
                with sqlite3.connect(tier3_db, timeout=20) as conn:
                    conn.execute(
                        "CREATE TABLE IF NOT EXISTS seeds (id TEXT PRIMARY KEY, seed_text TEXT, category TEXT, success_rate REAL)"
                    )
                    conn.execute(
                        "INSERT INTO seeds (id, seed_text, category) VALUES (?, ?, ?)",
                        (seed_id, seed, category)
                    )
        except Exception as e:
            self.logger.warning(f"Store experience fallito: {e}")
