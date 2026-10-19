"""stickkit - hand-drawn stick-figure drawing kit for /stick-video.
Import from a project's scenes.py. Pip is an original character - keep it that way.
"""
import math, random, sys, os, subprocess, zlib
from multiprocessing import Pool
from PIL import Image, ImageDraw, ImageFont, ImageChops

W, H, SS, FPS = 1280, 720, 2, 24
BW, BH = W * SS, H * SS
KIT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT = os.getcwd()  # project dir: props/, frames/ live here
F = lambda n, s: ImageFont.truetype(f"{KIT}/fonts/{n}", int(s * SS))
HAND, BANG, MARK, GOCHI = "PatrickHand-Regular.ttf", "Bangers-Regular.ttf", "PermanentMarker-Regular.ttf", "GochiHand-Regular.ttf"
INK, GREEN, RED, BLUE, GRAY = (25, 25, 25), (38, 160, 60), (205, 40, 40), (40, 90, 170), (175, 175, 175)
SKIN, BEANIE, BEANIE_D = (247, 214, 176), (240, 160, 40), (205, 120, 20)
PROPS = {}

def prop(name):
    if name not in PROPS:
        PROPS[name] = Image.open(f"{ROOT}/props/{name}.png").convert("RGB")
    return PROPS[name]

# ---------- easing ----------
def clamp(x, a=0.0, b=1.0): return max(a, min(b, x))
def ease(x): x = clamp(x); return 1 - (1 - x) ** 3
def pop(t, t0, dur=0.28):
    """0 -> overshoot -> 1 scale for a pop-in starting at t0."""
    x = (t - t0) / dur
    if x <= 0: return 0.0
    if x >= 1: return 1.0
    return 1 + 2.2 * (x - 1) ** 3 + 1.2 * (x - 1) ** 2 if False else (1.0 + math.sin(x * math.pi) * 0.18) * ease(x * 1.4)
def lerp(a, b, x): return a + (b - a) * x

# ---------- wobbly drawing ----------
class Pen:
    def __init__(self, img, boil):
        self.img, self.d, self.boil = img, ImageDraw.Draw(img), boil
    def rng(self, key):
        return random.Random(zlib.crc32(repr((key, self.boil)).encode()))
    def P(self, x, y): return (x * SS, y * SS)
    def line(self, pts, w=4, c=INK, key=0, jit=1.6):
        r = self.rng(key)
        out = []
        for i in range(len(pts) - 1):
            (x0, y0), (x1, y1) = pts[i], pts[i + 1]
            n = max(2, int(math.hypot(x1 - x0, y1 - y0) / 18))
            for k in range(n + (1 if i == len(pts) - 2 else 0)):
                u = k / n
                out.append(((x0 + (x1 - x0) * u + r.uniform(-jit, jit)) * SS, (y0 + (y1 - y0) * u + r.uniform(-jit, jit)) * SS))
        self.d.line(out, fill=c, width=int(w * SS), joint="curve")
        for p in (out[0], out[-1]):
            rr = w * SS / 2
            self.d.ellipse((p[0] - rr, p[1] - rr, p[0] + rr, p[1] + rr), fill=c)
    def curve(self, pts, w=4, c=INK, key=0, jit=1.2, steps=24):
        # quadratic/cubic bezier through control points
        def bez(ps, u):
            while len(ps) > 1:
                ps = [(a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u) for a, b in zip(ps, ps[1:])]
            return ps[0]
        self.line([bez(pts, i / steps) for i in range(steps + 1)], w, c, key, jit)
    def ellipse(self, cx, cy, rx, ry, w=4, c=INK, fill=None, key=0, jit=1.5):
        r = self.rng(key)
        n = 40
        ph = r.uniform(0, 6.28)
        pts = []
        for i in range(n + 3):
            a = ph + i / n * 2 * math.pi
            k = 1 + r.uniform(-0.012, 0.012)
            pts.append((cx + math.cos(a) * rx * k, cy + math.sin(a) * ry * k))
        if fill:
            self.d.polygon([(x * SS, y * SS) for x, y in pts[:n]], fill=fill)
        if w: self.line(pts, w, c, (key, 1), jit * 0.4)
    def poly(self, pts, w=4, c=INK, fill=None, key=0, jit=1.5):
        r = self.rng(key)
        jp = [(x + r.uniform(-jit, jit), y + r.uniform(-jit, jit)) for x, y in pts]
        if fill: self.d.polygon([(x * SS, y * SS) for x, y in jp], fill=fill)
        if w: self.line(jp + [jp[0]], w, c, (key, 1), jit * 0.5)
    def rect(self, x, y, w_, h_, w=4, c=INK, fill=None, key=0):
        self.poly([(x, y), (x + w_, y), (x + w_, y + h_), (x, y + h_)], w, c, fill, key)
    def text(self, s, x, y, size, font=HAND, c=INK, anchor="mm", rot=0, scale=1.0, key=0, stroke=0, sc=INK, jit=True):
        if scale <= 0.01: return
        r = self.rng(("t", key, s))
        if jit:
            x += r.uniform(-0.8, 0.8); y += r.uniform(-0.8, 0.8); rot += r.uniform(-0.6, 0.6)
        fnt = F(font, size * scale)
        if rot == 0 and scale == 1.0 and False:
            pass
        bbox = self.d.textbbox((0, 0), s, font=fnt, stroke_width=int(stroke * SS * scale))
        tw, th = bbox[2] - bbox[0] + 20, bbox[3] - bbox[1] + 20
        layer = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
        ImageDraw.Draw(layer).text((10 - bbox[0], 10 - bbox[1]), s, font=fnt, fill=c, stroke_width=int(stroke * SS * scale), stroke_fill=sc)
        if rot: layer = layer.rotate(rot, resample=Image.BICUBIC, expand=True)
        ax = {"l": 0, "m": 0.5, "r": 1}[anchor[0]]; ay = {"t": 0, "m": 0.5, "b": 1}[anchor[1]]
        self.img.paste(layer, (int(x * SS - layer.width * ax), int(y * SS - layer.height * ay)), layer)
    def image(self, name, cx, cy, h, scale=1.0, rot=0, flip=False):
        if scale <= 0.01: return
        im = prop(name)
        if flip: im = im.transpose(Image.FLIP_LEFT_RIGHT)
        hh = int(h * scale * SS); ww = int(im.width * hh / im.height)
        im = im.resize((ww, hh), Image.LANCZOS)
        if rot: im = im.rotate(rot, resample=Image.BICUBIC, expand=True, fillcolor=(255, 255, 255))
        x0, y0 = int(cx * SS - im.width / 2), int(cy * SS - im.height / 2)
        box = (x0, y0, x0 + im.width, y0 + im.height)
        # clip to canvas
        cx0, cy0 = max(0, box[0]), max(0, box[1]); cx1, cy1 = min(BW, box[2]), min(BH, box[3])
        if cx1 <= cx0 or cy1 <= cy0: return
        sub = im.crop((cx0 - x0, cy0 - y0, cx1 - x0, cy1 - y0))
        base = self.img.crop((cx0, cy0, cx1, cy1)).convert("RGB")
        self.img.paste(ImageChops.multiply(base, sub), (cx0, cy0))

# ---------- Pip: original character ----------
def pip(p, x, y, s=1.0, arms=((-140, -110), (-40, -70)), legs=(-105, -75), mouth="smile", eyes="dot",
        pointer=None, key="pip", look=(0, 0), blush=False, tilt=0, body=1.0):
    """x,y = feet center. arms angles in degrees for (upper,lower) of left & right; 0=right, -90=up."""
    hr = 52 * s
    hip = (x, y - 95 * s)
    neck = (x + tilt * s, y - 205 * s * body)
    hc = (neck[0] + tilt * 0.3 * s, neck[1] - hr * 0.92)
    # legs
    for i, a in enumerate(legs):
        a = math.radians(-a)
        foot = (hip[0] + math.cos(a) * 100 * s, hip[1] + math.sin(a) * 100 * s)
        p.line([hip, foot, (foot[0] + (14 if i else -14) * s, foot[1] + 2)], 4.5 * s, key=(key, "leg", i))
    p.line([hip, neck], 4.5 * s, key=(key, "body"))
    sh = (neck[0], neck[1] + 18 * s)
    hands = []
    for i, (a1, a2) in enumerate(arms):
        r1, r2 = math.radians(a1), math.radians(a2)
        el = (sh[0] + math.cos(r1) * 55 * s, sh[1] + math.sin(r1) * 55 * s)
        hd = (el[0] + math.cos(r2) * 52 * s, el[1] + math.sin(r2) * 52 * s)
        p.line([sh, el, hd], 4.5 * s, key=(key, "arm", i))
        hands.append(hd)
    if pointer is not None:
        hd = hands[pointer[0]]
        tip = pointer[1]
        p.line([hd, tip], 5 * s, c=(120, 80, 40), key=(key, "ptr"))
        p.line([(lerp(hd[0], tip[0], .85), lerp(hd[1], tip[1], .85)), tip], 5 * s, c=(60, 40, 20), key=(key, "ptr2"))
    # head
    p.ellipse(hc[0], hc[1], hr, hr * 1.03, 4.5 * s, fill=SKIN, key=(key, "head"))
    # beanie
    bx, by = hc[0], hc[1] - hr * 0.25
    pts = [(bx - hr * 1.02 + hr * 2.04 * i / 20, by - math.sin(math.pi * i / 20) * hr * 0.95) for i in range(21)]
    p.poly(pts, 4.5 * s, fill=BEANIE, key=(key, "bean"), jit=1)
    p.poly([(bx - hr * 1.08, by - 2 * s), (bx + hr * 1.08, by - 2 * s), (bx + hr * 1.06, by + 16 * s), (bx - hr * 1.06, by + 16 * s)], 4 * s, fill=BEANIE_D, key=(key, "band"))
    p.ellipse(bx + 6 * s, by - hr * 0.98, 13 * s, 12 * s, 4 * s, fill=(250, 245, 235), key=(key, "pom"))
    # glasses + eyes
    ex = 19 * s; ey = hc[1] + 10 * s
    lx, ly = look[0] * 5 * s, look[1] * 4 * s
    for sgn in (-1, 1):
        cx = hc[0] + sgn * ex + tilt * 0.2 * s
        if eyes == "dot":
            p.ellipse(cx + lx, ey + ly, 4.5 * s, 5.5 * s, 0, fill=INK, key=(key, "eye", sgn))
        elif eyes == "wide":
            p.ellipse(cx + lx, ey + ly, 7 * s, 8 * s, 0, fill=INK, key=(key, "eye", sgn))
        elif eyes == "closed":
            p.curve([(cx - 7 * s, ey), (cx, ey + 5 * s), (cx + 7 * s, ey)], 3.5 * s, key=(key, "eye", sgn))
        elif eyes == "squint":
            p.line([(cx - 7 * s, ey - sgn * 2 * s), (cx + 7 * s, ey + sgn * 2 * s)], 3.5 * s, key=(key, "eye", sgn))
        p.ellipse(cx, ey, 15 * s, 13 * s, 3.2 * s, key=(key, "gl", sgn))
    p.line([(hc[0] - ex + 15 * s, ey - 2 * s), (hc[0] + ex - 15 * s, ey - 2 * s)], 3 * s, key=(key, "bridge"))
    my = hc[1] + 34 * s
    if blush:
        for sgn in (-1, 1): p.ellipse(hc[0] + sgn * 34 * s, my - 6 * s, 9 * s, 5 * s, 0, fill=(240, 150, 150), key=(key, "bl", sgn))
    if mouth == "smile":
        p.curve([(hc[0] - 15 * s, my - 3 * s), (hc[0], my + 9 * s), (hc[0] + 16 * s, my - 4 * s)], 3.5 * s, key=(key, "m"))
    elif mouth == "grin":
        p.poly([(hc[0] - 18 * s, my - 4 * s), (hc[0] + 18 * s, my - 4 * s), (hc[0] + 10 * s, my + 10 * s), (hc[0] - 10 * s, my + 10 * s)], 3.5 * s, fill=(130, 30, 40), key=(key, "m"))
    elif mouth == "o":
        p.ellipse(hc[0], my + 2 * s, 7 * s, 9 * s, 3.5 * s, fill=(130, 30, 40), key=(key, "m"))
    elif mouth == "flat":
        p.line([(hc[0] - 12 * s, my), (hc[0] + 12 * s, my + 1 * s)], 3.5 * s, key=(key, "m"))
    elif mouth == "frown":
        p.curve([(hc[0] - 14 * s, my + 6 * s), (hc[0], my - 5 * s), (hc[0] + 14 * s, my + 6 * s)], 3.5 * s, key=(key, "m"))
    elif mouth == "smirk":
        p.curve([(hc[0] - 12 * s, my + 2 * s), (hc[0] + 4 * s, my + 4 * s), (hc[0] + 16 * s, my - 6 * s)], 3.5 * s, key=(key, "m"))
    return hc, hands

# arm presets (upper, lower) degrees
A_DOWN_L, A_DOWN_R = (120, 100), (60, 80)
A_HIP_L, A_HIP_R = (150, 40), (30, 140)
A_POINT_R = (-20, -25)
A_POINT_L = (200, 205)
A_UP_L, A_UP_R = (-120, -100), (-60, -80)
A_CHIN_R = (60, -150)
A_SHRUG_L, A_SHRUG_R = (160, -120), (20, -60)
A_WAVE_R = (-30, -95)

# ---------- extras: generic stick people (not Pip) ----------
def stick(p, x, y, s=1.0, head=(230, 230, 230), mouth="flat", arms=(A_DOWN_L, A_DOWN_R), key="st", hat=None):
    hip = (x, y - 70 * s); neck = (x, y - 150 * s); hr = 30 * s
    hc = (x, neck[1] - hr * 0.95)
    for i, a in enumerate((-105, -75)):
        a = math.radians(-a); p.line([hip, (hip[0] + math.cos(a) * 72 * s, hip[1] + math.sin(a) * 72 * s)], 3.5 * s, key=(key, "l", i))
    p.line([hip, neck], 3.5 * s, key=(key, "b"))
    hands = []
    for i, (a1, a2) in enumerate(arms):
        r1, r2 = math.radians(a1), math.radians(a2); sh = (neck[0], neck[1] + 12 * s)
        el = (sh[0] + math.cos(r1) * 38 * s, sh[1] + math.sin(r1) * 38 * s); hd = (el[0] + math.cos(r2) * 36 * s, el[1] + math.sin(r2) * 36 * s)
        p.line([sh, el, hd], 3.5 * s, key=(key, "a", i)); hands.append(hd)
    p.ellipse(hc[0], hc[1], hr, hr, 3.5 * s, fill=head, key=(key, "h"))
    for sg in (-1, 1): p.ellipse(hc[0] + sg * 10 * s, hc[1] - 2 * s, 3 * s, 3.5 * s, 0, fill=INK, key=(key, "e", sg))
    my = hc[1] + 13 * s
    if mouth == "o": p.ellipse(hc[0], my, 5 * s, 6 * s, 3 * s, fill=(130, 30, 40), key=(key, "m"))
    elif mouth == "frown": p.curve([(hc[0] - 9 * s, my + 3 * s), (hc[0], my - 3 * s), (hc[0] + 9 * s, my + 3 * s)], 3 * s, key=(key, "m"))
    else: p.line([(hc[0] - 8 * s, my), (hc[0] + 8 * s, my)], 3 * s, key=(key, "m"))
    if hat == "top":
        p.rect(hc[0] - 20 * s, hc[1] - hr - 38 * s, 40 * s, 36 * s, 3.5 * s, fill=INK, key=(key, "ht"))
        p.line([(hc[0] - 32 * s, hc[1] - hr - 2 * s), (hc[0] + 32 * s, hc[1] - hr - 2 * s)], 5 * s, key=(key, "hb"))
    return hc, hands

def bubble(p, x, y, w, h, tail, txt, size=30, scale=1.0, key="bub", font=HAND, c=INK):
    if scale <= 0.01: return
    w, h = w * scale, h * scale
    p.ellipse(x, y, w / 2, h / 2, 3.5, fill=(255, 255, 255), key=(key, "b"))
    if tail is None: tx = None
    else:
        tx, ty = tail
    if tx is not None: p.poly([(x - w * 0.12, y + h * 0.36), (tx, ty), (x + w * 0.05, y + h * 0.44)], 0, fill=(255, 255, 255), key=(key, "t"))
    if tx is not None: p.line([(x - w * 0.12, y + h * 0.38), (tx, ty), (x + w * 0.05, y + h * 0.45)], 3.5, key=(key, "tl"))
    for i, ln in enumerate(txt.split("\n")):
        n = len(txt.split("\n"))
        p.text(ln, x, y + (i - (n - 1) / 2) * size * 1.05 * scale, size, font, c, scale=scale, key=(key, i))

def balance(p, cx, cy, ang=0, key="bal", s=1.0):
    """Hand-drawn balance. cx,cy = pivot. ang>0 tips right side down. Returns (left_pan_xy, right_pan_xy)."""
    wood, wood_d = (150, 95, 50), (110, 68, 35)
    p.poly([(cx - 14*s, cy), (cx + 14*s, cy), (cx + 18*s, cy + 300*s), (cx - 18*s, cy + 300*s)], 4, fill=wood, key=(key, "post"))
    p.poly([(cx - 110*s, cy + 300*s), (cx + 110*s, cy + 300*s), (cx + 90*s, cy + 330*s), (cx - 90*s, cy + 330*s)], 4, fill=wood_d, key=(key, "base"))
    a = math.radians(ang); L = 300*s
    ends = []
    for sg in (-1, 1):
        ends.append((cx + sg * math.cos(a) * L, cy + sg * math.sin(a) * L))
    dx, dy = -math.sin(a) * 11*s, math.cos(a) * 11*s
    (lx, ly), (rx, ry) = ends
    p.poly([(lx - dx, ly - dy), (rx - dx, ry - dy), (rx + dx, ry + dy), (lx + dx, ly + dy)], 4, fill=wood, key=(key, "beam"))
    p.ellipse(cx, cy, 16*s, 16*s, 4, fill=(220, 180, 60), key=(key, "piv"))
    pans = []
    for i, (ex, ey) in enumerate(ends):
        py = ey + 150*s
        p.line([(ex, ey), (ex - 85*s, py)], 3, key=(key, "c1", i)); p.line([(ex, ey), (ex + 85*s, py)], 3, key=(key, "c2", i))
        pts = [(ex - 95*s + 190*s*k/16, py + math.sin(math.pi*k/16) * 45*s) for k in range(17)]
        p.poly(pts, 4, fill=(210, 120, 50), key=(key, "pan", i), jit=0.8)
        pans.append((ex, py))
    return pans

def chalkboard(p, x, y, w, h, key="cb"):
    p.rect(x - 16, y - 16, w + 32, h + 32, 5, fill=(120, 78, 45), key=(key, "f"))
    p.rect(x, y, w, h, 4, fill=(40, 110, 60), key=(key, "b"))

def arrow(p, x0, y0, x1, y1, w=5, c=RED, key="ar", prog=1.0):
    if prog <= 0: return
    x1, y1 = lerp(x0, x1, prog), lerp(y0, y1, prog)
    p.line([(x0, y0), (x1, y1)], w, c, key=(key, 0))
    a = math.atan2(y1 - y0, x1 - x0)
    for d in (2.5, -2.5):
        p.line([(x1, y1), (x1 - math.cos(a + d / 6.5) * 22, y1 - math.sin(a + d / 6.5) * 22)], w, c, key=(key, d))

def bar(p, x, y_base, w, h, fill, key="bar", prog=1.0):
    hh = h * ease(prog)
    if hh < 2: return
    p.rect(x, y_base - hh, w, hh, 4, fill=fill, key=key)

def doodle_pc(p, x, y, s=1, key="pc"):
    p.rect(x - 50 * s, y - 70 * s, 100 * s, 72 * s, 4, fill=(225, 220, 200), key=(key, 1))
    p.rect(x - 38 * s, y - 60 * s, 76 * s, 50 * s, 3, fill=(60, 120, 170), key=(key, 2))
    p.rect(x - 62 * s, y + 8 * s, 124 * s, 22 * s, 4, fill=(225, 220, 200), key=(key, 3))
def doodle_globe(p, x, y, s=1, key="gl"):
    p.ellipse(x, y, 48 * s, 48 * s, 4, fill=(110, 180, 230), key=(key, 1))
    p.ellipse(x, y, 20 * s, 48 * s, 3, key=(key, 2))
    p.line([(x - 48 * s, y), (x + 48 * s, y)], 3, key=(key, 3))
    p.text("www", x, y - 70 * s, 30 * s, HAND, BLUE, key=(key, 4))
def doodle_phone(p, x, y, s=1, key="ph"):
    p.rect(x - 30 * s, y - 55 * s, 60 * s, 110 * s, 4, fill=(50, 50, 55), key=(key, 1))
    p.rect(x - 23 * s, y - 45 * s, 46 * s, 82 * s, 3, fill=(120, 200, 230), key=(key, 2))
    for i in range(3):
        for j in range(4): p.rect(x - 18 * s + i * 14 * s, y - 38 * s + j * 18 * s, 9 * s, 9 * s, 0, fill=[(240, 90, 80), (250, 200, 60), (90, 200, 120)][(i + j) % 3], key=(key, i, j))


# ---------- timing + render loop ----------
import json, re
_WORDS = None
def word_at(word, after=0.0):
    """Start time of the first spoken `word` at or after `after` seconds (from words.json)."""
    global _WORDS
    if _WORDS is None:
        _WORDS = json.load(open(f"{ROOT}/words.json"))
    w = re.sub(r"[^a-z0-9]", "", word.lower())
    for tok, t0, t1 in _WORDS:
        if t0 >= after and (tok == w or tok.startswith(w)):
            return t0
    raise KeyError(f"{word!r} not spoken after {after}s")

def make_frame(scenes, t):
    img = Image.new("RGB", (BW, BH), (255, 255, 255))
    p = Pen(img, boil=int(t * 8))  # line boil at 8 fps
    [f for s, f in scenes if s <= t][-1](p, t)
    return img.resize((W, H), Image.LANCZOS)

_SC = None
def _init(scenes, canvas):
    # spawn-safe: workers re-import this module, so hand them the scenes + canvas size
    global _SC
    _SC = scenes
    set_canvas(*canvas)

def _save(i):
    make_frame(_SC, i / FPS).save(f"{ROOT}/frames/{i:05d}.png", compress_level=1)

def run(scenes, total):
    """CLI: python3 scenes.py            -> render all frames to ./frames
            python3 scenes.py --still T.. -> still_T.png per time, for checking"""
    global _SC
    _SC = scenes
    a = sys.argv[1:]
    if a and a[0] == "--still":
        for ts in a[1:]:
            make_frame(scenes, float(ts)).save(f"{ROOT}/still_{ts}.png")
        return
    import shutil
    shutil.rmtree(f"{ROOT}/frames", ignore_errors=True); os.makedirs(f"{ROOT}/frames")
    n = int(total * FPS)
    with Pool(os.cpu_count(), initializer=_init, initargs=(scenes, (W, H))) as pool:
        for k, _ in enumerate(pool.imap_unordered(_save, range(n), chunksize=8)):
            if k % 400 == 0: print(k, "/", n, flush=True)

# ---------- real screenshots ----------
def card(p, path, cx, cy, w, source, scale=1.0, rot=0):
    """Paste a real screenshot (headline crop, chart) as a tilted card with a source caption.
    `path` is relative to the project dir. Always pass the real source - never fabricate one."""
    if scale <= 0.01: return
    im = Image.open(f"{ROOT}/{path}").convert("RGB")
    ww = int(w * scale * SS); hh = int(im.height * ww / im.width)
    im = im.resize((ww, hh), Image.LANCZOS)
    pad = 6 * SS
    framed = Image.new("RGBA", (ww + 2 * pad, hh + 2 * pad), (30, 30, 30, 255))
    framed.paste(im, (pad, pad))
    if rot: framed = framed.rotate(rot, resample=Image.BICUBIC, expand=True)
    shadow = Image.new("RGBA", framed.size, (0, 0, 0, 0))
    shadow.paste((0, 0, 0, 60), mask=framed.split()[3])
    x0, y0 = int(cx * SS - framed.width / 2), int(cy * SS - framed.height / 2)
    p.img.paste(shadow, (x0 + 10 * SS, y0 + 12 * SS), shadow)
    p.img.paste(framed, (x0, y0), framed)
    p.text(f"Source: {source}", cx, cy + (hh / SS) / 2 + 40 * scale, 20, HAND, GRAY, scale=scale, jit=False)

def set_canvas(w, h):
    """Switch canvas size, e.g. set_canvas(720, 1280) for vertical 9:16. Call before run()."""
    global W, H, BW, BH
    W, H, BW, BH = w, h, w * SS, h * SS

# ---------- animated GIF as a card ----------
_GIFS = {}
def gif_card(p, t, path, cx, cy, w, t0, radius=0.17):
    """Play an animated GIF (path relative to the project dir) as a rounded square card that pops in at t0.
    Frame = elapsed time x the GIF's own frame duration, so it loops in real time."""
    sc = pop(t, t0)
    if sc <= 0.01: return
    if path not in _GIFS:
        from PIL import ImageSequence
        g = Image.open(f"{ROOT}/{path}")
        _GIFS[path] = ([f.convert("RGB") for f in ImageSequence.Iterator(g)], (g.info.get("duration") or 100) / 1000)
    frames, fd = _GIFS[path]
    fr = frames[int(max(0, t - t0) / fd) % len(frames)]
    ww = int(w * sc * SS); hh = int(fr.height * ww / fr.width)
    im = fr.resize((ww, hh), Image.NEAREST)
    mask = Image.new("L", (ww, hh), 0); ImageDraw.Draw(mask).rounded_rectangle((0, 0, ww - 1, hh - 1), int(min(ww, hh) * radius), fill=255)
    p.img.paste(im, (int(cx * SS - ww / 2), int(cy * SS - hh / 2)), mask)
