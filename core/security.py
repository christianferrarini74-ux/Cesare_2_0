import os
from pathlib import Path
import logging

logger = logging.getLogger("CESARE.Security")

def validate_path(path: str, workspace_dir: str) -> str:
    """
    Verifica che il path sia all'interno della sandbox del workspace.
    Previene attacchi di Directory Traversal.
    """
    # Risolvi workspace con realpath (segue symlink)
    abs_workspace = os.path.realpath(os.path.abspath(workspace_dir))
    
    # Protezione contro raddoppio 'workspace/' indotto dall'LLM
    p_parts = list(Path(path).parts)
    while p_parts and (p_parts[0].lower() in ('workspace', '.') or p_parts[0] in ('/', '\\')):
        p_parts.pop(0)
    clean_path = os.path.join(*p_parts) if p_parts else "."
    
    # Risolvi target con realpath (segue symlink)
    abs_target = os.path.realpath(os.path.abspath(os.path.join(abs_workspace, clean_path)))
    
    if not abs_target.startswith(abs_workspace):
        logger.warning(f"Tentativo di violazione sandbox: {path}")
        raise PermissionError("Accesso negato: non puoi uscire dal workspace di CESARE.")
    
    return abs_target

def audit_log(action: str, details: str):
    """
    Registra ogni azione sensibile come richiesto dalla Bibbia.
    """
    logger.info(f"AUDIT | {action} | {details}")

def check_override(text: str, secret_code: str = "CESARE_2024") -> bool:
    """
    Verifica il protocollo BIBBIA OVERRIDE.
    """
    return f"BIBBIA OVERRIDE: {secret_code}" in text