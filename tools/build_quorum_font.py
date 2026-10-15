#!/usr/bin/env python3
"""Rebuild the tiny, original superscript-Q font used by the browser UI.

The committed WOFF file is all the app and normal site build need. Rebuilding
this optional development asset requires fontTools:
``python -m pip install fonttools``. No other font is used as a source.
The original outline is covered by this project's MIT license.
"""

from pathlib import Path

from fontTools.fontBuilder import FontBuilder
from fontTools.pens.cu2quPen import Cu2QuPen
from fontTools.pens.ttGlyphPen import TTGlyphPen


ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "web" / "quorum-superscript.woff"


def ellipse(pen, cx, cy, rx, ry, *, reverse=False):
    """Draw an oval with a reversed counter; the four cubics are original."""
    k = 0.5522847498307936
    direction = -1 if reverse else 1
    rx *= direction
    pen.moveTo((cx, cy + ry))
    pen.curveTo((cx + k * rx, cy + ry), (cx + rx, cy + k * ry), (cx + rx, cy))
    pen.curveTo((cx + rx, cy - k * ry), (cx + k * rx, cy - ry), (cx, cy - ry))
    pen.curveTo((cx - k * rx, cy - ry), (cx - rx, cy - k * ry), (cx - rx, cy))
    pen.curveTo((cx - rx, cy + k * ry), (cx - k * rx, cy + ry), (cx, cy + ry))
    pen.closePath()


def build():
    glyph_pen = TTGlyphPen(None)
    pen = Cu2QuPen(glyph_pen, max_err=0.5, reverse_direction=False)
    ellipse(pen, 220, 548, 164, 202)
    ellipse(pen, 220, 548, 111, 149, reverse=True)
    pen.moveTo((244, 455))
    pen.lineTo((282, 482))
    pen.lineTo((418, 320))
    pen.lineTo((378, 290))
    pen.closePath()

    builder = FontBuilder(1000, isTTF=True)
    builder.setupGlyphOrder([".notdef", "uniA7F4"])
    builder.setupCharacterMap({0xA7F4: "uniA7F4"})
    builder.setupGlyf({".notdef": TTGlyphPen(None).glyph(), "uniA7F4": glyph_pen.glyph()})
    builder.setupHorizontalMetrics({".notdef": (460, 0), "uniA7F4": (460, 56)})
    builder.setupHorizontalHeader(ascent=900, descent=-250)
    builder.setupNameTable({
        "familyName": "MuQL Quorum",
        "styleName": "Regular",
        "uniqueFontIdentifier": "MuQL Quorum 1.0",
        "fullName": "MuQL Quorum Regular",
        "psName": "MuQLQuorum-Regular",
        "version": "Version 1.0",
        "copyright": "Copyright (c) 2026 MuQL contributors",
        "licenseDescription": "Original outline released under the MIT License. See the project's LICENSE file.",
    })
    builder.setupOS2(sTypoAscender=900, sTypoDescender=-250, sTypoLineGap=0,
                     usWinAscent=900, usWinDescent=250, sxHeight=500, sCapHeight=730)
    builder.setupPost()
    builder.setupMaxp()
    # Fixed metadata makes repeated regeneration byte-for-byte reproducible.
    builder.font["head"].created = builder.font["head"].modified = 2082844800
    builder.font.recalcTimestamp = False
    builder.font.flavor = "woff"
    builder.save(OUTPUT)
    print(f"Built {OUTPUT} ({OUTPUT.stat().st_size} bytes)")


if __name__ == "__main__":
    build()
