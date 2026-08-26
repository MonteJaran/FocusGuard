"""Generates FocusGuard.ico using the app's own color scheme."""
from PIL import Image, ImageDraw
import os

def make_frame(size):
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    ring_w = max(2, size // 12)
    pad    = max(1, size // 16)

    # Outer ring
    d.ellipse([pad, pad, size - pad - 1, size - pad - 1],
              fill="#1a1a2e", outline="#e94560", width=ring_w)

    # Inner fill
    p2 = pad + ring_w + max(1, size // 20)
    d.ellipse([p2, p2, size - p2 - 1, size - p2 - 1], fill="#0f3460")

    cx, cy = size // 2, size // 2

    # Minute hand (12 o'clock)
    hand_w = max(1, size // 16)
    d.line([cx, cy, cx, size // 6 + pad], fill="#e94560", width=hand_w)

    # Hour hand
    d.line([cx, cy, cx + size // 5, cy + size // 9],
           fill="#e0e0e0", width=max(1, size // 20))

    # Centre dot
    r = max(2, size // 10)
    d.ellipse([cx - r, cy - r, cx + r, cy + r], fill="#e0e0e0")

    return img


sizes  = [16, 32, 48, 64, 128, 256]
frames = [make_frame(s) for s in sizes]
out    = os.path.join(os.path.dirname(os.path.abspath(__file__)), "FocusGuard.ico")
frames[0].save(out, format="ICO", sizes=[(s, s) for s in sizes],
               append_images=frames[1:])
print(f"Icon saved: {out}")
