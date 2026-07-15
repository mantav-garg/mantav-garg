"""
Renders a date/count CSV (from any parser in parsers/) into an isometric
3D contribution-style SVG, in every theme registered in PALETTES.

Adding a new theme is just adding a new entry to PALETTES - main.py picks
up every registered theme automatically and renders a full SVG for it
(rendering an extra theme is a cheap, purely-local operation).
"""

from __future__ import annotations

import csv
import datetime
import math
from pathlib import Path

# ---------------------------------------------------------------------------
# Theme registry
#
# To add a new theme, just add a new entry here with the same shape as the
# ones below. Every theme registered here gets a fully rendered SVG (with
# its own name stamped in the output) - nothing else needs to change.
#
#   "key": {
#       "name":       display name stamped into the SVG,
#       "background": page background fill for the whole canvas,
#       "empty":      color of a day with 0 contributions,
#       "levels":     4 colors, low -> high activity,
#       "text":       {"primary", "secondary", "accent"} text colors,
#       "panel":      {"bg", "border"} colors for the stat cards,
#   }
# ---------------------------------------------------------------------------

PALETTES = {
    "dark": {
        "name": "Github Dark",
        "background": "#0d1117",
        "empty": "#1e232b",
        "levels": ["#0e4429", "#006d32", "#26a641", "#39d353"],
        "text": {"primary": "#e6edf3", "secondary": "#7d8590", "accent": "#39d353"},
        "panel": {"bg": "#0d1117", "border": "#30363d"},
    },
    "light": {
        "name": "Github Light",
        "background": "#ffffff",
        "empty": "#C2C3C6",
        "levels": ["#9be9a8", "#40c463", "#30a14e", "#216e39"],
        "text": {"primary": "#1f2328", "secondary": "#59636e", "accent": "#216e39"},
        "panel": {"bg": "#ffffff", "border": "#d0d7de"},
    },
    "yellow_dark": {
        "name": "Yellow Dark",
        "background": "#0d1117",
        "empty": "#282828",
        "levels": ["#FFE135", "#FFDA03", "#EDC001", "#C49102"],
        "text": {"primary": "#e6edf3", "secondary": "#7d8590", "accent": "#FFDA03"},
        "panel": {"bg": "#0d1117", "border": "#30363d"},
    },
    "yellow_light": {
        "name": "Yellow Light",
        "background": "#ffffff",
        "empty": "#C2C3C6",
        "levels": ["#C49102", "#EDC001", "#FFDA03", "#FFE135"],
        "text": {"primary": "#1f2328", "secondary": "#59636e", "accent": "#C49102"},
        "panel": {"bg": "#ffffff", "border": "#d0d7de"},
    },
    "ocean": {
        "name": "Ocean",
        "background": "#081c24",
        "empty": "#0f2c37",
        "levels": ["#0a4a5c", "#0d7595", "#12a8d1", "#7fe0ff"],
        "text": {"primary": "#eaf7fb", "secondary": "#7fa8b5", "accent": "#7fe0ff"},
        "panel": {"bg": "#081c24", "border": "#123846"},
    },
    # "sunset": {
    #     "name": "Sunset",
    #     "background": "#1a1023",
    #     "empty": "#2a1c33",
    #     "levels": ["#7d2e68", "#c8395a", "#f2703c", "#ffc857"],
    #     "text": {"primary": "#fdf3e7", "secondary": "#b79aa8", "accent": "#ffc857"},
    #     "panel": {"bg": "#1a1023", "border": "#3a2740"},
    # },
}

FONT_STACK = '-apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif'

CELL = 12
GAP = 2
ANGLE_DEG = 20
SHADE_LEFT = 0.88
SHADE_RIGHT = 0.74

# Tower height tuning. BASE_HEIGHT is the height of the shortest non-zero
# day; MAX_HEIGHT is a hard ceiling used only as a safety cap. Actual
# heights are scaled logarithmically against the *busiest day in the
# dataset*, so a 9-contribution day and a 24-contribution day always end
# up visibly different towers instead of both slamming into a shared cap
# (this mirrors the more dramatic scaling used by GitHub's own isometric
# contribution viewers, e.g. jasonlong/isometric-contributions).
BASE_HEIGHT = 6
MAX_HEIGHT = 64

DAY_LABELS = ["S", "M", "T", "W", "T", "F", "S"]
MONTH_ABBR = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]

# When rendering with transparent=True, empty (0-contribution) day tiles
# are faded to this opacity instead of being fully opaque, so they don't
# blanket the whole canvas in a solid color - only the actual
# contribution bars (and the stat cards) stay fully opaque, and the rest
# of the image is genuinely see-through down to whatever page it's
# embedded on.
EMPTY_CELL_OPACITY_TRANSPARENT = 0.25


# ---------------------------------------------------------------------------
# CSV -> grid of cells
# ---------------------------------------------------------------------------

def read_csv(csv_path: Path) -> list[tuple[datetime.date, int]]:
    rows = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            date = datetime.datetime.strptime(row["date"], "%Y-%m-%d").date()
            count = int(row["count"])
            rows.append((date, count))
    rows.sort(key=lambda r: r[0])
    return rows


MIN_WEEKS = 52  # always render at least a full year, like GitHub's own graph


def build_week_grid(rows: list[tuple[datetime.date, int]], min_weeks: int = MIN_WEEKS):
    """Arrange (date, count) rows into a Sunday-start weekly grid, filling
    any missing dates with a count of 0.

    The grid always spans at least `min_weeks` weeks (padded with empty
    days as needed) so sparse datasets - e.g. a LeetCode calendar that
    only contains days with a submission - still render a proper-looking
    calendar instead of a tiny, cramped grid the stats panels don't have
    room for.
    """
    def sunday_index(d: datetime.date) -> int:
        # Python weekday(): Monday=0 ... Sunday=6. Shift so Sunday=0.
        return (d.weekday() + 1) % 7

    today = datetime.date.today()
    data_max = max(rows[-1][0], today) if rows else today
    data_min = rows[0][0] if rows else today

    counts_by_date = dict(rows)

    end = data_max + datetime.timedelta(days=6 - sunday_index(data_max))
    min_start = end - datetime.timedelta(weeks=min_weeks - 1)  # already Sunday-aligned
    data_start = data_min - datetime.timedelta(days=sunday_index(data_min))
    start = min(data_start, min_start)

    total_days = (end - start).days + 1
    weeks = total_days // 7

    cells = []
    day_totals = [0] * 7
    current = start
    for week in range(weeks):
        for day in range(7):
            count = counts_by_date.get(current, 0)
            cells.append({"week": week, "day": day, "count": count, "date": current})
            day_totals[day] += count
            current += datetime.timedelta(days=1)

    return cells, weeks, day_totals


def assign_levels(cells: list[dict]) -> list[dict]:
    """Bucket each cell's count into levels 0-4 using quartiles of the
    non-zero counts (mirrors GitHub's quartile-based shading)."""
    nonzero = sorted(c["count"] for c in cells if c["count"] > 0)
    if not nonzero:
        for c in cells:
            c["level"] = 0
        return cells

    def percentile(p: float) -> int:
        idx = min(len(nonzero) - 1, int(len(nonzero) * p))
        return nonzero[idx]

    t1, t2, t3 = percentile(0.25), percentile(0.5), percentile(0.75)

    for c in cells:
        count = c["count"]
        if count <= 0:
            c["level"] = 0
        elif count <= t1:
            c["level"] = 1
        elif count <= t2:
            c["level"] = 2
        elif count <= t3:
            c["level"] = 3
        else:
            c["level"] = 4
    return cells


# ---------------------------------------------------------------------------
# Stats (total / this week / best day / streaks)
# ---------------------------------------------------------------------------

def format_date(d: datetime.date) -> str:
    return f"{MONTH_ABBR[d.month - 1]} {d.day}"


def compute_stats(cells: list[dict]) -> dict:
    """Compute the numbers shown in the two side panels. `cells` must be in
    ascending date order (as produced by build_week_grid)."""
    total = sum(c["count"] for c in cells)
    n_days = len(cells)
    average = (total / n_days) if n_days else 0.0

    first_date = cells[0]["date"]
    last_date = cells[-1]["date"]

    last_week_num = cells[-1]["week"]
    this_week_cells = [c for c in cells if c["week"] == last_week_num]
    this_week_total = sum(c["count"] for c in this_week_cells)
    this_week_start = this_week_cells[0]["date"]
    this_week_end = this_week_cells[-1]["date"]

    best = max(cells, key=lambda c: c["count"])

    # Longest streak of consecutive days with count > 0.
    longest_len = 0
    longest_start = None
    longest_end = None
    run_start = None
    for c in cells:
        if c["count"] > 0:
            if run_start is None:
                run_start = c["date"]
            run_len = (c["date"] - run_start).days + 1
            if run_len > longest_len:
                longest_len = run_len
                longest_start = run_start
                longest_end = c["date"]
        else:
            run_start = None

    # Current streak: consecutive days with count > 0 ending at today.
    # build_week_grid() always pads the grid out to the end of the
    # calendar week (through Saturday), so the *last* cells in the grid
    # can be future dates with count 0 whenever today isn't a Saturday.
    # Starting the scan from the grid's last cell would hit one of those
    # empty future days first and break immediately, making the current
    # streak read as 0 on every day but Saturday. Skip those future
    # padding cells and start counting from today instead.
    today = datetime.date.today()
    current_len = 0
    current_start = None
    current_end = None
    for c in reversed(cells):
        if c["date"] > today:
            continue
        if c["count"] > 0:
            current_len += 1
            current_start = c["date"]
            if current_end is None:
                current_end = c["date"]
        else:
            break

    return {
        "total": total,
        "average": average,
        "first_date": first_date,
        "last_date": last_date,
        "this_week_total": this_week_total,
        "this_week_start": this_week_start,
        "this_week_end": this_week_end,
        "best_value": best["count"],
        "best_date": best["date"],
        "longest_len": longest_len,
        "longest_start": longest_start,
        "longest_end": longest_end,
        "current_len": current_len,
        "current_start": current_start,
        "current_end": current_end,
    }


# ---------------------------------------------------------------------------
# Isometric drawing helpers
# ---------------------------------------------------------------------------

def shade(hex_color: str, factor: float) -> str:
    h = hex_color.lstrip("#")
    r = int(h[0:2], 16)
    g = int(h[2:4], 16)
    b = int(h[4:6], 16)
    r = max(0, min(255, int(r * factor)))
    g = max(0, min(255, int(g * factor)))
    b = max(0, min(255, int(b * factor)))
    return f"#{r:02x}{g:02x}{b:02x}"


def project(x: float, y: float, z: float) -> tuple[float, float]:
    angle = math.radians(ANGLE_DEG)
    sx = (x - y) * math.cos(angle)
    sy = (x + y) * math.sin(angle) - z
    return sx, sy


def cube_faces_svg(gx: int, gy: int, height: int, top_color: str, opacity: float = 1.0) -> str:
    step = CELL + GAP
    x0, y0 = gx * step, gy * step
    size = CELL

    op_attr = "" if opacity >= 1.0 else f' fill-opacity="{opacity:.2f}"'

    tl = project(x0, y0, height)
    tr = project(x0 + size, y0, height)
    br = project(x0 + size, y0 + size, height)
    bl = project(x0, y0 + size, height)
    top_pts = f"{tl[0]:.2f},{tl[1]:.2f} {tr[0]:.2f},{tr[1]:.2f} {br[0]:.2f},{br[1]:.2f} {bl[0]:.2f},{bl[1]:.2f}"
    polys = [f'<polygon points="{top_pts}" fill="{top_color}"{op_attr}/>']

    if height > 0:
        lf_bb = project(x0, y0 + size, 0)
        lf_bt = project(x0, y0 + size, height)
        lf_tt = project(x0 + size, y0 + size, height)
        lf_tb = project(x0 + size, y0 + size, 0)
        left_pts = f"{lf_bb[0]:.2f},{lf_bb[1]:.2f} {lf_bt[0]:.2f},{lf_bt[1]:.2f} {lf_tt[0]:.2f},{lf_tt[1]:.2f} {lf_tb[0]:.2f},{lf_tb[1]:.2f}"
        polys.append(f'<polygon points="{left_pts}" fill="{shade(top_color, SHADE_LEFT)}"{op_attr}/>')

        rf_bb = project(x0 + size, y0 + size, 0)
        rf_bt = project(x0 + size, y0 + size, height)
        rf_tt = project(x0 + size, y0, height)
        rf_tb = project(x0 + size, y0, 0)
        right_pts = f"{rf_bb[0]:.2f},{rf_bb[1]:.2f} {rf_bt[0]:.2f},{rf_bt[1]:.2f} {rf_tt[0]:.2f},{rf_tt[1]:.2f} {rf_tb[0]:.2f},{rf_tb[1]:.2f}"
        polys.append(f'<polygon points="{right_pts}" fill="{shade(top_color, SHADE_RIGHT)}"{op_attr}/>')

    return "\n".join(polys)


def height_from_count(count: int, max_count: int) -> int:
    """Log-scale a day's count against the busiest day in the whole
    dataset (`max_count`), so towers are compared relative to each other
    rather than clipping at a fixed absolute ceiling. This is what makes
    e.g. a 24-contribution day render noticeably taller than a
    9-contribution day instead of both maxing out the same cap.
    """
    if count <= 0:
        return 0
    if max_count <= 1:
        return BASE_HEIGHT
    ratio = math.log1p(count) / math.log1p(max_count)
    height = BASE_HEIGHT + ratio * (MAX_HEIGHT - BASE_HEIGHT)
    return min(MAX_HEIGHT, int(round(height)))


# ---------------------------------------------------------------------------
# Side-panel stat cards (Contributions / Streaks), styled after GitHub's
# own isometric-contributions card look: a title, a bordered stat card
# with a few big numbers, and (for the contributions card) an averages
# line underneath.
# ---------------------------------------------------------------------------

PANEL_TITLE_SIZE = 15
PANEL_NUMBER_SIZE = 26
PANEL_LABEL_SIZE = 12
PANEL_SUB_SIZE = 10.5
PANEL_PAD_X = 22
PANEL_PAD_TOP = 28
PANEL_RADIUS = 10


def render_contributions_panel(anchor_x: float, anchor_y: float, theme: dict, stats: dict, label: str) -> str:
    """Top-right 'Contributions' card. anchor_x/anchor_y is the panel's
    top-right corner (title baseline)."""
    text = theme["text"]
    panel = theme["panel"]
    width = 340
    col_w = width / 3
    body_h = 92

    title_y = anchor_y
    box_top = title_y + 18
    box_left = anchor_x - width

    parts = [
        f'<text x="{box_left:.2f}" y="{title_y:.2f}" font-family=\'{FONT_STACK}\' '
        f'font-size="{PANEL_TITLE_SIZE}" font-weight="700" fill="{text["primary"]}">Contributions/Submissions</text>',
        f'<rect x="{box_left:.2f}" y="{box_top:.2f}" width="{width:.2f}" height="{body_h:.2f}" '
        f'rx="{PANEL_RADIUS}" fill="{panel["bg"]}" stroke="{panel["border"]}" stroke-width="0.8" fill-opacity="0.96"/>',
    ]

    total_range = f"{format_date(stats['first_date'])} \u2192 {format_date(stats['last_date'])}"
    week_range = f"{format_date(stats['this_week_start'])} \u2192 {format_date(stats['this_week_end'])}"
    best_sub = format_date(stats["best_date"]) if stats["best_value"] > 0 else "\u2013"

    cols = [
        (f"{stats['total']:,}", "This year", total_range),
        (f"{stats['this_week_total']:,}", "This week", week_range),
        (f"{stats['best_value']:,}", "Best day", best_sub),
    ]

    num_y = box_top + 34
    label_y = box_top + 56
    sub_y = box_top + 74

    for i, (value, clabel, sub) in enumerate(cols):
        col_left = box_left + i * col_w
        cx = col_left + PANEL_PAD_X
        parts.append(
            f'<text x="{cx:.2f}" y="{num_y:.2f}" font-family=\'{FONT_STACK}\' '
            f'font-size="{PANEL_NUMBER_SIZE}" font-weight="700" fill="{text["accent"]}">{value}</text>'
        )
        parts.append(
            f'<text x="{cx:.2f}" y="{label_y:.2f}" font-family=\'{FONT_STACK}\' '
            f'font-size="{PANEL_LABEL_SIZE}" font-weight="600" fill="{text["primary"]}">{clabel}</text>'
        )
        parts.append(
            f'<text x="{cx:.2f}" y="{sub_y:.2f}" font-family=\'{FONT_STACK}\' '
            f'font-size="{PANEL_SUB_SIZE}" fill="{text["secondary"]}">{sub}</text>'
        )

    avg_y = box_top + body_h + 20
    avg = stats["average"]
    parts.append(
        f'<text x="{anchor_x:.2f}" y="{avg_y:.2f}" text-anchor="end" font-family=\'{FONT_STACK}\' '
        f'font-size="12" fill="{text["secondary"]}">Average: '
        f'<tspan font-weight="700" fill="{text["accent"]}">{avg:.1f}</tspan> / day</text>'
    )

    return "\n".join(parts)


def render_streaks_panel(anchor_x: float, anchor_y: float, theme: dict, stats: dict) -> str:
    """Bottom-left 'Streaks' card. anchor_x/anchor_y is the panel's
    bottom-left corner (box bottom edge)."""
    text = theme["text"]
    panel = theme["panel"]
    width = 320
    col_w = width / 2
    body_h = 92

    box_bottom = anchor_y
    box_top = box_bottom - body_h
    title_y = box_top - 12
    box_left = anchor_x

    parts = [
        f'<text x="{box_left:.2f}" y="{title_y:.2f}" font-family=\'{FONT_STACK}\' '
        f'font-size="{PANEL_TITLE_SIZE}" font-weight="700" fill="{text["primary"]}">Streaks</text>',
        f'<rect x="{box_left:.2f}" y="{box_top:.2f}" width="{width:.2f}" height="{body_h:.2f}" '
        f'rx="{PANEL_RADIUS}" fill="{panel["bg"]}" stroke="{panel["border"]}" stroke-width="0.8" fill-opacity="0.96"/>',
    ]

    if stats["longest_len"] > 0:
        longest_sub = f"{format_date(stats['longest_start'])} \u2192 {format_date(stats['longest_end'])}"
    else:
        longest_sub = "No streak yet"

    if stats["current_len"] > 0:
        current_sub = f"{format_date(stats['current_start'])} \u2192 {format_date(stats['current_end'])}"
    else:
        current_sub = "No current streak"

    cols = [
        (f"{stats['longest_len']}", "days", "Longest", longest_sub),
        (f"{stats['current_len']}", "days", "Current", current_sub),
    ]

    num_y = box_top + 34
    label_y = box_top + 56
    sub_y = box_top + 74

    for i, (value, unit, clabel, sub) in enumerate(cols):
        col_left = box_left + i * col_w
        cx = col_left + PANEL_PAD_X
        parts.append(
            f'<text x="{cx:.2f}" y="{num_y:.2f}" font-family=\'{FONT_STACK}\' '
            f'font-size="{PANEL_NUMBER_SIZE}" font-weight="700" fill="{text["accent"]}">{value}'
            f'<tspan font-size="{PANEL_LABEL_SIZE}" font-weight="600" fill="{text["primary"]}"> {unit}</tspan></text>'
        )
        parts.append(
            f'<text x="{cx:.2f}" y="{label_y:.2f}" font-family=\'{FONT_STACK}\' '
            f'font-size="{PANEL_LABEL_SIZE}" font-weight="600" fill="{text["primary"]}">{clabel}</text>'
        )
        parts.append(
            f'<text x="{cx:.2f}" y="{sub_y:.2f}" font-family=\'{FONT_STACK}\' '
            f'font-size="{PANEL_SUB_SIZE}" fill="{text["secondary"]}">{sub}</text>'
        )

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Full SVG assembly
# ---------------------------------------------------------------------------

def render_svg(
    cells: list[dict],
    weeks: int,
    day_totals: list[int],
    theme_key: str,
    label: str,
    transparent: bool = False,
) -> str:
    if theme_key not in PALETTES:
        raise ValueError(f"Unknown theme '{theme_key}'. Available themes: {', '.join(PALETTES)}")
    theme = PALETTES[theme_key]

    sorted_cells = sorted(cells, key=lambda c: (c["week"] * 7 + c["day"], c["level"]))
    max_count = max((c["count"] for c in cells), default=0)
    max_height = max((height_from_count(c["count"], max_count) for c in cells), default=0)
    stats = compute_stats(cells)

    step = CELL + GAP
    corners = [
        project(0, 0, 0),
        project(weeks * step, 0, 0),
        project(0, 7 * step, 0),
        project(weeks * step, 7 * step, 0),
        project(0, 0, max_height),
        project(weeks * step, 0, max_height),
    ]
    xs = [x for x, _ in corners]
    ys = [y for _, y in corners]
    graph_min_x, graph_max_x = min(xs), max(xs)
    graph_min_y, graph_max_y = min(ys), max(ys)

    pad = 3
    # Generous margins: the stat cards are drawn *outside* the cube grid's
    # bounding box, on two diagonally-opposite corners (top-right /
    # bottom-left), like a scoreboard framing the graph.
    extra_top, extra_left, extra_right, extra_bottom = 132, 10, 24, 150

    min_x = graph_min_x - pad - extra_left
    min_y = graph_min_y - pad - extra_top
    width = (graph_max_x - graph_min_x) + 2 * pad + extra_left + extra_right
    height = (graph_max_y - graph_min_y) + 2 * pad + extra_top + extra_bottom

    # Anchor the panels to the *canvas's* actual corners (not the rotated
    # isometric diamond's bounding corners - those don't line up with the
    # visual top-right/bottom-left of the image, which is what caused the
    # panels to look misaligned). A small fixed margin keeps them from
    # touching the true edge of the SVG.
    canvas_right = min_x + width
    canvas_bottom = min_y + height
    margin = 20

    tr_anchor_x = canvas_right - margin
    tr_anchor_y = min_y + margin + PANEL_TITLE_SIZE
    bl_anchor_x = min_x + margin
    bl_anchor_y = canvas_bottom - margin

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{min_x:.2f} {min_y:.2f} {width:.2f} {height:.2f}" '
        f'width="{width:.0f}" height="{height:.0f}">'
    ]

    if not transparent and theme.get("background"):
        parts.append(
            f'<rect x="{min_x:.2f}" y="{min_y:.2f}" width="{width:.2f}" height="{height:.2f}" '
            f'fill="{theme["background"]}"/>'
        )

    for cell in sorted_cells:
        color = theme["empty"] if cell["level"] == 0 else theme["levels"][cell["level"] - 1]
        h = height_from_count(cell["count"], max_count)
        opacity = EMPTY_CELL_OPACITY_TRANSPARENT if (transparent and cell["level"] == 0) else 1.0
        parts.append(cube_faces_svg(cell["week"], cell["day"], h, color, opacity=opacity))

    parts.append(render_contributions_panel(tr_anchor_x, tr_anchor_y, theme, stats, label))
    parts.append(render_streaks_panel(bl_anchor_x, bl_anchor_y, theme, stats))

    # Small theme watermark so it's obvious which palette produced this
    # file just from looking at the SVG itself.
    parts.append(
        f'<text x="{(min_x + width - 8):.2f}" y="{(min_y + height - 8):.2f}" text-anchor="end" '
        f'font-family=\'{FONT_STACK}\' font-size="9" fill="{theme["text"]["secondary"]}" opacity="0.6">'
        f'{theme["name"]} theme</text>'
    )

    parts.append("</svg>")

    return "\n".join(parts)


def render_svg_from_csv(csv_path: Path, theme: str, label: str, transparent: bool = False) -> str:
    """Read a date,count CSV and return a rendered isometric SVG string.

    transparent=True omits the full-canvas background rect (the SVG's
    outer viewBox stays see-through, e.g. for embedding in a README on
    top of GitHub's own page background). The stat cards still get their
    own panel background so their text stays legible either way.
    """
    rows = read_csv(csv_path)
    cells, weeks, day_totals = build_week_grid(rows)
    cells = assign_levels(cells)
    return render_svg(cells, weeks, day_totals, theme, label, transparent=transparent)
