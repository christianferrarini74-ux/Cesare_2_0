import os
import yaml
import logging
from pathlib import Path

logger = logging.getLogger("CESARE.Setup")

def load_config(config_path: str = "config.yaml") -> dict:
    """Carica il file di configurazione YAML."""
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Configurazione non trovata: {config_path}")
    
    with open(config_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f)

def ensure_system_paths(config: dict):
    """
    Analizza ricorsivamente la sezione 'paths' della configurazione e assicura
    che ogni directory e file di base (log, markdown) esistano nel filesystem.
    """
    def process_entry(entry):
        if isinstance(entry, str):
            # Identifica se la stringa è un percorso (assoluto o con separatori)
            if os.path.isabs(entry) or "\\" in entry or "/" in entry:
                path = Path(entry)
                
                # Se il percorso ha un'estensione (es. .db, .log, .md), lo trattiamo come file
                if path.suffix:
                    # Assicura che la directory genitrice esista
                    if not path.parent.exists():
                        path.parent.mkdir(parents=True, exist_ok=True)
                        logger.info(f"Creata directory per file: {path.parent}")
                    
                    # Crea file vuoti per log e bibbia se mancano
                    # Nota: i file .db vengono creati automaticamente dai driver DB
                    if not path.exists() and path.suffix in ['.log', '.md', '.txt']:
                        path.touch()
                        logger.info(f"Inizializzato file: {path}")
                else:
                    # Lo trattiamo come una directory
                    if not path.exists():
                        path.mkdir(parents=True, exist_ok=True)
                        logger.info(f"Creata directory: {path}")

        elif isinstance(entry, dict):
            for value in entry.values():
                process_entry(value)
        elif isinstance(entry, list):
            for item in entry:
                process_entry(item)

    # Avvia la scansione dalla radice della sezione paths
    if 'paths' in config:
        logger.info("Verifica integrità percorsi in corso...")
        process_entry(config['paths'])
    else:
        logger.warning("Sezione 'paths' non trovata nel file di configurazione.")
    logger.info("Inizializzazione filesystem completata.")