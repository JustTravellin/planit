# PyInstaller spec. Build on Windows from the p1s-controller folder:  pyinstaller packaging/p1s-gui.spec
# Not built or tested in the cloud environment where it was written.
from PyInstaller.utils.hooks import collect_submodules

hidden = collect_submodules("pyqtgraph") + ["keyring.backends.Windows", "keyring.backends.fail"]

a = Analysis(
    ["launch.py"],
    pathex=[".."],
    hiddenimports=hidden,
    excludes=["tkinter", "matplotlib"],
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="P1S Controller", console=False)
coll = COLLECT(exe, a.binaries, a.datas, name="P1S Controller")
