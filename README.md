# Cesare_2_0

**Un Agente AI Autonomo Locale con Memoria Gerarchica 3-Tier e Sandbox Rigida**

![Python](https://img.shields.io/badge/Python-3776AB?logo=python&logoColor=white)
![LangGraph](https://img.shields.io/badge/LangGraph-000000?logo=langchain&logoColor=white)
![Ollama](https://img.shields.io/badge/Ollama-000000?logo=ollama&logoColor=white)
![Streamlit](https://img.shields.io/badge/Streamlit-FF4B4B?logo=streamlit&logoColor=white)

**Cesare 2.0** è un agente AI completamente locale, autonomo e auto-migliorante, progettato per chi vuole un'intelligenza artificiale potente, privata e sotto il proprio controllo.

Sviluppato in tempo libero da una sola persona, Cesare_2_0 dimostra che è possibile raggiungere un'architettura sofisticata senza budget aziendali multimilionari.

## ✨ Caratteristiche Principali

- **Memoria a 3 Tier** (una delle implementazioni più complete in ambito open-source):
  - **Tier 1** — Memoria effimera/sessionale (SQLite)
  - **Tier 2** — ROM (Fatti permanenti e preferenze dell'utente) con ChromaDB
  - **Tier 3** — Experience / Growth Seeds (auto-apprendimento da successi ed errori)

- **Sandbox di Sicurezza Estrema**:
  - Tutte le operazioni filesystem sono confinate in `./workspace/`
  - Audit log obbligatorio su ogni azione
  - "Bible Override" solo per il creatore

- **Architettura Multi-Agente** (LangGraph):
  - Modalità Singolo o **Team** (Orchestrator + Researcher + Programmer + Worker)

- **Interfaccia Streamlit** moderna e intuitiva (multi-pagina)
- **Chronos Scheduler** — Gestione task temporizzati e agenda persistente
- **Tooling Ricco**:
  - Navigazione web (Playwright + DuckDuckGo)
  - Lettura/scrittura documenti Office, PDF, EPUB
  - OCR, analisi immagini, trascrizione video/audio
  - Query SQLite, gestione archivi, ecc.

- **Self-Improvement** tramite nodo **Reflect** che genera "Semi di Crescita"
- **100% Locale** — Nessun dato esce dal tuo computer (Ollama)
- **Pronto per l'eseguibile** (PyInstaller spec incluso)

## Perché Cesare_2_0 è speciale

Mentre molti progetti open-source si fermano a semplici wrapper intorno a LangChain, Cesare_2_0 introduce:

- Una vera **memoria gerarchica ispirata al cervello umano**
- Un sistema di **auto-riflessione** che permette all'agente di imparare dai propri errori
- Una **sandbox ferrea** pensata per l'uso reale quotidiano
- Un approccio "Bibbia" (regole supreme immutabili) che garantisce sicurezza e coerenza

È uno dei pochi progetti open-source che prova a creare un agente che non solo esegue, ma **impara e cresce** nel tempo.

## Architettura

```
core/          → Graph LangGraph, memoria, sicurezza, helpers
agents/        → Logica multi-agente
tools/         → Tutti i tool (sandboxed)
gui/           → Interfaccia Streamlit + gestione memoria
scheduler/     → Chronos (task scheduling)
workspace/     → Tutto ciò che l'agente può modificare
bible.md       → Regole supreme del sistema
```

## Installazione

```bash
git clone https://github.com/christianferrarini74-ux/Cesare_2_0.git
cd Cesare_2_0

# Crea ambiente (consigliato)
python -m venv venv
source venv/bin/activate    # Windows: venv\Scripts\activate

pip install -r requirements.txt

# Scarica il modello Ollama (esempio)
ollama pull gemma4:26b      # o il modello che preferisci
```

### Avvio

```bash
streamlit run main.py
```

## Configurazione

Modifica `config.yaml` per:
- Modello Ollama da usare
- Modalità (single/team)
- Isolamento memoria per agente
- Chiavi API (opzionali)

## Screenshots

*(Aggiungi qui immagini della GUI quando disponibili)*

- Dashboard
- Chat con memoria visibile
- Pagina Memoria 3-Tier
- Chronos Scheduler
- Editor Bibbia

## Roadmap Futura

- Miglioramento continuo del Tier 3 (distillazione automatica)
- Integrazione vocale (STT/TTS)
- Multi-modalità avanzata
- Supporto per tool esterni sicuri
- Versione desktop (PyInstaller one-file)
- Community contributions guidelines

## Filosofia

> "Ogni comodità è un limite."  
> — Cesare

L'agente è progettato per essere rigoroso, sicuro e in continua evoluzione.

## Autore

Sviluppato da **Christian Ferrarini** in tempo libero, fuori dall'orario di lavoro.

Se trovi valore in questo progetto, una stella ⭐ è il modo migliore per supportare lo sviluppo.

## License

MIT License — Sei libero di usarlo, modificarlo e migliorarlo.

---

**Cesare_2_0** — Non è solo un altro agente AI.  
È un tentativo serio di costruire qualcosa di duraturo, privato e intelligente.

**Benvenuto nel futuro degli agenti personali open-source.**
```
