"""
CESARE 2.0 - Core Orchestrator Refactored
Integra i nuovi moduli di validazione, assembly e parsing robusto.
"""
import asyncio
import time
import uuid
import logging
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime

from .models import (
    AgentResult, OrchestratorPlan, TaskDefinition, 
    ExecutionStatus, AgentRole, SynthesisContext
)
from .pipeline import AssemblyEngine
from .json_parser import RobustJSONParser

logger = logging.getLogger(__name__)


@dataclass
class DebugMessage:
    """Rappresenta un messaggio di debug per il tracciamento delle comunicazioni."""
    timestamp: datetime = field(default_factory=datetime.now)
    direction: str = ""  # "TO_AGENT" o "FROM_AGENT"
    agent_id: str = ""
    task_description: str = ""
    message_content: Dict[str, Any] = field(default_factory=dict)
    response_content: Dict[str, Any] = field(default_factory=dict)
    status: str = ""
    execution_time_ms: float = 0.0


class DebugLogger:
    """Logger di debug per tracciare le comunicazioni tra Cesare e gli agenti."""
    
    def __init__(self, enabled: bool = False):
        self.enabled = enabled
        self.messages: List[DebugMessage] = []
        self._lock = asyncio.Lock()
    
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
    
    async def log_message_to_agent(self, agent_id: str, task: TaskDefinition, 
                                   message: Dict[str, Any]) -> None:
        """Registra un messaggio inviato a un agente."""
        if not self.enabled:
            return
        
        async with self._lock:
            debug_msg = DebugMessage(
                direction="TO_AGENT",
                agent_id=agent_id,
                task_description=task.description,
                message_content=message,
                status="sent"
            )
            self.messages.append(debug_msg)
            logger.debug(f"[DEBUG] TO_AGENT[{agent_id}]: {task.description}")
    
    async def log_response_from_agent(self, agent_id: str, task: TaskDefinition,
                                      response: Dict[str, Any], 
                                      execution_time_ms: float,
                                      status: str = "success") -> None:
        """Registra una risposta ricevuta da un agente."""
        if not self.enabled:
            return
        
        async with self._lock:
            # Trova il messaggio corrispondente e aggiornalo
            for msg in reversed(self.messages):
                if msg.direction == "TO_AGENT" and msg.agent_id == agent_id and msg.status == "sent":
                    msg.response_content = response
                    msg.status = status
                    msg.execution_time_ms = execution_time_ms
                    break
            
            logger.debug(f"[DEBUG] FROM_AGENT[{agent_id}]: Status={status}, Time={execution_time_ms:.2f}ms")
    
    async def log_error(self, agent_id: str, task: TaskDefinition, 
                        error: str, execution_time_ms: float) -> None:
        """Registra un errore nella comunicazione con un agente."""
        if not self.enabled:
            return
        
        async with self._lock:
            debug_msg = DebugMessage(
                direction="ERROR",
                agent_id=agent_id,
                task_description=task.description,
                message_content={"error": error},
                status="error",
                execution_time_ms=execution_time_ms
            )
            self.messages.append(debug_msg)
            logger.error(f"[DEBUG] ERROR[{agent_id}]: {error}")
    
    def get_messages(self) -> List[DebugMessage]:
        """Restituisce tutti i messaggi di debug registrati."""
        return self.messages.copy()
    
    def get_filtered_messages(self, agent_id: Optional[str] = None, 
                              direction: Optional[str] = None,
                              status: Optional[str] = None) -> List[DebugMessage]:
        """Restituisce i messaggi filtrati per criteri specifici."""
        filtered = self.messages
        
        if agent_id:
            filtered = [m for m in filtered if m.agent_id == agent_id]
        
        if direction:
            filtered = [m for m in filtered if m.direction == direction]
        
        if status:
            filtered = [m for m in filtered if m.status == status]
        
        return filtered
    
    def clear(self) -> None:
        """Pulisce tutti i messaggi di debug registrati."""
        self.messages.clear()
    
    def to_dict(self) -> Dict[str, Any]:
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


class MockLLMProvider:
    """Simulatore di LLM per testing senza dipendenze esterne."""
    
    def __init__(self, debug_logger: Optional[DebugLogger] = None):
        self.debug_logger = debug_logger or DebugLogger(enabled=False)
    
    async def generate_plan(self, objective: str) -> Dict[str, Any]:
        await asyncio.sleep(0.1)  # Simula latenza
        return {
            "plan_id": str(uuid.uuid4()),
            "objective": objective,
            "tasks": [
                {"task_id": "research_1", "description": "Ricerca dati", "priority": 3, "critical": True},
                {"task_id": "code_1", "description": "Scrivi codice", "priority": 4, "critical": True},
                {"task_id": "review_1", "description": "Revisiona", "priority": 2, "critical": False}
            ],
            "expected_outputs_schema": {
                "research_1": "dataset_summary",
                "code_1": "code_snippet",
                "review_1": "feedback_points"
            },
            "synthesis_strategy": "parallel_merge"
        }

    async def execute_agent_task(self, task: TaskDefinition) -> Dict[str, Any]:
        start_time = time.time()
        await asyncio.sleep(0.2)  # Simula esecuzione
        
        # Log del messaggio inviato all'agente
        await self.debug_logger.log_message_to_agent(
            agent_id=task.task_id,
            task=task,
            message={"task_id": task.task_id, "description": task.description}
        )
        
        # Simulazione realistica: a volte fallisce
        if task.task_id == "review_1" and False:  # Disabilitato per demo
            execution_time_ms = (time.time() - start_time) * 1000
            error_response = {"status": "error", "message": "Timeout simulato"}
            
            # Log dell'errore
            await self.debug_logger.log_error(
                agent_id=task.task_id,
                task=task,
                error="Timeout simulato",
                execution_time_ms=execution_time_ms
            )
            return error_response
        
        response = {
            "status": "success",
            "content": {
                f"output_{task.task_id}": f"Dati generati per {task.description}",
                "confidence": 0.95
            }
        }
        
        execution_time_ms = (time.time() - start_time) * 1000
        
        # Log della risposta dall'agente
        await self.debug_logger.log_response_from_agent(
            agent_id=task.task_id,
            task=task,
            response=response,
            execution_time_ms=execution_time_ms,
            status="success"
        )
        
        return response

    async def synthesize_final_answer(self, prompt: str) -> str:
        await asyncio.sleep(0.3)
        return f"Sintesi finale basata su: {prompt[:50]}..."


class Orchestrator:
    """
    Orchestratore CESARE 2.0 con validazione rigorosa e Clean-Pipe.
    Include funzionalità di debug per tracciare le comunicazioni con gli agenti.
    """

    def __init__(self, debug_enabled: bool = False):
        self.debug_logger = DebugLogger(enabled=debug_enabled)
        self.llm = MockLLMProvider(debug_logger=self.debug_logger)
        self.assembly_engine = AssemblyEngine()
        self.json_parser = RobustJSONParser()
        self.active_plans: Dict[str, OrchestratorPlan] = {}
    
    def enable_debug(self):
        """Abilita il logging di debug per tracciare le comunicazioni con gli agenti."""
        self.debug_logger.enable()
    
    def disable_debug(self):
        """Disabilita il logging di debug."""
        self.debug_logger.disable()
    
    def is_debug_enabled(self) -> bool:
        """Restituisce True se il debug logging è abilitato."""
        return self.debug_logger.is_enabled()
    
    def get_debug_messages(self) -> List[Dict[str, Any]]:
        """
        Restituisce tutti i messaggi di debug registrati come dictionary.
        Utile per visualizzare nella UI gli scambi tra Cesare e gli agenti.
        """
        return self.debug_logger.to_dict()
    
    def clear_debug_messages(self):
        """Pulisce tutti i messaggi di debug registrati."""
        self.debug_logger.clear()

    async def execute_task(self, objective: str) -> Dict[str, Any]:
        """
        Esegue un task completo dall'analisi alla sintesi finale.
        """
        logger.info(f"Avvio esecuzione task: {objective}")
        
        # FASE 1: Generazione Piano (con validazione Pydantic)
        raw_plan = await self.llm.generate_plan(objective)
        try:
            plan = OrchestratorPlan(**raw_plan)
            logger.info(f"Piano generato: {plan.plan_id}")
        except Exception as e:
            logger.error(f"Validazione piano fallita: {e}")
            return {"status": "error", "message": f"Schema drift nel piano: {str(e)}"}

        # FASE 2: Esecuzione Parallela degli Agenti
        results = await self._execute_agents_parallel(plan.tasks)
        
        # FASE 3: Validazione e Graceful Degradation
        is_valid, critical_errors = self.assembly_engine.validate_results(results, plan)
        
        if not is_valid:
            logger.warning(f"Esecuzione parziale. Errori critici: {critical_errors}")
            # Qui si potrebbe implementare un retry automatico o notifica
        
        # FASE 4: Assembly del Contesto (Clean-Pipe)
        context = self.assembly_engine.assemble_context(results, plan)
        
        # FASE 5: Sintesi Finale (senza JSON grezzo nel prompt)
        synthesis_prompt = self.assembly_engine.render_prompt(context)
        final_answer = await self.llm.synthesize_final_answer(synthesis_prompt)
        
        return {
            "status": "completed" if is_valid else "partial_success",
            "plan_id": plan.plan_id,
            "final_answer": final_answer,
            "critical_failures": context.critical_failures,
            "metadata": context.metadata
        }

    async def _execute_agents_parallel(self, tasks: List[TaskDefinition]) -> List[AgentResult]:
        """
        Esegue i task in parallelo e valida ogni risultato con Pydantic.
        """
        async def run_single_task(task: TaskDefinition) -> AgentResult:
            start_time = time.time()
            try:
                raw_result = await self.llm.execute_agent_task(task)
                
                # Parsing robusto dell'output LLM
                if isinstance(raw_result, str):
                    parsed_data, error = self.json_parser.parse(raw_result)
                    if error:
                        raise ValueError(error)
                else:
                    parsed_data = raw_result
                
                execution_time = (time.time() - start_time) * 1000
                
                # Validazione rigorosa con Pydantic
                status = ExecutionStatus.SUCCESS if parsed_data.get("status") == "success" else ExecutionStatus.CRITICAL_FAIL
                return AgentResult(
                    agent_id=task.task_id,
                    role=AgentRole.RESEARCHER,  # Semplificato per demo
                    status=status,
                    content=parsed_data.get("content", {}),
                    error_message=parsed_data.get("message"),
                    execution_time_ms=execution_time
                )
                
            except Exception as e:
                execution_time = (time.time() - start_time) * 1000
                logger.error(f"Task {task.task_id} fallito: {e}")
                return AgentResult(
                    agent_id=task.task_id,
                    role=AgentRole.RESEARCHER,
                    status=ExecutionStatus.CRITICAL_FAIL if task.critical else ExecutionStatus.PARTIAL_FAILURE,
                    content={},
                    error_message=str(e),
                    execution_time_ms=execution_time
                )

        # Esecuzione concorrente
        coroutines = [run_single_task(task) for task in tasks]
        results = await asyncio.gather(*coroutines)
        return list(results)
