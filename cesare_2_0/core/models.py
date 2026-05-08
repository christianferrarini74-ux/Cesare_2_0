"""
CESARE 2.0 - Strictly Typed Data Models
Utilizza Pydantic V2 per garantire la validazione a runtime e prevenire Schema Drift.
"""
from pydantic import BaseModel, Field, validator
from typing import List, Dict, Any, Optional, Literal
from enum import Enum
from datetime import datetime


class AgentRole(str, Enum):
    RESEARCHER = "researcher"
    CODER = "coder"
    ANALYST = "analyst"
    REVIEWER = "reviewer"
    COORDINATOR = "coordinator"
    SYNTHESIZER = "synthesizer"


class ExecutionStatus(str, Enum):
    PENDING = "pending"
    SUCCESS = "success"
    PARTIAL_FAILURE = "partial_failure"
    CRITICAL_FAIL = "critical_fail"
    TIMEOUT = "timeout"


class AgentResult(BaseModel):
    """
    Risultato validato di un singolo agente.
    Garantisce che ogni output abbia uno stato chiaro e dati strutturati.
    """
    agent_id: str
    role: AgentRole
    status: ExecutionStatus
    content: Dict[str, Any]  # Dati strutturati specifici del task
    error_message: Optional[str] = None
    execution_time_ms: float
    timestamp: datetime = Field(default_factory=datetime.now)

    @validator('content')
    def ensure_content_not_empty_on_success(cls, v, values):
        if values.get('status') == ExecutionStatus.SUCCESS and not v:
            raise ValueError("Success status requires non-empty content")
        return v


class TaskDefinition(BaseModel):
    """Definizione tipizzata di un task da eseguire."""
    task_id: str
    description: str
    priority: int = Field(ge=1, le=5)
    dependencies: List[str] = []  # ID dei task da completare prima
    timeout_seconds: float = 30.0
    critical: bool = True  # Se False, il fallimento è gestibile (graceful degradation)


class OrchestratorPlan(BaseModel):
    """
    Piano d'azione generato dal Coordinatore.
    Definisce il contratto esatto tra orchestrazione ed esecuzione.
    """
    plan_id: str
    objective: str
    tasks: List[TaskDefinition]
    expected_outputs_schema: Dict[str, str]  # Mappa: task_id -> descrizione chiave output attesa
    synthesis_strategy: Literal["sequential", "parallel_merge", "conditional"]
    
    class Config:
        frozen = True  # Il piano non deve essere modificato dopo la creazione


class SynthesisContext(BaseModel):
    """
    Contesto pulito preparato per il Sintetizzatore.
    Non contiene JSON grezzi, ma campi già popolati e validati.
    """
    objective: str
    summary_results: Dict[str, str]  # Mappa task_id -> riassunto testuale sicuro
    critical_failures: List[str]  # Lista di ID task falliti criticamente
    metadata: Dict[str, Any]
