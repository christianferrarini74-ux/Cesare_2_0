from apscheduler.schedulers.blocking import BlockingScheduler
import logging
import time

logger = logging.getLogger("CESARE.Scheduler")

class CesareScheduler:
    def __init__(self, config, agente):
        self.config = config
        self.agente = agente
        self.scheduler = BlockingScheduler()
        self._setup_jobs()

    def _setup_jobs(self):
        interval = self.config.get('scheduler', {}).get('check_interval_seconds', 60)
        self.scheduler.add_job(self.check_system_health, 'interval', seconds=interval)

    def check_system_health(self):
        """Esempio di task proattivo"""
        logger.info("Esecuzione controllo di routine del sistema...")
        # Qui l'agente potrebbe fare un'auto-analisi del workspace
        # result = self.agente.run("Esegui un check del workspace e segnala anomalie.")

    def run(self):
        try:
            self.scheduler.start()
        except (KeyboardInterrupt, SystemExit):
            pass