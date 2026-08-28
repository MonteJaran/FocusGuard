"""
generate_icon.py - Regenerate FocusGuard.ico.

Development tool, not shipped and not a runtime dependency: it needs Pillow,
which the app itself no longer uses. Run it only when the icon design changes.

    python -m pip install Pillow
    python generate_icon.py

Writes every size Windows actually asks for. The previous icon contained a
single 16x16 image, so Windows upscaled it everywhere else — the taskbar, the
Alt-Tab switcher, the desktop shortcut, the installer and Explorer's large-icon
view were all a blurry 16x16 stretched to 48 or 256 pixels. That is worse now
that the app is DPI-aware, because the OS no longer hides it behind its own
bitmap scaling.
"""

from pathlib import Path

from PIL import Image, ImageDraw

OUTPUT = Path(__file__).parent / "FocusGuard.ico"

# Windows picks from these: 16 for the tray and title bar, 32 for the taskbar,
# 48 for the desktop, 256 for Explorer's large view and the installer.
SIZES = [16, 24, 32, 48, 64, 128, 256]

# Matches the app's palette (ui/app.py).
NAVY = (26, 26, 46, 255)
DEEP = (15, 52, 96, 255)
ACCENT = (233, 69, 96, 255)
LIGHT = (224, 224, 224, 255)


def draw_icon(size: int) -> Image.Image:
    """
    A clock face, drawn at 4x and downsampled so the edges are smooth.

    Detail is dropped at small sizes rather than scaled down: a 16x16 icon with
    hairline strokes turns into grey mush, so below 32 pixels it keeps only the
    ring and the hands.
    """
    scale = 4
    px = size * scale
    img = Image.new("RGBA", (px, px), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    ring = max(2, int(px * 0.07))
    inset = ring // 2

    d.ellipse([inset, inset, px - inset, px - inset], fill=NAVY,
              outline=ACCENT, width=ring)

    if size >= 32:
        pad = int(px * 0.16)
        d.ellipse([pad, pad, px - pad, px - pad], fill=DEEP)

    centre = px / 2
    hand = max(2, int(px * 0.055))

    # Minute hand, pointing up.
    d.line([centre, centre, centre, px * 0.22], fill=ACCENT,
           width=hand, joint="curve")
    # Hour hand, pointing lower-right.
    d.line([centre, centre, px * 0.72, px * 0.60], fill=LIGHT,
           width=max(2, hand - scale), joint="curve")

    if size >= 24:
        dot = max(2, int(px * 0.055))
        d.ellipse([centre - dot, centre - dot, centre + dot, centre + dot],
                  fill=LIGHT)

    return img.resize((size, size), Image.LANCZOS)


def main() -> None:
    images = [draw_icon(size) for size in SIZES]
    # Pillow writes the extra sizes from the base image's `append_images`.
    images[-1].save(
        OUTPUT,
        format="ICO",
        sizes=[(s, s) for s in SIZES],
        append_images=images[:-1],
    )
    print(f"Wrote {OUTPUT} with sizes: {', '.join(f'{s}x{s}' for s in SIZES)}")


if __name__ == "__main__":
    main()
