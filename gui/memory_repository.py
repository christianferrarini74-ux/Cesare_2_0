import sqlite3
import os
from datetime import datetime, timedelta
from typing import List, Optional
from gui.models import MemoryEntry, MemoryTier

class MemoryRepository:
    """
    Livello di astrazione per l'accesso alla memoria di CESARE.
    Gestisce la lettura dai database SQLite esistenti.
    """
    def __init__(self, config_paths: dict):
        self.paths = dict(config_paths)
        # Retrocompatibilita': supporta sia tierX_db che tierX
        if 'tier1_db' not in self.paths and 'tier1' in self.paths:
            self.paths['tier1_db'] = self.paths['tier1']
        if 'tier2_db' not in self.paths and 'tier2' in self.paths:
            self.paths['tier2_db'] = self.paths['tier2']
        if 'tier3_db' not in self.paths and 'tier3' in self.paths:
            self.paths['tier3_db'] = self.paths['tier3']

    def _get_conn(self, db_key: str):
        return sqlite3.connect(self.paths[db_key])

    def get_tier1(self) -> List[MemoryEntry]:
        """Recupera le interazioni recenti (Tier 1)."""
        entries = []
        try:
            with self._get_conn('tier1_db') as conn:
                cursor = conn.execute("SELECT id, timestamp, role, content FROM interactions ORDER BY timestamp DESC")
                for row in cursor.fetchall():
                    ts = datetime.fromisoformat(row[1])
                    # Scadenza fissa a 30 giorni come da specifica
                    expires = ts + timedelta(days=30)
                    entries.append(MemoryEntry(
                        id=f"t1_{row[0]}",
                        tier=MemoryTier.TIER_1,
                        content=row[3],
                        timestamp=ts,
                        summary=f"Interazione {row[2]}",
                        expires_at=expires,
                        tags=[row[2]]
                    ))
        except Exception: pass # In caso di DB mancante o vuoto
        return entries

    def get_tier2(self) -> List[MemoryEntry]:
        """Recupera i fatti permanenti (Tier 2)."""
        # Nota: In un sistema reale, qui si interrogherebbe anche ChromaDB.
        # Per questa UI, leggiamo i metadati salvati su SQLite per la visualizzazione.
        entries = []
        try:
            with self._get_conn('tier2_db') as conn:
                cursor = conn.execute("SELECT id, key, value FROM rom_metadata")
                for row in cursor.fetchall():
                    entries.append(MemoryEntry(
                        id=f"t2_{row[0]}",
                        tier=MemoryTier.TIER_2,
                        content=row[2],
                        timestamp=datetime.now(), # ROM non ha sempre timestamp esplicito
                        summary=row[1],
                        tags=["Permanente", "Fatto"]
                    ))
        except Exception: pass
        return entries

    def get_tier3(self) -> List[MemoryEntry]:
        """Recupera i semi di esperienza (Tier 3)."""
        entries = []
        try:
            with self._get_conn('tier3_db') as conn:
                cursor = conn.execute("SELECT id, seed_text, category, success_rate FROM seeds")
                for row in cursor.fetchall():
                    # Parsing del seed_text per separare Errore e Principio (se possibile)
                    text = row[1]
                    error_part = text.split(". Lezione:")[0] if ". Lezione:" in text else text
                    principle_part = text.split(". Lezione:")[1] if ". Lezione:" in text else "Adattamento dinamico."
                    
                    entries.append(MemoryEntry(
                        id=row[0],
                        tier=MemoryTier.TIER_3,
                        content=text,
                        timestamp=datetime.now(),
                        summary=f"Lezione: {row[2]}",
                        original_error=error_part,
                        corrective_principle=principle_part,
                        tags=[row[2], "Evoluzione"],
                        importance=int(row[3] * 10) if row[3] else 7
                    ))
        except Exception: pass
        return entries

    def get_all(self) -> List[MemoryEntry]:
        """Unifica tutti i tier in un'unica lista."""
        return self.get_tier1() + self.get_tier2() + self.get_tier3()

    def search(self, query: str) -> List[MemoryEntry]:
        """Filtra la memoria in base a una stringa di ricerca."""
        all_mem = self.get_all()
        if not query: return all_mem
        q = query.lower()
        return [e for e in all_mem if q in e.content.lower() or q in e.summary.lower()]

    def get_mock_data(self) -> List[MemoryEntry]:
        """Dati di esempio per dimostrazione UI."""
        return [
            MemoryEntry("m1", MemoryTier.TIER_1, "L'utente ha chiesto di analizzare il file 'report_vendite.pdf'.", 
                        datetime.now(), "Analisi PDF", expires_at=datetime.now() + timedelta(days=12)),
            MemoryEntry("m2", MemoryTier.TIER_2, "Il creatore preferisce risposte concise e codice Python 3.12.", 
                        datetime.now(), "Preferenze Codice", tags=["Config", "User"]),
            MemoryEntry("m3", MemoryTier.TIER_3, 
                        "FALLIMENTO: Tentativo di scrivere in C:/Windows/. Lezione: Rispetta sempre la sandbox ./workspace/.", 
                        datetime.now(), "Violazione Sandbox", 
                        original_error="Tentativo di scrittura fuori workspace", 
                        corrective_principle="Rispetta sempre la sandbox ./workspace/",
                        tags=["Sicurezza"])
        ]
