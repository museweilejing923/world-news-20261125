#!/usr/bin/env python3
"""Draw the 25 November 2026 world-news infographic (1024x1024 PNG).

Pure PIL, no network, no randomness, no clock: the same input always
produces the same bytes. Writes /output/entry.png (create the directory
if needed). An optional first argument overrides the output path, which
is handy for testing: python3 main.py /tmp/test/entry.png
"""
import hashlib
import io
import os
import sys

from PIL import Image, ImageDraw, ImageFont

W, H = 1024, 1024
OUT = "/output/entry.png"

# ---------------------------------------------------------------- layout
# Card grid and text-area geometry, kept in one place so the layout can
# be tuned without hunting for magic numbers through the drawing code.
PAGE_MARGIN = 24
HEADER_H = 124
HEADER_RULE_H = 4
GRID_TOP = 140
CARD_W, CARD_H = 480, 250
CARD_GAP = 14
CARD_RADIUS = 12
TOP_BAR_H = 14
CARD_PAD = 18
CARD_TEXT_TOP = 64              # headline top, measured from the card top
CARD_TEXT_BOTTOM = CARD_H - 26  # top edge of the stat pill
HEADLINE_LEADING = 34
BODY_LEADING = 27
HEADLINE_BODY_GAP = 6
PILL_H = 22
PILL_RADIUS = 11
FOOTER_TOP = 926
FOOTER_BOTTOM = 1018

# Font sizes and card/header/footer geometry: every number that positions
# text or icons lives here, so the drawing code below reads as layout,
# not arithmetic.
FONT_TITLE = 48
FONT_DATE = 26
FONT_KICKER = 24
FONT_SUB = 21
FONT_TAG = 21
FONT_HEADLINE = 29
FONT_BODY = 22
FONT_PILL = 17
FONT_FOOTER_HEAD = 20
FONT_FOOTER_ITEM = 19
ICON_DISC_DX = 40
ICON_DISC_DY = 36
ICON_DISC_R = 20
ICON_SIZE = 13
TAG_DX = 72
TAG_DY = 27
PILL_PAD_X = 26
PILL_TEXT_DX = 13
PILL_TEXT_DY = 2
PILL_TINT = 0.88               # how far the pill tint moves toward white
HEADER_TITLE_Y = 12
HEADER_DATE_Y = 72
HEADER_RIGHT_Y1 = 16
HEADER_RIGHT_Y2 = 48
HEADER_RIGHT_Y3 = 84
FOOTER_HEAD_X = 44
FOOTER_HEAD_Y = 934
FOOTER_ITEM_Y = 958
FOOTER_DOT_X0 = 44
FOOTER_DOT_X1 = 56
FOOTER_DOT_Y0 = 5
FOOTER_DOT_Y1 = 17
FOOTER_TEXT_X = 66
FOOTER_STEP = 21

FONT_DIR = "/usr/share/fonts/truetype/dejavu/"
F_BOLD = FONT_DIR + "DejaVuSans-Bold.ttf"
F_REG = FONT_DIR + "DejaVuSans.ttf"


def font(path, size):
    return ImageFont.truetype(path, size)


# ---------------------------------------------------------------- palette
NAVY = (15, 31, 61)
NAVY_SOFT = (185, 196, 214)
GOLD = (232, 179, 60)
BG = (242, 244, 247)
CARD = (255, 255, 255)
INK = (18, 26, 38)
BODY = (58, 68, 82)
WHITE = (255, 255, 255)

STORIES = [
    dict(
        tag="SPACE", color=(108, 63, 181), icon="rocket",
        headline="Pakistan's first astronaut in space",
        body="Shenzhou-24 carries Pakistan's first astronaut to China's Tiangong station.",
        pill="First foreign astronaut",
    ),
    dict(
        tag="TECH", color=(30, 158, 90), icon="chip",
        headline="Huawei convicted in US court",
        body="A Brooklyn jury convicts Huawei of fraud, sanctions violations and trade-secret theft.",
        pill="10 of 12 counts",
    ),
    dict(
        tag="MIDDLE EAST", color=(214, 58, 47), icon="tanker",
        headline="Tankers hit mines in Hormuz",
        body="Two oil tankers hit naval mines and catch fire in the world's busiest oil chokepoint.",
        pill="2 tankers hit",
    ),
    dict(
        tag="EUROPE", color=(37, 99, 235), icon="refinery",
        headline="Ukraine hits refineries; Kyiv needs \u20ac115bn",
        body="Drones set two Russian refineries ablaze; Zelensky says Ukraine needs \u20ac115bn for 2027.",
        pill="\u20ac115bn for 2027",
    ),
    dict(
        tag="MARKETS", color=(14, 116, 144), icon="chart",
        headline="Asia's AI rally reverses",
        body="Kospi plunges 6.2%, Taiwan falls about 5% and the Nikkei drops 2.8% as Nvidia slides 5.9%.",
        pill="Kospi -6.2% \u2022 Nikkei -2.8%",
    ),
    dict(
        tag="AMERICAS", color=(234, 88, 12), icon="rescue",
        headline="Colombia frees supermarket hostages",
        body="Troops storm a Cartagena supermarket, freeing every hostage and killing one captor.",
        pill="All hostages freed",
    ),
]

FOOTER = [
    ("North Korea orders Switzerland's Pyongyang office shut and expels its diplomat in 48 hours.", (37, 99, 235)),
    ("Bangladesh raises garment workers' minimum wage by 36% after weeks of protests.", (30, 158, 90)),
    ("Senegal restored as Africa Cup champions after a court overturns the earlier ruling.", (214, 58, 47)),
]


# ---------------------------------------------------------------- helpers
def wrap(draw, text, fnt, max_w):
    """Greedy word wrap; returns list of lines that fit max_w."""
    lines, cur = [], ""
    for word in text.split(" "):
        trial = word if not cur else cur + " " + word
        if draw.textlength(trial, font=fnt) <= max_w:
            cur = trial
        else:
            if cur:
                lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def text(draw, xy, s, fnt, fill):
    draw.text(xy, s, font=fnt, fill=fill)


def vcenter_offset(head_lines, body_lines):
    """Vertical offset that centres the headline+body block in a card.

    The text area runs from CARD_TEXT_TOP down to the stat pill. A card
    whose headline wraps to one line (or whose body is short) is pushed
    down so the empty space above the body matches the space below it,
    instead of the text bunching at the top and leaving a dead gap.
    Cards with a full two-line headline and three-line body barely move.
    """
    content = (len(head_lines) * HEADLINE_LEADING + HEADLINE_BODY_GAP
               + len(body_lines) * BODY_LEADING)
    area = CARD_TEXT_BOTTOM - CARD_TEXT_TOP
    return max(0, (area - content) // 2)


# ---------------------------------------------------------------- icons
def icon_rocket(d, cx, cy, s):
    # s = half-size of the drawing box
    d.polygon([(cx, cy - s), (cx + s * 0.42, cy - s * 0.1),
               (cx + s * 0.42, cy + s * 0.55), (cx - s * 0.42, cy + s * 0.55),
               (cx - s * 0.42, cy - s * 0.1)], fill=WHITE)
    d.polygon([(cx - s * 0.42, cy + s * 0.1), (cx - s * 0.85, cy + s * 0.6),
               (cx - s * 0.42, cy + s * 0.55)], fill=WHITE)
    d.polygon([(cx + s * 0.42, cy + s * 0.1), (cx + s * 0.85, cy + s * 0.6),
               (cx + s * 0.42, cy + s * 0.55)], fill=WHITE)
    d.ellipse([cx - s * 0.2, cy - s * 0.35, cx + s * 0.2, cy + s * 0.05],
              fill=(108, 63, 181))
    d.polygon([(cx - s * 0.22, cy + s * 0.62), (cx + s * 0.22, cy + s * 0.62),
               (cx, cy + s * 1.0)], fill=(232, 179, 60))


def icon_chip(d, cx, cy, s):
    d.rectangle([cx - s * 0.55, cy - s * 0.55, cx + s * 0.55, cy + s * 0.55],
                outline=WHITE, width=3)
    d.rectangle([cx - s * 0.25, cy - s * 0.25, cx + s * 0.25, cy + s * 0.25],
                fill=WHITE)
    for k in (-1, 0, 1):
        d.line([(cx + k * s * 0.35, cy - s * 0.85), (cx + k * s * 0.35, cy - s * 0.55)],
               fill=WHITE, width=3)
        d.line([(cx + k * s * 0.35, cy + s * 0.55), (cx + k * s * 0.35, cy + s * 0.85)],
               fill=WHITE, width=3)
        d.line([(cx - s * 0.85, cy + k * s * 0.35), (cx - s * 0.55, cy + k * s * 0.35)],
               fill=WHITE, width=3)
        d.line([(cx + s * 0.55, cy + k * s * 0.35), (cx + s * 0.85, cy + k * s * 0.35)],
               fill=WHITE, width=3)


def icon_tanker(d, cx, cy, s):
    d.polygon([(cx - s * 0.9, cy - s * 0.1), (cx + s * 0.9, cy - s * 0.1),
               (cx + s * 0.65, cy + s * 0.45), (cx - s * 0.65, cy + s * 0.45)],
              fill=WHITE)
    d.rectangle([cx - s * 0.55, cy - s * 0.45, cx - s * 0.1, cy - s * 0.1], fill=WHITE)
    d.rectangle([cx + s * 0.05, cy - s * 0.6, cx + s * 0.45, cy - s * 0.1], fill=WHITE)
    d.rectangle([cx + s * 0.55, cy - s * 0.85, cx + s * 0.75, cy - s * 0.1], fill=WHITE)
    for k, off in enumerate((-0.55, 0.0, 0.55)):
        d.arc([cx + (off - 0.35) * s, cy + s * 0.55, cx + (off + 0.35) * s,
               cy + s * 1.05], 180, 360, fill=WHITE, width=3)


def icon_refinery(d, cx, cy, s):
    d.rectangle([cx - s * 0.8, cy - s * 0.2, cx - s * 0.35, cy + s * 0.7], fill=WHITE)
    d.rectangle([cx - s * 0.15, cy - s * 0.55, cx + s * 0.3, cy + s * 0.7], fill=WHITE)
    d.rectangle([cx + s * 0.45, cy + s * 0.1, cx + s * 0.85, cy + s * 0.7], fill=WHITE)
    d.polygon([(cx - s * 0.55, cy - s * 0.2), (cx - s * 0.35, cy - s * 0.75),
               (cx - s * 0.15, cy - s * 0.2)], fill=(232, 179, 60))
    d.polygon([(cx + s * 0.05, cy - s * 0.55), (cx + s * 0.25, cy - s * 1.0),
               (cx + s * 0.4, cy - s * 0.55)], fill=(232, 179, 60))


def icon_chart(d, cx, cy, s):
    pts = [(cx - s * 0.9, cy - s * 0.55), (cx - s * 0.45, cy - s * 0.25),
           (cx, cy - s * 0.5), (cx + s * 0.45, cy + s * 0.15),
           (cx + s * 0.9, cy + s * 0.55)]
    d.line(pts, fill=WHITE, width=4, joint="curve")
    d.polygon([(cx + s * 0.9, cy + s * 0.55), (cx + s * 0.55, cy + s * 0.35),
               (cx + s * 0.55, cy + s * 0.75)], fill=WHITE)
    d.line([(cx - s * 0.95, cy + s * 0.75), (cx + s * 0.95, cy + s * 0.75)],
           fill=WHITE, width=3)


def icon_rescue(d, cx, cy, s):
    d.polygon([(cx, cy - s * 0.85), (cx + s * 0.75, cy - s * 0.55),
               (cx + s * 0.75, cy + s * 0.15), (cx, cy + s * 0.9),
               (cx - s * 0.75, cy + s * 0.15), (cx - s * 0.75, cy - s * 0.55)],
              fill=WHITE)
    d.line([(cx - s * 0.35, cy), (cx - s * 0.08, cy + s * 0.3),
            (cx + s * 0.45, cy - s * 0.35)], fill=(234, 88, 12), width=4,
           joint="curve")


ICONS = {"rocket": icon_rocket, "chip": icon_chip, "tanker": icon_tanker,
         "refinery": icon_refinery, "chart": icon_chart, "rescue": icon_rescue}


# ---------------------------------------------------------------- card
def draw_card(d, x, y, w, h, story):
    color = story["color"]
    d.rounded_rectangle([x, y, x + w, y + h], radius=CARD_RADIUS, fill=CARD)
    # coloured top bar with rounded top corners
    d.rounded_rectangle([x, y, x + w, y + TOP_BAR_H], radius=CARD_RADIUS, fill=color)
    d.rectangle([x, y + TOP_BAR_H // 2, x + w, y + TOP_BAR_H], fill=color)
    # icon disc + tag
    cx, cy, r = x + ICON_DISC_DX, y + ICON_DISC_DY, ICON_DISC_R
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=color)
    ICONS[story["icon"]](d, cx, cy, ICON_SIZE)
    text(d, (x + TAG_DX, y + TAG_DY), story["tag"], font(F_BOLD, FONT_TAG), color)
    # headline, max 2 lines
    hl = wrap(d, story["headline"], font(F_BOLD, FONT_HEADLINE), w - CARD_PAD * 2)
    assert len(hl) <= 2, story["headline"]
    # body, max 3 lines
    bl = wrap(d, story["body"], font(F_REG, FONT_BODY), w - CARD_PAD * 2)
    assert len(bl) <= 3, story["body"]
    # Vertically balance the headline+body block inside the card's text
    # area so a one-line headline does not leave a dead gap above the body.
    yy = y + CARD_TEXT_TOP + vcenter_offset(hl, bl)
    for line in hl:
        text(d, (x + CARD_PAD, yy), line, font(F_BOLD, FONT_HEADLINE), INK)
        yy += HEADLINE_LEADING
    yy += HEADLINE_BODY_GAP
    for line in bl:
        text(d, (x + CARD_PAD, yy), line, font(F_REG, FONT_BODY), BODY)
        yy += BODY_LEADING
    # stat pill: light tint of the story colour, bold text in full colour
    pill_f = font(F_BOLD, FONT_PILL)
    pw = d.textlength(story["pill"], font=pill_f) + PILL_PAD_X
    py = y + CARD_TEXT_BOTTOM
    tint = tuple(int(c + (255 - c) * PILL_TINT) for c in color)
    d.rounded_rectangle([x + CARD_PAD, py, x + CARD_PAD + pw, py + PILL_H],
                        radius=PILL_RADIUS, fill=tint)
    text(d, (x + CARD_PAD + PILL_TEXT_DX, py + PILL_TEXT_DY), story["pill"], pill_f, color)


# ---------------------------------------------------------------- page
def build():
    """Draw the page and return the finished image (no file written)."""
    img = Image.new("RGB", (W, H), BG)
    d = ImageDraw.Draw(img, "RGBA")

    # header
    d.rectangle([0, 0, W, HEADER_H], fill=NAVY)
    text(d, (PAGE_MARGIN, HEADER_TITLE_Y), "WORLD NEWS", font(F_BOLD, FONT_TITLE), WHITE)
    text(d, (PAGE_MARGIN, HEADER_DATE_Y), "WEDNESDAY, 25 NOVEMBER 2026", font(F_BOLD, FONT_DATE), GOLD)
    d.text((W - PAGE_MARGIN, HEADER_RIGHT_Y1), "THE DAY IN", font=font(F_BOLD, FONT_KICKER), fill=WHITE, anchor="ra")
    d.text((W - PAGE_MARGIN, HEADER_RIGHT_Y2), "ONE PAGE", font=font(F_BOLD, FONT_KICKER), fill=WHITE, anchor="ra")
    d.text((W - PAGE_MARGIN, HEADER_RIGHT_Y3), "6 big stories + more", font=font(F_REG, FONT_SUB), fill=NAVY_SOFT, anchor="ra")
    d.rectangle([0, HEADER_H, W, HEADER_H + HEADER_RULE_H], fill=GOLD)

    # story grid 2 x 3
    for i, story in enumerate(STORIES):
        x = PAGE_MARGIN + (i % 2) * (CARD_W + CARD_GAP)
        y = GRID_TOP + (i // 2) * (CARD_H + CARD_GAP)
        draw_card(d, x, y, CARD_W, CARD_H, story)

    # footer strip
    d.rounded_rectangle([PAGE_MARGIN, FOOTER_TOP, W - PAGE_MARGIN, FOOTER_BOTTOM],
                        radius=CARD_RADIUS, fill=CARD)
    text(d, (FOOTER_HEAD_X, FOOTER_HEAD_Y), "ALSO TODAY", font(F_BOLD, FONT_FOOTER_HEAD), NAVY)
    yy = FOOTER_ITEM_Y
    for s, c in FOOTER:
        d.ellipse([FOOTER_DOT_X0, yy + FOOTER_DOT_Y0, FOOTER_DOT_X1, yy + FOOTER_DOT_Y1], fill=c)
        text(d, (FOOTER_TEXT_X, yy), s, font(F_REG, FONT_FOOTER_ITEM), BODY)
        yy += FOOTER_STEP

    return img


def render_png():
    """Render the page and return its PNG bytes."""
    buf = io.BytesIO()
    build().save(buf, format="PNG")
    return buf.getvalue()


def write_entry(out_path=OUT):
    """Render twice, verify determinism and size, then write the PNG.

    Raises if the two renders differ, if the image is not exactly
    1024x1024, or if the PNG is 1 MiB or larger.
    """
    first = render_png()
    second = render_png()
    if first != second:
        raise SystemExit("non-deterministic render: two draws differ")
    img = Image.open(io.BytesIO(first))
    assert img.size == (W, H), img.size
    assert len(first) < 1024 * 1024, len(first)
    parent = os.path.dirname(out_path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(out_path, "wb") as f:
        f.write(first)
    # Self-check: read the file back and confirm it is exactly the render
    # verified in memory, then render once more from scratch and confirm
    # the program is byte-stable across separate renders.
    with open(out_path, "rb") as f:
        on_disk = f.read()
    assert on_disk == first, "written file differs from in-memory render"
    assert len(on_disk) < 1024 * 1024, len(on_disk)
    assert Image.open(io.BytesIO(on_disk)).size == (W, H)
    assert render_png() == first, "fresh re-render differs from written file"
    return first


if __name__ == "__main__":
    data = write_entry(sys.argv[1] if len(sys.argv) > 1 else OUT)
    print("size", len(data), "sha256", hashlib.sha256(data).hexdigest())
