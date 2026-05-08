"""
MiniCesare Programmatore.
Clone completo di CESARE con identità orientata al codice.
Ha accesso a tutti i tool — può navigare il web, leggere repository,
scrivere file, eseguire ricerche. La specializzazione è nella memoria
e nel modello LLM scelto, non nei permessi.
"""
from .base_agent import MiniCesare


class ProgrammerAgent(MiniCesare):
    def __init__(self, config: dict):
        super().__init__(config, "programmer")
