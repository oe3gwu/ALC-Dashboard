from __future__ import annotations

from io import BytesIO
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.graphics.shapes import Drawing, Group, Line, PolyLine, String, Rect
from reportlab.platypus import PageBreak, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

# Always light — matches current UI (independent of app theme)
BLUE = colors.HexColor("#2a7ab0")
BLUE_DARK = colors.HexColor("#1f628f")
ORANGE = colors.HexColor("#ec6a0c")
GREEN = colors.HexColor("#00a65a")
TEXT = colors.HexColor("#333333")
MUTED = colors.HexColor("#4b646f")
LINE = colors.HexColor("#d2d6de")
AXIS = colors.HexColor("#8e989d")
PANEL = colors.HexColor("#f4f6f9")
ROW_ALT = colors.HexColor("#f4f6f9")
WHITE = colors.white


def _fmt_tick(v: float, digits: int = 2) -> str:
    if abs(v) >= 100:
        return f"{v:.0f}"
    if abs(v) >= 10:
        return f"{v:.1f}"
    return f"{v:.{digits}f}"


def _rotated_label(x: float, y: float, text: str, fill: Any, font_size: float = 8) -> Group:
    """90° counter-clockwise label (reportlab y-up)."""
    g = Group()
    g.add(String(0, 0, text, fillColor=fill, fontSize=font_size, textAnchor="middle"))
    # rotate 90° CCW around origin, then translate
    g.transform = (0, 1, -1, 0, x, y)
    return g


def _chart(samples: list[dict[str, Any]], width: float = 250, height: float = 120) -> Drawing:
    d = Drawing(width, height)
    d.add(Rect(0, 0, width, height, fillColor=PANEL, strokeColor=LINE, strokeWidth=0.8))
    if not samples:
        d.add(String(width / 2, height / 2, "Keine Daten", fillColor=MUTED, textAnchor="middle"))
        return d

    voltages = [s["voltage_V"] for s in samples if s.get("voltage_V") is not None]
    currents = [s["current_mA"] for s in samples if s.get("current_mA") is not None]
    if not voltages:
        return d

    left = 52
    right = 52
    bottom = 32
    top = 20
    plot_w = width - left - right
    plot_h = height - bottom - top

    vmin, vmax = min(voltages), max(voltages)
    if vmax <= vmin:
        vmax = vmin + 0.1
    vpad = max((vmax - vmin) * 0.08, 0.05)
    vmin -= vpad
    vmax += vpad

    cmin, cmax = 0.0, 100.0
    if currents:
        cmin, cmax = min(currents), max(currents)
        if cmax <= cmin:
            if abs(cmin) < 1e-6:
                cmin, cmax = 0.0, 100.0
            else:
                cmax = cmin + 1
        else:
            cpad = (cmax - cmin) * 0.08
            cmin = max(0.0, cmin - cpad) if cmin >= 0 else cmin - cpad
            cmax += cpad

    t_max = max((len(samples) - 1) * 5, 1)  # 5 s per sample

    def x_at(i: int) -> float:
        return left + (i / max(len(samples) - 1, 1)) * plot_w

    def y_v(v: float) -> float:
        return bottom + ((v - vmin) / (vmax - vmin)) * plot_h

    def y_c(c: float) -> float:
        return bottom + ((c - cmin) / (cmax - cmin)) * plot_h

    # grid + Y ticks (U left, I right)
    for g in range(5):
        frac = g / 4
        gy = bottom + frac * plot_h
        d.add(Line(left, gy, left + plot_w, gy, strokeColor=LINE, strokeWidth=0.4))
        uv = vmin + frac * (vmax - vmin)
        iv = cmin + frac * (cmax - cmin)
        d.add(String(left - 4, gy - 3, _fmt_tick(uv), fillColor=BLUE, fontSize=7, textAnchor="end"))
        d.add(String(left + plot_w + 4, gy - 3, _fmt_tick(iv, 1), fillColor=ORANGE, fontSize=7, textAnchor="start"))

    # X ticks (time)
    for g in range(5):
        frac = g / 4
        gx = left + frac * plot_w
        d.add(Line(gx, bottom, gx, bottom + plot_h, strokeColor=LINE, strokeWidth=0.35))
        t = frac * t_max
        d.add(String(gx, bottom - 12, _fmt_tick(t, 0), fillColor=MUTED, fontSize=7, textAnchor="middle"))

    # series
    pts: list[float] = []
    for i, s in enumerate(samples):
        if s.get("voltage_V") is None:
            continue
        pts.extend([x_at(i), y_v(s["voltage_V"])])
    if len(pts) >= 4:
        d.add(PolyLine(pts, strokeColor=BLUE, strokeWidth=1.4))

    if currents:
        cpts: list[float] = []
        for i, s in enumerate(samples):
            if s.get("current_mA") is None:
                continue
            cpts.extend([x_at(i), y_c(s["current_mA"])])
        if len(cpts) >= 4:
            d.add(PolyLine(cpts, strokeColor=ORANGE, strokeWidth=1.2))

    # axes
    d.add(Line(left, bottom, left, bottom + plot_h, strokeColor=AXIS, strokeWidth=1))
    d.add(Line(left + plot_w, bottom, left + plot_w, bottom + plot_h, strokeColor=AXIS, strokeWidth=1))
    d.add(Line(left, bottom, left + plot_w, bottom, strokeColor=AXIS, strokeWidth=1))

    # axis titles
    d.add(_rotated_label(14, bottom + plot_h / 2, "U (V)", BLUE, 8))
    d.add(_rotated_label(width - 12, bottom + plot_h / 2, "I (mA)", ORANGE, 8))
    d.add(String(left + plot_w / 2, 6, "t (s)", fillColor=MUTED, fontSize=8, textAnchor="middle"))
    d.add(
        String(
            left + plot_w / 2,
            height - 8,
            "U (V) blau  ·  I (mA) orange",
            fillColor=MUTED,
            fontSize=8,
            textAnchor="middle",
        )
    )
    return d


def _chart_capacity(samples: list[dict[str, Any]], width: float = 250, height: float = 120) -> Drawing:
    """Capacity (mAh) chart — green, matches UI COLOR_C."""
    d = Drawing(width, height)
    d.add(Rect(0, 0, width, height, fillColor=PANEL, strokeColor=LINE, strokeWidth=0.8))
    if not samples:
        d.add(String(width / 2, height / 2, "Keine Daten", fillColor=MUTED, textAnchor="middle"))
        return d

    caps = [s["capacity_mAh"] for s in samples if s.get("capacity_mAh") is not None]
    if not caps:
        d.add(String(width / 2, height / 2, "Keine Kapazitätsdaten", fillColor=MUTED, textAnchor="middle"))
        return d

    left = 52
    right = 24
    bottom = 32
    top = 20
    plot_w = width - left - right
    plot_h = height - bottom - top

    cmin, cmax = min(caps), max(caps)
    if cmax <= cmin:
        if abs(cmin) < 1e-6:
            cmin, cmax = 0.0, 100.0
        else:
            pad = max(5.0, abs(cmin) * 0.12)
            cmin = max(0.0, cmin - pad)
            cmax = cmax + pad
    else:
        cpad = (cmax - cmin) * 0.08
        cmin = max(0.0, cmin - cpad)
        cmax += cpad

    t_max = max((len(samples) - 1) * 5, 1)

    def x_at(i: int) -> float:
        return left + (i / max(len(samples) - 1, 1)) * plot_w

    def y_c(c: float) -> float:
        return bottom + ((c - cmin) / (cmax - cmin)) * plot_h

    for g in range(5):
        frac = g / 4
        gy = bottom + frac * plot_h
        d.add(Line(left, gy, left + plot_w, gy, strokeColor=LINE, strokeWidth=0.4))
        cv = cmin + frac * (cmax - cmin)
        d.add(String(left - 4, gy - 3, _fmt_tick(cv, 1), fillColor=GREEN, fontSize=7, textAnchor="end"))

    for g in range(5):
        frac = g / 4
        gx = left + frac * plot_w
        d.add(Line(gx, bottom, gx, bottom + plot_h, strokeColor=LINE, strokeWidth=0.35))
        t = frac * t_max
        d.add(String(gx, bottom - 12, _fmt_tick(t, 0), fillColor=MUTED, fontSize=7, textAnchor="middle"))

    pts: list[float] = []
    for i, s in enumerate(samples):
        if s.get("capacity_mAh") is None:
            continue
        pts.extend([x_at(i), y_c(s["capacity_mAh"])])
    if len(pts) >= 4:
        d.add(PolyLine(pts, strokeColor=GREEN, strokeWidth=1.4))

    d.add(Line(left, bottom, left, bottom + plot_h, strokeColor=AXIS, strokeWidth=1))
    d.add(Line(left, bottom, left + plot_w, bottom, strokeColor=AXIS, strokeWidth=1))
    d.add(_rotated_label(14, bottom + plot_h / 2, "C (mAh)", GREEN, 8))
    d.add(String(left + plot_w / 2, 6, "t (s)", fillColor=MUTED, fontSize=8, textAnchor="middle"))
    d.add(
        String(
            left + plot_w / 2,
            height - 8,
            "C (mAh) grün",
            fillColor=MUTED,
            fontSize=8,
            textAnchor="middle",
        )
    )
    return d


def _sample_indices(n: int, max_rows: int) -> list[int]:
    """Evenly spaced indices including first and last, at most max_rows."""
    if n <= 0:
        return []
    if n <= max_rows:
        return list(range(n))
    if max_rows == 1:
        return [0]
    idxs = [round(i * (n - 1) / (max_rows - 1)) for i in range(max_rows)]
    # unique while preserving order
    out: list[int] = []
    for i in idxs:
        if not out or i != out[-1]:
            out.append(i)
    if out[-1] != n - 1:
        out[-1] = n - 1
    return out


def _page2_table(samples: list[dict[str, Any]], page_w: float, page_h: float) -> Table:
    """Build a data table that fits on exactly one landscape page (uses full height)."""
    title_h = 28  # page-2 heading + spacing
    usable_h = page_h - title_h
    usable_w = page_w

    # Conservative row budget so the table never spills to page 3
    # (reportlab row height is larger than font+padding alone)
    font_size = 8
    pad = 2.5
    row_h = 19.0
    max_data_rows = max(10, min(24, int(usable_h / row_h) - 1))

    n = len(samples)
    idxs = _sample_indices(n, max_data_rows)
    rows: list[list[str]] = [["#", "t (s)", "U (V)", "I (mA)", "C (mAh)", "Marker"]]
    if not idxs:
        rows.append(["—", "—", "—", "—", "—", ""])
    else:
        for i in idxs:
            s = samples[i]
            rows.append(
                [
                    str(i),
                    str(i * 5),
                    "" if s.get("voltage_V") is None else f"{s['voltage_V']:.3f}",
                    "" if s.get("current_mA") is None else f"{s['current_mA']:.1f}",
                    "" if s.get("capacity_mAh") is None else f"{s['capacity_mAh']:.2f}",
                    s.get("marker") or "",
                ]
            )

    data_rows = len(rows) - 1
    # Enlarge type if few rows — keep within one page by capping against budget
    if data_rows <= 16:
        font_size, pad = 10, 4
    elif data_rows <= 22:
        font_size, pad = 9, 3
    # If enlarged typography would exceed page, fall back
    if (data_rows + 1) * (font_size + 2 * pad + 3.5) > usable_h:
        font_size, pad = 8, 2.5

    col_w = [usable_w * f for f in (0.08, 0.12, 0.18, 0.18, 0.18, 0.26)]
    # No repeatRows — must stay on a single page (no header clone on page 3)
    table = Table(rows, colWidths=col_w)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), BLUE),
                ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("TEXTCOLOR", (0, 1), (-1, -1), TEXT),
                ("FONTSIZE", (0, 0), (-1, -1), font_size),
                ("GRID", (0, 0), (-1, -1), 0.35, LINE),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, ROW_ALT]),
                ("TOPPADDING", (0, 0), (-1, -1), pad),
                ("BOTTOMPADDING", (0, 0), (-1, -1), pad),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    return table


def build_logger_pdf(session: dict[str, Any]) -> bytes:
    buf = BytesIO()
    page_w, page_h = landscape(A4)
    left_m = 15 * mm
    right_m = 15 * mm
    top_m = 12 * mm
    bottom_m = 12 * mm
    content_w = page_w - left_m - right_m
    content_h = page_h - top_m - bottom_m

    doc = SimpleDocTemplate(
        buf,
        pagesize=landscape(A4),
        leftMargin=left_m,
        rightMargin=right_m,
        topMargin=top_m,
        bottomMargin=bottom_m,
    )
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "TitleELV",
        parent=styles["Title"],
        textColor=BLUE_DARK,
        fontSize=18,
        spaceAfter=6,
        fontName="Helvetica-Bold",
    )
    meta_style = ParagraphStyle(
        "MetaELV",
        parent=styles["Normal"],
        textColor=TEXT,
        fontSize=10,
        spaceAfter=4,
    )
    section_title = ParagraphStyle(
        "SectionTitle",
        parent=styles["Heading2"],
        textColor=BLUE_DARK,
        fontSize=12,
        spaceAfter=8,
        fontName="Helvetica-Bold",
    )
    footer_style = ParagraphStyle(
        "FooterELV",
        parent=styles["Normal"],
        textColor=MUTED,
        fontSize=8,
        alignment=1,
    )

    body: list[Any] = []
    header = session.get("header") or {}
    ch = (session.get("channel") or 0) + 1
    body.append(Paragraph("ELV ALC Dashboard — Datenlogger", title_style))
    body.append(
        Paragraph(
            f"Kanal {ch} · {header.get('battery_type_name', '—')} · "
            f"{header.get('program_name', '—')} · "
            f"{session.get('sample_count', 0)} Messwerte · "
            f"{session.get('saved_at', '')}",
            meta_style,
        )
    )
    body.append(Spacer(1, 6))

    meta = [
        ["Kapazität (mAh)", f"{header.get('capacity_mAh', '—')}"],
        ["Ladestrom (mA)", f"{header.get('charge_mA', '—')}"],
        ["Entladestrom (mA)", f"{header.get('discharge_mA', '—')}"],
        ["Zellen", f"{header.get('cells', '—')}"],
        ["Pause (s)", f"{header.get('pause_s', '—')}"],
    ]
    t = Table(meta, colWidths=[60 * mm, 40 * mm])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), PANEL),
                ("TEXTCOLOR", (0, 0), (-1, -1), TEXT),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("GRID", (0, 0), (-1, -1), 0.4, LINE),
                ("PADDING", (0, 0), (-1, -1), 5),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
            ]
        )
    )
    body.append(t)
    body.append(Spacer(1, 10))

    samples = session.get("samples") or []
    # Page 1: meta + U/I chart
    body.append(Paragraph(f"Strom / Spannung (Kanal {ch})", section_title))
    chart_h = min(260, content_h - 160)
    body.append(_chart(samples, width=content_w, height=max(180, chart_h)))
    body.append(Spacer(1, 6))
    body.append(Paragraph("ELV ALC Dashboard", footer_style))

    # Page 2: capacity chart
    body.append(PageBreak())
    body.append(Paragraph(f"Kapazität (Kanal {ch})", section_title))
    cap_h = min(280, content_h - 60)
    body.append(_chart_capacity(samples, width=content_w, height=max(200, cap_h)))
    body.append(Spacer(1, 6))
    body.append(Paragraph("ELV ALC Dashboard", footer_style))

    # Page 3: data table — subsampled/scaled to fit this page alone
    body.append(PageBreak())
    body.append(Paragraph(f"Messwerte (Kanal {ch}) — Auszug (1 Seite)", section_title))
    body.append(_page2_table(samples, content_w, content_h))

    doc.build(body)
    return buf.getvalue()


def write_pdf(session: dict[str, Any], path: Path) -> Path:
    path.write_bytes(build_logger_pdf(session))
    return path
