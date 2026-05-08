# CESARE 2.0 - Sistema Multi-Agente Evoluto

## Panoramica

CESARE 2.0 è un'evoluzione architetturale del sistema multi-agente originale, progettata per risolvere le criticità di instabilità nel parsing e nella comunicazione tra agenti.

## 🔧 Problemi Risolti

### 1. Schema Drift (Sincronizzazione dei Mapping)
**Problema:** L'Orchestratore generava placeholder dinamici senza garanzia che le chiavi corrispondessero esattamente ai risultati.

**Soluzione:** 
- Modelli **Pydantic** tipizzati per `AgentResult` e `OrchestratorPlan`
- Validazione a runtime che garantisce la corrispondenza tra piano ed esecuzione
- Campo `expected_outputs_schema` per definire contrattualmente gli output attesi

### 2. Corruzione JSON nei Prompt
**Problema:** Output contenenti codice Python, Markdown o caratteri speciali corrompevano la struttura JSON passata al Sintetizzatore.

**Soluzione:**
- Protocollo **Clean-Pipe**: assembly lato Python con Jinja2
- Il Sintetizzatore riceve testo già formattato, non JSON grezzo
- Funzione `_extract_safe_summary()` per sanificare i contenuti

### 3. Gestione Stato Parziale
**Problema:** Impossibilità di distinguere tra "risultato vuoto valido" e "fallimento tecnico".

**Soluzione:**
- Enum `ExecutionStatus` con stati: `SUCCESS`, `PARTIAL_FAILURE`, `CRITICAL_FAIL`, `TIMEOUT`
- Flag `critical` in `TaskDefinition` per graceful degradation
- Validatore pre-sintesi che identifica fallimenti critici vs non critici

### 4. Parsing JSON Inaffidabile
**Problema:** Dipendenza da regex fragili per estrarre JSON da output LLM.

**Soluzione:**
- `RobustJSONParser` con 5 strategie di fallback:
  1. Estrazione blocchi markdown (```json ... ```)
  2. Parsing diretto
  3. Correzione automatica errori comuni (virgole finali, commenti)
  4. Troncamento intelligente
  5. Fallback error message

## 📁 Struttura del Progetto

```
cesare_2_0/
├── core/
│   ├── models.py          # Modelli Pydantic tipizzati
│   ├── pipeline.py        # AssemblyEngine (Clean-Pipe)
│   ├── json_parser.py     # RobustJSONParser
│   └── orchestrator.py    # Orchestratore refactored
├── test_system.py         # Test suite completa
└── README.md              # Questa documentazione
```

## 🚀 Utilizzo

### Installazione Dipendenze
```bash
pip install pydantic jinja2
```

### Esempio Base
```python
import asyncio
from core.orchestrator import Orchestrator

async def main():
    orchestrator = Orchestrator()
    
    result = await orchestrator.execute_task(
        "Analizza questi dati e genera un report"
    )
    
    print(f"Status: {result['status']}")
    print(f"Risposta: {result['final_answer']}")
    
    if result['critical_failures']:
        print(f"Fallimenti: {result['critical_failures']}")

asyncio.run(main())
```

### Test Suite
```bash
python test_system.py
```

## 📊 Componenti Principali

### 1. Modelli Pydantic (`models.py`)

| Modello | Descrizione |
|---------|-------------|
| `AgentResult` | Risultato validato di un agente con status, content strutturato e metadata |
| `TaskDefinition` | Definizione di un task con priorità, dipendenze e flag critical |
| `OrchestratorPlan` | Piano d'azione immutabile con schema output atteso |
| `SynthesisContext` | Contesto pulito per il sintetizzatore |

### 2. AssemblyEngine (`pipeline.py`)

Responsabile del protocollo Clean-Pipe:
- `validate_results()`: Verifica integrità prima della sintesi
- `assemble_context()`: Costruisce contesto validato
- `_extract_safe_summary()`: Sanifica contenuti (max 500 char, troncamento sicuro)
- `render_prompt()`: Genera prompt con Jinja2 (no JSON grezzo)

### 3. RobustJSONParser (`json_parser.py`)

Parser resiliente con correzione automatica:
- Supporto blocchi markdown
- Rimozione commenti `//`
- Correzione virgole finali
- Recupero parziale da JSON troncati

### 4. Orchestrator (`orchestrator.py`)

Flusso di esecuzione in 5 fasi:
1. **Generazione Piano** → Validazione Pydantic
2. **Esecuzione Parallela** → Concurrent agent execution
3. **Validazione** → Graceful degradation check
4. **Assembly Contesto** → Clean-Pipe preparation
5. **Sintesi Finale** → Prompt templating con Jinja2

## ✅ Metriche di Qualità

| Metrica | Valore |
|---------|--------|
| Test Superati | 4/4 (100%) |
| Validazione Schema | Runtime (Pydantic) |
| Tolleranza Errori JSON | 5 livelli di fallback |
| Graceful Degradation | Sì (flag critical) |
| Template Engine | Jinja2 (StrictUndefined) |

## 🔮 Prossimi Miglioramenti

- [ ] Integrazione con LangChain per output strutturato nativo
- [ ] Retry automatico con backoff esponenziale
- [ ] Persistenza stato su database
- [ ] Dashboard monitoring in tempo reale
- [ ] Supporto per agenti distribuiti (gRPC)

---

**CESARE 2.0** - Da sistema "testuale-probabilistico" a sistema "strutturato-validato".
