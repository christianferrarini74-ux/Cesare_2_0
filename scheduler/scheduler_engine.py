import time
import threading
import logging
import os
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from core.helpers import get_validated_config
from core.memory import CesareMemory
from core.graph import get_cesare_app

logger = logging.getLogger("CESARE.Chronos")

def run_task(config, task_id, title, description, target_folder):
    """Esegue un task proattivo in modalità silent."""
    try:
        logger.info(f"Avvio Task: {title} (ID: {task_id})")
        
        paths = config.get('paths', {})
        memory = CesareMemory(paths)
        
        # Inizializza l'agente con il root temporaneo (context_folder)
        cesare = get_cesare_app(config, context_folder=target_folder)
        
        # Preparazione prompt di trigger
        context_msg = f"TASK AUTOMATICO: {description}. "
        if target_folder:
            context_msg += f"Le tue operazioni sono focalizzate sulla cartella context: '{target_folder}'. "
        context_msg += "Esegui ora il compito e fornisci un report sintetico."

        # Invocazione
        result = cesare.invoke({"messages": [{"role": "user", "content": context_msg}]})
        response = result["messages"][-1].content
        
        # Update status
        memory.update_task_status(task_id, "Completed", response[:500])
        
        # Log su file dedicato
        log_path = os.path.join(os.path.dirname(config['paths']['calendar_db']), "task_history.md")
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"\n## {datetime.now()} | {title}\n**Status:** Completed\n**Response:** {response}\n---\n")
            
    except Exception as e:
        logger.error(f"Errore Task {task_id}: {str(e)}")
        CesareMemory(config['paths']).update_task_status(task_id, "Failed", str(e))

def scheduler_loop(config):
    """Loop principale dello scheduler Chronos."""
    scheduler = BackgroundScheduler()
    memory = CesareMemory(config['paths'])
    
    # Determiniamo la directory di base (root) per ricaricare il config
    work_dir = os.path.dirname(config['paths']['bible'])

    def check_jobs():
        # Ricarica configurazione fresca per vedere cambi su switch PLAY/PAUSE e percorsi
        fresh_config = get_validated_config(work_dir)
        if not fresh_config.get('scheduler', {}).get('active', True):
            return
            
        paths = fresh_config.get('paths', {})
        # Utilizziamo una istanza di memoria aggiornata se i percorsi sono cambiati
        fresh_memory = CesareMemory(fresh_config['paths'])
        due_tasks = fresh_memory.get_due_tasks()
        
        for task in due_tasks:
            # task: (id, title, description, trigger_time, recurrence, target_folder, status, last_log)
            fresh_memory.update_task_status(task[0], "Running")
            # Esegui in un nuovo thread per non bloccare lo scheduler
            threading.Thread(target=run_task, args=(fresh_config, task[0], task[1], task[2], task[5])).start()

    scheduler.add_job(check_jobs, 'interval', seconds=60)
    scheduler.start()
    logger.info("Chronos Engine avviato.")
    while True:
        time.sleep(10)

def start_scheduler(config):
    """Avvia il thread dello scheduler."""
    t = threading.Thread(target=scheduler_loop, args=(config,), daemon=True)
    t.start()