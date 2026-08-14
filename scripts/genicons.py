"""Generate the full Aqsacloud icon set from the measured logo geometry.

The mark is a stroked cloud = union of two circles, measured off logo.png:
  big   : center (15.0, 15.0) r 15.0
  small : center (29.5, 19.5) r  9.5
  stroke: 3.6
all in a 40 x 30 design box.
"""
import os
from PIL import Image, ImageDraw, ImageChops

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "icons")

BG = (5, 10, 20, 255)        # #050A14 from the logo background
ORANGE = (245, 166, 35, 255)  # #F5A623 exact logo orange
WHITE = (255, 255, 255, 255)

CW, CH = 40.0, 30.0           # cloud design box
BIG = (15.0, 15.0, 15.0)      # cx, cy, r
SMALL = (29.5, 20.0, 10.0)
# the two lobes sit on a shared flat base; without this connecting body the
# silhouette reads as two stuck-together circles instead of a cloud.
# every primitive must bottom out on exactly BASELINE or the flat edge steps.
BASELINE = 30.0               # == BIG.cy+r == SMALL.cy+r
RECT = (15.0, 15.0, 29.5, BASELINE)   # x0, y0, x1, y1
STROKE = 3.6

SS = 8                        # supersample factor


def _shape(d, inset, scale, ox, oy):
    """Draw the cloud silhouette (two lobes + connecting body), inset by `inset`."""
    for cx, cy, r in (BIG, SMALL):
        rr = r - inset
        if rr <= 0:
            continue
        d.ellipse([ox + (cx - rr) * scale, oy + (cy - rr) * scale,
                   ox + (cx + rr) * scale, oy + (cy + rr) * scale], fill=255)
    # Connecting body. Its left/right/top edges sit inside the lobes, so only the
    # baseline needs insetting to keep the stroke an even width along the bottom.
    rx0, ry0, rx1, ry1 = RECT
    d.rectangle([ox + rx0 * scale, oy + ry0 * scale,
                 ox + rx1 * scale, oy + (ry1 - inset) * scale], fill=255)


def cloud_mask(size, frac=0.68, yshift=0.0):
    """Return an L-mode mask (size x size) of the stroked cloud ring."""
    S = size * SS
    scale = (S * frac) / CW
    ox = (S - CW * scale) / 2.0
    oy = (S - CH * scale) / 2.0 + yshift * S * SS

    outer = Image.new("L", (S, S), 0)
    _shape(ImageDraw.Draw(outer), 0.0, scale, ox, oy)

    inner = Image.new("L", (S, S), 0)
    _shape(ImageDraw.Draw(inner), STROKE, scale, ox, oy)

    ring = ImageChops.subtract(outer, inner)
    return ring.resize((size, size), Image.LANCZOS)


def icon(size, bg=BG, fg=ORANGE, frac=0.68, round_mask=False, opaque=False):
    """Square app icon: cloud on background."""
    img = Image.new("RGBA", (size, size), bg if bg else (0, 0, 0, 0))
    layer = Image.new("RGBA", (size, size), fg)
    img.paste(layer, (0, 0), cloud_mask(size, frac))

    if round_mask:
        S = size * SS
        m = Image.new("L", (S, S), 0)
        ImageDraw.Draw(m).ellipse([0, 0, S - 1, S - 1], fill=255)
        m = m.resize((size, size), Image.LANCZOS)
        out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        out.paste(img, (0, 0), m)
        img = out

    if opaque:                      # iOS forbids alpha
        flat = Image.new("RGB", (size, size), bg[:3])
        flat.paste(img, (0, 0), img)
        return flat
    return img


def transparent_mark(size, fg=ORANGE, frac=0.86):
    """Cloud on transparency - for tray icons and adaptive foregrounds."""
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    layer = Image.new("RGBA", (size, size), fg)
    img.paste(layer, (0, 0), cloud_mask(size, frac))
    return img


def stat_icon(size):
    """Android notification icon: white silhouette, alpha only (LA mode)."""
    m = cloud_mask(size, 0.82)
    img = Image.new("LA", (size, size), (255, 0))
    img.putalpha(m)
    img.paste(Image.new("L", (size, size), 255), (0, 0), m)
    return img


def save(img, rel):
    p = os.path.join(OUT, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    img.save(p)
    return p


def main():
    os.makedirs(OUT, exist_ok=True)
    n = 0

    # ---- res/ desktop icons ----
    save(icon(1024), "res/icon.png"); n += 1
    save(icon(1024), "res/mac-icon.png"); n += 1
    save(icon(128), "res/128x128.png"); n += 1
    save(icon(256), "res/128x128@2x.png"); n += 1
    save(icon(64), "res/64x64.png"); n += 1
    save(icon(32), "res/32x32.png"); n += 1

    # multi-resolution .ico
    ico_sizes = [16, 24, 32, 48, 64, 128, 256]
    base = icon(256)
    p = os.path.join(OUT, "res/icon.ico")
    base.save(p, format="ICO", sizes=[(s, s) for s in ico_sizes]); n += 1

    tray = transparent_mark(64)
    p = os.path.join(OUT, "res/tray-icon.ico")
    tray.save(p, format="ICO", sizes=[(16, 16), (20, 20), (24, 24), (32, 32), (48, 48)]); n += 1

    # mac tray: light/dark variants at 2x
    save(transparent_mark(44, fg=(255, 255, 255, 255)), "res/mac-tray-dark-x2.png"); n += 1
    save(transparent_mark(44, fg=(0, 0, 0, 255)), "res/mac-tray-light-x2.png"); n += 1

    # ---- Android ----
    android = {"mdpi": 48, "hdpi": 72, "xhdpi": 96, "xxhdpi": 144, "xxxhdpi": 192}
    fg_sizes = {"mdpi": 108, "hdpi": 162, "xhdpi": 216, "xxhdpi": 324, "xxxhdpi": 432}
    stat_sizes = {"mdpi": 24, "hdpi": 36, "xhdpi": 48, "xxhdpi": 72, "xxxhdpi": 96}
    for d, s in android.items():
        base_d = f"flutter/android/app/src/main/res/mipmap-{d}"
        save(icon(s), f"{base_d}/ic_launcher.png"); n += 1
        save(icon(s, round_mask=True), f"{base_d}/ic_launcher_round.png"); n += 1
        # adaptive foreground: content must sit inside the centre 66/108 safe zone
        save(transparent_mark(fg_sizes[d], frac=0.46), f"{base_d}/ic_launcher_foreground.png"); n += 1
        save(stat_icon(stat_sizes[d]), f"{base_d}/ic_stat_logo.png"); n += 1

    # ---- iOS (opaque, no alpha) ----
    ios = {
        "Icon-App-1024x1024@1x.png": 1024,
        "Icon-App-20x20@1x.png": 20, "Icon-App-20x20@2x.png": 40, "Icon-App-20x20@3x.png": 60,
        "Icon-App-29x29@1x.png": 29, "Icon-App-29x29@2x.png": 58, "Icon-App-29x29@3x.png": 87,
        "Icon-App-40x40@1x.png": 40, "Icon-App-40x40@2x.png": 80, "Icon-App-40x40@3x.png": 120,
        "Icon-App-60x60@2x.png": 120, "Icon-App-60x60@3x.png": 180,
        "Icon-App-76x76@1x.png": 76, "Icon-App-76x76@2x.png": 152,
        "Icon-App-83.5x83.5@2x.png": 167,
    }
    for name, s in ios.items():
        save(icon(s, opaque=True), f"flutter/ios/Runner/Assets.xcassets/AppIcon.appiconset/{name}"); n += 1

    print(f"generated {n} files into {OUT}")


if __name__ == "__main__":
    main()
