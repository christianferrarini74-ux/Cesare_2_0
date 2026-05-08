from langchain_core.tools import StructuredTool
from tools.video_transcriber import VideoTranscriber
import logging

logger = logging.getLogger("CESARE.VideoTools")

def get_video_tools(config):
    """Ritorna la lista dei tool video disponibili per l'agente."""
    
    transcriber = VideoTranscriber(config)
    
    return [
        StructuredTool.from_function(
            name="transcribe_video",
            func=lambda video_path: transcriber.run(video_path),
            description="Trascrive il parlato di un file video locale in testo. "
                        "Richiede il percorso relativo al workspace (es. 'video.mp4'). "
                        "Restituisce metadati e percorsi dei file generati."
        )
    ]