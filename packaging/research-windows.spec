"""Separate engineering acceptance build; does not overwrite companion releases."""
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files,collect_submodules,copy_metadata
root=Path(SPECPATH).parent
datas=[]
for package in ['base','growth_local','growth','genai_prices']:
    datas+=collect_data_files(package)
for package in ['genai-prices','pydantic-ai-slim','keyring','mcp','aiortc']:
    datas+=copy_metadata(package)
research=root/'src/base/app/research/functional'
for source in [research/'worker.py',*(research/'vendor').rglob('*')]:
    if source.is_file() and '__pycache__' not in source.parts:
        datas.append((str(source),str(source.parent.relative_to(root/'src'))))
hidden=['keyring.backends.Windows','win32cred','pydantic_ai.providers.deepseek','pydantic_ai.models.openai','PIL.PngImagePlugin','PIL.JpegImagePlugin']
hidden+=collect_submodules('mcp.server.fastmcp')
a=Analysis([str(root/'packaging/local_entry.py')],pathex=[str(root/'src')],binaries=[],datas=datas,hiddenimports=hidden,hookspath=[],runtime_hooks=[],excludes=['pytest','tkinter','IPython','numpy','matplotlib'],noarchive=False)
pyz=PYZ(a.pure)
gui=EXE(pyz,a.scripts,[],exclude_binaries=True,name='HyperGrowthResearch',debug=False,bootloader_ignore_signals=False,strip=False,upx=False,console=False)
mcp=EXE(pyz,a.scripts,[],exclude_binaries=True,name='HyperGrowthResearchMCP',debug=False,bootloader_ignore_signals=False,strip=False,upx=False,console=True)
coll=COLLECT(gui,mcp,a.binaries,a.datas,strip=False,upx=False,name='HyperGrowth-Research-Acceptance-0.2')
