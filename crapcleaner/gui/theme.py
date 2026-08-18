from PySide6.QtGui import QColor, QIcon
from PySide6.QtWidgets import QApplication

AMBER_CRT = {
    "window": "#0a0804",
    "panel": "#141008",
    "surface": "#1f180c",
    "surface2": "#2b2211",
    "elevated": "#382c16",
    "border": "#2b2211",
    "border2": "#47381d",
    "text": "#ffb000",
    "muted": "#cc8d00",
    "faint": "#996a00",
    "accent": "#ffaa00",
    "accent_hover": "#ffc040",
    "accent_pressed": "#e69900",
    "accent_soft": "rgba(255, 170, 0, 0.15)",
    "success": "#52e060",
    "success_soft": "rgba(82, 224, 96, 0.15)",
    "warning": "#ffd700",
    "warning_soft": "rgba(255, 215, 0, 0.15)",
    "danger": "#ff4d4d",
    "danger_soft": "rgba(255, 77, 77, 0.15)",
    "review": "#ff8800",
    "review_soft": "rgba(255, 136, 0, 0.15)",
    "info": "#38d9f5",
    "info_soft": "rgba(56, 217, 245, 0.15)",
    "selection": "#ffaa00",
    "safe": "#52e060",
}

ANALOG_HORROR = {
    "window": "#050505",
    "panel": "#0f0f0f",
    "surface": "#171717",
    "surface2": "#212121",
    "elevated": "#2b2b2b",
    "border": "#212121",
    "border2": "#363636",
    "text": "#e0e0e0",
    "muted": "#8c8c8c",
    "faint": "#5e5e5e",
    "accent": "#b30000",
    "accent_hover": "#cc0000",
    "accent_pressed": "#800000",
    "accent_soft": "rgba(179, 0, 0, 0.15)",
    "success": "#2e8b57",
    "success_soft": "rgba(46, 139, 87, 0.15)",
    "warning": "#a68a00",
    "warning_soft": "rgba(166, 138, 0, 0.15)",
    "danger": "#e60000",
    "danger_soft": "rgba(230, 0, 0, 0.15)",
    "review": "#cc5200",
    "review_soft": "rgba(204, 82, 0, 0.15)",
    "info": "#4682b4",
    "info_soft": "rgba(70, 130, 180, 0.15)",
    "selection": "#b30000",
    "safe": "#2e8b57",
}

ADWAITA_DARK = {
    "window": "#1e1e1e",
    "panel": "#242424",
    "surface": "#303030",
    "surface2": "#3c3c3c",
    "elevated": "#454545",
    "border": "#3c3c3c",
    "border2": "#5b5b5b",
    "text": "#ffffff",
    "muted": "#c0bfbc",
    "faint": "#9a9996",
    "accent": "#3584e4",
    "accent_hover": "#4b97ee",
    "accent_pressed": "#1c71d8",
    "accent_soft": "rgba(53, 132, 228, 0.18)",
    "success": "#33d17a",
    "success_soft": "rgba(51, 209, 122, 0.15)",
    "warning": "#f6d32d",
    "warning_soft": "rgba(246, 211, 45, 0.15)",
    "danger": "#ed333b",
    "danger_soft": "rgba(237, 51, 59, 0.15)",
    "review": "#ff7800",
    "review_soft": "rgba(255, 120, 0, 0.15)",
    "info": "#62a0ea",
    "info_soft": "rgba(98, 160, 234, 0.15)",
    "selection": "#3584e4",
    "safe": "#33d17a",
}

ADWAITA_LIGHT = {
    "window": "#f6f5f4",
    "panel": "#ffffff",
    "surface": "#f0efed",
    "surface2": "#e7e6e4",
    "elevated": "#ffffff",
    "border": "#d7d6d3",
    "border2": "#c0bfbc",
    "text": "#241f31",
    "muted": "#5e5c64",
    "faint": "#77767b",
    "accent": "#3584e4",
    "accent_hover": "#4b97ee",
    "accent_pressed": "#1c71d8",
    "accent_soft": "rgba(53, 132, 228, 0.15)",
    "success": "#2ec27e",
    "success_soft": "rgba(46, 194, 126, 0.15)",
    "warning": "#e5a50a",
    "warning_soft": "rgba(229, 165, 10, 0.15)",
    "danger": "#c01c28",
    "danger_soft": "rgba(192, 28, 40, 0.15)",
    "review": "#ff7800",
    "review_soft": "rgba(255, 120, 0, 0.15)",
    "info": "#1a5fb4",
    "info_soft": "rgba(26, 95, 180, 0.15)",
    "selection": "#3584e4",
    "safe": "#2ec27e",
}

ARCTIC = {
    "window": "#f0f4f8",
    "panel": "#ffffff",
    "surface": "#e2e8f0",
    "surface2": "#cbd5e1",
    "elevated": "#ffffff",
    "border": "#cbd5e1",
    "border2": "#94a3b8",
    "text": "#1e293b",
    "muted": "#475569",
    "faint": "#64748b",
    "accent": "#3b82f6",
    "accent_hover": "#60a5fa",
    "accent_pressed": "#2563eb",
    "accent_soft": "rgba(59, 130, 246, 0.15)",
    "success": "#059669",
    "success_soft": "rgba(5, 150, 105, 0.15)",
    "warning": "#d97706",
    "warning_soft": "rgba(217, 119, 6, 0.15)",
    "danger": "#dc2626",
    "danger_soft": "rgba(220, 38, 38, 0.15)",
    "review": "#ea580c",
    "review_soft": "rgba(234, 88, 12, 0.15)",
    "info": "#0891b2",
    "info_soft": "rgba(8, 145, 178, 0.15)",
    "selection": "#3b82f6",
    "safe": "#059669",
}

BLACK_MESA = {
    "window": "#15181a",
    "panel": "#1d2124",
    "surface": "#252a2e",
    "surface2": "#2e3439",
    "elevated": "#383f45",
    "border": "#2e3439",
    "border2": "#474f57",
    "text": "#dcdfe4",
    "muted": "#9aa2ac",
    "faint": "#6e7681",
    "accent": "#f8981d",
    "accent_hover": "#faba4d",
    "accent_pressed": "#d97d0d",
    "accent_soft": "rgba(248, 152, 29, 0.15)",
    "success": "#22c55e",
    "success_soft": "rgba(34, 197, 94, 0.15)",
    "warning": "#eab308",
    "warning_soft": "rgba(234, 179, 8, 0.15)",
    "danger": "#ef4444",
    "danger_soft": "rgba(239, 68, 68, 0.15)",
    "review": "#ea580c",
    "review_soft": "rgba(234, 88, 12, 0.15)",
    "info": "#06b6d4",
    "info_soft": "rgba(6, 182, 212, 0.15)",
    "selection": "#f8981d",
    "safe": "#22c55e",
}

BUBBLEGUM = {
    "window": "#fff5f8",
    "panel": "#ffffff",
    "surface": "#fde7ef",
    "surface2": "#fbcfe1",
    "elevated": "#ffffff",
    "border": "#fbcfe1",
    "border2": "#f9a8d4",
    "text": "#4a1528",
    "muted": "#832c4e",
    "faint": "#aa5476",
    "accent": "#ec4899",
    "accent_hover": "#f472b6",
    "accent_pressed": "#db2777",
    "accent_soft": "rgba(236, 72, 153, 0.15)",
    "success": "#059669",
    "success_soft": "rgba(5, 150, 105, 0.15)",
    "warning": "#d97706",
    "warning_soft": "rgba(217, 119, 6, 0.15)",
    "danger": "#e11d48",
    "danger_soft": "rgba(225, 29, 72, 0.15)",
    "review": "#ea580c",
    "review_soft": "rgba(234, 88, 12, 0.15)",
    "info": "#0284c7",
    "info_soft": "rgba(2, 132, 199, 0.15)",
    "selection": "#ec4899",
    "safe": "#059669",
}

COBALT = {
    "window": "#0d1824",
    "panel": "#132335",
    "surface": "#1a2f47",
    "surface2": "#223d5c",
    "elevated": "#2a4c73",
    "border": "#223d5c",
    "border2": "#366091",
    "text": "#ffffff",
    "muted": "#a5c5dc",
    "faint": "#6895b6",
    "accent": "#ffc600",
    "accent_hover": "#ffd633",
    "accent_pressed": "#e6b200",
    "accent_soft": "rgba(255, 198, 0, 0.15)",
    "success": "#3ad900",
    "success_soft": "rgba(58, 217, 0, 0.15)",
    "warning": "#ff9d00",
    "warning_soft": "rgba(255, 157, 0, 0.15)",
    "danger": "#ff0033",
    "danger_soft": "rgba(255, 0, 51, 0.15)",
    "review": "#ff628c",
    "review_soft": "rgba(255, 98, 140, 0.15)",
    "info": "#0088ff",
    "info_soft": "rgba(0, 136, 255, 0.15)",
    "selection": "#ffc600",
    "safe": "#3ad900",
}

COFFEE = {
    "window": "#120e0c",
    "panel": "#1c1613",
    "surface": "#261e1a",
    "surface2": "#332822",
    "elevated": "#40332b",
    "border": "#332822",
    "border2": "#4d3d33",
    "text": "#f5eee6",
    "muted": "#d5c3b2",
    "faint": "#9e8a79",
    "accent": "#d97706",
    "accent_hover": "#f59e0b",
    "accent_pressed": "#b45309",
    "accent_soft": "rgba(217, 119, 6, 0.15)",
    "success": "#84cc16",
    "success_soft": "rgba(132, 204, 22, 0.15)",
    "warning": "#eab308",
    "warning_soft": "rgba(234, 179, 8, 0.15)",
    "danger": "#ef4444",
    "danger_soft": "rgba(239, 68, 68, 0.15)",
    "review": "#ea580c",
    "review_soft": "rgba(234, 88, 12, 0.15)",
    "info": "#06b6d4",
    "info_soft": "rgba(6, 182, 212, 0.15)",
    "selection": "#d97706",
    "safe": "#84cc16",
}

COMMODORE_64 = {
    "window": "#30246e",
    "panel": "#3f3091",
    "surface": "#503db8",
    "surface2": "#634ccf",
    "elevated": "#775fe6",
    "border": "#503db8",
    "border2": "#775fe6",
    "text": "#a4a1f4",
    "muted": "#8477ce",
    "faint": "#6c5eb5",
    "accent": "#a4a1f4",
    "accent_hover": "#c4c1ff",
    "accent_pressed": "#8477ce",
    "accent_soft": "rgba(164, 161, 244, 0.15)",
    "success": "#588d43",
    "success_soft": "rgba(88, 141, 67, 0.15)",
    "warning": "#c9d487",
    "warning_soft": "rgba(201, 212, 135, 0.15)",
    "danger": "#9a6759",
    "danger_soft": "rgba(154, 103, 89, 0.15)",
    "review": "#8b553f",
    "review_soft": "rgba(139, 85, 63, 0.15)",
    "info": "#79c1c8",
    "info_soft": "rgba(121, 193, 200, 0.15)",
    "selection": "#a4a1f4",
    "safe": "#588d43",
}

CRIMSON = {
    "window": "#12080d",
    "panel": "#1c0c14",
    "surface": "#29131d",
    "surface2": "#381a28",
    "elevated": "#4a2234",
    "border": "#381a28",
    "border2": "#5c2a41",
    "text": "#faedf3",
    "muted": "#d4b3c4",
    "faint": "#9d738a",
    "accent": "#e11d48",
    "accent_hover": "#f43f5e",
    "accent_pressed": "#be123c",
    "accent_soft": "rgba(225, 29, 72, 0.15)",
    "success": "#10b981",
    "success_soft": "rgba(16, 185, 129, 0.15)",
    "warning": "#f59e0b",
    "warning_soft": "rgba(245, 158, 11, 0.15)",
    "danger": "#ff2e5b",
    "danger_soft": "rgba(255, 46, 91, 0.15)",
    "review": "#fb923c",
    "review_soft": "rgba(251, 146, 60, 0.15)",
    "info": "#38bdf8",
    "info_soft": "rgba(56, 189, 248, 0.15)",
    "selection": "#e11d48",
    "safe": "#10b981",
}

CYBERPUNK = {
    "window": "#090714",
    "panel": "#110e24",
    "surface": "#1b1633",
    "surface2": "#251e45",
    "elevated": "#312859",
    "border": "#251e45",
    "border2": "#3e3270",
    "text": "#fdf4ff",
    "muted": "#d8b4fe",
    "faint": "#9333ea",
    "accent": "#f43f5e",
    "accent_hover": "#fb7185",
    "accent_pressed": "#e11d48",
    "accent_soft": "rgba(244, 63, 94, 0.15)",
    "success": "#00f5a0",
    "success_soft": "rgba(0, 245, 160, 0.15)",
    "warning": "#facc15",
    "warning_soft": "rgba(250, 204, 21, 0.15)",
    "danger": "#ff2a5f",
    "danger_soft": "rgba(255, 42, 95, 0.15)",
    "review": "#fb923c",
    "review_soft": "rgba(251, 146, 60, 0.15)",
    "info": "#00f0ff",
    "info_soft": "rgba(0, 240, 255, 0.15)",
    "selection": "#f43f5e",
    "safe": "#00f5a0",
}

DARK = {
    "window": "#0d0e12",
    "panel": "#14151a",
    "surface": "#1b1d24",
    "surface2": "#24262f",
    "elevated": "#2d303b",
    "border": "#24262f",
    "border2": "#363a47",
    "text": "#f8fafc",
    "muted": "#cbd5e1",
    "faint": "#94a3b8",
    "accent": "#3b82f6",
    "accent_hover": "#60a5fa",
    "accent_pressed": "#2563eb",
    "accent_soft": "rgba(59, 130, 246, 0.15)",
    "success": "#10b981",
    "success_soft": "rgba(16, 185, 129, 0.15)",
    "warning": "#f59e0b",
    "warning_soft": "rgba(245, 158, 11, 0.15)",
    "danger": "#ef4444",
    "danger_soft": "rgba(239, 68, 68, 0.15)",
    "review": "#f97316",
    "review_soft": "rgba(249, 115, 22, 0.15)",
    "info": "#06b6d4",
    "info_soft": "rgba(6, 182, 212, 0.15)",
    "selection": "#3b82f6",
    "safe": "#10b981",
}

DRACULA = {
    "window": "#1e1f29",
    "panel": "#282a36",
    "surface": "#343746",
    "surface2": "#44475a",
    "elevated": "#52566e",
    "border": "#44475a",
    "border2": "#6272a4",
    "text": "#f8f8f2",
    "muted": "#bfbfcb",
    "faint": "#6272a4",
    "accent": "#bd93f9",
    "accent_hover": "#d1b3ff",
    "accent_pressed": "#9965f4",
    "accent_soft": "rgba(189, 147, 249, 0.15)",
    "success": "#50fa7b",
    "success_soft": "rgba(80, 250, 123, 0.15)",
    "warning": "#f1fa8c",
    "warning_soft": "rgba(241, 250, 140, 0.15)",
    "danger": "#ff5555",
    "danger_soft": "rgba(255, 85, 85, 0.15)",
    "review": "#ffb86c",
    "review_soft": "rgba(255, 184, 108, 0.15)",
    "info": "#8be9fd",
    "info_soft": "rgba(139, 233, 253, 0.15)",
    "selection": "#bd93f9",
    "safe": "#50fa7b",
}

EMERALD = {
    "window": "#040d0a",
    "panel": "#091712",
    "surface": "#10211a",
    "surface2": "#183026",
    "elevated": "#214234",
    "border": "#183026",
    "border2": "#285241",
    "text": "#ecfdf5",
    "muted": "#a7f3d0",
    "faint": "#6ee7b7",
    "accent": "#10b981",
    "accent_hover": "#34d399",
    "accent_pressed": "#059669",
    "accent_soft": "rgba(16, 185, 129, 0.15)",
    "success": "#00e676",
    "success_soft": "rgba(0, 230, 118, 0.15)",
    "warning": "#facc15",
    "warning_soft": "rgba(250, 204, 21, 0.15)",
    "danger": "#ef4444",
    "danger_soft": "rgba(239, 68, 68, 0.15)",
    "review": "#fb923c",
    "review_soft": "rgba(251, 146, 60, 0.15)",
    "info": "#22d3ee",
    "info_soft": "rgba(34, 211, 238, 0.15)",
    "selection": "#10b981",
    "safe": "#00e676",
}

FOREST = {
    "window": "#0b110e",
    "panel": "#121a15",
    "surface": "#1a251e",
    "surface2": "#233329",
    "elevated": "#2d4034",
    "border": "#233329",
    "border2": "#364f3e",
    "text": "#e8f3ea",
    "muted": "#b5cdbb",
    "faint": "#87a691",
    "accent": "#4ade80",
    "accent_hover": "#86efac",
    "accent_pressed": "#22c55e",
    "accent_soft": "rgba(74, 222, 128, 0.15)",
    "success": "#22c55e",
    "success_soft": "rgba(34, 197, 94, 0.15)",
    "warning": "#eab308",
    "warning_soft": "rgba(234, 179, 8, 0.15)",
    "danger": "#ef4444",
    "danger_soft": "rgba(239, 68, 68, 0.15)",
    "review": "#fb923c",
    "review_soft": "rgba(251, 146, 60, 0.15)",
    "info": "#2dd4bf",
    "info_soft": "rgba(45, 212, 191, 0.15)",
    "selection": "#4ade80",
    "safe": "#22c55e",
}

GAMEBOY = {
    "window": "#0b2b0b",
    "panel": "#123812",
    "surface": "#1c4a1c",
    "surface2": "#285c28",
    "elevated": "#367036",
    "border": "#285c28",
    "border2": "#438243",
    "text": "#9bbc0f",
    "muted": "#8bac0f",
    "faint": "#5a802a",
    "accent": "#b0d424",
    "accent_hover": "#c8f032",
    "accent_pressed": "#9bbc0f",
    "accent_soft": "rgba(176, 212, 36, 0.15)",
    "success": "#9bbc0f",
    "success_soft": "rgba(155, 188, 15, 0.15)",
    "warning": "#8bac0f",
    "warning_soft": "rgba(139, 172, 15, 0.15)",
    "danger": "#306230",
    "danger_soft": "rgba(48, 98, 48, 0.15)",
    "review": "#8bac0f",
    "review_soft": "rgba(139, 172, 15, 0.15)",
    "info": "#9bbc0f",
    "info_soft": "rgba(155, 188, 15, 0.15)",
    "selection": "#306230",
    "safe": "#9bbc0f",
}

GRAPHITE = {
    "window": "#111111",
    "panel": "#171717",
    "surface": "#1f1f1f",
    "surface2": "#292929",
    "elevated": "#333333",
    "border": "#292929",
    "border2": "#404040",
    "text": "#ededed",
    "muted": "#bdbdbd",
    "faint": "#909090",
    "accent": "#9ca3af",
    "accent_hover": "#cbd5e1",
    "accent_pressed": "#6b7280",
    "accent_soft": "rgba(156, 163, 175, 0.15)",
    "success": "#4ade80",
    "success_soft": "rgba(74, 222, 128, 0.15)",
    "warning": "#facc15",
    "warning_soft": "rgba(250, 204, 21, 0.15)",
    "danger": "#ef4444",
    "danger_soft": "rgba(239, 68, 68, 0.15)",
    "review": "#fb923c",
    "review_soft": "rgba(251, 146, 60, 0.15)",
    "info": "#67e8f9",
    "info_soft": "rgba(103, 232, 249, 0.15)",
    "selection": "#9ca3af",
    "safe": "#4ade80",
}

GRUVBOX = {
    "window": "#191b1c",
    "panel": "#222425",
    "surface": "#2d2a29",
    "surface2": "#383432",
    "elevated": "#45403d",
    "border": "#383432",
    "border2": "#544d49",
    "text": "#ebdbb2",
    "muted": "#d5c4a1",
    "faint": "#a89984",
    "accent": "#fe8019",
    "accent_hover": "#ffa14f",
    "accent_pressed": "#d65d0e",
    "accent_soft": "rgba(254, 128, 25, 0.15)",
    "success": "#b8bb26",
    "success_soft": "rgba(184, 187, 38, 0.15)",
    "warning": "#fabd2f",
    "warning_soft": "rgba(250, 189, 47, 0.15)",
    "danger": "#fb4934",
    "danger_soft": "rgba(251, 73, 52, 0.15)",
    "review": "#d65d0e",
    "review_soft": "rgba(214, 93, 14, 0.15)",
    "info": "#83a598",
    "info_soft": "rgba(131, 165, 152, 0.15)",
    "selection": "#fe8019",
    "safe": "#b8bb26",
}

HIGH_CONTRAST = {
    "window": "#000000",
    "panel": "#000000",
    "surface": "#121212",
    "surface2": "#242424",
    "elevated": "#363636",
    "border": "#ffffff",
    "border2": "#ffffff",
    "text": "#ffffff",
    "muted": "#e0e0e0",
    "faint": "#a0a0a0",
    "accent": "#00b0ff",
    "accent_hover": "#66d4ff",
    "accent_pressed": "#0080c0",
    "accent_soft": "rgba(0, 176, 255, 0.15)",
    "success": "#00e676",
    "success_soft": "rgba(0, 230, 118, 0.15)",
    "warning": "#ffd600",
    "warning_soft": "rgba(255, 214, 0, 0.15)",
    "danger": "#ff5252",
    "danger_soft": "rgba(255, 82, 82, 0.15)",
    "review": "#ffab40",
    "review_soft": "rgba(255, 171, 64, 0.15)",
    "info": "#40c4ff",
    "info_soft": "rgba(64, 196, 255, 0.15)",
    "selection": "#00b0ff",
    "safe": "#00e676",
}

LAVENDER = {
    "window": "#f3f0fa",
    "panel": "#ffffff",
    "surface": "#e9e4f5",
    "surface2": "#dad1eb",
    "elevated": "#ffffff",
    "border": "#dad1eb",
    "border2": "#c4b6df",
    "text": "#28233d",
    "muted": "#5c5478",
    "faint": "#8277a5",
    "accent": "#7c3aed",
    "accent_hover": "#8b5cf6",
    "accent_pressed": "#6d28d9",
    "accent_soft": "rgba(124, 58, 237, 0.15)",
    "success": "#059669",
    "success_soft": "rgba(5, 150, 105, 0.15)",
    "warning": "#d97706",
    "warning_soft": "rgba(217, 119, 6, 0.15)",
    "danger": "#dc2626",
    "danger_soft": "rgba(220, 38, 38, 0.15)",
    "review": "#ea580c",
    "review_soft": "rgba(234, 88, 12, 0.15)",
    "info": "#0891b2",
    "info_soft": "rgba(8, 145, 178, 0.15)",
    "selection": "#7c3aed",
    "safe": "#059669",
}

LIGHT = {
    "window": "#f1f5f9",
    "panel": "#ffffff",
    "surface": "#e2e8f0",
    "surface2": "#cbd5e1",
    "elevated": "#ffffff",
    "border": "#cbd5e1",
    "border2": "#94a3b8",
    "text": "#0f172a",
    "muted": "#475569",
    "faint": "#64748b",
    "accent": "#2563eb",
    "accent_hover": "#3b82f6",
    "accent_pressed": "#1d4ed8",
    "accent_soft": "rgba(37, 99, 235, 0.15)",
    "success": "#059669",
    "success_soft": "rgba(5, 150, 105, 0.15)",
    "warning": "#d97706",
    "warning_soft": "rgba(217, 119, 6, 0.15)",
    "danger": "#dc2626",
    "danger_soft": "rgba(220, 38, 38, 0.15)",
    "review": "#ea580c",
    "review_soft": "rgba(234, 88, 12, 0.15)",
    "info": "#0891b2",
    "info_soft": "rgba(8, 145, 178, 0.15)",
    "selection": "#2563eb",
    "safe": "#059669",
}

MATCHA = {
    "window": "#edf3ef",
    "panel": "#ffffff",
    "surface": "#dfeae3",
    "surface2": "#cce0d2",
    "elevated": "#ffffff",
    "border": "#cce0d2",
    "border2": "#aecab6",
    "text": "#1c2e22",
    "muted": "#415e4a",
    "faint": "#63846e",
    "accent": "#2e7d32",
    "accent_hover": "#388e3c",
    "accent_pressed": "#1b5e20",
    "accent_soft": "rgba(46, 125, 50, 0.15)",
    "success": "#16a34a",
    "success_soft": "rgba(22, 163, 74, 0.15)",
    "warning": "#ca8a04",
    "warning_soft": "rgba(202, 138, 4, 0.15)",
    "danger": "#dc2626",
    "danger_soft": "rgba(220, 38, 38, 0.15)",
    "review": "#c2410c",
    "review_soft": "rgba(194, 65, 12, 0.15)",
    "info": "#0d9488",
    "info_soft": "rgba(13, 148, 136, 0.15)",
    "selection": "#2e7d32",
    "safe": "#16a34a",
}

MATRIX = {
    "window": "#020a05",
    "panel": "#06140a",
    "surface": "#0a1f0f",
    "surface2": "#102e17",
    "elevated": "#174020",
    "border": "#102e17",
    "border2": "#1e5229",
    "text": "#dcfce7",
    "muted": "#86efac",
    "faint": "#4ade80",
    "accent": "#22c55e",
    "accent_hover": "#4ade80",
    "accent_pressed": "#16a34a",
    "accent_soft": "rgba(34, 197, 94, 0.15)",
    "success": "#00ff66",
    "success_soft": "rgba(0, 255, 102, 0.15)",
    "warning": "#eab308",
    "warning_soft": "rgba(234, 179, 8, 0.15)",
    "danger": "#ef4444",
    "danger_soft": "rgba(239, 68, 68, 0.15)",
    "review": "#f97316",
    "review_soft": "rgba(249, 115, 22, 0.15)",
    "info": "#06b6d4",
    "info_soft": "rgba(6, 182, 212, 0.15)",
    "selection": "#22c55e",
    "safe": "#00ff66",
}

MIDNIGHT = {
    "window": "#090d1a",
    "panel": "#101626",
    "surface": "#161e33",
    "surface2": "#1d2842",
    "elevated": "#253354",
    "border": "#1d2842",
    "border2": "#2e3e66",
    "text": "#eef2ff",
    "muted": "#b6c2e6",
    "faint": "#8494c4",
    "accent": "#6366f1",
    "accent_hover": "#818cf8",
    "accent_pressed": "#4f46e5",
    "accent_soft": "rgba(99, 102, 241, 0.15)",
    "success": "#34d399",
    "success_soft": "rgba(52, 211, 153, 0.15)",
    "warning": "#fbbf24",
    "warning_soft": "rgba(251, 191, 36, 0.15)",
    "danger": "#fb7185",
    "danger_soft": "rgba(251, 113, 133, 0.15)",
    "review": "#f59e0b",
    "review_soft": "rgba(245, 158, 11, 0.15)",
    "info": "#38bdf8",
    "info_soft": "rgba(56, 189, 248, 0.15)",
    "selection": "#6366f1",
    "safe": "#34d399",
}

MINT_CHOCO = {
    "window": "#120e0d",
    "panel": "#1a1312",
    "surface": "#241b19",
    "surface2": "#302422",
    "elevated": "#3d2d2a",
    "border": "#302422",
    "border2": "#4a3733",
    "text": "#e6faf6",
    "muted": "#a7e6da",
    "faint": "#73bfae",
    "accent": "#2dd4bf",
    "accent_hover": "#5eead4",
    "accent_pressed": "#14b8a6",
    "accent_soft": "rgba(45, 212, 191, 0.15)",
    "success": "#34d399",
    "success_soft": "rgba(52, 211, 153, 0.15)",
    "warning": "#fbbf24",
    "warning_soft": "rgba(251, 191, 36, 0.15)",
    "danger": "#fb7185",
    "danger_soft": "rgba(251, 113, 133, 0.15)",
    "review": "#fb923c",
    "review_soft": "rgba(251, 146, 60, 0.15)",
    "info": "#38bdf8",
    "info_soft": "rgba(56, 189, 248, 0.15)",
    "selection": "#2dd4bf",
    "safe": "#34d399",
}

MONOKAI = {
    "window": "#1e1f20",
    "panel": "#272822",
    "surface": "#32332c",
    "surface2": "#3e3f37",
    "elevated": "#4c4d44",
    "border": "#3e3f37",
    "border2": "#5a5c51",
    "text": "#fcfcfa",
    "muted": "#c1c0c0",
    "faint": "#727072",
    "accent": "#ffd866",
    "accent_hover": "#ffe185",
    "accent_pressed": "#e6bf4d",
    "accent_soft": "rgba(255, 216, 102, 0.15)",
    "success": "#a9dc76",
    "success_soft": "rgba(169, 220, 118, 0.15)",
    "warning": "#fc9867",
    "warning_soft": "rgba(252, 152, 103, 0.15)",
    "danger": "#ff6188",
    "danger_soft": "rgba(255, 97, 136, 0.15)",
    "review": "#ab9df2",
    "review_soft": "rgba(171, 157, 242, 0.15)",
    "info": "#78dce8",
    "info_soft": "rgba(120, 220, 232, 0.15)",
    "selection": "#ffd866",
    "safe": "#a9dc76",
}

NORD = {
    "window": "#242933",
    "panel": "#2e3440",
    "surface": "#3b4252",
    "surface2": "#434c5e",
    "elevated": "#4c566a",
    "border": "#434c5e",
    "border2": "#5e697e",
    "text": "#eceff4",
    "muted": "#e5e9f0",
    "faint": "#d8dee9",
    "accent": "#88c0d0",
    "accent_hover": "#9fd5e5",
    "accent_pressed": "#6fa6b7",
    "accent_soft": "rgba(136, 192, 208, 0.15)",
    "success": "#a3be8c",
    "success_soft": "rgba(163, 190, 140, 0.15)",
    "warning": "#ebcb8b",
    "warning_soft": "rgba(235, 203, 139, 0.15)",
    "danger": "#bf616a",
    "danger_soft": "rgba(191, 97, 106, 0.15)",
    "review": "#d08770",
    "review_soft": "rgba(208, 135, 112, 0.15)",
    "info": "#81a1c1",
    "info_soft": "rgba(129, 161, 193, 0.15)",
    "selection": "#88c0d0",
    "safe": "#a3be8c",
}

OCEANIC = {
    "window": "#08111a",
    "panel": "#0e1a26",
    "surface": "#152536",
    "surface2": "#1c3247",
    "elevated": "#25405c",
    "border": "#1c3247",
    "border2": "#2b4b6b",
    "text": "#e2f1f8",
    "muted": "#9ec0d6",
    "faint": "#658da8",
    "accent": "#0ea5e9",
    "accent_hover": "#38bdf8",
    "accent_pressed": "#0284c7",
    "accent_soft": "rgba(14, 165, 233, 0.15)",
    "success": "#10b981",
    "success_soft": "rgba(16, 185, 129, 0.15)",
    "warning": "#f59e0b",
    "warning_soft": "rgba(245, 158, 11, 0.15)",
    "danger": "#f43f5e",
    "danger_soft": "rgba(244, 63, 94, 0.15)",
    "review": "#f97316",
    "review_soft": "rgba(249, 115, 22, 0.15)",
    "info": "#06b6d4",
    "info_soft": "rgba(6, 182, 212, 0.15)",
    "selection": "#0ea5e9",
    "safe": "#10b981",
}

OLED = {
    "window": "#000000",
    "panel": "#050505",
    "surface": "#0d0d0d",
    "surface2": "#141414",
    "elevated": "#1c1c1c",
    "border": "#141414",
    "border2": "#262626",
    "text": "#f8fafc",
    "muted": "#c2cbd8",
    "faint": "#8b95a5",
    "accent": "#4f8cff",
    "accent_hover": "#7aa8ff",
    "accent_pressed": "#3570e0",
    "accent_soft": "rgba(79, 140, 255, 0.15)",
    "success": "#22c55e",
    "success_soft": "rgba(34, 197, 94, 0.15)",
    "warning": "#fbbf24",
    "warning_soft": "rgba(251, 191, 36, 0.15)",
    "danger": "#ef4444",
    "danger_soft": "rgba(239, 68, 68, 0.15)",
    "review": "#fb923c",
    "review_soft": "rgba(251, 146, 60, 0.15)",
    "info": "#22d3ee",
    "info_soft": "rgba(34, 211, 238, 0.15)",
    "selection": "#4f8cff",
    "safe": "#22c55e",
}

ONE_DARK = {
    "window": "#1b1f23",
    "panel": "#21252b",
    "surface": "#282c34",
    "surface2": "#333842",
    "elevated": "#3f4552",
    "border": "#333842",
    "border2": "#49505e",
    "text": "#abb2bf",
    "muted": "#828997",
    "faint": "#5c6370",
    "accent": "#61afef",
    "accent_hover": "#7ec0f5",
    "accent_pressed": "#4d9ae0",
    "accent_soft": "rgba(97, 175, 239, 0.15)",
    "success": "#98c379",
    "success_soft": "rgba(152, 195, 121, 0.15)",
    "warning": "#e5c07b",
    "warning_soft": "rgba(229, 192, 123, 0.15)",
    "danger": "#e06c75",
    "danger_soft": "rgba(224, 108, 117, 0.15)",
    "review": "#d19a66",
    "review_soft": "rgba(209, 154, 102, 0.15)",
    "info": "#56b6c2",
    "info_soft": "rgba(86, 182, 194, 0.15)",
    "selection": "#61afef",
    "safe": "#98c379",
}

PARCHMENT = {
    "window": "#faf7f2",
    "panel": "#f4f0e6",
    "surface": "#ebe4d5",
    "surface2": "#ded5c2",
    "elevated": "#ffffff",
    "border": "#ded5c2",
    "border2": "#c9bfa8",
    "text": "#1c1917",
    "muted": "#57534e",
    "faint": "#78716c",
    "accent": "#b45309",
    "accent_hover": "#d97706",
    "accent_pressed": "#92400e",
    "accent_soft": "rgba(180, 83, 9, 0.15)",
    "success": "#15803d",
    "success_soft": "rgba(21, 128, 61, 0.15)",
    "warning": "#c2410c",
    "warning_soft": "rgba(194, 65, 12, 0.15)",
    "danger": "#b91c1c",
    "danger_soft": "rgba(185, 28, 28, 0.15)",
    "review": "#ea580c",
    "review_soft": "rgba(234, 88, 12, 0.15)",
    "info": "#0369a1",
    "info_soft": "rgba(3, 105, 161, 0.15)",
    "selection": "#b45309",
    "safe": "#15803d",
}

PULP_SEVENTIES = {
    "window": "#261510",
    "panel": "#331c15",
    "surface": "#42251c",
    "surface2": "#543024",
    "elevated": "#693b2d",
    "border": "#543024",
    "border2": "#754637",
    "text": "#f4e8d3",
    "muted": "#c9b193",
    "faint": "#998063",
    "accent": "#e65c00",
    "accent_hover": "#ff7a24",
    "accent_pressed": "#bf4d00",
    "accent_soft": "rgba(230, 92, 0, 0.15)",
    "success": "#529924",
    "success_soft": "rgba(82, 153, 36, 0.15)",
    "warning": "#d9a011",
    "warning_soft": "rgba(217, 160, 17, 0.15)",
    "danger": "#cc2929",
    "danger_soft": "rgba(204, 41, 41, 0.15)",
    "review": "#b35900",
    "review_soft": "rgba(179, 89, 0, 0.15)",
    "info": "#298a8a",
    "info_soft": "rgba(41, 138, 138, 0.15)",
    "selection": "#e65c00",
    "safe": "#529924",
}

ROSE_PINE = {
    "window": "#161420",
    "panel": "#1f1d2e",
    "surface": "#26233a",
    "surface2": "#34304f",
    "elevated": "#423d63",
    "border": "#34304f",
    "border2": "#4e4975",
    "text": "#e0def4",
    "muted": "#908caa",
    "faint": "#6e6a86",
    "accent": "#c4a7e7",
    "accent_hover": "#d8c0f5",
    "accent_pressed": "#a986d9",
    "accent_soft": "rgba(196, 167, 231, 0.15)",
    "success": "#9ccfd8",
    "success_soft": "rgba(156, 207, 216, 0.15)",
    "warning": "#f6c177",
    "warning_soft": "rgba(246, 193, 119, 0.15)",
    "danger": "#eb6f92",
    "danger_soft": "rgba(235, 111, 146, 0.15)",
    "review": "#ea9a97",
    "review_soft": "rgba(234, 154, 151, 0.15)",
    "info": "#31748f",
    "info_soft": "rgba(49, 116, 143, 0.15)",
    "selection": "#c4a7e7",
    "safe": "#9ccfd8",
}

SLATE = {
    "window": "#16191d",
    "panel": "#1e2227",
    "surface": "#282d33",
    "surface2": "#333941",
    "elevated": "#404751",
    "border": "#333941",
    "border2": "#4a535e",
    "text": "#e6edf3",
    "muted": "#b9c4cf",
    "faint": "#8d99a6",
    "accent": "#58a6ff",
    "accent_hover": "#79b8ff",
    "accent_pressed": "#3d8bdd",
    "accent_soft": "rgba(88, 166, 255, 0.15)",
    "success": "#3fb950",
    "success_soft": "rgba(63, 185, 80, 0.15)",
    "warning": "#d29922",
    "warning_soft": "rgba(210, 153, 34, 0.15)",
    "danger": "#f85149",
    "danger_soft": "rgba(248, 81, 73, 0.15)",
    "review": "#db6d28",
    "review_soft": "rgba(219, 109, 40, 0.15)",
    "info": "#39c5cf",
    "info_soft": "rgba(57, 197, 207, 0.15)",
    "selection": "#58a6ff",
    "safe": "#3fb950",
}

SOLARIZED_DARK = {
    "window": "#00232c",
    "panel": "#002b36",
    "surface": "#073642",
    "surface2": "#0b4a59",
    "elevated": "#116073",
    "border": "#0b4a59",
    "border2": "#16728a",
    "text": "#eee8d5",
    "muted": "#b6c2c2",
    "faint": "#93a1a1",
    "accent": "#268bd2",
    "accent_hover": "#4aa3e0",
    "accent_pressed": "#1c6fa8",
    "accent_soft": "rgba(38, 139, 210, 0.15)",
    "success": "#859900",
    "success_soft": "rgba(133, 153, 0, 0.15)",
    "warning": "#b58900",
    "warning_soft": "rgba(181, 137, 0, 0.15)",
    "danger": "#dc322f",
    "danger_soft": "rgba(220, 50, 47, 0.15)",
    "review": "#cb4b16",
    "review_soft": "rgba(203, 75, 22, 0.15)",
    "info": "#2aa198",
    "info_soft": "rgba(42, 161, 152, 0.15)",
    "selection": "#268bd2",
    "safe": "#859900",
}

SOLAR_ECLIPSE = {
    "window": "#0a0a0c",
    "panel": "#111114",
    "surface": "#18181c",
    "surface2": "#222228",
    "elevated": "#2d2d35",
    "border": "#222228",
    "border2": "#363640",
    "text": "#fef9c3",
    "muted": "#e2d58e",
    "faint": "#a89b58",
    "accent": "#eab308",
    "accent_hover": "#facc15",
    "accent_pressed": "#ca8a04",
    "accent_soft": "rgba(234, 179, 8, 0.15)",
    "success": "#22c55e",
    "success_soft": "rgba(34, 197, 94, 0.15)",
    "warning": "#fb923c",
    "warning_soft": "rgba(251, 146, 60, 0.15)",
    "danger": "#ef4444",
    "danger_soft": "rgba(239, 68, 68, 0.15)",
    "review": "#f97316",
    "review_soft": "rgba(249, 115, 22, 0.15)",
    "info": "#38bdf8",
    "info_soft": "rgba(56, 189, 248, 0.15)",
    "selection": "#eab308",
    "safe": "#22c55e",
}

SUNSET = {
    "window": "#140e18",
    "panel": "#1d1424",
    "surface": "#271a30",
    "surface2": "#342240",
    "elevated": "#422c52",
    "border": "#342240",
    "border2": "#4e3561",
    "text": "#fdf2f8",
    "muted": "#e4c1de",
    "faint": "#a87c9f",
    "accent": "#fb7185",
    "accent_hover": "#fda4af",
    "accent_pressed": "#f43f5e",
    "accent_soft": "rgba(251, 113, 133, 0.15)",
    "success": "#34d399",
    "success_soft": "rgba(52, 211, 153, 0.15)",
    "warning": "#fbbf24",
    "warning_soft": "rgba(251, 191, 36, 0.15)",
    "danger": "#ef4444",
    "danger_soft": "rgba(239, 68, 68, 0.15)",
    "review": "#fb923c",
    "review_soft": "rgba(251, 146, 60, 0.15)",
    "info": "#38bdf8",
    "info_soft": "rgba(56, 189, 248, 0.15)",
    "selection": "#fb7185",
    "safe": "#34d399",
}

SYNTHWAVE = {
    "window": "#140c24",
    "panel": "#1d1233",
    "surface": "#271945",
    "surface2": "#332159",
    "elevated": "#422a73",
    "border": "#332159",
    "border2": "#51358c",
    "text": "#fff1f2",
    "muted": "#f472b6",
    "faint": "#c084fc",
    "accent": "#ff2a85",
    "accent_hover": "#ff5ca8",
    "accent_pressed": "#d91a6d",
    "accent_soft": "rgba(255, 42, 133, 0.15)",
    "success": "#05ffa1",
    "success_soft": "rgba(5, 255, 161, 0.15)",
    "warning": "#ffe600",
    "warning_soft": "rgba(255, 230, 0, 0.15)",
    "danger": "#ff3864",
    "danger_soft": "rgba(255, 56, 100, 0.15)",
    "review": "#ff7b00",
    "review_soft": "rgba(255, 123, 0, 0.15)",
    "info": "#00f0ff",
    "info_soft": "rgba(0, 240, 255, 0.15)",
    "selection": "#ff2a85",
    "safe": "#05ffa1",
}

TOKYO_NIGHT = {
    "window": "#13131a",
    "panel": "#1a1b26",
    "surface": "#222436",
    "surface2": "#2d3047",
    "elevated": "#3b3f5c",
    "border": "#2d3047",
    "border2": "#464b6e",
    "text": "#c0caf5",
    "muted": "#a9b1d6",
    "faint": "#565f89",
    "accent": "#7aa2f7",
    "accent_hover": "#9ab8ff",
    "accent_pressed": "#5d87e0",
    "accent_soft": "rgba(122, 162, 247, 0.15)",
    "success": "#9ece6a",
    "success_soft": "rgba(158, 206, 106, 0.15)",
    "warning": "#e0af68",
    "warning_soft": "rgba(224, 175, 104, 0.15)",
    "danger": "#f7768e",
    "danger_soft": "rgba(247, 118, 142, 0.15)",
    "review": "#ff9e64",
    "review_soft": "rgba(255, 158, 100, 0.15)",
    "info": "#7dcfff",
    "info_soft": "rgba(125, 207, 255, 0.15)",
    "selection": "#7aa2f7",
    "safe": "#9ece6a",
}

VAPORWAVE = {
    "window": "#0d001a",
    "panel": "#150029",
    "surface": "#200040",
    "surface2": "#2d0059",
    "elevated": "#3b0073",
    "border": "#2d0059",
    "border2": "#4a008c",
    "text": "#e6ffff",
    "muted": "#99ffff",
    "faint": "#4dffff",
    "accent": "#ff00ff",
    "accent_hover": "#ff4dff",
    "accent_pressed": "#cc00cc",
    "accent_soft": "rgba(255, 0, 255, 0.15)",
    "success": "#00ffcc",
    "success_soft": "rgba(0, 255, 204, 0.15)",
    "warning": "#ffcc00",
    "warning_soft": "rgba(255, 204, 0, 0.15)",
    "danger": "#ff0066",
    "danger_soft": "rgba(255, 0, 102, 0.15)",
    "review": "#ff9900",
    "review_soft": "rgba(255, 153, 0, 0.15)",
    "info": "#00ffff",
    "info_soft": "rgba(0, 255, 255, 0.15)",
    "selection": "#ff00ff",
    "safe": "#00ffcc",
}

VAULT = {
    "window": "#15233d",
    "panel": "#1b2d4f",
    "surface": "#233963",
    "surface2": "#2c487a",
    "elevated": "#375996",
    "border": "#2c487a",
    "border2": "#4167ad",
    "text": "#f0f4f8",
    "muted": "#a6b8d4",
    "faint": "#738eb5",
    "accent": "#fcd12a",
    "accent_hover": "#fde066",
    "accent_pressed": "#d9b01c",
    "accent_soft": "rgba(252, 209, 42, 0.15)",
    "success": "#4ade80",
    "success_soft": "rgba(74, 222, 128, 0.15)",
    "warning": "#facc15",
    "warning_soft": "rgba(250, 204, 21, 0.15)",
    "danger": "#ef4444",
    "danger_soft": "rgba(239, 68, 68, 0.15)",
    "review": "#fb923c",
    "review_soft": "rgba(251, 146, 60, 0.15)",
    "info": "#38bdf8",
    "info_soft": "rgba(56, 189, 248, 0.15)",
    "selection": "#fcd12a",
    "safe": "#4ade80",
}

WINDOWS_95 = {
    "window": "#b3b3b3",
    "panel": "#c0c0c0",
    "surface": "#d4d4d4",
    "surface2": "#e8e8e8",
    "elevated": "#ffffff",
    "border": "#a0a0a0",
    "border2": "#808080",
    "text": "#000000",
    "muted": "#404040",
    "faint": "#808080",
    "accent": "#000080",
    "accent_hover": "#0000ff",
    "accent_pressed": "#000040",
    "accent_soft": "rgba(0, 0, 128, 0.15)",
    "success": "#008000",
    "success_soft": "rgba(0, 128, 0, 0.15)",
    "warning": "#808000",
    "warning_soft": "rgba(128, 128, 0, 0.15)",
    "danger": "#ff0000",
    "danger_soft": "rgba(255, 0, 0, 0.15)",
    "review": "#800080",
    "review_soft": "rgba(128, 0, 128, 0.15)",
    "info": "#008080",
    "info_soft": "rgba(0, 128, 128, 0.15)",
    "selection": "#000080",
    "safe": "#008000",
}

CUSTOM = {
    "window": "#0c111c",
    "panel": "#111827",
    "surface": "#1e293b",
    "surface2": "#283548",
    "elevated": "#334155",
    "border": "#283548",
    "border2": "#3b4d66",
    "text": "#f8fafc",
    "muted": "#94a3b8",
    "faint": "#64748b",
    "accent": "#3b82f6",
    "accent_hover": "#60a5fa",
    "accent_pressed": "#2563eb",
    "accent_soft": "rgba(59, 130, 246, 0.15)",
    "success": "#34d399",
    "success_soft": "rgba(52, 211, 153, 0.15)",
    "warning": "#fbbf24",
    "warning_soft": "rgba(251, 191, 36, 0.15)",
    "danger": "#f87171",
    "danger_soft": "rgba(248, 113, 113, 0.15)",
    "review": "#fb923c",
    "review_soft": "rgba(251, 146, 60, 0.15)",
    "info": "#38bdf8",
    "info_soft": "rgba(56, 189, 248, 0.15)",
    "selection": "#3b82f6",
    "safe": "#34d399",
}

PALETTES = {
    "amber-crt": AMBER_CRT,
    "analog-horror": ANALOG_HORROR,
    "adwaita-dark": ADWAITA_DARK,
    "adwaita-light": ADWAITA_LIGHT,
    "arctic": ARCTIC,
    "black-mesa": BLACK_MESA,
    "bubblegum": BUBBLEGUM,
    "cobalt": COBALT,
    "coffee": COFFEE,
    "commodore-64": COMMODORE_64,
    "crimson": CRIMSON,
    "cyberpunk": CYBERPUNK,
    "dark": DARK,
    "dracula": DRACULA,
    "emerald": EMERALD,
    "forest": FOREST,
    "gameboy": GAMEBOY,
    "graphite": GRAPHITE,
    "gruvbox": GRUVBOX,
    "high-contrast": HIGH_CONTRAST,
    "lavender": LAVENDER,
    "light": LIGHT,
    "matcha": MATCHA,
    "matrix": MATRIX,
    "midnight": MIDNIGHT,
    "mint-choco": MINT_CHOCO,
    "monokai": MONOKAI,
    "nord": NORD,
    "oceanic": OCEANIC,
    "oled": OLED,
    "one-dark": ONE_DARK,
    "parchment": PARCHMENT,
    "pulp-seventies": PULP_SEVENTIES,
    "rose-pine": ROSE_PINE,
    "slate": SLATE,
    "solar-eclipse": SOLAR_ECLIPSE,
    "solarized-dark": SOLARIZED_DARK,
    "sunset": SUNSET,
    "synthwave": SYNTHWAVE,
    "tokyo-night": TOKYO_NIGHT,
    "vaporwave": VAPORWAVE,
    "vault": VAULT,
    "windows-95": WINDOWS_95,
    "custom": CUSTOM,
}

THEME_LABELS = {
    "amber-crt": "Amber CRT",
    "analog-horror": "Analog VHS",
    "adwaita-dark": "Adwaita Dark",
    "adwaita-light": "Adwaita Light",
    "arctic": "Arctic Light",
    "black-mesa": "Facility Orange",
    "bubblegum": "Bubblegum Pop",
    "cobalt": "Cobalt Royal",
    "coffee": "Espresso Roast",
    "commodore-64": "Commodore 64",
    "crimson": "Crimson Velvet",
    "cyberpunk": "Cyberpunk Neon",
    "dark": "Dark (default)",
    "dracula": "Dracula",
    "emerald": "Emerald Obsidian",
    "forest": "Forest",
    "gameboy": "Handheld Green",
    "graphite": "Graphite",
    "gruvbox": "Gruvbox Retro",
    "high-contrast": "High Contrast",
    "lavender": "Lavender Mist",
    "light": "Light",
    "matcha": "Matcha Latte",
    "matrix": "Matrix Terminal",
    "midnight": "Midnight Blue",
    "mint-choco": "Mint Chocolate",
    "monokai": "Monokai Pro",
    "nord": "Nordic Frost",
    "oceanic": "Oceanic Abyss",
    "oled": "OLED Black",
    "one-dark": "One Dark",
    "parchment": "Parchment & Ink",
    "pulp-seventies": "70s Pulp",
    "rose-pine": "Rosé Pine",
    "slate": "Slate",
    "solar-eclipse": "Solar Eclipse",
    "solarized-dark": "Solarized Dark",
    "sunset": "Sunset Glow",
    "synthwave": "Synthwave '80s",
    "tokyo-night": "Tokyo Night",
    "vaporwave": "Vaporwave '90s",
    "vault": "Vault 1950s",
    "windows-95": "Retro OS",
    "custom": "Custom Theme",
}

THEME_CATEGORIES = {
    "modern-dark": "Modern Dark",
    "light": "Light & Pastel",
    "retro": "Retro & Vintage",
    "cyber": "Cyber & Synth",
    "code": "Code Palettes",
    "nature": "Warm & Nature",
    "custom": "Custom",
}

THEME_CATEGORY_MAP = {
    "custom": "custom",
    "dark": "modern-dark",
    "adwaita-dark": "modern-dark",
    "oled": "modern-dark",
    "slate": "modern-dark",
    "graphite": "modern-dark",
    "midnight": "modern-dark",
    "high-contrast": "modern-dark",
    "light": "light",
    "adwaita-light": "light",
    "arctic": "light",
    "bubblegum": "light",
    "parchment": "light",
    "windows-95": "retro",
    "commodore-64": "retro",
    "gameboy": "retro",
    "amber-crt": "retro",
    "matrix": "retro",
    "vault": "retro",
    "analog-horror": "retro",
    "pulp-seventies": "retro",
    "cyberpunk": "cyber",
    "synthwave": "cyber",
    "vaporwave": "cyber",
    "solar-eclipse": "cyber",
    "dracula": "code",
    "monokai": "code",
    "tokyo-night": "code",
    "nord": "code",
    "one-dark": "code",
    "rose-pine": "code",
    "solarized-dark": "code",
    "cobalt": "code",
    "coffee": "nature",
    "matcha": "nature",
    "forest": "nature",
    "gruvbox": "nature",
    "sunset": "nature",
    "emerald": "nature",
    "crimson": "nature",
    "lavender": "nature",
    "mint-choco": "nature",
    "oceanic": "nature",
    "black-mesa": "nature",
}

THEME_DESCRIPTIONS = {
    "custom": "Personalized theme generated from your chosen primary color",
    "dark": "Default dark sleek styling with blue accents",
    "oled": "Pitch-black dark mode optimized for OLED screens",
    "slate": "Cool slate gray with soft balanced tones",
    "graphite": "Deep graphite charcoal with monochrome focus",
    "midnight": "Deep midnight navy with royal accents",
    "high-contrast": "Maximized contrast for high visibility & accessibility",
    "light": "Crisp clean light mode with standard bright surfaces",
    "arctic": "Cool icy arctic white with vibrant cyan-blue",
    "bubblegum": "Playful candy pink and bright pastel highlights",
    "parchment": "Warm vintage manuscript beige and deep sepia ink",
    "windows-95": "Nostalgic 1995 desktop gray and classic teal",
    "commodore-64": "Iconic 1982 8-bit blue and lavender computer vibes",
    "gameboy": "Authentic 4-shade dot-matrix LCD green handheld",
    "amber-crt": "Glowing monochromatic amber phosphor CRT terminal",
    "matrix": "Cybernetic digital rain and phosphor terminal green",
    "vault": "1950s atomic-age Pip-Boy amber & survival green",
    "analog-horror": "Gritty low-light VHS tape and warning red accents",
    "adwaita-dark": "GNOME-inspired neutral dark surfaces with restrained blue accents",
    "adwaita-light": "GNOME-inspired clean light surfaces with understated blue accents",
    "pulp-seventies": "Groovy 1970s paperback yellow, orange & brown",
    "cyberpunk": "Night City neon yellow and high-tech electric cyan",
    "synthwave": "Outrun '80s retro neon magenta and glowing grid violet",
    "vaporwave": "Aesthetic '90s pastel sunset pink, teal & lavender",
    "solar-eclipse": "Dark celestial totality corona and blazing solar gold",
    "dracula": "The legendary dark theme for developers and vampires",
    "monokai": "Iconic code editor color scheme with vivid accents",
    "tokyo-night": "Modern Tokyo neon nightscape aesthetic",
    "nord": "Arctic, north-bluish clean and elegant developer palette",
    "one-dark": "Atom & VSCode iconic balanced developer theme",
    "rose-pine": "Soho-inspired all natural pine, rose and gold",
    "solarized-dark": "Ethan Schoonover's calibrated precision dark palette",
    "cobalt": "Royal deep cobalt blue and contrasting goldenrod",
    "coffee": "Warm espresso beans, roasted crema and cozy mocha",
    "matcha": "Serene Japanese green tea leaves and rich cream",
    "forest": "Deep evergreen pine woods and earthy moss",
    "gruvbox": "Retro groove box warm earthy tones",
    "sunset": "Dusk horizon gradient with golden orange and purple",
    "emerald": "Dark obsidian stone with lustrous emerald jewels",
    "crimson": "Luxurious velvet dark mahogany and deep royal red",
    "lavender": "Calming pastel lavender mist and violet florals",
    "mint-choco": "Dark rich chocolate with crisp refreshing mint",
    "oceanic": "Deep marine abyss with turquoise coral highlights",
    "black-mesa": "Lambda facility industrial hazard orange & titanium",
}


def _build_stylesheet(p: dict) -> str:
    return f"""
    QMainWindow, QDialog, QWidget#CentralWidget, QWidget#WindowRoot {{
        background-color: {p["window"]};
    }}
    QWidget {{
        color: {p["text"]};
        font-family: 'Segoe UI Variable Display', 'Segoe UI', -apple-system, sans-serif;
        font-size: 13px;
    }}
    QStackedWidget {{ background: transparent; }}
    QScrollArea {{ background: transparent; border: none; }}
    QScrollArea > QWidget > QWidget {{ background: transparent; }}
    QLabel {{
        background: transparent;
        border: none;
    }}
    QLabel[pageTitle="true"] {{
        font-size: 22px;
        font-weight: 700;
        letter-spacing: -0.3px;
        color: {p["text"]};
    }}
    QLabel[pageSubtitle="true"] {{
        font-size: 13px;
        color: {p["muted"]};
        line-height: 1.4;
    }}
    QLabel[section="true"] {{
        font-size: 11px;
        font-weight: 700;
        letter-spacing: 1.2px;
        text-transform: uppercase;
        color: {p["faint"]};
    }}
    QLabel[subtle="true"] {{
        color: {p["muted"]};
    }}
    QLabel[strong="true"] {{
        font-weight: 600;
        color: {p["text"]};
    }}
    QLabel[heroValue="true"] {{
        font-size: 32px;
        font-weight: 800;
        letter-spacing: -0.5px;
        color: {p["text"]};
    }}
    QFrame[card="true"] {{
        background-color: {p["panel"]};
        border: 1px solid {p["border"]};
        border-radius: 10px;
    }}
    QFrame[cardHover="true"]:hover {{
        border-color: {p["border2"]};
        background-color: {p["surface"]};
    }}
    /* Driven by effects.elevate(). A property toggle rather than a geometry change,
       so a lifting card cannot reflow the row it sits in. */
    QFrame[hovered="true"] {{
        border: 1px solid {p["accent"]};
        background-color: {p["elevated"]};
    }}
    QFrame[statCard="true"] {{
        background-color: {p["panel"]};
        border: 1px solid {p["border"]};
        border-radius: 10px;
    }}
    QFrame[statCard="true"]:hover {{
        border-color: {p["border2"]};
    }}
    QLabel[badge="true"] {{
        background-color: {p["surface"]};
        color: {p["muted"]};
        border-radius: 9px;
        padding: 3px 10px;
        font-size: 11px;
        font-weight: 600;
    }}
    QLabel[badge="true"][level="accent"] {{ background-color: {p["accent_soft"]}; color: {p["accent"]}; }}
    QLabel[badge="true"][level="safe"]   {{ background-color: {p["success_soft"]}; color: {p["success"]}; }}
    QLabel[badge="true"][level="warn"]   {{ background-color: {p["warning_soft"]}; color: {p["warning"]}; }}
    QLabel[badge="true"][level="danger"] {{ background-color: {p["danger_soft"]}; color: {p["danger"]}; }}
    QLabel[badge="true"][level="review"] {{ background-color: {p["review_soft"]}; color: {p["review"]}; }}
    QLabel[badge="true"][level="info"]   {{ background-color: {p["info_soft"]}; color: {p["info"]}; }}
    QPushButton {{
        background-color: {p["surface"]};
        border: 1px solid {p["border"]};
        border-radius: 6px;
        padding: 7px 16px;
        color: {p["text"]};
        font-weight: 500;
        font-size: 13px;
    }}
    QPushButton:hover {{
        background-color: {p["surface2"]};
        border-color: {p["border2"]};
    }}
    QPushButton:pressed {{
        background-color: {p["elevated"]};
    }}
    QPushButton:focus {{
        border-color: {p["accent"]};
    }}
    QPushButton:disabled {{
        color: {p["faint"]};
        background-color: {p["surface"]};
        border-color: {p["border"]};
    }}
    QPushButton[primary="true"] {{
        background-color: {p["accent"]};
        border: 1px solid {p["accent"]};
        color: #ffffff;
        font-weight: 600;
    }}
    QPushButton[primary="true"]:hover {{
        background-color: {p["accent_hover"]};
        border-color: {p["accent_hover"]};
    }}
    QPushButton[primary="true"]:pressed {{
        background-color: {p["accent_pressed"]};
        border-color: {p["accent_pressed"]};
    }}
    QPushButton[primary="true"]:disabled {{
        background-color: {p["surface2"]};
        border-color: {p["border"]};
        color: {p["faint"]};
    }}
    QPushButton[danger="true"] {{
        background-color: {p["danger"]};
        border: 1px solid {p["danger"]};
        color: #ffffff;
        font-weight: 600;
    }}
    QPushButton[danger="true"]:hover {{
        background-color: #f87171;
        border-color: #f87171;
    }}
    QPushButton[danger="true"]:pressed {{
        background-color: #dc2626;
        border-color: #dc2626;
    }}
    QPushButton[danger="true"]:disabled {{
        background-color: {p["surface2"]};
        border-color: {p["border"]};
        color: {p["faint"]};
    }}
    QPushButton[ghost="true"] {{
        background: transparent;
        border: none;
        color: {p["accent"]};
        padding: 4px 8px;
        font-weight: 500;
    }}
    QPushButton[ghost="true"]:hover {{
        background-color: {p["accent_soft"]};
        border-radius: 4px;
    }}
    QPushButton[chip="true"] {{
        background-color: transparent;
        border: none;
        border-bottom: 2px solid transparent;
        border-radius: 0px;
        padding: 4px 10px;
        color: {p["muted"]};
        font-size: 12px;
        font-weight: 500;
    }}
    QPushButton[chip="true"]:hover {{
        background-color: transparent;
        color: {p["text"]};
        border-bottom: 2px solid {p["border2"]};
    }}
    QPushButton[chip="true"][active="true"] {{
        background-color: transparent;
        border-bottom: 2px solid {p["accent"]};
        color: {p["accent"]};
        font-weight: 600;
    }}
    QFrame#SideBar {{
        background-color: {p["panel"]};
        border-right: 1px solid {p["border"]};
    }}
    QLabel#BrandTitle {{
        font-size: 16px;
        font-weight: 700;
        letter-spacing: -0.2px;
        color: {p["text"]};
    }}
    QLabel#BrandSub {{
        font-size: 11px;
        color: {p["faint"]};
    }}
    QLabel[navSection="true"] {{
        font-size: 10px;
        font-weight: 700;
        letter-spacing: 1.2px;
        color: {p["faint"]};
        padding-left: 10px;
        padding-top: 10px;
        padding-bottom: 2px;
        text-transform: uppercase;
    }}
    QPushButton[nav="true"] {{
        background: transparent;
        border: none;
        border-left: 3px solid transparent;
        border-radius: 6px;
        padding-left: 10px;
        padding-right: 10px;
        color: {p["muted"]};
        font-size: 13px;
        font-weight: 500;
        text-align: left;
    }}
    QPushButton[nav="true"]:hover {{
        background-color: {p["surface"]};
        color: {p["text"]};
    }}
    QPushButton[nav="true"][active="true"] {{
        background-color: {p["accent_soft"]};
        color: {p["accent"]};
        border-left: 3px solid {p["accent"]};
        font-weight: 600;
    }}
    QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {{
        background-color: {p["surface"]};
        border: 1px solid {p["border"]};
        border-radius: 6px;
        padding: 6px 10px;
        color: {p["text"]};
        selection-background-color: {p["selection"]};
    }}
    QLineEdit:hover, QSpinBox:hover, QDoubleSpinBox:hover, QComboBox:hover {{
        border-color: {p["border2"]};
    }}
    QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {{
        border-color: {p["accent"]};
        background-color: {p["surface"]};
    }}
    QComboBox::drop-down {{
        border: none;
        width: 24px;
    }}
    QComboBox QAbstractItemView {{
        background-color: {p["elevated"]};
        border: 1px solid {p["border"]};
        border-radius: 6px;
        selection-background-color: {p["accent_soft"]};
        selection-color: {p["accent"]};
        padding: 4px;
        outline: none;
    }}
    QSpinBox::up-button, QSpinBox::down-button {{
        background-color: {p["surface"]};
        border: none;
        width: 18px;
    }}
    QSpinBox::up-button:hover, QSpinBox::down-button:hover {{
        background-color: {p["surface2"]};
    }}
    QCheckBox {{
        spacing: 8px;
        color: {p["text"]};
        background: transparent;
    }}
    QCheckBox::indicator {{
        width: 16px;
        height: 16px;
        border: 1px solid {p["border2"]};
        border-radius: 4px;
        background: {p["surface"]};
    }}
    QCheckBox::indicator:hover {{
        border-color: {p["accent"]};
    }}
    QCheckBox::indicator:checked {{
        background-color: {p["accent"]};
        border-color: {p["accent"]};
    }}
    QCheckBox::indicator:disabled {{
        background: {p["border"]};
        border-color: {p["border"]};
    }}
    QProgressBar {{
        border: none;
        border-radius: 5px;
        background: {p["surface"]};
        text-align: center;
        height: 18px;
        color: {p["muted"]};
        font-weight: 600;
        font-size: 11px;
    }}
    QProgressBar::chunk {{
        border-radius: 5px;
        background-color: {p["accent"]};
    }}
    QProgressBar[good="true"]::chunk {{ background-color: {p["success"]}; }}
    QProgressBar[warn="true"]::chunk {{ background-color: {p["warning"]}; }}
    QProgressBar[bad="true"]::chunk  {{ background-color: {p["danger"]}; }}
    QProgressBar[thin="true"] {{
        height: 6px;
        border-radius: 3px;
    }}
    QProgressBar[thin="true"]::chunk {{ border-radius: 3px; }}
    QTreeWidget, QTableWidget, QListWidget {{
        background-color: {p["panel"]};
        border: 1px solid {p["border"]};
        border-radius: 8px;
        alternate-background-color: {p["surface"]};
        selection-background-color: {p["accent_soft"]};
        selection-color: {p["text"]};
        outline: none;
    }}
    QTableWidget::item, QTreeWidget::item {{
        padding: 4px 6px;
    }}
    QTableWidget::item:selected, QTreeWidget::item:selected {{
        background-color: {p["accent_soft"]};
        color: {p["text"]};
    }}
    QTableWidget::item:hover, QTreeWidget::item:hover {{
        background-color: {p["surface2"]};
    }}
    QHeaderView::section {{
        background-color: {p["surface"]};
        border: none;
        border-bottom: 1px solid {p["border"]};
        padding: 8px 10px;
        color: {p["faint"]};
        font-weight: 600;
        font-size: 12px;
    }}
    QHeaderView::section:hover {{
        background-color: {p["surface2"]};
        color: {p["text"]};
    }}
    QGroupBox {{
        border: 1px solid {p["border"]};
        border-radius: 10px;
        margin-top: 14px;
        background-color: {p["panel"]};
        padding-top: 14px;
    }}
    QGroupBox::title {{
        subcontrol-origin: margin;
        left: 12px;
        padding: 0 6px;
        color: {p["muted"]};
        font-weight: 600;
        font-size: 12px;
    }}
    QFrame#DriveCard {{
        background-color: {p["panel"]};
        border: 1px solid {p["border"]};
        border-radius: 10px;
    }}
    QFrame#DriveCard:hover {{
        border-color: {p["border2"]};
        background-color: {p["surface"]};
    }}
    QFrame#DriveCard[selected="true"] {{
        border: 2px solid {p["accent"]};
        background-color: {p["surface"]};
    }}
    QMenu {{
        background-color: {p["elevated"]};
        border: 1px solid {p["border"]};
        border-radius: 8px;
        padding: 6px;
    }}
    QMenu::item {{
        padding: 7px 24px 7px 12px;
        border-radius: 5px;
        color: {p["text"]};
    }}
    QMenu::item:selected {{
        background-color: {p["accent_soft"]};
        color: {p["accent"]};
    }}
    QMenu::separator {{
        height: 1px;
        background-color: {p["border"]};
        margin: 4px 6px;
    }}
    QToolTip {{
        background-color: {p["elevated"]};
        color: {p["text"]};
        border: 1px solid {p["border2"]};
        border-radius: 5px;
        padding: 5px 9px;
        font-size: 12px;
    }}
    QStatusBar {{
        background: {p["panel"]};
        border-top: 1px solid {p["border"]};
        color: {p["muted"]};
        font-size: 12px;
        padding: 2px 10px;
    }}
    QScrollBar:vertical {{
        background: transparent;
        width: 8px;
        margin: 2px;
    }}
    QScrollBar::handle:vertical {{
        background: {p["border2"]};
        border-radius: 4px;
        min-height: 26px;
    }}
    QScrollBar::handle:vertical:hover {{
        background: {p["faint"]};
    }}
    QScrollBar:horizontal {{
        background: transparent;
        height: 6px;
        margin: 1px;
    }}
    QScrollBar::handle:horizontal {{
        background: {p["border2"]};
        border-radius: 3px;
        min-width: 26px;
    }}
    QScrollBar::handle:horizontal:hover {{
        background: {p["faint"]};
    }}
    QScrollBar::add-line, QScrollBar::sub-line {{ width: 0; height: 0; }}
    QScrollBar::add-page, QScrollBar::sub-page {{ background: transparent; }}
    """


def apply_theme(app: QApplication, theme: str) -> None:
    palette = palette_for(theme)
    app.setStyleSheet(_build_stylesheet(palette))
    from PySide6.QtGui import QPalette

    pal = QPalette()
    bg = QColor(palette["window"])
    surface = QColor(palette["surface"])
    text = QColor(palette["text"])
    muted = QColor(palette["muted"])
    accent = QColor(palette["accent"])
    pal.setColor(QPalette.ColorRole.Window, bg)
    pal.setColor(QPalette.ColorRole.WindowText, text)
    pal.setColor(QPalette.ColorRole.Base, surface)
    pal.setColor(QPalette.ColorRole.AlternateBase, QColor(palette["panel"]))
    pal.setColor(QPalette.ColorRole.Text, text)
    pal.setColor(QPalette.ColorRole.Button, surface)
    pal.setColor(QPalette.ColorRole.ButtonText, text)
    pal.setColor(QPalette.ColorRole.Highlight, accent)
    pal.setColor(QPalette.ColorRole.HighlightedText, QColor("white"))
    pal.setColor(QPalette.ColorRole.PlaceholderText, muted)
    pal.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, muted)
    pal.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, muted)
    app.setPalette(pal)


_custom_palette_cache: dict = {}


def get_custom_theme_palette(custom_config: dict | None = None) -> dict:
    """Generate and cache the custom palette based on settings or provided config."""
    global _custom_palette_cache
    if custom_config is None:
        try:
            from crapcleaner.config import load_settings

            settings = load_settings()
            custom_config = settings.get("custom_theme", {})
        except Exception:
            custom_config = {}

    primary = custom_config.get("primary_color", "#3b82f6")
    mode = custom_config.get("mode", "dark")
    mood = custom_config.get("mood", "cohesive")
    s_contrast = custom_config.get("surface_contrast", 1.0)
    a_intensity = custom_config.get("accent_intensity", 1.0)
    bg_dark = custom_config.get("bg_darkness", 1.0)

    cache_key = (primary, mode, mood, float(s_contrast), float(a_intensity), float(bg_dark))
    if _custom_palette_cache.get("key") == cache_key and "palette" in _custom_palette_cache:
        return _custom_palette_cache["palette"]

    from crapcleaner.gui.color_engine import generate_custom_palette

    pal = generate_custom_palette(
        primary_color=primary,
        mode=mode,
        surface_contrast=s_contrast,
        accent_intensity=a_intensity,
        bg_darkness=bg_dark,
        mood=mood,
    )
    _custom_palette_cache["key"] = cache_key
    _custom_palette_cache["palette"] = pal
    return pal


def invalidate_custom_theme_cache() -> None:
    """Clear the cached custom palette so the next lookup regenerates it."""
    global _custom_palette_cache
    _custom_palette_cache.clear()


THEMES = tuple(PALETTES)


def palette_for(theme: str) -> dict:
    if theme == "custom":
        return get_custom_theme_palette()
    return PALETTES.get(theme, DARK)


def theme_label(theme: str) -> str:
    return THEME_LABELS.get(theme, theme.title())


def get_theme_category(theme: str) -> str:
    return THEME_CATEGORY_MAP.get(theme, "modern-dark")


def get_theme_category_label(theme: str) -> str:
    cat = get_theme_category(theme)
    return THEME_CATEGORIES.get(cat, cat.replace("-", " ").title())


def get_theme_description(theme: str) -> str:
    return THEME_DESCRIPTIONS.get(theme, f"{theme_label(theme)} color scheme")


def is_dark_theme(theme: str) -> bool:
    pal = palette_for(theme)
    hex_color = pal.get("window", "#000000").lstrip("#")
    if len(hex_color) == 6:
        try:
            r = int(hex_color[0:2], 16)
            g = int(hex_color[2:4], 16)
            b = int(hex_color[4:6], 16)
            lum = 0.299 * r + 0.587 * g + 0.114 * b
            return lum < 128
        except ValueError:
            pass
    return True


def get_theme_swatches(theme: str) -> list[str]:
    pal = palette_for(theme)
    return [
        pal.get("window", "#000000"),
        pal.get("surface", "#222222"),
        pal.get("accent", "#3b82f6"),
        pal.get("text", "#ffffff"),
        pal.get("success", "#22c55e"),
    ]


def fade_theme_change(window, apply_callback, duration_ms: int = 180) -> None:
    from PySide6.QtCore import QEasingCurve, QPropertyAnimation, Qt
    from PySide6.QtWidgets import QGraphicsOpacityEffect, QLabel

    fade_anim = getattr(window, "_theme_fade_anim", None)
    if fade_anim:
        try:
            fade_anim.stop()
        except Exception:
            pass
        setattr(window, "_theme_fade_anim", None)

    fade_overlay = getattr(window, "_theme_fade_overlay", None)
    if fade_overlay:
        try:
            fade_overlay.deleteLater()
        except Exception:
            pass
        setattr(window, "_theme_fade_overlay", None)

    snapshot = None
    if duration_ms > 0 and window is not None and window.isVisible():
        try:
            snapshot = window.grab()
        except Exception:
            snapshot = None
    apply_callback()
    if snapshot is None or snapshot.isNull():
        return
    try:
        overlay = QLabel(window)
        overlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        overlay.setPixmap(snapshot)
        overlay.setGeometry(0, 0, snapshot.width(), snapshot.height())
        effect = QGraphicsOpacityEffect(overlay)
        overlay.setGraphicsEffect(effect)
        overlay.show()
        overlay.raise_()
        animation = QPropertyAnimation(effect, b"opacity", overlay)
        animation.setDuration(duration_ms)
        animation.setStartValue(1.0)
        animation.setEndValue(0.0)
        animation.setEasingCurve(QEasingCurve.Type.InOutQuad)
        animation.finished.connect(overlay.deleteLater)
        setattr(window, "_theme_fade_anim", animation)
        setattr(window, "_theme_fade_overlay", overlay)
        animation.start()
    except Exception:
        pass


def color(theme: str, name: str) -> str:
    return palette_for(theme)[name]


def accent_color(theme: str) -> QColor:
    return QColor(color(theme, "accent"))


def make_window_icon() -> QIcon:
    from PySide6.QtCore import QRectF, Qt
    from PySide6.QtGui import QBrush, QLinearGradient, QPainter, QPen, QPixmap

    from crapcleaner.gui.icons import draw_glyph

    pixmap = QPixmap(64, 64)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.TextAntialiasing)
    rect = QRectF(2, 2, 60, 60)
    gradient = QLinearGradient(rect.topLeft(), rect.bottomRight())
    gradient.setColorAt(0.0, QColor("#2563eb"))
    gradient.setColorAt(1.0, QColor("#60a5fa"))
    painter.setBrush(QBrush(gradient))
    painter.setPen(QPen(QColor("#3b82f6"), 1))
    painter.drawRoundedRect(rect, 14, 14)
    draw_glyph(painter, rect, "brand", "#ffffff", 38)
    painter.end()
    return QIcon(pixmap)
