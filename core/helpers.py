import os
import yaml
from pathlib import Path


def ensure_config_paths_exist(paths_config: dict, base_dir: str | Path):
    """
    Verifica/crea tutti i path definiti in config['paths'] (anche annidati).
    Se il path sembra un file, crea la directory padre; altrimenti crea la directory stessa.
    """
    base_path = Path(base_dir)

    def _ensure(node):
        if isinstance(node, dict):
            for v in node.values():
                _ensure(v)
            return

        if not isinstance(node, str):
            return

        p = Path(node)
        if not p.is_absolute():
            p = base_path / p

        if p.suffix:
            p.parent.mkdir(parents=True, exist_ok=True)
        else:
            p.mkdir(parents=True, exist_ok=True)

    _ensure(paths_config)

def init_cesare_workspace(base_path: str):
    """
    Inizializza la struttura delle cartelle di CESARE se non esistono.
    L'utente fornisce la directory base, CESARE crea il resto.
    """
    base = Path(base_path)
    folders = [
        base / "workspace",
        base / "workspace" / "memory" / "vector_index",
        base / "workspace" / "logs",
        base / "workspace" / "chronos",
        base / "workspace" / "context",
        base / "tools" / "custom"
    ]
    
    for folder in folders:
        folder.mkdir(parents=True, exist_ok=True)

    (base / "workspace" / "logs" / "audit.log").touch(exist_ok=True)

    # Template per config.yaml se manca
    config_path = base / "config.yaml"
    if not config_path.exists():
        default_config = {
            "agent": {
                "model": "gemma4",
                "temperature": 0.1,
                "base_url": "http://localhost:11434"
            },
            "paths": {
                "bible": "bible.md",
                "workspace": "workspace",
                "tier1_db": "workspace/logs/interactions.db",
                "tier2_db": "workspace/memory/rom.db",
                "tier3_db": "workspace/memory/experience.db",
                "calendar_db": "workspace/chronos/calendar.db",
                "vector_db": "workspace/memory/vector_index",
                "logs": "workspace/logs/audit.log"
            },
            "channels": {
                "telegram": {"enabled": False, "token": "TOKEN_HERE"}
            },
            "scheduler": {"active": True},
            "video": {
                "model_size": "base",
                "device": "cpu",
                "compute_type": "int8",
                "ffmpeg_path": "ffmpeg"
            }
        }
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(default_config, f, default_flow_style=False)
    # Template per bible.md completo (La Legge) (rimane al root del progetto)
    bible_path = base / "bible.md" 
    if not bible_path.exists():
        bible_content = """# LA BIBBIA DI CESARE

## REGOLE ASSOLUTE
1. **SANDBOX**: Non puoi MAI scrivere o leggere file al di fuori della cartella `./workspace/`.
2. **IDENTITÀ**: Sei CESARE, un agente autonomo locale.
3. **SICUREZZA**: Ogni azione distruttiva deve essere loggata tramite `audit_log`.
4. **SUPREMAZIA**: Questo file è la legge suprema.
5. **INVIOLABILITÀ**: Tu non puoi modificare questo file (bible.md). Solo l'utente tramite GUI può farlo.
## PROTOCOLLI DI RAGIONAMENTO
- Inizia ogni risposta interna con: "Rispettando la Bibbia al 100%..."

## PROTOCOLLI DI GESTIONE DOCUMENTI
- Per leggere file .docx, usa 'read_docx'.
- Per creare file .docx, usa 'create_docx'.
- Per leggere file .pdf, usa 'read_pdf'.
- Per leggere file .xlsx (Excel), usa 'read_xlsx'. Puoi specificare il nome del foglio.
- Per creare file .xlsx (Excel) da dati CSV, usa 'create_xlsx'. Puoi specificare il nome del foglio.
- NON usare 'read_file' o 'write_file' per questi formati specifici.



## BIBBIA OVERRIDE
- Riservato al Creatore.
[FINE DELLA BIBBIA]"""
        with open(bible_path, "w", encoding="utf-8") as f:
            f.write(bible_content)

def get_validated_config(base_path: str):
    """
    Carica il config.yaml e rende tutti i percorsi assoluti rispetto alla base_path.
    """
    config_path = Path(base_path) / "config.yaml"
    if not config_path.exists():
        return {}

    with open(config_path, "r", encoding="utf-8") as f:
        config = yaml.safe_load(f)

    # Rende tutti i percorsi nel config ASSOLUTI rispetto alla root del progetto
    if 'paths' in config:
        # Assicura retrocompatibilità per la nuova chiave calendar_db
        default_paths = {
            "calendar_db": "workspace/chronos/calendar.db",
            "tier1_db": "workspace/logs/interactions.db",
            "tier2_db": "workspace/memory/rom.db",
            "tier3_db": "workspace/memory/experience.db",
            "vector_db": "workspace/memory/vector_index"
        }
        for k, v in default_paths.items():
            if k not in config['paths']:
                config['paths'][k] = v
            
        def resolve_paths(node):
            if isinstance(node, dict):
                for key, val in node.items():
                    node[key] = resolve_paths(val)
                return node
            elif isinstance(node, str):
                if not os.path.isabs(node):
                    return str((Path(base_path) / node).absolute())
                else:
                    return os.path.abspath(node)
            return node

        config['paths'] = resolve_paths(config['paths'])
        ensure_config_paths_exist(config['paths'], base_path)

    return config

def save_config(base_path: str, data: dict):
    path = Path(base_path) / "config.yaml"
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f)
