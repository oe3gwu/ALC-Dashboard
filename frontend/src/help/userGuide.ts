import type { Locale } from '../i18n'

export type GuideLink = { label: string; href: string }

export type GuideBlock =
  | { type: 'p'; text: string }
  | { type: 'ul'; items: string[] }
  | { type: 'ol'; items: string[] }
  | { type: 'warn'; text: string }
  | { type: 'links'; items: GuideLink[] }

export type GuideSection = {
  id: string
  title: string
  blocks: GuideBlock[]
}

const ELV_LINKS: GuideLink[] = [
  {
    label: 'ALC 8500-2 Expert — Bedienungsanleitung (PDF)',
    href: 'https://media.elv.com/file/59066_69326_alc8500e_2_um.pdf',
  },
  {
    label: 'ALC 8000 Plus / 8500 Expert — ELVjournal Protokoll (PDF)',
    href: 'https://media.elv.com/file/59066_alc8000_alc8500_expert_teil7.pdf',
  },
  {
    label: 'ALC 3000 PC / 5000 Mobile — ChargeEasy Teil 2 (PDF)',
    href: 'https://media.elv.com/file/76962_alc3000pc_teil2.pdf',
  },
]

const ELV_LINKS_EN: GuideLink[] = [
  {
    label: 'ALC 8500-2 Expert — user manual (PDF)',
    href: 'https://media.elv.com/file/59066_69326_alc8500e_2_um.pdf',
  },
  {
    label: 'ALC 8000 Plus / 8500 Expert — ELVjournal protocol (PDF)',
    href: 'https://media.elv.com/file/59066_alc8000_alc8500_expert_teil7.pdf',
  },
  {
    label: 'ALC 3000 PC / 5000 Mobile — ChargeEasy part 2 (PDF)',
    href: 'https://media.elv.com/file/76962_alc3000pc_teil2.pdf',
  },
]

const de: GuideSection[] = [
  {
    id: 'overview',
    title: 'Überblick',
    blocks: [
      {
        type: 'p',
        text: 'Das ELV ALC Dashboard steuert ELV-/Voltcraft-ALC-Ladegeräte über USB oder serielle Schnittstelle. Die Navigation links führt zu den Funktionen; Sprache (DE/EN) und Hell-/Dunkelmodus stellen Sie oben rechts um.',
      },
      {
        type: 'p',
        text: 'Welche Menüpunkte sichtbar sind, hängt vom gewählten Gerätemodell ab (z. B. Datenlogger oder Akku-Datenbank nur bei unterstützten Geräten).',
      },
      {
        type: 'p',
        text: 'Diese Anleitung beschreibt die Bedienung des Dashboards und die grobe Bedeutung der Programme. Für Detailinfos (Grenzwerte, genaue Programmabläufe, Chemie-Tabellen, herstellerspezifische Sicherheitshinweise) immer die offizielle ELV-/Voltcraft-Bedienungsanleitung zum jeweiligen Ladegerät konsultieren — siehe Abschnitt „ELV-Gerätedokumentation“.',
      },
    ],
  },
  {
    id: 'safety',
    title: 'Sicherheit & Lithium',
    blocks: [
      {
        type: 'warn',
        text: 'Lithium-Akkus (Li-Ion, LiPo, LiFePO₄), die in Serie geschaltet sind, dürfen mit diesem Ladegerät nur mit aktivem Balancer bzw. als balanciertes Pack geladen werden. Ohne Balancing können einzelne Zellen überladen werden — Brand- und Explosionsgefahr.',
      },
      {
        type: 'warn',
        text: 'Parallel geschaltete Li-Zellen: nur baugleiche, gleich geladene Zellen bzw. freigegebene Packs laden. Ungeprüftes Parallel-Laden ohne passende Absicherung ist riskant.',
      },
      {
        type: 'ul',
        items: [
          'Akkuchemie und Zellenanzahl am Gerät/Dashboard korrekt setzen.',
          'Polarität beachten; beschädigte oder aufgeblähte Zellen nicht laden.',
          'Lade- und Entladeströme an Kapazität und Herstellerangaben anpassen — nicht „blind“ mit hohen Strömen fahren.',
          'Bei ungewöhnlicher Hitze, Geruch oder Geräuschen den Vorgang sofort abbrechen.',
        ],
      },
    ],
  },
  {
    id: 'chargeBasics',
    title: 'Richtig laden und entladen',
    blocks: [
      {
        type: 'p',
        text: 'Vor dem Start: Akkutyp, Zellen, Kapazität und Ströme prüfen. Die angezeigte Max.-Spannung beim Vorgang starten ist nur eine Orientierung aus Typ und Zellen — kein Ersatz für Herstellergrenzen.',
      },
      {
        type: 'ul',
        items: [
          'Laden: Programm „Laden“ — Abschluss über die Gerätechemie (−ΔU bzw. Spannungsgrenzen); danach oft Erhaltungsladung.',
          'Entladen: Programm „Entladen“ bis Entladeschluss — zur Kapazitätsprüfung oder zum Entleeren vor dem Neuladen.',
          'Ströme typischerweise im Bereich der Herstellerempfehlung wählen (oft ein Bruchteil bis etwa 1 C, je nach Chemie und Zelle).',
          'Pause: Wartezeit zwischen Phasen (z. B. nach dem Entladen vor dem Laden).',
          'Formierstrom: eigener Strom für Formier-/Auffrisch-Phasen, wo das Modell ihn anbietet.',
          'Maximale Ladung (Vollfaktor): begrenzt, wie „voll“ geladen wird — nur bei unterstützten Geräten.',
          'Blei-Aktivator: spezielles Programmteil für Bleiakkus — nur auf freigeschalteten Kanälen/Modellen.',
        ],
      },
      {
        type: 'p',
        text: 'Exakte Grenzwerte und empfohlenen Abläufe entnehmen Sie der ELV-Gerätedokumentation und dem Akku-Datenblatt.',
      },
    ],
  },
  {
    id: 'programs',
    title: 'Programme — wofür sie da sind',
    blocks: [
      {
        type: 'p',
        text: 'Nicht jedes Programm ist auf jedem Modell und für jede Chemie verfügbar. Formieren, Zyklen und Auffrischen akzeptiert das Gerät nur bei NiCd/NiMH/NiZn (bei Pb/Li erscheint eine Ablehnung). Die Zyklenanzahl für „Zyklen“ und „Formieren“ stellen Sie unter Akku-Typ-Parameter ein.',
      },
      {
        type: 'ul',
        items: [
          'Laden — nur laden bis zum Ladeende.',
          'Entladen — nur entladen (Restenergie / Kapazitätsmessung).',
          'Entladen–Laden — zuerst entladen, dann laden (häufig „frisch starten“).',
          'Test — kurzer Check bzw. Funktions-/Kapazitätsprüfung laut Gerätelogik.',
          'Wartung — schonendes bzw. erhaltendes Programm (je nach Chemie).',
          'Formieren — wiederholtes Laden/Entladen für neue oder lange gelagerte Ni-Zellen.',
          'Zyklen — mehrmals Entladen und Laden (Training oder Messung über mehrere Durchläufe).',
          'Auffrischen — Regenerieren / Kapazität wiederherstellen (typisch NiCd/NiMH nach längerer Lagerung).',
        ],
      },
    ],
  },
  {
    id: 'elvDocs',
    title: 'ELV-Gerätedokumentation',
    blocks: [
      {
        type: 'p',
        text: 'Für Detailinfos immer die offizielle Bedienungsanleitung Ihres Ladegeräts konsultieren. Die folgenden PDFs sind bekannte Herstellerquellen und ersetzen nicht die passende Anleitung zu Ihrem genauen Modell und Firmware-Stand:',
      },
      { type: 'links', items: ELV_LINKS },
      {
        type: 'p',
        text: 'Weitere Hinweise und Downloads finden Sie auf den ELV-/Voltcraft-Produktseiten zu Ihrem Gerät.',
      },
    ],
  },
  {
    id: 'connect',
    title: 'Verbindung herstellen',
    blocks: [
      {
        type: 'ol',
        items: [
          'Unter Einstellungen das richtige Gerätemodell wählen (z. B. ALC 8500-2 Expert).',
          'Seriellen Port eintragen (z. B. /dev/ttyUSB0) oder leer lassen für Auto-Detect.',
          'Für Tests ohne Hardware: Port leeren und Simulator aktivieren.',
          '„Verbinden“ drücken. „Speichern“ schreibt die Einstellung in config.yaml, startet aber keine Verbindung.',
          '„Trennen“ beendet die Verbindung absichtlich; nach unerwartetem USB-Abstecken versucht das Dashboard die Verbindung wiederherzustellen.',
        ],
      },
      {
        type: 'ul',
        items: [
          'Status in der Seitenleiste: Verbunden, Simulator (Zeit ×10), Fehler oder Offline.',
          'Unter Linux braucht der Benutzer oft die Gruppe dialout für den seriellen Port.',
          'Abfrageintervall steuert, wie oft Live-Daten vom Gerät geholt werden.',
        ],
      },
    ],
  },
  {
    id: 'channels',
    title: 'Kanäle',
    blocks: [
      {
        type: 'p',
        text: 'Die Kanalseite zeigt alle Kanäle des Geräts mit Spannung (U), Strom (I), Kapazität und Prozessphase (z. B. Laden, Entladen, Leerlauf).',
      },
      {
        type: 'ul',
        items: [
          'Diagramm umschalten zwischen U/I und Kapazität.',
          '„Detail“ öffnet die detaillierte Live-Ansicht eines Kanals.',
          '„Start“ springt zu Vorgang starten für diesen Kanal.',
          '„Stop“ bricht den laufenden Vorgang auf dem Kanal ab.',
        ],
      },
    ],
  },
  {
    id: 'start',
    title: 'Vorgang starten',
    blocks: [
      {
        type: 'p',
        text: 'Siehe auch die Abschnitte „Sicherheit & Lithium“, „Richtig laden und entladen“ und „Programme“, bevor Sie einen Vorgang starten.',
      },
      {
        type: 'ol',
        items: [
          'Kanal wählen und optional ein Preset aus der Akku-Datenbank laden.',
          'Programm, Akkutyp, Zellenanzahl, Kapazität und Ströme einstellen.',
          'Max. Spannung wird aus Akkutyp und Zellen berechnet (nur Anzeige).',
          'Bei unterstützten Geräten: Maximale Ladung (Vollfaktor) und Blei-Aktivator.',
          '„Prüfen / Übernehmen“ — das Gerät kann Werte korrigieren; bei Abweichungen erscheint eine Bestätigung.',
          '„Vorgang starten“ startet den Prozess auf dem gewählten Kanal.',
        ],
      },
      {
        type: 'p',
        text: '„Vom Gerät übernehmen“ lädt die zuletzt auf dem Kanal gespeicherten Parameter, startet aber noch nichts.',
      },
    ],
  },
  {
    id: 'detail',
    title: 'Kanal-Detail',
    blocks: [
      {
        type: 'p',
        text: 'Gestapelte Live-Diagramme für Spannung/Strom und Kapazität. Mit der Maus zoomen (Drag/Auswahl), wenn ein Vorgang läuft.',
      },
      {
        type: 'ul',
        items: [
          '„Live-Ansicht“ (rechts neben Stop) setzt den Zoom zurück und setzt die Live-Anzeige fort — nur aktiv bei laufendem Vorgang und aktivem Zoom.',
          'Kanalwechsel und Stop sind in der Detailansicht ebenfalls möglich.',
        ],
      },
    ],
  },
  {
    id: 'batteries',
    title: 'Akku-Datenbank',
    blocks: [
      {
        type: 'p',
        text: 'Bis zu 40 Presets lokal speichern und bearbeiten. Die lokale Liste ist unabhängig vom Gerät, bis Sie importieren oder exportieren.',
      },
      {
        type: 'ul',
        items: [
          'Von ALC importieren / Ins ALC exportieren — Synchronisation mit dem Gerät.',
          'JSON speichern / laden — Backup oder Austausch der Presets.',
          'Slot löschen setzt lokal auf Standard zurück; erst der Export schreibt aufs Gerät.',
        ],
      },
    ],
  },
  {
    id: 'chemistry',
    title: 'Akku-Typ-Parameter',
    blocks: [
      {
        type: 'p',
        text: 'Erweiterte Parameter pro Chemie (Entlade-/Ladeschluss, −ΔU, Zyklen u. a.). Zuerst „Einlesen“, Werte prüfen, dann „Übernehmen“.',
      },
      {
        type: 'ul',
        items: [
          'ELV-Werkswerte setzen die Werkseinstellung eines ALC 8500-2.',
          'Falsche Werte können Akkus schädigen — nur ändern, wenn Sie die Wirkung kennen; Details in der ELV-Doku.',
          'Display-Beleuchtung und Beeps gehören zu den Einstellungen, nicht hierher.',
        ],
      },
    ],
  },
  {
    id: 'logger',
    title: 'Datenlogger',
    blocks: [
      {
        type: 'p',
        text: 'Loggerdaten vom Gerät auslesen, in Diagrammen ansehen und als Archiv speichern (JSON, CSV, PDF).',
      },
      {
        type: 'ul',
        items: [
          'Auslesen kann je nach Datenmenge dauern — Fortschritt wird angezeigt.',
          'PDF: Querformat mit U/I-, Kapazitäts- und Datentabelle.',
          'Logger am Gerät löschen ist möglich; Archivdateien liegen unter data/logger/.',
          'Zoom in den Logger-Diagrammen wie in der Kanal-Detailansicht.',
        ],
      },
    ],
  },
  {
    id: 'device',
    title: 'Geräteinfo & Firmware',
    blocks: [
      {
        type: 'ul',
        items: [
          'Geräteinfo: Modell, Port, Seriennummer, Firmware — je nach Gerät.',
          'Innenwiderstand (Ri) ist über USB nicht messbar; Messung nur am Gerät mit Vierleiterkabel.',
          'Firmware: nur Anleitung — dieses Dashboard schreibt keine Firmware. Updates mit dem ELV-Update-Tool laut Gerätepaket.',
        ],
      },
    ],
  },
  {
    id: 'settings-ui',
    title: 'Einstellungen & Oberfläche',
    blocks: [
      {
        type: 'ul',
        items: [
          'Verbindung: Gerät, Port, Simulator, Abfrageintervall — siehe Abschnitt „Verbindung herstellen“.',
          'Gerät (Display): bei ALC 8500-2 Hintergrundbeleuchtung (Zeitmodus), Kontrast und Beeps — Einlesen / Übernehmen.',
          'Sprache und Theme in der Kopfzeile; die gewählte Sprache gilt auch für diese Anleitung.',
        ],
      },
    ],
  },
  {
    id: 'tips',
    title: 'Hinweise',
    blocks: [
      {
        type: 'ul',
        items: [
          'Simulator: Vorgänge laufen beschleunigt (×10) — ideal zum Ausprobieren.',
          'Bei USB-Abstecken erscheint ein Fehlerstatus; die App versucht automatisch neu zu verbinden (nicht nach manuellem Trennen).',
          'Wenn die Verbindung zum Dashboard-Server selbst wegbricht, erscheint ein Hinweisdialog mit erneutem Versuch.',
          'Nicht alle Funktionen gibt es auf jedem Modell — ausgegraute Menüpunkte sind für das aktuelle Profil nicht verfügbar.',
        ],
      },
    ],
  },
]

const en: GuideSection[] = [
  {
    id: 'overview',
    title: 'Overview',
    blocks: [
      {
        type: 'p',
        text: 'The ELV ALC Dashboard controls ELV/Voltcraft ALC chargers over USB or a serial port. Use the left navigation for features; switch language (DE/EN) and light/dark theme at the top right.',
      },
      {
        type: 'p',
        text: 'Which menu items appear depends on the selected device model (for example data logger or battery database only on supported devices).',
      },
      {
        type: 'p',
        text: 'This guide covers dashboard operation and the rough purpose of each program. For detailed information (limits, exact program sequences, chemistry tables, manufacturer safety notes) always consult the official ELV/Voltcraft manual for your charger — see the “ELV device documentation” section.',
      },
    ],
  },
  {
    id: 'safety',
    title: 'Safety & lithium',
    blocks: [
      {
        type: 'warn',
        text: 'Lithium batteries (Li-Ion, LiPo, LiFePO₄) connected in series must only be charged with this charger using an active balancer or as a balanced pack. Without balancing, individual cells can overcharge — fire and explosion hazard.',
      },
      {
        type: 'warn',
        text: 'Parallel lithium cells: only charge matched, equally charged cells or approved packs. Unchecked parallel charging without proper protection is risky.',
      },
      {
        type: 'ul',
        items: [
          'Set battery chemistry and cell count correctly on the device/dashboard.',
          'Observe polarity; do not charge damaged or swollen cells.',
          'Match charge and discharge currents to capacity and manufacturer ratings — do not run high currents “blindly”.',
          'If you notice unusual heat, smell, or noise, stop the process immediately.',
        ],
      },
    ],
  },
  {
    id: 'chargeBasics',
    title: 'Charging and discharging basics',
    blocks: [
      {
        type: 'p',
        text: 'Before starting: check battery type, cells, capacity, and currents. The max. voltage shown on Start process is only a guide from type and cells — not a substitute for manufacturer limits.',
      },
      {
        type: 'ul',
        items: [
          'Charge: program “Charge” — ends via device chemistry (−ΔV or voltage limits); often followed by trickle/maintenance.',
          'Discharge: program “Discharge” to cut-off — for capacity checks or emptying before a fresh charge.',
          'Choose currents typically within the manufacturer’s recommendation (often a fraction up to about 1 C, depending on chemistry and cell).',
          'Pause: wait time between phases (e.g. after discharge before charge).',
          'Forming current: separate current for forming/refresh phases where the model offers it.',
          'Maximum charge (full factor): limits how “full” the charge goes — only on supported devices.',
          'Lead activator: special path for lead-acid — only on enabled channels/models.',
        ],
      },
      {
        type: 'p',
        text: 'Exact limits and recommended procedures come from the ELV device documentation and the battery datasheet.',
      },
    ],
  },
  {
    id: 'programs',
    title: 'Programs — what they are for',
    blocks: [
      {
        type: 'p',
        text: 'Not every program is available on every model or chemistry. Exact phase sequences and cut-off criteria are in the ELV docs; cycle counts for “Cycle” and “Forming” are set under Chemistry parameters.',
      },
      {
        type: 'ul',
        items: [
          'Charge — charge only until charge end.',
          'Discharge — discharge only (remaining energy / capacity measurement).',
          'Discharge–Charge — discharge first, then charge (common “fresh start”).',
          'Test — short check or function/capacity test per device logic.',
          'Maintain — gentle / maintenance-style program (chemistry-dependent).',
          'Forming — repeated charge/discharge for new or long-stored Ni cells.',
          'Cycle — repeated discharge and charge (training or multi-run measurement).',
          'Refresh — regenerate / restore capacity (typically NiCd/NiMH after long storage).',
        ],
      },
    ],
  },
  {
    id: 'elvDocs',
    title: 'ELV device documentation',
    blocks: [
      {
        type: 'p',
        text: 'For detailed information always consult the official manual for your charger. The PDFs below are known manufacturer sources and do not replace the correct manual for your exact model and firmware:',
      },
      { type: 'links', items: ELV_LINKS_EN },
      {
        type: 'p',
        text: 'Further notes and downloads are on the ELV/Voltcraft product pages for your device.',
      },
    ],
  },
  {
    id: 'connect',
    title: 'Connect',
    blocks: [
      {
        type: 'ol',
        items: [
          'Under Settings, select the correct device model (e.g. ALC 8500-2 Expert).',
          'Enter the serial port (e.g. /dev/ttyUSB0) or leave it empty for auto-detect.',
          'For testing without hardware: clear the port and enable the simulator.',
          'Click Connect. Save writes the setting to config.yaml but does not open a connection.',
          'Disconnect ends the link deliberately; after an unexpected USB unplug the dashboard tries to reconnect.',
        ],
      },
      {
        type: 'ul',
        items: [
          'Sidebar status: Connected, Simulator (time ×10), Error, or Offline.',
          'On Linux you often need membership in the dialout group for the serial port.',
          'Poll interval controls how often live data is fetched from the device.',
        ],
      },
    ],
  },
  {
    id: 'channels',
    title: 'Channels',
    blocks: [
      {
        type: 'p',
        text: 'The channels page shows every channel with voltage (U), current (I), capacity, and process stage (e.g. charge, discharge, idle).',
      },
      {
        type: 'ul',
        items: [
          'Toggle the chart between U/I and capacity.',
          'Detail opens the live detail view for that channel.',
          'Start jumps to Start process for that channel.',
          'Stop aborts the running process on the channel.',
        ],
      },
    ],
  },
  {
    id: 'start',
    title: 'Start process',
    blocks: [
      {
        type: 'p',
        text: 'Also see the “Safety & lithium”, “Charging and discharging basics”, and “Programs” sections before starting a run.',
      },
      {
        type: 'ol',
        items: [
          'Choose a channel and optionally load a preset from the battery database.',
          'Set program, battery type, cell count, capacity, and currents.',
          'Max. voltage is calculated from battery type and cells (display only).',
          'On supported devices: maximum charge (full factor) and lead activator.',
          'Check / Apply — the device may correct values; a confirmation appears if they differ.',
          'Start process starts the run on the selected channel.',
        ],
      },
      {
        type: 'p',
        text: 'Load from device fills in parameters last stored on that channel but does not start yet.',
      },
    ],
  },
  {
    id: 'detail',
    title: 'Channel detail',
    blocks: [
      {
        type: 'p',
        text: 'Stacked live charts for voltage/current and capacity. Zoom with the mouse (drag/select) while a process is running.',
      },
      {
        type: 'ul',
        items: [
          'Live View (to the right of Stop) resets zoom and resumes live display — only enabled when a process is running and zoom is active.',
          'You can also change channel and stop from the detail view.',
        ],
      },
    ],
  },
  {
    id: 'batteries',
    title: 'Battery database',
    blocks: [
      {
        type: 'p',
        text: 'Store and edit up to 40 presets locally. The local list stays independent of the device until you import or export.',
      },
      {
        type: 'ul',
        items: [
          'Import from ALC / Export to ALC — sync with the device.',
          'Save / load JSON — backup or share presets.',
          'Reset slot restores the local default; only export writes to the device.',
        ],
      },
    ],
  },
  {
    id: 'chemistry',
    title: 'Chemistry parameters',
    blocks: [
      {
        type: 'p',
        text: 'Advanced per-chemistry settings (cut-offs, −ΔU, cycles, etc.). Read first, review, then Apply.',
      },
      {
        type: 'ul',
        items: [
          'ELV factory loads stock ALC 8500-2 defaults.',
          'Wrong values can damage batteries — change only if you understand the effects; see the ELV docs for details.',
          'Display backlight and beeps live under Settings, not here.',
        ],
      },
    ],
  },
  {
    id: 'logger',
    title: 'Data logger',
    blocks: [
      {
        type: 'p',
        text: 'Read logger data from the device, inspect charts, and archive as JSON, CSV, or PDF.',
      },
      {
        type: 'ul',
        items: [
          'Readout can take a while depending on data size — progress is shown.',
          'PDF: landscape report with U/I, capacity, and data table pages.',
          'You can clear the on-device logger; archive files are stored under data/logger/.',
          'Zoom in logger charts works like channel detail.',
        ],
      },
    ],
  },
  {
    id: 'device',
    title: 'Device info & firmware',
    blocks: [
      {
        type: 'ul',
        items: [
          'Device info: model, port, serial number, firmware — depending on the device.',
          'Internal resistance (Ri) cannot be measured over USB; measurement is on the device with a four-wire cable only.',
          'Firmware: instructions only — this dashboard does not flash firmware. Use the ELV update tool from the device package.',
        ],
      },
    ],
  },
  {
    id: 'settings-ui',
    title: 'Settings & UI',
    blocks: [
      {
        type: 'ul',
        items: [
          'Connection: device, port, simulator, poll interval — see the Connect section.',
          'Device (display): on ALC 8500-2, backlight (timer mode), contrast, and beeps — Read / Apply.',
          'Language and theme in the header; the selected language also applies to this guide.',
        ],
      },
    ],
  },
  {
    id: 'tips',
    title: 'Notes',
    blocks: [
      {
        type: 'ul',
        items: [
          'Simulator: processes run accelerated (×10) — ideal for trying features.',
          'After USB unplug an error status appears; the app tries to reconnect automatically (not after a manual disconnect).',
          'If the link to the dashboard server itself drops, a dialog appears with a retry.',
          'Not every feature exists on every model — greyed-out menu items are unavailable for the current profile.',
        ],
      },
    ],
  },
]

export function getUserGuide(locale: Locale): GuideSection[] {
  return locale === 'de' ? de : en
}
