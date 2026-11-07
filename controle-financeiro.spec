# PyInstaller: gera um ControleFinanceiro.exe único, com janela nativa.
# Rode pelo scripts\gerar_exe.bat (ele prepara tudo antes). Executar da RAIZ do projeto.
from PyInstaller.utils.hooks import collect_all, collect_submodules

# Recursos que precisam ir dentro do .exe: as telas compiladas e as migrações do banco.
datas = [
    ("frontend/dist", "frontend/dist"),      # abre em RAIZ(_MEIPASS)/frontend/dist
    ("backend/app/migrations", "app/migrations"),
]
binaries = []
hiddenimports = collect_submodules("uvicorn")

# A janela nativa (pywebview) e seus backends costumam escapar à análise automática.
for pacote in ("webview",):
    d, b, h = collect_all(pacote)
    datas += d
    binaries += b
    hiddenimports += h

a = Analysis(
    ["backend/run_desktop.py"],
    pathex=["backend"],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    runtime_hooks=[],
    excludes=["pytest", "httpx"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="ControleFinanceiro",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,              # sem janela preta de terminal
    icon="scripts/icone.ico",
)

# Segundo executável, da MESMA base: abre em modo DEMONSTRAÇÃO.
# O modo é detectado pelo nome do arquivo (ver backend/run_desktop.py),
# por isso reaproveita o mesmo Analysis e PYZ — só muda o nome.
exe_demo = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="ControleFinanceiro-Demonstracao",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    icon="scripts/icone.ico",
)
