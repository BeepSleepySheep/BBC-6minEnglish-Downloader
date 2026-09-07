#!/usr/bin/env python3
import os
import sys

from PIL import Image
from reportlab.graphics import renderPM
from svglib.svglib import svg2rlg

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_SVG = os.path.join(HERE, "bbc6min_teal.svg")
DEFAULT_ICO = os.path.join(HERE, "bbc6min_teal.ico")
DEFAULT_PNG = os.path.join(HERE, "bbc6min_teal_preview.png")
HI_DPI = 384
ICO_SIZES = [(16, 16), (24, 24), (32, 32), (48, 48), (64, 64), (128, 128), (256, 256)]


def main() -> int:
    svg_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_SVG
    ico_path = sys.argv[2] if len(sys.argv) > 2 else DEFAULT_ICO
    png_path = sys.argv[3] if len(sys.argv) > 3 else DEFAULT_PNG

    if not os.path.isfile(svg_path):
        sys.stderr.write(f"\u9519\u8bef: \u627e\u4e0d\u5230 SVG \u6587\u4ef6 {svg_path}\n")
        return 1

    print(f"[\u56fe\u6807] \u6e32\u67d3 SVG -> \u9ad8\u6e05 PNG ({HI_DPI} dpi): {svg_path}")
    drawing = svg2rlg(svg_path)
    renderPM.drawToFile(drawing, png_path, fmt="PNG", dpi=HI_DPI)
    img = Image.open(png_path).convert("RGBA")
    print(f"[\u56fe\u6807] \u751f\u6210\u591a\u5c3a\u5bf8 ICO {ICO_SIZES}...")
    img.save(ico_path, format="ICO", sizes=ICO_SIZES)
    print(f"[\u56fe\u6807] ICO \u5df2\u751f\u6210: {ico_path}")
    print(f"[\u56fe\u6807] \u9884\u89c8 \u5df2\u751f\u6210: {png_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
