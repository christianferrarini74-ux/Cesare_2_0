"""
MiniCesare Ricercatore.
Clone completo di CESARE con identità orientata alla ricerca e all'analisi.
Può scrivere file, eseguire codice, usare il web — è un agente completo.
"""
from .base_agent import MiniCesare


class ResearcherAgent(MiniCesare):
    def __init__(self, config: dict):
        super().__init__(config, "researcher")
