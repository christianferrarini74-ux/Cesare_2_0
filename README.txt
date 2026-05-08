=======================================================================
          CESARE - AGENTE AUTONOMO LOCALE (VERSIONE PROFESSIONALE)
=======================================================================

CESARE è un agente autonomo basato su LangGraph e Ollama, progettato per
operare in locale con massima sicurezza, audit log e gestione documentale.

-----------------------------------------------------------------------
1. REQUISITI PRELIMINARI
-----------------------------------------------------------------------
- Python 3.12 o superiore.
- Ollama (scaricabile da https://ollama.com).
- Modello LLM scaricato tramite Ollama (es: qwen3.5:35b o qwen2.5:7b).
  Comando: ollama pull qwen3.5:35b

-----------------------------------------------------------------------
2. INSTALLAZIONE DIPENDENZE PYTHON
-----------------------------------------------------------------------
Aprire il terminale nella cartella del progetto ed eseguire:

pip install -r requirements.txt

-----------------------------------------------------------------------
3. DIPENDENZE DI SISTEMA (OBBLIGATORIE PER OCR, PDF E VIDEO)
-----------------------------------------------------------------------
Per permettere a CESARE di leggere PDF scansionati, immagini e 
processare video, è necessario installare i seguenti componenti:

A) TESSERACT OCR:
   - Windows: Scaricare l'installer da https://github.com/UB-Mannheim/tesseract/wiki
   - Aggiungere il percorso di installazione (es. C:\Program Files\Tesseract-OCR) 
     alle Variabili di Ambiente del sistema (PATH).

B) POPPLER (per pdf2image):
   - Windows: Scaricare i binari (es. da @oschwartz10612 su GitHub).
   - Estrarre la cartella e aggiungere la sottocartella /bin al PATH di sistema.

C) FFMPEG (per la trascrizione video):
   - Windows: Scaricare i binari da https://www.gyan.dev/ffmpeg/builds/
   - Estrarre la cartella e aggiungere la sottocartella /bin al PATH di sistema.
   - Verificare l'installazione nel terminale con il comando: ffmpeg -version

-----------------------------------------------------------------------
4. CONFIGURAZIONE
-----------------------------------------------------------------------
Modificare il file 'config.yaml' per definire i percorsi del workspace,
del database e della Bibbia. Assicurarsi che le cartelle indicate esistano
o che l'utente abbia i permessi di creazione.

-----------------------------------------------------------------------
5. AVVIO DEL PROGRAMMA
-----------------------------------------------------------------------
Modalità Interfaccia Grafica (Consigliata):
   streamlit run gui/app.py

Modalità Headless (Telegram/Scheduler):
   python main.py