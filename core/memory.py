import sqlite3
import chromadb
from datetime import datetime
import os
import time
import uuid

class CesareMemory:
    def __init__(self, config_paths: dict):
        # Riceve i percorsi già pronti dal Config
        self.paths = {k: os.path.abspath(v) if isinstance(v, (str, bytes, os.PathLike)) else v
                      for k, v in config_paths.items()}

        # Retrocompatibilita': supporta sia tierX_db che tierX
        aliases = {
            "tier1": "tier1_db",
            "tier2": "tier2_db",
            "tier3": "tier3_db",
        }
        for old_key, new_key in aliases.items():
            if new_key not in self.paths and old_key in self.paths:
                self.paths[new_key] = self.paths[old_key]

        # Assicura directory
        for p in self.paths.values():
            if isinstance(p, (str, bytes, os.PathLike)):
                p_str = str(p)
                # Se ha estensione, trattiamolo come file e creiamo la parent.
                # Altrimenti, trattiamolo come directory.
                target_dir = os.path.dirname(p_str) if os.path.splitext(p_str)[1] else p_str
                if target_dir:
                    os.makedirs(target_dir, exist_ok=True)

        self._init_dbs()
        
        self.vector_client = chromadb.PersistentClient(path=self.paths['vector_db'])
        # TIER 2: EXPLICIT ROM (Verità Assolute)
        self.rom_collection = self.vector_client.get_or_create_collection(name="cesare_rom")
        # TIER 3: EXPERIENCE LEDGER (Evolutiva)
        self.exp_collection = self.vector_client.get_or_create_collection(name="cesare_experience")

    def _get_conn(self, db_path_key: str):
        """Ritorna una connessione fresca con un timeout di 20 secondi per gestire la concorrenza."""
        return sqlite3.connect(self.paths[db_path_key], timeout=20)

    def _init_dbs(self):
        # TIER 1: Interactions
        with self._get_conn('tier1_db') as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS interactions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    role TEXT,
                    content TEXT
                )
            ''')

        # TIER 2: ROM Explicit Knowledge
        with self._get_conn('tier2_db') as conn:
            conn.execute(
                'CREATE TABLE IF NOT EXISTS rom_metadata (id TEXT PRIMARY KEY, key TEXT, value TEXT, timestamp TEXT)'
            )

        # TIER 3: Experience Ledger
        with self._get_conn('tier3_db') as conn:
            conn.execute('CREATE TABLE IF NOT EXISTS seeds (id TEXT PRIMARY KEY, seed_text TEXT, category TEXT, success_rate REAL)')

        # DB Calendario (Chronos)
        with self._get_conn('calendar_db') as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS calendar_tasks (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT,
                    description TEXT,
                    trigger_time TEXT,
                    recurrence TEXT,
                    target_folder TEXT,
                    status TEXT DEFAULT 'Pending',
                    last_run_log TEXT
                )
            ''')

    def add_interaction(self, role: str, content: str):
        with self._get_conn('tier1_db') as conn:
            conn.execute(
                "INSERT INTO interactions (timestamp, role, content) VALUES (?, ?, ?)",
                (datetime.now().isoformat(), role, content)
            )

    def store_rom(self, text: str, metadata: dict):
        """TIER 2: Solo per fatti espliciti e comandi del Creatore."""
        rom_id = f"rom_{uuid.uuid4().hex}"
        ts = datetime.now().isoformat()

        self.rom_collection.add(
            documents=[text],
            metadatas=[metadata],
            ids=[rom_id]
        )
        # Salvataggio metadata in SQL per GUI e audit locale
        with self._get_conn('tier2_db') as conn:
            conn.execute(
                "INSERT INTO rom_metadata (id, key, value, timestamp) VALUES (?, ?, ?, ?)",
                (rom_id, metadata.get("key", metadata.get("type", "fact")), text, ts)
            )

    def store_experience(self, seed: str, metadata: dict):
        """TIER 3: Incisione del Seme di Crescita (Lezioni apprese)."""
        self.exp_collection.add(
            documents=[seed],
            metadatas=[metadata],
            ids=[f"exp_{uuid.uuid4().hex}"]
        )

    def search_rom(self, query: str, n_results: int = 3):
        results = self.rom_collection.query(query_texts=[query], n_results=n_results)
        return results['documents'][0] if results['documents'] else []

    def search_experience(self, query: str, n_results: int = 3):
        results = self.exp_collection.query(query_texts=[query], n_results=n_results)
        return results['documents'][0] if results['documents'] else []

    def cleanup_old_memory(self, days: int = 30):
        """Rimuove interazioni effimere. ROM ed Esperienza sono PERMANENTI."""
        with self._get_conn('tier1_db') as conn:
            conn.execute("DELETE FROM interactions WHERE timestamp < datetime('now', ?)", (f'-{days} days',))
        return "Cleanup TIER 1 completato."

    def get_due_tasks(self):
        with self._get_conn('calendar_db') as conn:
            now = datetime.now().strftime("%Y-%m-%d %H:%M")
            cursor = conn.execute("SELECT * FROM calendar_tasks WHERE trigger_time <= ? AND status = 'Pending'", (now,))
            return cursor.fetchall()

    def update_task_status(self, task_id, status, log=None):
        with self._get_conn('calendar_db') as conn:
            conn.execute("UPDATE calendar_tasks SET status = ?, last_run_log = ? WHERE id = ?", (status, log, task_id))

    def manage_calendar_db(self, action: str, task_id: int = None, data: dict = None):
        with self._get_conn('calendar_db') as conn:
            cursor = conn.cursor()
            if action == "list":
                cursor.execute("SELECT id, title, trigger_time, status FROM calendar_tasks")
                return str(cursor.fetchall())
            elif action == "create":
                cursor.execute("""
                    INSERT INTO calendar_tasks (title, description, trigger_time, recurrence, target_folder)
                    VALUES (?, ?, ?, ?, ?)
                """, (data.get('title'), data.get('description'), data.get('trigger_time'), data.get('recurrence'), data.get('target_folder')))
                return f"Task '{data.get('title')}' programmato con successo."
            elif action == "delete" and task_id:
                cursor.execute("DELETE FROM calendar_tasks WHERE id = ?", (task_id,))
                return f"Task {task_id} eliminato."
            return "Azione calendario non valida."

    def dispatch_memory(self, tier: int, content: str, metadata: dict = None):
        """Memory Dispatcher per smistare le informazioni ai tier corretti."""
        if metadata is None: metadata = {"timestamp": str(time.time())}
        if tier == 1:
            self.add_interaction(metadata.get("role", "system"), content)
        elif tier == 2:
            self.store_rom(content, metadata)
        elif tier == 3:
            # Doppio salvataggio: Vettoriale (per RAG) e SQL (per metadati/statistiche)
            seed_id = f"exp_{uuid.uuid4().hex}"
            self.exp_collection.add(documents=[content], metadatas=[metadata], ids=[seed_id])
            with self._get_conn('tier3_db') as conn:
                conn.execute("INSERT INTO seeds (id, seed_text, category) VALUES (?, ?, ?)", 
                             (seed_id, content, metadata.get("category", "general")))
