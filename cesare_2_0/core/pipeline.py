"""
CESARE 2.0 - Clean-Pipe Assembly Engine
Implementa il protocollo di interscambio "Clean-Pipe" per eliminare i rischi di JSON corruption.
Utilizza Jinja2 per il templating sicuro lato Python prima dell'invio all'LLM.
"""
from jinja2 import Template, StrictUndefined
from typing import Dict, List, Any
import logging

from .models import AgentResult, OrchestratorPlan, SynthesisContext, ExecutionStatus

logger = logging.getLogger(__name__)


class AssemblyEngine:
    """
    Motore di assemblaggio che trasforma risultati grezzi in un contesto pulito.
    Previene l'iniezione di JSON malformati nei prompt di sistema.
    """

    def __init__(self):
        # Template sicuro per la sintesi finale
        self.synthesis_template = Template("""
# Obiettivo: {{ objective }}

## Stato Esecuzione
{% if critical_failures %}
⚠️ **ATTENZIONE**: Sono stati rilevati fallimenti critici nei seguenti moduli:
{% for failure in critical_failures %}
- {{ failure }}
{% endfor %}
{% else %}
✅ Tutti i moduli critici hanno completato l'esecuzione con successo.
{% endif %}

## Risultati Parziali
{% for task_id, summary in summary_results.items() %}
### {{ task_id }}
{{ summary }}

{% endfor %}

## Istruzioni per la Sintesi Finale
Genera una risposta coerente basandoti SOLO sui dati sopra riportati.
Se un modulo è fallito, non inventare dati ma segnala esplicitamente il gap informativo.
""", undefined=StrictUndefined)

    def validate_results(self, results: List[AgentResult], plan: OrchestratorPlan) -> tuple[bool, List[str]]:
        """
        Verifica l'integrità dei risultati prima della sintesi (Graceful Degradation).
        Restituisce: (is_valid, list_of_critical_errors)
        """
        critical_errors = []
        result_map = {r.agent_id: r for r in results}

        for task in plan.tasks:
            result = result_map.get(task.task_id)
            
            if not result:
                if task.critical:
                    critical_errors.append(f"Task {task.task_id} mancante (Critical)")
                continue
            
            if result.status == ExecutionStatus.CRITICAL_FAIL:
                critical_errors.append(f"Task {task.task_id} fallito criticamente: {result.error_message}")
            elif result.status == ExecutionStatus.TIMEOUT:
                if task.critical:
                    critical_errors.append(f"Task {task.task_id} timeout (Critical)")
        
        is_valid = len(critical_errors) == 0
        return is_valid, critical_errors

    def assemble_context(self, results: List[AgentResult], plan: OrchestratorPlan) -> SynthesisContext:
        """
        Costruisce un oggetto SynthesisContext validato.
        Estrae solo le informazioni necessarie e le sanifica.
        """
        summary_results = {}
        critical_failures = []

        for result in results:
            if result.status in [ExecutionStatus.CRITICAL_FAIL, ExecutionStatus.TIMEOUT]:
                # Cerchiamo se questo task era critico nel piano
                task_def = next((t for t in plan.tasks if t.task_id == result.agent_id), None)
                if task_def and task_def.critical:
                    critical_failures.append(result.agent_id)
                
                # Aggiungiamo un riassunto sicuro dell'errore
                summary_results[result.agent_id] = f"[ERRORE]: {result.error_message or 'Fallimento sconosciuto'}"
            else:
                # Estraiamo un riassunto testuale sicuro dal content strutturato
                # Evitiamo di passare interi blob JSON o codice
                safe_summary = self._extract_safe_summary(result.content)
                summary_results[result.agent_id] = safe_summary

        context = SynthesisContext(
            objective=plan.objective,
            summary_results=summary_results,
            critical_failures=critical_failures,
            metadata={
                "total_agents": len(results),
                "success_count": sum(1 for r in results if r.status == ExecutionStatus.SUCCESS),
                "plan_id": plan.plan_id
            }
        )
        return context

    def _extract_safe_summary(self, content: Dict[str, Any]) -> str:
        """
        Estrae un riassunto testuale sicuro da un dizionario di contenuti.
        Previene l'iniezione di caratteri speciali o codice non escapato.
        """
        if not content:
            return "Nessun dato disponibile."
        
        # Strategia: prendiamo i primi 2-3 campi rilevanti e li convertiamo in stringa pulita
        lines = []
        for key, value in list(content.items())[:3]:
            val_str = str(value)
            # Troncamento di sicurezza per evitare prompt injection o overflow
            if len(val_str) > 500:
                val_str = val_str[:497] + "..."
            lines.append(f"- **{key}**: {val_str}")
        
        return "\n".join(lines) if lines else "Dati presenti ma non riassumibili."

    def render_prompt(self, context: SynthesisContext) -> str:
        """
        Genera il prompt finale per il Sintetizzatore usando il template Jinja2.
        Garantisce che il testo sia già formattato e privo di errori di sintassi JSON.
        """
        try:
            return self.synthesis_template.render(
                objective=context.objective,
                summary_results=context.summary_results,
                critical_failures=context.critical_failures
            )
        except Exception as e:
            logger.error(f"Errore nel rendering del template: {e}")
            # Fallback di emergenza
            return f"Sintesi per: {context.objective}. Errori critici: {', '.join(context.critical_failures)}."
