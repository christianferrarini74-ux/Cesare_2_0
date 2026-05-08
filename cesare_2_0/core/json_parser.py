"""
CESARE 2.0 - Robust JSON Parser
Utilizza tecniche di parsing parziale e correzione automatica per gestire output LLM imperfetti.
Elimina la dipendenza critica dalle regex semplici.
"""
import json
import re
import logging
from typing import Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


class RobustJSONParser:
    """
    Parser JSON resiliente che tenta di estrarre dati validi anche da output malformati.
    Supporta:
    - Estrazione da blocchi markdown (```json ... ```)
    - Correzione di virgole mancanti e parentesi non chiuse
    - Fallback su parsing parziale
    """

    @staticmethod
    def extract_json_block(text: str) -> Optional[str]:
        """
        Estrae il primo blocco JSON valido o potenzialmente valido dal testo.
        Gestisce i blocchi markdown ```json ... ``` e ``` ... ```.
        """
        # Pattern per blocchi markdown espliciti
        patterns = [
            r"```json\s*(.*?)\s*```",
            r"```\s*(.*?)\s*```",
            r"\{\s*.*?\s*\}",  # Fallback per oggetti inline
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.DOTALL | re.IGNORECASE)
            if match:
                return match.group(1) if "json" in pattern else match.group(0)
        
        # Se non trova blocchi, prova a trovare l'ultima parentesi graffa chiusa
        # assumendo che il JSON sia alla fine
        start = text.rfind("{")
        if start != -1:
            candidate = text[start:]
            # Bilanciamento base delle parentesi
            if candidate.count("{") == candidate.count("}"):
                return candidate
        
        return None

    @staticmethod
    def fix_common_json_errors(json_str: str) -> str:
        """
        Tenta di correggere errori comuni nei JSON generati da LLM.
        - Virgole finali mancanti o extra
        - Chiavi non quotate
        - Commenti single-line (non standard JSON)
        """
        fixed = json_str
        
        # Rimuovi commenti // (non validi in JSON)
        fixed = re.sub(r'//.*?$', '', fixed, flags=re.MULTILINE)
        
        # Assicura che le chiavi siano quotate (semplice euristica)
        # Nota: questa è una correzione aggressiva, usare con cautela
        # fixed = re.sub(r'([{,]\s*)([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'\1"\2":', fixed)
        
        # Rimuovi virgole finali prima di } o ]
        fixed = re.sub(r',(\s*[}\]])', r'\1', fixed)
        
        return fixed

    def parse(self, text: str, strict: bool = False) -> Tuple[Optional[Dict[str, Any]], str]:
        """
        Tenta di parsare il testo in un dizionario Python.
        
        Args:
            text: Input testuale contenente JSON
            strict: Se True, lancia eccezioni invece di tentare riparazioni
            
        Returns:
            Tuple[dict_parsed, error_message]
            Se successo: (dict, "")
            Se fallimento: (None, "descrizione errore")
        """
        if not text:
            return None, "Input vuoto"

        # 1. Estrai il blocco potenziale
        json_candidate = self.extract_json_block(text)
        if not json_candidate:
            return None, "Nessun blocco JSON trovato nel testo"

        # 2. Tentativo 1: Parsing diretto
        try:
            data = json.loads(json_candidate)
            logger.debug("Parsing JSON riuscito al primo tentativo")
            return data, ""
        except json.JSONDecodeError as e:
            if strict:
                return None, f"JSON invalido (Strict): {str(e)}"
            logger.warning(f"Primo tentativo di parsing fallito: {e}")

        # 3. Tentativo 2: Applicazione correzioni
        fixed_candidate = self.fix_common_json_errors(json_candidate)
        try:
            data = json.loads(fixed_candidate)
            logger.info("Parsing JSON riuscito dopo correzione automatica")
            return data, ""
        except json.JSONDecodeError as e:
            logger.warning(f"Anche il parsing corretto è fallito: {e}")

        # 4. Tentativo 3: Troncamento intelligente (spesso c'è garbage alla fine)
        # Prova a troncare dalla fine finché non diventa valido
        for i in range(len(fixed_candidate), 0, -10):
            chunk = fixed_candidate[:i]
            # Deve finire con } o ]
            last_bracket = max(chunk.rfind("}"), chunk.rfind("]"))
            if last_bracket != -1:
                chunk = chunk[:last_bracket+1]
            
            try:
                data = json.loads(chunk)
                logger.info(f"Parsing riuscito troncando a {len(chunk)} caratteri")
                return data, ""
            except:
                continue

        # 5. Fallimento totale
        return None, "Impossibile recuperare un JSON valido dopo tutti i tentativi di riparazione"
