#!/usr/bin/env python3
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

root = Path(__file__).resolve().parent
with ZipFile(root / "aigakira-virtual-joysticks.tpp", "w", compression=ZIP_DEFLATED) as archive:
    archive.write(root / "aigakira-virtual-joysticks" / "entry.tp", "aigakira-virtual-joysticks/entry.tp")
    archive.write(root / "aigakira-virtual-joysticks" / "plugin.py", "aigakira-virtual-joysticks/plugin.py")
    archive.write(root / "LICENSE", "aigakira-virtual-joysticks/LICENSE")
    archive.write(root / "VERSION", "aigakira-virtual-joysticks/VERSION")
    archive.write(root / "aigakira-virtual-joysticks.py", "aigakira-virtual-joysticks/aigakira-virtual-joysticks.py")
    archive.write(root / "aigakira-virtual-joysticks-windows.py", "aigakira-virtual-joysticks/aigakira-virtual-joysticks-windows.py")
print("Built aigakira-virtual-joysticks.tpp")