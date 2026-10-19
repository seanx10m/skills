"""The cast for /stick-video: two separate hosts who take turns.
    normal_guy(p, x, y, s, ...)  teal beanie, round glasses        - voice Umbriel
    cool_guy(p, x, y, s, ...)    charcoal beanie, wraparound shades - voice Algieba
Both wear a plain knit beanie with a stitched stripe, no pom-pom, and default to a wide
stance with arms crossed. Same pose args as pip(); presets CROSSED, HIPS, POINTING.
In a dialogue video, host(p, t, P, SPK, x, y, s, ...) draws whoever is speaking at t.
    from cast import *     # after: from stickkit import *"""
import stickkit
from stickkit import *

TEAL, TEAL_D, RIB = (70, 150, 160), (45, 110, 120), (50, 100, 108)
STRIPE, STRIPE_D = (240, 200, 90), (200, 160, 50)
BLACK, BLACK_D, RIB_BLACK = (48, 48, 52), (30, 30, 33), (72, 72, 78)

# confident default stance: wide feet, arms crossed. Presets for the rest.
A_CROSS_L, A_CROSS_R = (128, -14), (52, 194)
LEGS_WIDE = (-114, -66)
CROSSED = dict(arms=(A_CROSS_L, A_CROSS_R))
HIPS = dict(arms=(A_HIP_L, A_HIP_R))
POINTING = dict(arms=(A_HIP_L, A_POINT_R))

def ppip(p, x, y, s=1.0, **kw):
    """Same args as pip(). Teal beanie, no pom-pom, a knitted stripe of V stitches.
    Defaults to a wide stance with arms crossed; pass arms=/legs= to override."""
    cool = kw.pop("cool", False)
    black = kw.pop("black", False)
    rib = RIB_BLACK if black else RIB
    kw.setdefault("arms", (A_CROSS_L, A_CROSS_R))
    kw.setdefault("legs", LEGS_WIDE)
    old = stickkit.BEANIE, stickkit.BEANIE_D
    stickkit.BEANIE, stickkit.BEANIE_D = (BLACK, BLACK_D) if black else (TEAL, TEAL_D)
    key = kw.get("key", "pip")
    real_ellipse = p.ellipse
    def no_pom(*a, **k):
        if isinstance(k.get("key"), tuple) and k["key"][-1] == "pom": return
        return real_ellipse(*a, **k)
    p.ellipse = no_pom
    try:
        hc, hands = pip(p, x, y, s, **kw)
    finally:
        stickkit.BEANIE, stickkit.BEANIE_D = old
        p.ellipse = real_ellipse
    hr = 52 * s
    bx, by = hc[0], hc[1] - hr * 0.25
    # ribbing on the cuff
    n = 14
    for i in range(1, n):
        xx = bx - hr * 1.06 + hr * 2.12 * i / n
        p.line([(xx, by + 1 * s), (xx, by + 13 * s)], 1.6 * s, c=rib, key=(key, "rib", i), jit=0.4)
    # knitted stripe: one V stitch per cell in a row across the beanie
    cols, cell = 9, hr * 0.2
    x0 = bx - cols * cell / 2 + cell / 2
    gy = by - hr * 0.3
    for c in range(cols):
        gx = x0 + c * cell
        for col, wd in ((STRIPE_D, 0.42), (STRIPE, 0.26)):
            p.line([(gx - cell * 0.46, gy - cell * 0.4), (gx, gy + cell * 0.46), (gx + cell * 0.46, gy - cell * 0.4)],
                   wd * cell, c=col, key=(key, "st", c, wd), jit=0.12)
    if cool: shades(p, hc, s, key)
    return hc, hands

LENS = [(120, 60, 200), (220, 60, 150), (245, 120, 60), (250, 210, 70)]

def shades(p, hc, s, key="pip"):
    """Oversized wraparound shield sunglasses with a mirrored rainbow lens. Covers the round glasses."""
    hr = 52 * s
    ey = hc[1] + 10 * s
    L, R, top, bot = hc[0] - hr * 1.02, hc[0] + hr * 1.02, ey - 9 * s, ey + 16 * s
    # lens: horizontal mirror bands, clipped to a shield with a nose notch
    shield = [(L, top), (R, top), (R - 4 * s, bot - 2 * s), (hc[0] + 9 * s, bot), (hc[0], bot - 9 * s), (hc[0] - 9 * s, bot), (L + 4 * s, bot - 2 * s)]
    p.poly(shield, 0, fill=LENS[0], key=(key, "lens"), jit=0.3)
    n = len(LENS)
    for i in range(1, n):
        yy = top + (bot - top) * i / n
        p.poly([(L + 2 * s, yy), (R - 2 * s, yy), (R - 4 * s, bot - 2 * s), (hc[0] + 9 * s, bot), (hc[0], bot - 9 * s),
                (hc[0] - 9 * s, bot), (L + 4 * s, bot - 2 * s)], 0, fill=LENS[i], key=(key, "band", i), jit=0.3)
    p.poly(shield, 4 * s, key=(key, "rim"), jit=0.5)
    p.line([(L - 3 * s, top - 1 * s), (R + 3 * s, top - 1 * s)], 7 * s, key=(key, "brow"), jit=0.4)
    # glare streaks
    for i, dx in enumerate((-0.62, 0.38)):
        p.line([(hc[0] + hr * dx, top + 5 * s), (hc[0] + hr * dx + 9 * s, top + 3 * s)], 2.6 * s, c=(255, 255, 255), key=(key, "gl", i), jit=0.2)


# ---------- the two hosts: separate characters ----------
def normal_guy(p, x, y, s=1.0, **kw):
    """Teal beanie, round glasses. Voice: Umbriel."""
    return ppip(p, x, y, s, **kw)

def cool_guy(p, x, y, s=1.0, **kw):
    """Charcoal beanie, always in the wraparound shades. Voice: Algieba."""
    kw.setdefault("mouth", "smirk")
    return ppip(p, x, y, s, black=True, cool=True, **kw)

NORMAL_VOICE, COOL_VOICE = "Umbriel", "Algieba"

VOICES = {"normal": (NORMAL_VOICE, "Say this like a casual, friendly American YouTube explainer, conversational and natural, medium-brisk pace, with short natural pauses between paragraphs:"),
          "cool": (COOL_VOICE, "Say this like a smooth, laid-back, confident cool guy explaining tech to a friend, relaxed but brisk pace, a little swagger, with short natural pauses between paragraphs:")}

def speaker_at(t, P, SPK):
    """Name of whoever speaks at t, from para_starts (P) and speakers.json (SPK)."""
    i = max([k for k, st in enumerate(P) if st <= t + 0.01] or [0])
    return SPK[i]

def host(p, t, P, SPK, x, y, s=1.0, **kw):
    """Draw whoever is speaking at t (dialogue mode)."""
    if speaker_at(t, P, SPK) == "cool":
        kw.pop("eyes", None)  # the shades cover the eyes
        return cool_guy(p, x, y, s, **kw)
    return normal_guy(p, x, y, s, **kw)
