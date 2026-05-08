# cesare.spec — template per PyInstaller
# Eseguire con: pyinstaller cesare.spec

block_cipher = None

a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
    datas=[
        # File di configurazione e dati
        ('bible.md', '.'),
        ('config.yaml', '.'),
        # Prompt degli agenti (file .md necessari a runtime)
        ('agents/prompts/*.md', 'agents/prompts'),
    ],
    hiddenimports=[
        # Moduli che PyInstaller non trova automaticamente
        'chromadb',
        'chromadb.db.impl.sqlite',
        'langchain_ollama',
        'langchain_core',
        'langgraph',
        'streamlit',
        'apscheduler',
        'apscheduler.schedulers.background',
        'apscheduler.schedulers.blocking',
        'ddgs',
        'faster_whisper',
        'core',
        'core.graph',
        'core.memory',
        'core.helpers',
        'core.security',
        'core.state',
        'tools',
        'tools.filesystem',
        'tools.web_tools',
        'tools.video_tools',
        'tools.video_transcriber',
        'tools.media',
        'gui',
        'gui.calendar_view',
        'gui.ui',
        'gui.styles',
        'gui.models',
        'gui.memory_repository',
        'scheduler',
        'scheduler.scheduler_engine',
        'channels',
        'channels.telegram',
        'agents',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='CESARE',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,           # True per vedere i log in console
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)