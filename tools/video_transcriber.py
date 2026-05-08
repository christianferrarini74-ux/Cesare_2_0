import os
import json
import time
import logging
from datetime import datetime
from pathlib import Path
from typing import Dict, Any
from faster_whisper import WhisperModel

from tools.media import extract_audio_from_video
from core.security import validate_path, audit_log

logger = logging.getLogger("CESARE.VideoTranscriber")

class VideoTranscriber:
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.workspace_path = config['paths']['workspace']
        
        # Caricamento parametri Whisper dal config
        video_cfg = config.get('video', {})
        self.model_size = video_cfg.get('model_size', 'base')
        self.device = video_cfg.get('device', 'cpu')
        self.compute_type = video_cfg.get('compute_type', 'int8')
        self.ffmpeg_cmd = video_cfg.get('ffmpeg_path', 'ffmpeg')
        
        self._model = None

    @property
    def model(self):
        """Caricamento lazy del modello Whisper per risparmiare RAM."""
        if self._model is None:
            logger.info(f"Caricamento modello Whisper: {self.model_size} ({self.device})")
            self._model = WhisperModel(self.model_size, device=self.device, compute_type=self.compute_type)
        return self._model

    def _get_output_dir(self, video_path: str) -> str:
        """Genera il percorso della cartella di output basata sul nome del video."""
        video_name = Path(video_path).stem
        output_dir = os.path.join(self.workspace_path, "outputs", video_name)
        os.makedirs(output_dir, exist_ok=True)
        return output_dir

    def run(self, relative_video_path: str) -> Dict[str, Any]:
        """
        Esegue l'intero workflow: Validazione -> Estrazione -> Trascrizione -> Salvataggio.
        """
        start_time = time.time()
        
        try:
            # 1. Validazione percorso (sandbox)
            abs_video_path = validate_path(relative_video_path, self.workspace_path)
            if not os.path.exists(abs_video_path):
                raise FileNotFoundError(f"Video non trovato: {relative_video_path}")

            output_dir = self._get_output_dir(abs_video_path)
            metadata_path = os.path.join(output_dir, "metadata.json")

            # Controllo se i risultati esistono già
            if os.path.exists(metadata_path):
                logger.info("Risultati già presenti, salto la rielaborazione.")
                with open(metadata_path, 'r', encoding='utf-8') as f:
                    return json.load(f)

            # 2. Estrazione Audio
            audio_tmp_path = os.path.join(output_dir, "temp_audio.wav")
            if not extract_audio_from_video(abs_video_path, audio_tmp_path, ffmpeg_cmd=self.ffmpeg_cmd):
                raise RuntimeError("Fallimento estrazione audio dal video.")

            # 3. Trascrizione
            logger.info(f"Inizio trascrizione di: {relative_video_path}")
            segments, info = self.model.transcribe(audio_tmp_path, beam_size=5)
            
            all_segments = []
            full_text_list = []
            
            for segment in segments:
                seg_data = {
                    "start": round(segment.start, 2),
                    "end": round(segment.end, 2),
                    "text": segment.text.strip()
                }
                all_segments.append(seg_data)
                full_text_list.append(segment.text.strip())
                logger.debug(f"[{seg_data['start']}s -> {seg_data['end']}s] {seg_data['text']}")

            full_text = " ".join(full_text_list)

            # 4. Salvataggio Output
            # transcript.txt
            with open(os.path.join(output_dir, "transcript.txt"), "w", encoding="utf-8") as f:
                f.write(full_text)

            # transcript.json
            transcript_data = {
                "source_file": relative_video_path,
                "language": info.language,
                "duration_seconds": round(info.duration, 2),
                "segments": all_segments
            }
            with open(os.path.join(output_dir, "transcript.json"), "w", encoding="utf-8") as f:
                json.dump(transcript_data, f, indent=2, ensure_ascii=False)

            # 5. Generazione Metadata
            processing_time = round(time.time() - start_time, 2)
            metadata = {
                "status": "success",
                "processing_time_seconds": processing_time,
                "model_used": self.model_size,
                "word_count": len(full_text.split()),
                "created_at": datetime.now().isoformat(),
                "output_directory": os.path.relpath(output_dir, self.workspace_path)
            }
            
            with open(metadata_path, "w", encoding="utf-8") as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)

            # Pulizia file temporaneo
            if os.path.exists(audio_tmp_path):
                os.remove(audio_tmp_path)

            audit_log("VIDEO_TRANSCRIPTION_COMPLETE", f"Completata trascrizione: {relative_video_path}")
            return metadata

        except Exception as e:
            error_msg = f"Errore durante la trascrizione video: {str(e)}"
            logger.error(error_msg)
            return {
                "status": "error",
                "error_detail": error_msg
            }

def transcribe_video_standalone(config: Dict[str, Any], video_path: str):
    """Funzione helper per la CLI."""
    transcriber = VideoTranscriber(config)
    print(f"[CESARE] Caricamento file: {video_path}...")
    print(f"[CESARE] Analisi in corso (modello: {transcriber.model_size})...")
    
    # Notifiche simulate per la console
    # (In V1, run() è sincrono, ma stampiamo passi logici)
    print("[CESARE] Estrazione audio...")
    print("[CESARE] Trascrizione in corso (potrebbe richiedere tempo)...")
    
    result = transcriber.run(video_path)
    
    if result.get("status") == "success":
        print("[CESARE] Salvataggio output...")
        print(f"[CESARE] Fatto. Risultati in: {result['output_directory']}")
        print(f"[CESARE] Tempo impiegato: {result['processing_time_seconds']}s")
        return True
    else:
        print(f"[CESARE] ERRORE: {result.get('error_detail')}")
        return False