"""Virtual machine and container storage detection and reporting.

Identifies WSL2 VHDX virtual disks, Docker container storage, VirtualBox images,
VMware disks, and Hyper-V virtual drives.
Read-only by default; provides technical guidance rather than automatic compaction.
"""

import os
from dataclasses import dataclass
from datetime import datetime

from crapcleaner.utils.platform import get_local_appdata, get_user_profile, is_windows


@dataclass
class VmStorageItem:
    platform: str
    path: str
    size: int
    last_modified: datetime | None
    guidance: str

    def to_dict(self) -> dict:
        return {
            "platform": self.platform,
            "path": self.path,
            "size": self.size,
            "last_modified": self.last_modified.isoformat() if self.last_modified else None,
            "guidance": self.guidance,
        }


def detect_virtual_machine_storage() -> list[VmStorageItem]:
    """Scan standard locations for VM disk images and container storage layers."""
    items: list[VmStorageItem] = []
    user = get_user_profile()
    local = get_local_appdata()

    # 1. WSL2 Disks
    wsl_candidates = [
        (os.path.join(local, "Docker", "wsl"), "Docker WSL2 backend (ext4.vhdx)"),
        (os.path.join(local, "Packages"), "WSL2 Distribution image (ext4.vhdx)"),
        (os.path.join(user, ".wsl"), "WSL2 user disk"),
        (os.path.join(local, "wsl"), "WSL2 system disk"),
    ]
    for root, desc in wsl_candidates:
        if not os.path.isdir(root):
            continue
        for dirpath, _dirnames, filenames in os.walk(root):
            for name in filenames:
                if name.lower().endswith(".vhdx"):
                    full = os.path.join(dirpath, name)
                    try:
                        st = os.stat(full)
                        mtime = datetime.fromtimestamp(st.st_mtime)
                        sz = st.st_size
                    except OSError:
                        continue
                    items.append(
                        VmStorageItem(
                            platform="WSL2 / Docker",
                            path=full,
                            size=sz,
                            last_modified=mtime,
                            guidance=(
                                f"{desc}. Reclaim space using 'wsl --manage <distro> --compact' "
                                f"or optimize disk via diskpart. Do not delete active distros."
                            ),
                        )
                    )

    # 2. VirtualBox VMs
    vbox_dirs = [
        os.path.join(user, "VirtualBox VMs"),
        os.path.join(user, ".VirtualBox"),
    ]
    for root in vbox_dirs:
        if not os.path.isdir(root):
            continue
        for dirpath, _dirnames, filenames in os.walk(root):
            for name in filenames:
                if name.lower().endswith((".vdi", ".vbox", ".vbox-prev")):
                    full = os.path.join(dirpath, name)
                    if name.lower().endswith(".vdi"):
                        try:
                            st = os.stat(full)
                            mtime = datetime.fromtimestamp(st.st_mtime)
                            sz = st.st_size
                        except OSError:
                            continue
                        items.append(
                            VmStorageItem(
                                platform="VirtualBox",
                                path=full,
                                size=sz,
                                last_modified=mtime,
                                guidance="VirtualBox virtual disk (.vdi). Compact using VBoxManage modifymedium --compact if needed.",
                            )
                        )

    # 3. VMware Disks
    vmware_dirs = [
        os.path.join(user, "Documents", "Virtual Machines"),
        os.path.join(user, "vmware"),
    ]
    for root in vmware_dirs:
        if not os.path.isdir(root):
            continue
        for dirpath, _dirnames, filenames in os.walk(root):
            for name in filenames:
                if name.lower().endswith(".vmdk"):
                    full = os.path.join(dirpath, name)
                    try:
                        st = os.stat(full)
                        mtime = datetime.fromtimestamp(st.st_mtime)
                        sz = st.st_size
                    except OSError:
                        continue
                    items.append(
                        VmStorageItem(
                            platform="VMware",
                            path=full,
                            size=sz,
                            last_modified=mtime,
                            guidance="VMware virtual disk (.vmdk). Manage snapshots and defragment inside VMware Workstation/Player.",
                        )
                    )

    # 4. Hyper-V Disks (Windows)
    if is_windows():
        hyperv_dirs = [
            "C:\\ProgramData\\Microsoft\\Windows\\Hyper-V\\Virtual Hard Disks",
            "C:\\Users\\Public\\Documents\\Hyper-V\\Virtual Hard Disks",
        ]
        for root in hyperv_dirs:
            if not os.path.isdir(root):
                continue
            for dirpath, _dirnames, filenames in os.walk(root):
                for name in filenames:
                    if name.lower().endswith((".vhdx", ".vhd")):
                        full = os.path.join(dirpath, name)
                        try:
                            st = os.stat(full)
                            mtime = datetime.fromtimestamp(st.st_mtime)
                            sz = st.st_size
                        except OSError:
                            continue
                        items.append(
                            VmStorageItem(
                                platform="Hyper-V",
                                path=full,
                                size=sz,
                                last_modified=mtime,
                                guidance="Hyper-V virtual disk. Compact via Hyper-V Manager or Edit-VHD cmdlet in PowerShell.",
                            )
                        )

    items.sort(key=lambda item: item.size, reverse=True)
    return items
