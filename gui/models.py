from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List

class MemoryTier(Enum):
    """Definisce i tre livelli di memoria di CESARE."""
    TIER_1 = "Temporale"
    TIER_2 = "ROM"
    TIER_3 = "Esperienza"

@dataclass
class MemoryEntry:
    """Rappresenta una singola voce di memoria indipendentemente dal Tier."""
    id: str
    tier: MemoryTier
    content: str
    timestamp: datetime
    summary: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    importance: int = 5
    tags: List[str] = field(default_factory=list)
    
    # Specifico per Tier 1 (Scadenza)
    expires_at: Optional[datetime] = None
    
    # Specifico per Tier 3 (Wisdom)
    original_error: Optional[str] = None
    corrective_principle: Optional[str] = None

    @property
    def expiration_days(self) -> int:
        """Calcola i giorni rimanenti per la memoria Tier 1."""
        if self.expires_at:
            delta = self.expires_at - datetime.now()
            return max(0, delta.days)
        return 0