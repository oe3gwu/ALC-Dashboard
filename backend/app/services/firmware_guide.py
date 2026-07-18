"""Guided firmware-update instructions per device profile (no in-app flash)."""

from __future__ import annotations

from typing import Any

from app.devices.profiles import DeviceProfile, get_profile

_TOOL_HINT = "Update-Tool aus dem ELV-Paket — Pfad/COM laut Paket-Anleitung"

_COMMON_NOTES = [
    "Dieses Dashboard flasht nicht — nur Anleitung.",
    "Nur offizielle ELV-Firmware-Dateien verwenden.",
    "USB-Kabel während des Updates nicht trennen.",
    "Bei Abbruch: Vorgang laut Anleitung im ELV-Paket wiederholen.",
]


def build_firmware_guide(device_model: str) -> dict[str, Any]:
    profile = get_profile(device_model)
    body = _guide_for_profile(profile)
    return {
        "device_model": profile.id,
        "device_label": profile.label,
        "supported": profile.features.firmware_guided,
        "tool_hint": _TOOL_HINT,
        **body,
    }


def _guide_for_profile(profile: DeviceProfile) -> dict[str, Any]:
    mid = profile.id
    if mid == "alc8500_2_expert":
        return {
            "safety": "Nur Dateien der Form updateALC8xxx-2_V… (ELV-Paket, Webcode #10073). Keine Akkus anschließen.",
            "filename_hint": "updateALC8xxx-2_V….bin/.hex (ELV-Paket, Webcode #10073)",
            "steps": [
                "Offizielle Firmware von ELV herunterladen und entpacken (Webcode #10073).",
                "ALC per USB verbinden.",
                "Keine Akkus angeschlossen lassen.",
                "Gerät am Netzschalter ausschalten — USB-Kabel stecken lassen.",
                "Beide Pfeiltasten (links + rechts) gedrückt halten und Gerät einschalten.",
                "Loslassen, sobald „Display Test“ erscheint — Anzeige bis Update-Ende belassen.",
                f"{_TOOL_HINT} — nicht dieses Dashboard.",
                "Nach Erfolg startet das ALC selbstständig neu. Danach Dashboard neu verbinden.",
            ],
            "notes": list(_COMMON_NOTES)
            + [
                "Bootloader-Schritte: ELV Soft-/Firmware-Upgrade-PDF (ALC 8500 Expert-2).",
            ],
        }

    if mid in ("alc8000", "alc8500_expert"):
        return {
            "safety": "Firmware und Bootloader-Schritte nur laut Anleitung im ELV-Download für dieses Modell. Keine Akkus anschließen.",
            "filename_hint": "Firmware-Datei laut ELV-Download für ALC 8000 / 8500 Expert",
            "steps": [
                f"Offizielle Firmware für {profile.label} von ELV herunterladen und entpacken.",
                "Dateinamen und Bootloader-Tastenfolge der Paket-Anleitung folgen (nicht raten).",
                "Gerät per USB verbinden; keine Akkus angeschlossen.",
                "Gerät laut Paket-Anleitung in den Update-Modus bringen — USB stecken lassen.",
                f"{_TOOL_HINT} — nicht dieses Dashboard.",
                "Nach Erfolg Gerät neu starten und Dashboard neu verbinden.",
            ],
            "notes": list(_COMMON_NOTES)
            + [
                "Manuals bestätigen Firmware-Update über USB; Details stehen im ELV-Paket.",
            ],
        }

    if mid == "alc5000_mobile":
        return {
            "safety": "Laut Bedienungsanleitung (§30.5): an beiden Ladekanälen keinen Akku anschließen.",
            "filename_hint": "Firmware-Datei laut ELV-Download für ALC 5000 Mobile",
            "steps": [
                "Offizielle Firmware für ALC 5000 Mobile von ELV herunterladen und entpacken.",
                "Sicherstellen, dass an beiden Ladekanälen kein Akku angeschlossen ist (Manual §30.5).",
                "Gerät per USB verbinden.",
                "Update-Modus und Dateiauswahl laut Anleitung im ELV-Firmware-Paket.",
                f"{_TOOL_HINT} — nicht dieses Dashboard.",
                "Nach Erfolg Gerät neu starten und Dashboard neu verbinden.",
            ],
            "notes": list(_COMMON_NOTES)
            + [
                "Quelle: ALC 5000 Mobile Bedienungsanleitung §30.5.",
            ],
        }

    if mid == "alc3000_pc":
        return {
            "safety": "Laut Bedienungsanleitung (§16.5): keinen Akku anschließen.",
            "filename_hint": "Firmware-Datei laut ELV-Download für ALC 3000 PC",
            "steps": [
                "Offizielle Firmware für ALC 3000 PC von ELV herunterladen und entpacken.",
                "Sicherstellen, dass kein Akku angeschlossen ist (Manual §16.5).",
                "Gerät per USB verbinden.",
                "Update-Modus und Dateiauswahl laut Anleitung im ELV-Firmware-Paket.",
                f"{_TOOL_HINT} — nicht dieses Dashboard.",
                "Nach Erfolg Gerät neu starten und Dashboard neu verbinden.",
            ],
            "notes": list(_COMMON_NOTES)
            + [
                "Quelle: ALC 3000 PC Bedienungsanleitung §16.5.",
            ],
        }

    return {
        "safety": (
            f"Für {profile.label} ist kein Firmware-Assistent freigeschaltet "
            "(kein dokumentiertes User-USB-Flash)."
        ),
        "filename_hint": "—",
        "steps": [
            "Kein geführtes USB-Firmware-Update für dieses Gerätemodell in diesem Dashboard.",
        ],
        "notes": [
            "ALC 7000 Expert: PC-Anbindung über RS-232 zur Steuerung/Logger — kein User-USB-Flash hier.",
        ],
    }
