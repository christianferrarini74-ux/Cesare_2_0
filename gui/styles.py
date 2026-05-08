def get_custom_css():
    """Ritorna il CSS personalizzato per la Dark Mode Premium di CESARE."""
    return """
    <style>
        .stApp {
            background-color: #0E1117;
        }
        .memory-card {
            background-color: #1E2129;
            border-radius: 10px;
            padding: 20px;
            border-left: 5px solid #4F4F4F;
            margin-bottom: 15px;
            transition: transform 0.2s;
        }
        .memory-card:hover {
            transform: scale(1.01);
            border-color: #00FFA3;
        }
        .tier-badge {
            font-size: 0.8em;
            padding: 2px 8px;
            border-radius: 5px;
            font-weight: bold;
            text-transform: uppercase;
        }
        .tier-1 { background-color: #2E5BFF; color: white; }
        .tier-2 { background-color: #FFD700; color: black; }
        .tier-3 { background-color: #FF4B4B; color: white; }
        
        .expiration-text {
            color: #888;
            font-style: italic;
            font-size: 0.9em;
        }
        
        .detail-header {
            color: #00FFA3;
            font-family: 'Courier New', monospace;
        }
        
        .principle-box {
            background-color: #0A2E20;
            padding: 15px;
            border-radius: 5px;
            border: 1px solid #00FFA3;
            margin-top: 10px;
        }
    </style>
    """