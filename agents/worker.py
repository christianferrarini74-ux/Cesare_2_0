"""
MiniCesare Lavoratore.
Clone completo di CESARE con identità orientata all'elaborazione dati
e alla produzione di documenti strutturati.
"""
from .base_agent import MiniCesare


class WorkerAgent(MiniCesare):
    def __init__(self, config: dict):
        super().__init__(config, "worker")
