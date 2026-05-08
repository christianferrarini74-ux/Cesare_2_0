import ffmpeg
import os
import logging
import shutil
from core.security import audit_log

logger = logging.getLogger("CESARE.Utils.Media")

def extract_audio_from_video(video_path: str, audio_output_path: str, ffmpeg_cmd: str = "ffmpeg") -> bool:
    """
    Estrae l'audio da un file video usando ffmpeg e lo salva in formato WAV 16kHz mono.
    """
    try:
        # Se il file audio esiste già, lo rimuoviamo per sicurezza
        if not shutil.which(ffmpeg_cmd):
            logger.error(f"FFmpeg ({ffmpeg_cmd}) non è installato o non è presente nel PATH di sistema.")
            print(f"[ERRORE CRITICO] FFmpeg non trovato ({ffmpeg_cmd}). Per favore installalo o specifica il percorso nel config.")
            return False

        if os.path.exists(audio_output_path):
            os.remove(audio_output_path)

        audit_log("VIDEO_AUDIO_EXTRACTION", f"Estrazione audio da: {video_path}")
        
        # Configurazione ffmpeg per estrazione ottimale per Whisper
        # -vn: no video, -ac 1: mono, -ar 16000: sample rate 16kHz
        stream = ffmpeg.input(video_path)
        stream = ffmpeg.output(stream, audio_output_path, ac=1, ar='16000', loglevel="error")
        
        # Eseguiamo il comando specificando l'eseguibile
        ffmpeg.run(stream, overwrite_output=True, cmd=ffmpeg_cmd)
        
        if os.path.exists(audio_output_path):
            logger.info(f"Audio estratto con successo: {audio_output_path}")
            return True
        else:
            logger.error("File audio non generato dopo l'esecuzione di ffmpeg.")
            return False
            
    except Exception as e:
        logger.error(f"Errore durante l'estrazione audio: {str(e)}")
        return False