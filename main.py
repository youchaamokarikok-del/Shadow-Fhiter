import pygame, random, math, os, array, threading, time

# ---- switches (turn off if something misbehaves on your phone) ----
USE_SOUND = True         # sound + music
FANCY_BUTTONS = True     # shiny 3D buttons


def show_error(err):
    try:
        print(err)
    except Exception:
        pass
    try:
        try:
            here = os.path.dirname(os.path.abspath(__file__))
        except Exception:
            here = "."
        try:
            with open(os.path.join(here, "fighter_error.txt"), "w") as fh:
                fh.write(err)
        except Exception:
            pass
        try:
            with open(os.path.join(here, "fighter_stage.txt"), "w") as fh:
                fh.write("err")
        except Exception:
            pass
        if not pygame.get_init():
            pygame.init()
        scr = pygame.display.get_surface() or pygame.display.set_mode((0, 0))
        w, h = scr.get_size()
        fnt = pygame.font.Font(None, max(20, h // 26))
        maxc = max(20, w // max(1, fnt.size("M")[0]))
        lines = ["ERROR - take a screenshot and send it to Claude", ""]
        for ln in err.splitlines()[-16:]:
            while len(ln) > maxc:
                lines.append(ln[:maxc])
                ln = ln[maxc:]
            lines.append(ln)
        clk = pygame.time.Clock()
        n = 0
        while True:
            n += 1
            for e in pygame.event.get():
                if e.type == pygame.QUIT or (n > 150 and e.type in (pygame.FINGERDOWN, pygame.MOUSEBUTTONDOWN)):
                    return
            scr.fill((25, 0, 0))
            y = 10
            for ln in lines:
                scr.blit(fnt.render(ln, True, (255, 225, 225)), (10, y))
                y += fnt.get_height() + 2
            pygame.display.flip()
            clk.tick(15)
    except Exception:
        pass


try:
    _here0 = os.path.dirname(os.path.abspath(__file__))
except Exception:
    _here0 = "."
STAGE_FILE = os.path.join(_here0, "fighter_stage.txt")
FLAGS_FILE = os.path.join(_here0, "fighter_flags.txt")
SAVE = os.path.join(_here0, "fighter_save2.txt")


def _rd(p):
    try:
        with open(p) as fh:
            return fh.read().strip()
    except Exception:
        return ""


def _wr(p, t):
    try:
        with open(p, "w") as fh:
            fh.write(t)
    except Exception:
        pass


LASTMARK = ["init"]


def mark(t):
    LASTMARK[0] = t
    _wr(STAGE_FILE, t)


FLAGS = set()
SAFE_UI = False
LITE = [False]          # switched on automatically if the phone is slow
W, H = 800, 450
GROUND = 310
NUM_LEVELS = 80
NUM_WORLDS = 16


# ---------------------------------------------------------------- helpers
def P(p):
    return (int(p[0]), int(p[1]))


def shade(c, f):
    return tuple(max(0, min(255, int(v * f))) for v in c[:3])


def lerp(c1, c2, t):
    return tuple(int(c1[i] + (c2[i] - c1[i]) * t) for i in range(3))


def clampi(v, lo, hi):
    return max(lo, min(hi, int(v)))


def ik(s, t, l1, l2, pref):
    """Two-bone limb: returns (middle joint, end point)."""
    dx, dy = t[0] - s[0], t[1] - s[1]
    d = max(0.01, min(math.hypot(dx, dy), l1 + l2 - 0.01))
    a = math.atan2(dy, dx)
    c = (l1 * l1 + d * d - l2 * l2) / (2 * l1 * d)
    b = math.acos(max(-1.0, min(1.0, c)))
    best = None
    for sign in (1, -1):
        ex = s[0] + l1 * math.cos(a + sign * b)
        ey = s[1] + l1 * math.sin(a + sign * b)
        score = (ex - s[0]) * pref[0] + (ey - s[1]) * pref[1]
        if best is None or score > best[0]:
            best = (score, (ex, ey))
    end = (s[0] + d * math.cos(a), s[1] + d * math.sin(a))
    return best[1], end


def seg(surf, a, b, w1, w2, col, edge, hi=True):
    """Tapered limb piece with an outline and simple light/shadow stripes."""
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    ln = math.hypot(dx, dy)
    if ln < 0.5:
        ln = 0.5
    nx, ny = -dy / ln, dx / ln
    for k in (0, 1):
        c = edge if k == 0 else col
        e = 3 if k == 0 else 0
        h1 = (w1 + e) / 2.0
        h2 = (w2 + e) / 2.0
        pts = [(ax + nx * h1, ay + ny * h1), (bx + nx * h2, by + ny * h2),
               (bx - nx * h2, by - ny * h2), (ax - nx * h1, ay - ny * h1)]
        pygame.draw.polygon(surf, c, pts)
        pygame.draw.circle(surf, c, P(a), max(1, int(h1)))
        pygame.draw.circle(surf, c, P(b), max(1, int(h2)))
    if hi and w1 >= 6 and not LITE[0]:
        sg = 1 if (-nx - ny) > 0 else -1
        o1, o2 = w1 * 0.22 * sg, w2 * 0.22 * sg
        t = max(1, int(w1 * 0.2))
        pygame.draw.line(surf, shade(col, 1.3), (ax + nx * o1, ay + ny * o1), (bx + nx * o2, by + ny * o2), t)
        pygame.draw.line(surf, shade(col, 0.7), (ax - nx * o1 * 1.3, ay - ny * o1 * 1.3),
                         (bx - nx * o2 * 1.3, by - ny * o2 * 1.3), t)


def blob(surf, center, rx, ry, col, edge):
    r = pygame.Rect(0, 0, max(2, int(rx * 2 + 3)), max(2, int(ry * 2 + 3)))
    r.center = (int(center[0]), int(center[1]))
    pygame.draw.ellipse(surf, edge, r)
    r2 = pygame.Rect(0, 0, max(2, int(rx * 2)), max(2, int(ry * 2)))
    r2.center = (int(center[0]), int(center[1]))
    pygame.draw.ellipse(surf, col, r2)


def poly(surf, pts, col, edge=None):
    if edge is not None:
        pygame.draw.polygon(surf, edge, pts, 3)
    pygame.draw.polygon(surf, col, pts)
    if edge is not None:
        pygame.draw.polygon(surf, edge, pts, 2)


# ---------------------------------------------------------------- save file
def load_cleared():
    try:
        with open(SAVE) as fh:
            return max(0, min(NUM_LEVELS, int(fh.read().strip())))
    except Exception:
        return 0


PROG_FILE = os.path.join(_here0, "fighter_prog.txt")
UP_NAMES = ["power", "health", "armor"]
UP_MAX = 10


def load_prog():
    d = {"coins": 0, "power": 0, "health": 0, "armor": 0}
    try:
        with open(PROG_FILE) as fh:
            parts = fh.read().strip().split(",")
        d["coins"] = max(0, int(parts[0]))
        for i, k in enumerate(UP_NAMES):
            d[k] = max(0, min(UP_MAX, int(parts[i + 1])))
    except Exception:
        pass
    return d


def save_prog(d):
    try:
        with open(PROG_FILE, "w") as fh:
            fh.write("%d,%d,%d,%d" % (d["coins"], d["power"], d["health"], d["armor"]))
    except Exception:
        pass


def save_cleared(n):
    try:
        with open(SAVE, "w") as fh:
            fh.write(str(n))
    except Exception:
        pass


# ---------------------------------------------------------------- sound (all generated in code, in a background thread)
GEN = 11025              # rate used while composing (upsampled to the phone's rate)
RATE, CH, REP = 22050, 1, 2
SOUND_OK = False
SFX = {}
MUSIC = {}
PENDING = []             # (name, bytes) produced by the worker thread
MUSIC_WANT = [None]
MUSIC_NOW = [None]
SOUND_ON = [True]
MUSIC_VOL = 0.55


def init_audio():
    global SOUND_OK, RATE, CH, REP
    SOUND_OK = False
    try:
        if "nosound" in FLAGS or not USE_SOUND:
            return
        mark("audio")
        if pygame.mixer.get_init() is None:
            pygame.mixer.init()
        mi = pygame.mixer.get_init()
        if mi:
            RATE, CH = mi[0], mi[2]
            REP = max(1, int(round(RATE / float(GEN))))
            SOUND_OK = True
    except Exception:
        SOUND_OK = False


def to_bytes(samples, peak_target=0.9):
    """float list (mono, GEN rate) -> bytes for the mixer (device rate / channels)."""
    pk = 0.0001
    for v in samples:
        a = v if v >= 0 else -v
        if a > pk:
            pk = a
    sc = peak_target / pk if pk > peak_target else 1.0
    ints = array.array("h", [int(max(-1.0, min(1.0, v * sc)) * 30000) for v in samples])
    m = REP * CH
    out = array.array("h", bytes(len(ints) * m * 2))
    for j in range(m):
        out[j::m] = ints
    return out.tobytes()


def tone(f0, f1, ms, vol=0.5, kind="sq", decay=1.0):
    n = int(GEN * ms / 1000)
    out = []
    ph = 0.0
    for i in range(n):
        t = i / float(n)
        ph += (f0 + (f1 - f0) * t) / GEN
        x = ph % 1.0
        if kind == "sq":
            w = 1.0 if x < 0.5 else -1.0
        elif kind == "saw":
            w = 2 * x - 1
        elif kind == "tri":
            w = 4 * abs(x - 0.5) - 1
        else:
            w = math.sin(2 * math.pi * x)
        out.append(w * vol * (1 - t) ** decay)
    return out


def noise(ms, vol=0.5, decay=2.0, lp=0.5):
    n = int(GEN * ms / 1000)
    out = []
    last = 0.0
    rnd = random.uniform
    for i in range(n):
        last += (rnd(-1, 1) - last) * lp
        out.append(last * vol * (1 - i / float(n)) ** decay)
    return out


def mix(*tracks):
    n = max(len(t) for t in tracks)
    out = [0.0] * n
    for t in tracks:
        for i, v in enumerate(t):
            out[i] += v
    return out


def mtof(n):
    return 440.0 * 2 ** ((n - 69) / 12.0)


def add_hit(buf, start, hit, vol):
    n = min(len(hit), len(buf) - start)
    for i in range(n):
        buf[start + i] += hit[i] * vol


def add_brass(buf, start, dur, midi, vol):
    f = mtof(midi)
    n = min(int(dur * GEN), len(buf) - start)
    if n <= 0:
        return
    inc, inc2 = f / GEN, f * 1.007 / GEN
    ph, ph2, lp = 0.0, 0.37, 0.0
    att = int(0.035 * GEN)
    rel = int(0.07 * GEN)
    for i in range(n):
        ph += inc
        if ph >= 1.0:
            ph -= 1.0
        ph2 += inc2
        if ph2 >= 1.0:
            ph2 -= 1.0
        v = (ph * 2 - 1) * 0.55 + (ph2 * 2 - 1) * 0.45
        if i < att:
            e = i / float(att)
            a = 0.12 + 0.4 * e
        else:
            e = 1.0
            a = 0.5
        if i > n - rel:
            e = (n - i) / float(rel)
        lp += (v - lp) * a
        buf[start + i] += lp * e * vol
    time.sleep(0.001)


def add_bass(buf, start, dur, midi, vol):
    f = mtof(midi)
    n = min(int(dur * GEN), len(buf) - start)
    if n <= 0:
        return
    inc = f / GEN
    ph, lp = 0.0, 0.0
    rel = int(0.04 * GEN)
    dec = 1.0 / max(1, n)
    for i in range(n):
        ph += inc
        if ph >= 1.0:
            ph -= 1.0
        v = (1.0 if ph < 0.5 else -1.0) * 0.6 + (ph * 2 - 1) * 0.4
        lp += (v - lp) * 0.35
        e = 1.0 - 0.35 * i * dec
        if i > n - rel:
            e *= (n - i) / float(rel)
        buf[start + i] += lp * e * vol
    time.sleep(0.001)


def add_pad(buf, start, dur, midi, vol):
    f = mtof(midi)
    n = min(int(dur * GEN), len(buf) - start)
    if n <= 0:
        return
    inc, inc2 = f / GEN, f * 1.004 / GEN
    ph, ph2 = 0.0, 0.5
    att = int(0.45 * GEN)
    rel = int(0.5 * GEN)
    for i in range(n):
        ph += inc
        if ph >= 1.0:
            ph -= 1.0
        ph2 += inc2
        if ph2 >= 1.0:
            ph2 -= 1.0
        v = (4 * abs(ph - 0.5) - 1) * 0.5 + (4 * abs(ph2 - 0.5) - 1) * 0.5
        e = 1.0
        if i < att:
            e = i / float(att)
        if i > n - rel:
            e = min(e, (n - i) / float(rel))
        buf[start + i] += v * e * vol
    time.sleep(0.001)


def drum_kick():
    return mix(tone(165, 42, 280, 0.95, "sin", 1.6), noise(14, 0.5, 1.0, 0.8))


def drum_snare():
    return mix(noise(210, 0.75, 2.2, 0.55), tone(210, 150, 110, 0.45, "tri", 1.4))


def drum_tom(f):
    return mix(tone(f * 1.5, f * 0.55, 380, 0.9, "sin", 1.7), noise(18, 0.25, 1.0, 0.5))


def drum_hat():
    return noise(38, 0.4, 3.0, 0.97)


def drum_gong():
    return mix(noise(1500, 0.45, 1.3, 0.35), tone(95, 80, 1500, 0.4, "sin", 1.0), tone(143, 120, 1200, 0.2, "sin", 1.0))


TRACKS = {
    "menu": dict(bpm=96, roots=[50, 46, 48, 45, 50, 46, 45, 45], style="menu", lead=[
        [(74, 2), (77, 2)], [(74, 1), (72, 1), (70, 2)], [(72, 2), (76, 2)], [(76, 2), (73, 2)],
        [(74, 2), (81, 2)], [(79, 2), (77, 2)], [(76, 1), (73, 1), (76, 2)], [(73, 4)]]),
    "battleA": dict(bpm=150, roots=[50, 50, 46, 46, 48, 48, 45, 45], style="march", lead=[
        [(74, 1), (69, .5), (74, .5), (77, 1), (76, .5), (74, .5)], [(69, 1), (72, .5), (74, .5), (76, 2)],
        [(77, 1), (74, .5), (77, .5), (81, 1), (79, .5), (77, .5)], [(74, 1.5), (72, .5), (70, 2)],
        [(76, 1), (79, .5), (76, .5), (72, 1), (76, .5), (79, .5)], [(74, 1), (76, 1), (79, 2)],
        [(76, .5), (69, .5), (73, .5), (76, .5), (81, 1), (79, .5), (76, .5)], [(76, 1), (73, 1), (69, 2)]]),
    "battleB": dict(bpm=160, roots=[45, 45, 53, 55, 45, 45, 53, 52], style="war", lead=[
        [(81, 1), (76, .5), (81, .5), (84, 1), (83, .5), (81, .5)], [(76, 1), (79, .5), (81, .5), (83, 2)],
        [(84, 1), (81, .5), (84, .5), (88, 1), (86, .5), (84, .5)], [(83, 1), (86, 1), (83, 2)],
        [(81, .5), (81, .5), (76, 1), (81, .5), (84, .5), (88, 1)], [(86, 1), (84, 1), (81, 2)],
        [(84, 1), (81, 1), (77, 1), (81, 1)], [(83, 1), (80, 1), (76, 2)]]),
    "boss": dict(bpm=168, roots=[50, 50, 51, 51, 50, 50, 45, 46], style="boss", lead=[
        [(74, 1), (74, .5), (77, .5), (74, 1), (73, .5), (74, .5)], [(69, 2), (70, 1), (69, 1)],
        [(75, 1), (75, .5), (78, .5), (75, 1), (74, .5), (75, .5)], [(70, 2), (72, 1), (70, 1)],
        [(74, .5), (77, .5), (81, 1), (80, 1), (77, 1)], [(74, 1), (77, 1), (74, 2)],
        [(76, .5), (73, .5), (69, 1), (73, 1), (76, 1)], [(77, 1), (74, 1), (70, 2)]]),
}

# 16 steps per bar. kick / snare / tom / hat / stab step lists
STYLES = {
    "menu": dict(kick=[0], snare=[], tom=[0, 8], hat=[], stab=[], gallop=False, pad=True),
    "march": dict(kick=[0, 8], snare=[4, 12], tom=[], hat=[0, 2, 4, 6, 8, 10, 12, 14], stab=[0, 6], gallop=True, pad=False),
    "war": dict(kick=[0, 6, 8, 10, 14], snare=[4, 12], tom=[2, 7], hat=[0, 2, 4, 6, 8, 10, 12, 14], stab=[0, 3, 6, 10], gallop=True, pad=False),
    "boss": dict(kick=[0, 2, 6, 8, 10, 14], snare=[4, 12], tom=[3, 11], hat=[1, 3, 5, 7, 9, 11, 13, 15], stab=[0, 8], gallop=True, pad=False),
}


def compose(name):
    tr = TRACKS[name]
    st = STYLES[tr["style"]]
    bpm = tr["bpm"]
    bars = len(tr["roots"])
    step = 60.0 / bpm / 4.0
    beat = step * 4
    nsamp = int(bars * 16 * step * GEN)
    buf = [0.0] * nsamp
    S = lambda s: int(s * step * GEN)
    kick, snare, hat, gong = drum_kick(), drum_snare(), drum_hat(), drum_gong()
    toms = [drum_tom(150), drum_tom(115), drum_tom(88), drum_tom(66)]
    for b in range(bars):
        base = b * 16
        root = tr["roots"][b]
        # drums
        for s_ in st["kick"]:
            add_hit(buf, S(base + s_), kick, 0.85 if tr["style"] != "menu" else 0.6)
        for s_ in st["snare"]:
            add_hit(buf, S(base + s_), snare, 0.55)
        for i_, s_ in enumerate(st["tom"]):
            add_hit(buf, S(base + s_), toms[(i_ + b) % 3 + 1], 0.55 if tr["style"] != "menu" else 0.8)
        for s_ in st["hat"]:
            add_hit(buf, S(base + s_), hat, 0.16)
        if tr["style"] == "menu":
            if b == bars - 1:
                for i_, s_ in enumerate(range(8, 16)):
                    add_hit(buf, S(base + s_), snare, 0.15 + 0.06 * i_)
        elif b % 4 == 3:
            for i_, s_ in enumerate((10, 12, 13, 14, 15)):
                add_hit(buf, S(base + s_), toms[min(3, i_ * 4 // 5 + (0 if i_ < 4 else 1))], 0.7)
        if b == 0 and tr["style"] == "boss":
            add_hit(buf, 0, gong, 0.7)
        if b == 0 and tr["style"] == "menu":
            add_hit(buf, 0, gong, 0.45)
        time.sleep(0.001)
        # bass / pad
        if st["pad"]:
            for iv in (0, 7, 12):
                add_pad(buf, S(base), 16 * step * 0.98, root + iv, 0.10)
        else:
            for e8 in range(8):
                n_ = root + (12 if e8 in (3, 7) else 0)
                add_bass(buf, S(base + e8 * 2), step * 1.8, n_, 0.26 if e8 % 4 == 0 else 0.21)
            for s_ in st["stab"]:
                for iv in (0, 7, 12):
                    add_brass(buf, S(base + s_), beat * 0.55, root + 12 + iv, 0.085)
        # lead melody
        pos = 0.0
        for m, d in tr["lead"][b]:
            t0 = S(base + pos * 4)
            vol = 0.19 if tr["style"] != "menu" else 0.17
            add_brass(buf, t0, d * beat * 0.97, m, vol)
            add_brass(buf, t0, d * beat * 0.97, m - 12, vol * 0.5)
            pos += d
    # tiny fade at the very end so the loop does not click
    for i in range(min(40, nsamp)):
        buf[nsamp - 1 - i] *= i / 40.0
    return buf


def make_sfx():
    out = {}
    out["punch"] = mix(noise(90, 0.7, 2, 0.35), tone(160, 70, 90, 0.5, "sin"))
    out["sword"] = mix(noise(200, 0.35, 1.2, 0.6), tone(900, 300, 180, 0.22, "saw"))
    out["gun"] = mix(noise(220, 0.9, 3, 0.25), tone(140, 40, 160, 0.6, "sq", 2))
    out["hit"] = mix(noise(110, 0.6, 2, 0.3), tone(220, 60, 120, 0.5, "sq"))
    out["block"] = mix(tone(700, 500, 70, 0.3, "sq"), noise(50, 0.3, 1, 0.7))
    out["ko"] = tone(420, 50, 600, 0.45, "saw", 1.5)
    out["click"] = tone(900, 900, 45, 0.3, "sq")
    out["win"] = (tone(523, 523, 110, 0.35) + tone(659, 659, 110, 0.35) + tone(784, 784, 110, 0.35)
                  + tone(1047, 1047, 320, 0.35))
    out["lose"] = tone(392, 392, 160, 0.35) + tone(330, 330, 160, 0.35) + tone(262, 262, 420, 0.35)
    out["stomp"] = mix(noise(450, 0.9, 2.5, 0.12), tone(70, 28, 450, 0.7, "sin", 1.8))
    out["roar"] = mix(noise(700, 0.4, 1.4, 0.3), tone(120, 55, 700, 0.35, "saw", 1.2))
    out["scream"] = mix(tone(220, 900, 1100, 0.42, "saw", 0.5), tone(110, 450, 1100, 0.3, "sq", 0.5),
                        noise(1100, 0.28, 0.8, 0.25))
    out["scream2"] = mix(tone(140, 520, 1100, 0.42, "saw", 0.5), tone(70, 260, 1100, 0.34, "sq", 0.5),
                         noise(1100, 0.32, 0.8, 0.2))
    out["rumble"] = mix(tone(48, 30, 1600, 0.7, "sin", 1.5), noise(1600, 0.3, 2, 0.12))
    out["heart"] = mix(tone(70, 40, 140, 0.9, "sin", 1.6), noise(90, 0.4, 2, 0.1))
    out["rip"] = mix(noise(300, 0.8, 2, 0.5), tone(320, 60, 300, 0.4, "saw"))
    out["flash"] = mix(noise(500, 0.8, 1.5, 0.6), tone(1400, 200, 500, 0.4, "saw", 1.2))
    out["crown"] = (tone(587, 587, 150, 0.3, "saw") + tone(698, 698, 150, 0.3, "saw") + tone(880, 880, 150, 0.3, "saw")
                    + mix(tone(1175, 1175, 700, 0.3, "saw", 0.6), tone(880, 880, 700, 0.2, "saw", 0.6),
                          tone(587, 587, 700, 0.2, "saw", 0.6)))
    return out


def audio_worker():
    try:
        for nm in ("fatality", "finishhim"):
            vp = os.path.join(_here0, nm + ".ogg")
            if os.path.exists(vp):
                PENDING.append(("sfx_" + nm, vp))
    except Exception:
        pass
    try:
        mp = os.path.join(_here0, "music.ogg")
        if os.path.exists(mp):
            for nm in ("menu", "battleA", "boss", "battleB"):
                PENDING.append(("music_" + nm, mp))
            for k, v in make_sfx().items():
                PENDING.append(("sfx_" + k, to_bytes(v, 0.85)))
            return
    except Exception:
        pass
    try:
        PENDING.append(("music_menu", to_bytes(compose("menu"))))
        for k, v in make_sfx().items():
            PENDING.append(("sfx_" + k, to_bytes(v, 0.85)))
            time.sleep(0.002)
        for nm in ("battleA", "boss", "battleB"):
            PENDING.append(("music_" + nm, to_bytes(compose(nm))))
    except Exception:
        pass


def start_audio_thread():
    if not SOUND_OK:
        return
    try:
        th = threading.Thread(target=audio_worker)
        th.daemon = True
        th.start()
    except Exception:
        pass


def _music_volume():
    return MUSIC_VOL if SOUND_ON[0] else 0.0


def _apply_music():
    if not SOUND_OK:
        return
    want = MUSIC_WANT[0]
    snd = MUSIC.get(want)
    cur = MUSIC_NOW[0]
    try:
        for s_ in MUSIC.values():
            s_.set_volume(_music_volume())
        if snd is None or cur == want:
            return
        if cur is not None and MUSIC.get(cur) is not None:
            MUSIC[cur].fadeout(500)
        snd.set_volume(_music_volume())
        snd.play(-1)
        MUSIC_NOW[0] = want
    except Exception:
        pass


def set_music(name):
    MUSIC_WANT[0] = name
    _apply_music()


def poll_audio():
    if not PENDING or not SOUND_OK:
        return
    prev = LASTMARK[0]
    try:
        name, data = PENDING.pop(0)
        mark("audio")
        snd = pygame.mixer.Sound(data) if isinstance(data, str) else pygame.mixer.Sound(buffer=data)
        mark(prev)
        if name.startswith("sfx_"):
            SFX[name[4:]] = snd
        else:
            MUSIC[name[6:]] = snd
            _apply_music()
    except Exception:
        pass


def play(name):
    if SOUND_OK and SOUND_ON[0]:
        s_ = SFX.get(name)
        if s_ is not None:
            try:
                s_.play()
            except Exception:
                pass


def toggle_sound():
    SOUND_ON[0] = not SOUND_ON[0]
    _apply_music()


# ---------------------------------------------------------------- weapons / looks
WEAPONS = [
    {"name": "Fists", "reach": 50, "dmg": 6, "cd": 9, "dur": 7, "hit": 2},
    {"name": "Sword", "reach": 80, "dmg": 14, "cd": 21, "dur": 10, "hit": 3},
    {"name": "Gun", "reach": 0, "dmg": 7, "cd": 17, "dur": 7, "hit": 1},
    {"name": "Club", "reach": 120, "dmg": 16, "cd": 55, "dur": 30, "hit": 16},
]
PLAYER_WEAPONS = 3
BULLETS = []
PARTICLES = []
SHAKE = [0]

SKINS = [(240, 206, 176), (226, 178, 134), (200, 148, 104), (165, 112, 76), (124, 82, 56), (92, 60, 42)]
HAIRS = [(30, 24, 20), (70, 44, 26), (150, 100, 50), (200, 190, 170), (20, 20, 24), (120, 40, 30)]

BASE_LOOK = {"skin": (236, 200, 168), "hair": (35, 30, 40), "hstyle": "short", "shirt": (120, 120, 120),
             "trim": (220, 220, 220), "pants": (60, 60, 70), "boots": (40, 32, 30), "belt": (90, 60, 30),
             "glove": None, "sleeves": "short", "headband": None, "armor": None, "mask": None,
             "beard": None, "cape": None, "helmet": None, "turban": None, "bare": False, "glow": None,
             "paint": None, "horns": False, "spikes": None, "fur": None, "scar": False, "necklace": None}


def mklook(**kw):
    d = dict(BASE_LOOK)
    d.update(kw)
    return d


PLAYER_LOOK = mklook(hair=(35, 30, 40), hstyle="spiky", shirt=(60, 140, 255), trim=(230, 235, 255),
                     pants=(40, 44, 66), boots=(30, 30, 40), belt=(210, 170, 60), glove=(210, 50, 50),
                     headband=(255, 215, 80), sleeves="short")


def make_look(L):
    """Look of the normal opponent of level L (0-based). Same level = same face every time."""
    w = (L // 5) % 8
    r = random.Random(900 + L * 13)
    skin = r.choice(SKINS)
    hair = r.choice(HAIRS)
    lk = mklook(skin=skin, hair=hair, hstyle=r.choice(["short", "spiky", "bald", "long", "mohawk", "ponytail"]))
    if w == 0:      # training yard: street brawlers
        lk.update(shirt=r.choice([(200, 60, 60), (220, 140, 40), (90, 90, 110), (60, 160, 100), (170, 60, 160)]),
                  pants=r.choice([(50, 50, 70), (80, 70, 50), (40, 40, 40)]), sleeves="none",
                  glove=r.choice([None, (235, 235, 235), (40, 40, 40)]))
        if r.random() < 0.45:
            lk["headband"] = r.choice([(220, 40, 40), (240, 240, 240)])
        if r.random() < 0.35:
            lk["beard"] = hair
    elif w == 1:    # bamboo dojo: monks and ninjas
        if r.random() < 0.5:
            lk.update(shirt=(30, 32, 40), trim=(160, 30, 30), pants=(26, 28, 34), boots=(20, 20, 26),
                      sleeves="long", mask=(26, 28, 34), hstyle="bald", glove=(26, 28, 34), headband=(160, 30, 30))
        else:
            lk.update(shirt=r.choice([(235, 235, 235), (230, 175, 60), (80, 120, 80)]), trim=(40, 40, 40),
                      pants=r.choice([(235, 235, 235), (40, 40, 50)]), boots=(120, 90, 60), belt=(30, 30, 30),
                      headband=r.choice([(40, 40, 40), (220, 50, 50)]))
    elif w == 2:    # desert: bandits
        lk.update(shirt=r.choice([(190, 150, 90), (160, 70, 50), (200, 190, 150)]), trim=(120, 50, 40),
                  pants=r.choice([(110, 80, 50), (70, 60, 50)]), boots=(80, 55, 35), belt=(150, 40, 40),
                  sleeves="long", turban=r.choice([(220, 205, 170), (170, 60, 50), (60, 90, 120)]),
                  hstyle="short", mask=r.choice([None, (150, 50, 40)]))
        if r.random() < 0.5:
            lk["beard"] = HAIRS[0]
    elif w == 3:    # snow peak: vikings
        lk.update(shirt=r.choice([(110, 80, 60), (70, 90, 120), (140, 60, 50)]), trim=(230, 230, 235),
                  pants=(70, 60, 55), boots=(60, 45, 35), belt=(50, 36, 28), sleeves="long",
                  fur=(235, 235, 240), beard=r.choice([(150, 100, 50), (200, 190, 170), (120, 60, 40)]),
                  helmet=r.choice([None, (150, 155, 165)]), horns=r.random() < 0.5)
    elif w == 4:    # harbor: dockworkers and sailors
        lk.update(shirt=r.choice([(235, 235, 240), (60, 90, 140), (200, 70, 60)]), trim=(30, 50, 100),
                  pants=(50, 60, 80), boots=(40, 36, 34), belt=(100, 70, 40), sleeves="short",
                  glove=r.choice([None, (120, 90, 60)]), headband=None)
        if r.random() < 0.5:
            lk["turban"] = r.choice([(40, 60, 100), (180, 50, 50)])
        if r.random() < 0.5:
            lk["beard"] = hair
    elif w == 5:    # jungle: tribal warriors
        lk.update(shirt=r.choice([(120, 70, 40), (50, 100, 60)]), bare=r.random() < 0.6, pants=(110, 80, 50),
                  boots=(90, 65, 40), belt=(200, 170, 60), sleeves="none", paint=r.choice([(220, 60, 40), (240, 240, 230), (60, 200, 90)]),
                  necklace=(235, 230, 210), hstyle=r.choice(["mohawk", "short", "long"]), glove=r.choice([None, (150, 110, 60)]))
    elif w == 6:    # volcano: forge warriors
        lk.update(shirt=(50, 44, 46), trim=(230, 110, 30), pants=(46, 40, 42), boots=(30, 26, 26), belt=(160, 90, 30),
                  skin=r.choice(SKINS[2:]), sleeves="none", bare=r.random() < 0.5, glove=(60, 50, 50),
                  glow=(255, 130, 30), hstyle=r.choice(["mohawk", "bald", "spiky"]), spikes=(110, 110, 120))
    else:           # sky citadel: royal guards
        lk.update(shirt=r.choice([(230, 230, 240), (60, 80, 160), (150, 40, 60)]), trim=(240, 200, 80),
                  armor=r.choice([(190, 195, 210), (220, 190, 90)]), pants=(60, 64, 90), boots=(180, 180, 195),
                  belt=(240, 200, 80), sleeves="long", glove=(190, 195, 210),
                  helmet=(190, 195, 210), cape=r.choice([(150, 40, 60), (50, 70, 150), None]),
                  horns=False)
    if r.random() < 0.18:
        lk["scar"] = True
    return lk


GIANT_NAMES = ["Grug the Brute", "Iron Colossus", "Dune Titan", "Frost Giant",
               "Harbor Behemoth", "Jungle Warlord", "Magma Colossus", "Storm Titan",
               "Neon Overlord", "Ice Emperor", "Ruin Guardian", "Tempest King",
               "Shadow Beast", "Lava Tyrant", "Star Devourer", "World Breaker"]


def make_giant_look(k):
    gl = [
        mklook(skin=(205, 160, 120), bare=False, shirt=(110, 78, 50), trim=(70, 50, 30), pants=(80, 66, 50),
               boots=(60, 44, 32), belt=(50, 36, 26), sleeves="none", hstyle="bald", beard=(70, 44, 26),
               glove=(60, 44, 32), scar=True),
        mklook(skin=(170, 175, 185), shirt=(120, 125, 140), armor=(150, 156, 170), trim=(220, 190, 90),
               pants=(70, 74, 90), boots=(90, 94, 108), belt=(220, 190, 90), sleeves="long", helmet=(150, 156, 170),
               glove=(150, 156, 170), spikes=(190, 195, 205)),
        mklook(skin=(150, 100, 66), bare=True, pants=(190, 150, 70), boots=(120, 80, 40), belt=(180, 40, 40),
               sleeves="none", turban=(180, 50, 40), glove=(240, 200, 80), beard=(30, 24, 20), necklace=(240, 200, 80)),
        mklook(skin=(170, 205, 230), bare=False, shirt=(235, 238, 245), trim=(150, 190, 230), pants=(90, 110, 150),
               boots=(60, 70, 100), belt=(120, 90, 60), sleeves="none", fur=(250, 250, 255), helmet=(150, 190, 225),
               horns=True, beard=(240, 240, 250)),
        mklook(skin=(70, 110, 120), bare=False, shirt=(230, 190, 40), trim=(200, 150, 20), pants=(60, 80, 100),
               boots=(30, 40, 50), belt=(120, 90, 50), sleeves="short", turban=(40, 60, 90), beard=(20, 30, 36),
               glove=(60, 70, 80), scar=True),
        mklook(skin=(90, 150, 80), bare=True, pants=(130, 90, 50), boots=(100, 70, 40), belt=(220, 190, 70),
               sleeves="none", paint=(240, 240, 230), necklace=(240, 235, 215), hstyle="mohawk", hair=(210, 60, 40),
               glove=(150, 110, 60), spikes=(235, 230, 210)),
        mklook(skin=(60, 38, 36), bare=True, pants=(40, 30, 30), boots=(30, 24, 24), belt=(200, 90, 30),
               sleeves="none", glow=(255, 140, 30), hstyle="spiky", hair=(255, 120, 30), glove=(50, 40, 40),
               spikes=(110, 100, 100), horns=True, helmet=None),
        mklook(skin=(120, 110, 190), bare=False, shirt=(60, 50, 120), armor=(235, 200, 90), trim=(240, 210, 90),
               pants=(50, 44, 100), boots=(235, 200, 90), belt=(240, 210, 90), sleeves="long", helmet=(235, 200, 90),
               horns=False, cape=(150, 40, 60), glove=(235, 200, 90), spikes=(240, 220, 120), beard=(235, 235, 250)),
    ]
    return gl[k % len(gl)]


# ---------------------------------------------------------------- particles
def spark(x, y, n, col, spread=5.0):
    for _ in range(n):
        if len(PARTICLES) > 70:
            break
        a = random.uniform(0, 6.283)
        v = random.uniform(1.5, spread)
        PARTICLES.append([x, y, math.cos(a) * v, math.sin(a) * v - 1.5, random.randint(10, 20), col])


def update_particles():
    for p in PARTICLES[:]:
        p[0] += p[2]
        p[1] += p[3]
        p[3] += 0.35
        p[4] -= 1
        if p[4] <= 0:
            PARTICLES.remove(p)


def draw_particles(surf):
    for p in PARTICLES:
        r = 2 if p[4] > 6 else 1
        pygame.draw.circle(surf, p[5], (int(p[0]), int(p[1])), r + 1)


# ---------------------------------------------------------------- weapon art
STEEL = (205, 212, 225)
EDGE = (24, 20, 26)


def draw_sword(surf, hf, d, k, C):
    nx, ny = -d[1], d[0]
    L = 66 * k
    g = (hf[0] + d[0] * 7 * k, hf[1] + d[1] * 7 * k)
    tip = (hf[0] + d[0] * L, hf[1] + d[1] * L)
    bw = 4.2 * k
    pts = [(g[0] + nx * bw, g[1] + ny * bw), (tip[0] + d[0] * 5 * k, tip[1] + d[1] * 5 * k),
           (g[0] - nx * bw, g[1] - ny * bw)]
    pygame.draw.polygon(surf, EDGE, [(p[0] + (p[0] - hf[0]) * 0.02, p[1]) for p in pts], 3)
    pygame.draw.polygon(surf, C(STEEL), pts)
    pygame.draw.line(surf, C((120, 130, 150)), P(g), P(tip), max(1, int(1.5 * k)))
    pygame.draw.line(surf, C((250, 252, 255)), (g[0] + nx * bw * 0.6, g[1] + ny * bw * 0.6),
                     (tip[0] + nx * 0.5, tip[1] + ny * 0.5), max(1, int(k)))
    g1 = (g[0] + nx * 10 * k, g[1] + ny * 10 * k)
    g2 = (g[0] - nx * 10 * k, g[1] - ny * 10 * k)
    pygame.draw.line(surf, EDGE, P(g1), P(g2), max(3, int(6 * k)))
    pygame.draw.line(surf, C((225, 180, 70)), P(g1), P(g2), max(2, int(4 * k)))
    a = (hf[0] - d[0] * 7 * k, hf[1] - d[1] * 7 * k)
    pygame.draw.line(surf, EDGE, P(a), P(g), max(3, int(6 * k)))
    pygame.draw.line(surf, C((110, 70, 44)), P(a), P(g), max(2, int(4 * k)))
    pygame.draw.circle(surf, C((225, 180, 70)), P((hf[0] - d[0] * 9 * k, hf[1] - d[1] * 9 * k)), max(2, int(3 * k)))


def draw_gun(surf, hf, f, k, C, firing):
    sx = hf[0]
    sy = hf[1]
    slide = [(sx - f * 2 * k, sy - 8 * k), (sx + f * 24 * k, sy - 8 * k), (sx + f * 24 * k, sy - 1 * k),
             (sx - f * 3 * k, sy - 1 * k)]
    poly(surf, slide, C((70, 76, 88)), EDGE)
    pygame.draw.line(surf, C((130, 138, 150)), (sx, sy - 6 * k), (sx + f * 22 * k, sy - 6 * k), max(1, int(1.5 * k)))
    grip = [(sx - f * 1 * k, sy - 1 * k), (sx + f * 7 * k, sy - 1 * k), (sx + f * 4 * k, sy + 12 * k),
            (sx - f * 4 * k, sy + 11 * k)]
    poly(surf, grip, C((120, 80, 50)), EDGE)
    pygame.draw.line(surf, EDGE, (sx + f * 8 * k, sy), (sx + f * 10 * k, sy + 5 * k), max(1, int(1.5 * k)))
    pygame.draw.line(surf, EDGE, (sx + f * 10 * k, sy + 5 * k), (sx + f * 5 * k, sy + 5 * k), max(1, int(1.5 * k)))
    if firing:
        mx, my = sx + f * 27 * k, sy - 5 * k
        star = []
        for i in range(10):
            a = i * math.pi / 5
            rr = (13 if i % 2 == 0 else 5) * k
            star.append((mx + math.cos(a) * rr * (1 if True else 1), my + math.sin(a) * rr * 0.8))
        pygame.draw.polygon(surf, (255, 150, 40), star)
        pygame.draw.circle(surf, (255, 240, 170), (int(mx), int(my)), max(2, int(4 * k)))


def draw_club(surf, hf, d, k, C):
    nx, ny = -d[1], d[0]
    a = (hf[0] - d[0] * 14 * k, hf[1] - d[1] * 14 * k)
    b = (hf[0] + d[0] * 78 * k, hf[1] + d[1] * 78 * k)
    pts = [(a[0] + nx * 4 * k, a[1] + ny * 4 * k), (b[0] + nx * 11 * k, b[1] + ny * 11 * k),
           (b[0] - nx * 11 * k, b[1] - ny * 11 * k), (a[0] - nx * 4 * k, a[1] - ny * 4 * k)]
    poly(surf, pts, C((120, 84, 52)), EDGE)
    pygame.draw.line(surf, C((160, 120, 80)), (a[0] + nx * 2 * k, a[1] + ny * 2 * k), (b[0] + nx * 6 * k, b[1] + ny * 6 * k), max(1, int(2 * k)))
    for i in range(1, 4):
        t = 0.45 + i * 0.16
        c0 = (hf[0] + d[0] * 78 * k * t, hf[1] + d[1] * 78 * k * t)
        wd = (4 + 7 * t) * k
        pygame.draw.line(surf, C((60, 56, 60)), (c0[0] + nx * wd, c0[1] + ny * wd), (c0[0] - nx * wd, c0[1] - ny * wd), max(2, int(3 * k)))
        pygame.draw.circle(surf, C((190, 190, 200)), P((c0[0] + nx * wd * 0.8, c0[1] + ny * wd * 0.8)), max(1, int(2 * k)))
        pygame.draw.circle(surf, C((190, 190, 200)), P((c0[0] - nx * wd * 0.8, c0[1] - ny * wd * 0.8)), max(1, int(2 * k)))


def draw_crown(surf, cx, cy, size, points, gem=(220, 40, 60), muted=False):
    """Golden crown with its base centred at (cx, cy)."""
    gold = (238, 196, 60)
    dark = (150, 105, 20)
    if muted:
        gold, dark, gem = (66, 68, 82), (38, 40, 52), (52, 54, 66)
    w = size
    pts = [(cx - w, cy), (cx - w, cy - w * 0.55)]
    n = max(3, points)
    for i in range(n):
        x0 = cx - w + (2.0 * w) * (i + 0.5) / n
        pts.append((cx - w + (2.0 * w) * i / n + w / n * 0.3, cy - w * 0.55))
        pts.append((x0, cy - w * 1.25))
    pts.append((cx + w, cy - w * 0.55))
    pts.append((cx + w, cy))
    pygame.draw.polygon(surf, dark, pts, max(2, int(size * 0.12)))
    pygame.draw.polygon(surf, gold, pts)
    pygame.draw.rect(surf, dark, (int(cx - w), int(cy - w * 0.22), int(2 * w), max(2, int(w * 0.22))))
    pygame.draw.rect(surf, (255, 232, 130), (int(cx - w), int(cy - w * 0.55), int(2 * w), max(2, int(w * 0.14))))
    for i in range(n):
        x0 = cx - w + (2.0 * w) * (i + 0.5) / n
        pygame.draw.circle(surf, gem if (i % 2 == 0 or muted) else (60, 160, 255), (int(x0), int(cy - w * 0.36)), max(2, int(w * 0.12)))
        pygame.draw.circle(surf, (255, 240, 170), (int(x0), int(cy - w * 1.25)), max(1, int(w * 0.09)))


# ---------------------------------------------------------------- the fighter
class Fighter:
    def __init__(self, x, look, speed=9, weapon=0, k=1.0):
        self.look = look
        self.k = k
        self.giant = k > 1.3
        self.speed = speed
        self.x, self.y = x, GROUND
        self.vy = 0
        self.hp = self.maxhp = 100
        self.weapon = weapon
        self.facing = 1
        self.atk = 0
        self.atk_total = 1
        self.cd = 0
        self.stun = 0
        self.kb = 0
        self.blocking = False
        self.moving = False
        self.walk = 0.0
        self.t = random.randint(0, 100)
        self.use_buf = False
        self.buf = 0
        self.prev_attack = False
        self.hit_done = True
        self.flash = 0
        self.alt = False
        self.dmg_mult = 1.0
        self.armor = 0.0
        self.ai = {"atk": 0.05, "blk": 0.2, "jump": 0.004}
        self.name = ""
        self.crowns = 0
        self.dead_img = None
        self.firing = 0
        self.sup = False
        self.redeyes = False
        self.aura = 0.0
        self.aura_col = (255, 200, 50)
        self.energy = 0.0
        self.regen = 0.0
        self.can_cast = False
        self.want_cast = False
        self.cast = 0
        self.pcol = (120, 200, 255)
        self.pdmg = 30

    @property
    def rect(self):
        k = self.k
        return pygame.Rect(int(self.x - 20 * k), int(self.y - 115 * k), int(40 * k), int(115 * k))

    def update(self, left, right, jump, attack, block, swap, opp):
        k = self.k
        self.t += 1
        self.facing = 1 if opp.x > self.x else -1
        self.moving = False
        if self.cd > 0:
            self.cd -= 1
        if self.firing > 0:
            self.firing -= 1
        if self.cast > 0:
            self.cast -= 1
        if self.can_cast and self.energy < 100:
            self.energy = min(100.0, self.energy + self.regen)
        if (self.can_cast and self.want_cast and self.energy >= 100 and self.cast == 0
                and self.stun == 0 and not self.blocking):
            self.energy = 0.0
            self.cast = 18
            BULLETS.append({"x": self.x + self.facing * 44 * k, "y": GROUND - 34, "vx": self.facing * 10,
                            "owner": self, "kind": "vortex", "col": self.pcol, "t": 0, "hit": False,
                            "dmg": int(round(self.pdmg * self.dmg_mult))})
            play("roar" if self.giant else "sword")
            spark(self.x + self.facing * 44 * k, self.y - 90 * k, 10, self.pcol, 6)
        if self.stun > 0:
            self.stun -= 1
            self.x += self.kb
            self.kb *= 0.8
            self.blocking = False
        else:
            self.blocking = bool(block)
            if self.blocking:
                self.atk = 0
            if not self.blocking:
                self.x += (right - left) * self.speed
                self.moving = (right - left) != 0
            if jump and self.y >= GROUND and not self.blocking and not self.giant:
                self.vy = -22
            if swap and self.atk == 0 and not self.giant:
                self.weapon = (self.weapon + 1) % PLAYER_WEAPONS
                play("click")
            if self.use_buf:
                if attack and not self.prev_attack:
                    self.buf = 12
                elif self.buf > 0:
                    self.buf -= 1
            want = attack or self.buf > 0
            if want and self.cd == 0 and self.atk == 0 and not self.blocking:
                self.buf = 0
                w = WEAPONS[self.weapon]
                self.atk = self.atk_total = w["dur"]
                self.cd = w["cd"]
                self.hit_done = False
                self.alt = not self.alt
                if self.weapon == 3:
                    play("roar" if random.random() < 0.5 else "sword")
                else:
                    play(("punch", "sword", "gun")[self.weapon])
                if self.weapon == 2:
                    self.firing = 4
                    BULLETS.append({"x": self.x + self.facing * 50 * k, "y": self.y - 94 * k,
                                    "vx": self.facing * 18, "owner": self})
        self.prev_attack = bool(attack)
        if self.flash > 0:
            self.flash -= 1
        if self.moving and self.y >= GROUND:
            self.walk += 0.45
        self.vy += 1.55
        self.y += self.vy
        if self.y >= GROUND:
            self.y, self.vy = GROUND, 0
        self.x = max(30, min(W - 30, self.x))
        if self.atk > 0:
            self.atk -= 1
            started = self.atk_total - self.atk
            w = WEAPONS[self.weapon]
            if (self.weapon != 2 and not self.hit_done and w["hit"] <= started <= w["hit"] + 3):
                reach = pygame.Rect(0, 0, int(w["reach"]), int(50 * k))
                reach.centery = int(self.y - 80 * k)
                if self.facing == 1:
                    reach.left = int(self.x + 12 * k)
                else:
                    reach.right = int(self.x - 12 * k)
                if reach.colliderect(opp.rect):
                    self.hit_done = True
                    opp.hit(self.facing, int(round(w["dmg"] * self.dmg_mult)))
                    self.energy = min(100.0, self.energy + 8)
                    if self.weapon == 3:
                        SHAKE[0] = 12
                        play("stomp")

    def hit(self, direction, dmg, ranged=False):
        k = self.k
        cx = self.x + direction * -10 * k
        cy = self.y - 80 * k
        if self.blocking:
            self.flash = 8
            self.x += direction * 5
            play("block")
            spark(self.x - direction * 28 * k, cy, 7, (170, 215, 255))
        else:
            self.hp -= max(1, int(round(dmg * (1.0 - self.armor))))
            self.energy = min(100.0, self.energy + 4)
            if self.giant:
                self.kb = direction * 1.5
                self.stun = 4
            else:
                self.kb = direction * (4 if ranged else 10)
                self.stun = 8 if ranged else 14
                self.atk = 0
            play("hit")
            spark(cx, cy, 9 if dmg < 20 else 16, (255, 190, 80))
            spark(cx, cy, 3, (255, 255, 255), 3)

    def draw(self, surf):
        k = self.k
        # ground shadow
        air = max(0.0, (GROUND - self.y) / 120.0)
        sw = int(46 * k * (1 - min(0.6, air)))
        if sw > 4:
            if SAFE_UI:
                pygame.draw.ellipse(surf, (20, 20, 24), (int(self.x - sw), int(GROUND - 5 * k + 2), sw * 2, int(9 * k)))
            else:
                sh = shadow_sprite(sw)
                surf.blit(sh, (int(self.x - sw), int(GROUND - 4 * k)))
        if self.hp <= 0:
            if self.dead_img is None:
                size = int(230 * k)
                tmp = pygame.Surface((size, size), pygame.SRCALPHA)
                self._body(tmp, size // 2, size - int(20 * k), False)
                self.dead_img = pygame.transform.rotate(tmp, 90 * self.facing)
            rect = self.dead_img.get_rect(center=(int(self.x - 24 * k * self.facing), int(GROUND - 22 * k)))
            surf.blit(self.dead_img, rect)
        else:
            if self.aura > 0:
                draw_aura(surf, self)
            self._body(surf, self.x, self.y, self.y < GROUND - 3)
            if self.blocking:
                self._shield(surf)
            if self.cast > 0:
                ox2 = int(self.x + self.facing * 46 * k)
                oy2 = int(self.y - 92 * k)
                rr = int((8 + (18 - self.cast) * 1.1) * k)
                pygame.draw.circle(surf, shade(self.pcol, 0.5), (ox2, oy2), rr + 6)
                pygame.draw.circle(surf, self.pcol, (ox2, oy2), rr + 2)
                pygame.draw.circle(surf, (255, 255, 255), (ox2, oy2), max(2, rr - 3))
            elif self.can_cast and self.energy >= 100 and self.k < 1.3:
                for i in range(3):
                    ax = int(self.x + random.randint(-16, 16))
                    pygame.draw.line(surf, (255, 240, 120) if i else self.pcol, (ax, int(self.y - 10)),
                                     (ax + random.randint(-4, 4), int(self.y - random.randint(60, 135))), 3)
            if False:
                pygame.draw.circle(surf, self.pcol, (int(self.x), int(self.y - 124 * k)), 4)

    def _shield(self, surf):
        k = self.k
        pulse = math.sin(pygame.time.get_ticks() / 110.0) * 3
        r = int((70 + pulse + (4 if self.flash > 0 else 0)) * k)
        c = (int(self.x), int(self.y - 58 * k))
        if not SAFE_UI:
            bub = pygame.Surface((2 * r + 4, 2 * r + 4), pygame.SRCALPHA)
            a = 95 if self.flash > 0 else 50
            pygame.draw.circle(bub, (120, 190, 255, a), (r + 2, r + 2), r)
            surf.blit(bub, (c[0] - r - 2, c[1] - r - 2))
        ring = (255, 255, 255) if self.flash > 0 else (130, 200, 255)
        pygame.draw.circle(surf, ring, c, r, 4)
        pygame.draw.circle(surf, (210, 235, 255), c, r - 8, 2)

    # ------------------------------------------------------------ the drawing
    def _body(self, surf, x, y, air):
        k = self.k
        f = self.facing
        L = self.look
        dead = self.hp <= 0
        flash = self.stun > 0 and not dead
        if flash:
            def C(c):
                return lerp(c, (255, 228, 228), 0.55)
        else:
            def C(c):
                return c
        ED = EDGE
        skin = C(L["skin"])
        skin_d = shade(skin, 0.78)
        shirt = C(L["shirt"])
        pants = C(L["pants"])
        t = self.t
        wid = self.weapon
        p = 1 - self.atk / float(self.atk_total) if self.atk > 0 else 0.0
        ease = math.sin(math.pi * min(1.0, p))
        moving = self.moving and not air

        # ---- body pose
        lean, drop = 2.0, 3.0
        if self.blocking:
            lean, drop = 1.0, 10.0
        elif self.stun > 0:
            lean, drop = -8.0, 2.0
        elif self.atk > 0:
            lean = 2.0 + (10 * ease if wid == 0 else (7 * ease if wid == 1 else (2 * ease if wid == 2 else 12 * ease)))
            if wid == 3 and p < 0.5:
                lean = 2.0 - 8 * (p / 0.5)
        if moving:
            bob = -abs(math.cos(self.walk)) * 2.2
            lean += 3
        elif air:
            bob = 0
        else:
            bob = math.sin(t * 0.09) * 1.3
        hip = (x, y - (56 - drop) * k + bob * k)
        sh = (x + f * lean * k, y - (100 - drop) * k + bob * k)
        hc = (sh[0] + f * 3 * k, sh[1] - 17 * k)
        if self.stun > 0:
            hc = (hc[0] - f * 4 * k, hc[1] + 1 * k)

        # ---- feet
        if air:
            fF = (x + f * 15 * k, y - 24 * k)
            fB = (x - f * 9 * k, y - 12 * k)
        elif moving:
            swing = math.sin(self.walk) * 20 * k
            fF = (x + f * 10 * k + swing, y - 5 * k - max(0.0, math.cos(self.walk)) * 9 * k)
            fB = (x - f * 10 * k - swing, y - 5 * k - max(0.0, -math.cos(self.walk)) * 9 * k)
        else:
            fF = (x + f * 17 * k, y - 5 * k)
            fB = (x - f * 14 * k, y - 5 * k)
            if self.blocking:
                fF = (x + f * 20 * k, y - 5 * k)
                fB = (x - f * 16 * k, y - 5 * k)

        # ---- hands
        theta = math.radians(-65)
        sw1 = (sh[0] + f * 2 * k, sh[1] + 2 * k)       # front shoulder
        sw2 = (sh[0] - f * 3 * k, sh[1] + 2 * k)       # back shoulder
        FH = (sw1[0] + f * 20 * k, sw1[1] + 6 * k)
        BH = (sw2[0] + f * 15 * k, sw2[1] + 12 * k)
        if wid == 1:
            FH = (sw1[0] + f * 20 * k, sw1[1] + 16 * k)
        if wid == 2:
            FH = (sw1[0] + f * 31 * k, sw1[1] + 4 * k)
            BH = (sw2[0] + f * 24 * k, sw2[1] + 8 * k)
        if wid == 3:
            FH = (sw1[0] + f * 14 * k, sw1[1] + 12 * k)
            BH = (sw2[0] + f * 12 * k, sw2[1] + 16 * k)
            theta = math.radians(-35)
        if self.blocking:
            FH = (sw1[0] + f * 17 * k, sw1[1] - 12 * k)
            BH = (sw2[0] + f * 12 * k, sw2[1] - 8 * k)
            theta = math.radians(-90)
        elif self.stun > 0:
            FH = (sw1[0] + f * 3 * k, sw1[1] + 22 * k)
            BH = (sw2[0] - f * 8 * k, sw2[1] + 18 * k)
        elif self.atk > 0:
            if wid == 0:
                reach = (22 + 42 * ease) * k
                if self.alt:
                    FH = (sw1[0] + f * reach, sw1[1] + 4 * k)
                else:
                    BH = (sw2[0] + f * reach, sw2[1] + 5 * k)
            elif wid == 1:
                theta = math.radians(-125 + 175 * p)
                FH = (sw1[0] + f * 20 * k, sw1[1] + (12 + 6 * p) * k)
            elif wid == 2:
                FH = (sw1[0] + f * (31 - 7 * (1 - p)) * k, sw1[1] + 4 * k)
            else:
                if p < 0.53:
                    theta = math.radians(-135 - 25 * (p / 0.53))
                    FH = (sw1[0] + f * 8 * k, sw1[1] - (6 + 20 * (p / 0.53)) * k)
                    BH = (sw2[0] + f * 4 * k, sw2[1] - (2 + 18 * (p / 0.53)) * k)
                elif p < 0.78:
                    q = (p - 0.53) / 0.25
                    theta = math.radians(-160 + 190 * q)
                    FH = (sw1[0] + f * (8 + 12 * q) * k, sw1[1] - (26 - 36 * q) * k)
                    BH = (sw2[0] + f * (4 + 12 * q) * k, sw2[1] - (20 - 32 * q) * k)
                else:
                    theta = math.radians(30)
                    FH = (sw1[0] + f * 22 * k, sw1[1] + 10 * k)
                    BH = (sw2[0] + f * 18 * k, sw2[1] + 14 * k)

        # ---- cape / long hair (behind everything)
        if L["cape"]:
            capec = C(L["cape"])
            fl = math.sin(t * 0.1) * 3 + (6 if moving else 0)
            pts = [(sh[0] - f * 4 * k, sh[1] - 2 * k), (sh[0] + f * 3 * k, sh[1] - 2 * k),
                   (hip[0] - f * (20 + fl) * k, hip[1] + 34 * k), (hip[0] - f * (6 + fl) * k, hip[1] + 40 * k)]
            poly(surf, pts, capec, ED)
        if L["hstyle"] == "long" and not L["helmet"] and not L["turban"]:
            hairc = C(L["hair"])
            pts = [(hc[0] - f * 3 * k, hc[1] - 9 * k), (hc[0] - f * 14 * k, hc[1] + 6 * k),
                   (sh[0] - f * 15 * k, sh[1] + 20 * k), (sh[0] - f * 5 * k, sh[1] + 10 * k)]
            poly(surf, pts, hairc, ED)

        # ---- back arm and back leg
        hf_pref = (-f * 0.3, 1.0)
        kB, aB = ik((hip[0] - f * 2 * k, hip[1]), fB, 30 * k, 30 * k, (f, 0))
        seg(surf, (hip[0] - f * 2 * k, hip[1]), kB, 15 * k, 12 * k, shade(pants, 0.82), ED)
        seg(surf, kB, aB, 12 * k, 9.5 * k, shade(pants, 0.82), ED)
        self._boot(surf, aB, f, k, C, shade(C(L["boots"]), 0.8))
        eB, hB = ik(sw2, BH, 22 * k, 22 * k, hf_pref)
        long_sl = L["sleeves"] == "long"
        up_c = shirt if L["sleeves"] != "none" and not L["bare"] else skin
        fo_c = shirt if long_sl and not L["bare"] else skin
        seg(surf, sw2, eB, 11.5 * k, 9.5 * k, shade(up_c, 0.82), ED)
        seg(surf, eB, hB, 9.5 * k, 7.5 * k, shade(fo_c, 0.82), ED)
        gcol = C(L["glove"]) if L["glove"] else skin
        pygame.draw.circle(surf, ED, P(hB), max(2, int(6.4 * k)))
        pygame.draw.circle(surf, shade(gcol, 0.85), P(hB), max(2, int(5 * k)))

        # ---- torso
        mid = ((sh[0] + hip[0]) / 2.0, (sh[1] + hip[1]) / 2.0)
        bare = L["bare"]
        tc = skin if bare else shirt
        pts = [(sh[0] - 12 * k, sh[1] + 1 * k), (sh[0] + 12 * k, sh[1] + 1 * k),
               (sh[0] + 13.5 * k, sh[1] + 11 * k), (mid[0] + 10 * k, mid[1] + 3 * k),
               (hip[0] + 10.5 * k, hip[1] + 2 * k), (hip[0] - 10.5 * k, hip[1] + 2 * k),
               (mid[0] - 10 * k, mid[1] + 3 * k), (sh[0] - 13.5 * k, sh[1] + 11 * k)]
        poly(surf, pts, tc, ED)
        # shading on the torso
        pygame.draw.line(surf, shade(tc, 1.22), (sh[0] - 8 * k, sh[1] + 4 * k), (mid[0] - 7 * k, mid[1] + 2 * k), max(1, int(3 * k)))
        pygame.draw.line(surf, shade(tc, 0.72), (sh[0] + 9 * k, sh[1] + 5 * k), (mid[0] + 7.5 * k, mid[1] + 2 * k), max(1, int(3 * k)))
        if bare:
            ln = shade(skin, 0.7)
            pygame.draw.line(surf, ln, (sh[0] - 8 * k, sh[1] + 11 * k), (sh[0] + 8 * k, sh[1] + 11 * k), max(1, int(2 * k)))
            pygame.draw.line(surf, ln, (sh[0], sh[1] + 4 * k), (sh[0], mid[1] + 6 * k), max(1, int(1.5 * k)))
            for i in range(3):
                yy = mid[1] + (1 + i * 5) * k
                pygame.draw.line(surf, ln, (hip[0] - 5 * k, yy), (hip[0] + 5 * k, yy), max(1, int(1.2 * k)))
        else:
            tr = C(L["trim"])
            pygame.draw.line(surf, tr, (sh[0] - 5 * k, sh[1] + 1 * k), (sh[0], sh[1] + 11 * k), max(1, int(2.5 * k)))
            pygame.draw.line(surf, tr, (sh[0] + 5 * k, sh[1] + 1 * k), (sh[0], sh[1] + 11 * k), max(1, int(2.5 * k)))
        if L["glow"]:
            gc = C(L["glow"])
            for dx, dy, ex, ey in ((-5, 8, -1, 14), (4, 6, 8, 12), (-2, 18, 3, 24), (6, 20, 4, 28)):
                pygame.draw.line(surf, gc, (sh[0] + dx * k, sh[1] + dy * k), (sh[0] + ex * k, sh[1] + ey * k), max(1, int(2 * k)))
        if L["armor"]:
            ac = C(L["armor"])
            plate = [(sh[0] - 10 * k, sh[1] + 3 * k), (sh[0] + 10 * k, sh[1] + 3 * k),
                     (sh[0] + 8 * k, mid[1] + 2 * k), (sh[0] - 8 * k, mid[1] + 2 * k)]
            poly(surf, plate, ac, ED)
            pygame.draw.line(surf, shade(ac, 1.25), (sh[0] - 6 * k, sh[1] + 5 * k), (sh[0] - 5 * k, mid[1]), max(1, int(2 * k)))
            pygame.draw.line(surf, C(L["trim"]), (sh[0], sh[1] + 4 * k), (sh[0], mid[1] + 1 * k), max(1, int(1.5 * k)))
        if L["necklace"]:
            nc = C(L["necklace"])
            for i in range(5):
                a = 0.4 + i * 0.58
                pygame.draw.circle(surf, nc, P((sh[0] + math.cos(a) * 8 * k - 0 * k, sh[1] + 2 * k + math.sin(a) * 7 * k)), max(1, int(2.2 * k)))
        # belt and hips
        bel = C(L["belt"])
        hipblk = [(hip[0] - 10.5 * k, hip[1] - 1 * k), (hip[0] + 10.5 * k, hip[1] - 1 * k),
                  (hip[0] + 10 * k, hip[1] + 9 * k), (hip[0] - 10 * k, hip[1] + 9 * k)]
        poly(surf, hipblk, pants, ED)
        pygame.draw.rect(surf, ED, (int(hip[0] - 11 * k), int(hip[1] - 4 * k), int(22 * k), max(3, int(6 * k))))
        pygame.draw.rect(surf, bel, (int(hip[0] - 10 * k), int(hip[1] - 3 * k), int(20 * k), max(2, int(4 * k))))
        pygame.draw.rect(surf, C((235, 200, 90)), (int(hip[0] + f * 2 * k - 2 * k), int(hip[1] - 4 * k), int(4 * k), max(3, int(5 * k))))
        if L["fur"]:
            fc = C(L["fur"])
            for i in range(-3, 4):
                bx = sh[0] + i * 3.6 * k
                pygame.draw.polygon(surf, fc, [(bx - 2.4 * k, sh[1] - 2 * k), (bx + 2.4 * k, sh[1] - 2 * k), (bx, sh[1] + 6 * k)])

        # ---- front leg
        kF, aF = ik((hip[0] + f * 2 * k, hip[1]), fF, 30 * k, 30 * k, (f, 0))
        seg(surf, (hip[0] + f * 2 * k, hip[1]), kF, 15.5 * k, 12.5 * k, pants, ED)
        seg(surf, kF, aF, 12.5 * k, 10 * k, pants, ED)
        if L["armor"]:
            pygame.draw.circle(surf, ED, P(kF), max(2, int(7.5 * k)))
            pygame.draw.circle(surf, C(L["armor"]), P(kF), max(2, int(6 * k)))
        self._boot(surf, aF, f, k, C, C(L["boots"]))

        # ---- head
        self._head(surf, hc, sh, f, k, C, skin)

        # ---- front arm
        eF, hF = ik(sw1, FH, 22 * k, 22 * k, hf_pref)
        seg(surf, sw1, eF, 12 * k, 10 * k, up_c, ED)
        seg(surf, eF, hF, 10 * k, 8 * k, fo_c, ED)
        if L["armor"] or L["spikes"]:
            col = C(L["armor"]) if L["armor"] else C(L["spikes"])
            pygame.draw.circle(surf, ED, P(sw1), max(2, int(8.5 * k)))
            pygame.draw.circle(surf, col, P(sw1), max(2, int(7 * k)))
            pygame.draw.circle(surf, shade(col, 1.3), (int(sw1[0] - 2 * k), int(sw1[1] - 2 * k)), max(1, int(2.5 * k)))
            if L["spikes"] and not L["armor"]:
                for ang in (-1.9, -1.3, -0.7):
                    pygame.draw.polygon(surf, C(L["spikes"]), [(sw1[0] + math.cos(ang - 0.25) * 6 * k, sw1[1] + math.sin(ang - 0.25) * 6 * k),
                                                              (sw1[0] + math.cos(ang) * 14 * k, sw1[1] + math.sin(ang) * 14 * k),
                                                              (sw1[0] + math.cos(ang + 0.25) * 6 * k, sw1[1] + math.sin(ang + 0.25) * 6 * k)])
        if L["glove"]:
            pygame.draw.line(surf, C(L["glove"]), P(eF if False else (hF[0] + (eF[0] - hF[0]) * 0.28, hF[1] + (eF[1] - hF[1]) * 0.28)), P(hF), max(2, int(9 * k)))
        pygame.draw.circle(surf, ED, P(hF), max(2, int(6.4 * k)))
        pygame.draw.circle(surf, gcol, P(hF), max(2, int(5 * k)))
        if wid in (0, 1, 2, 3) and L["glove"] is None and wid == 0:
            pygame.draw.line(surf, shade(skin, 0.7), (hF[0] - 2 * k, hF[1] - 1 * k), (hF[0] + 2 * k, hF[1] - 1 * k), 1)

        # ---- weapon
        if wid == 1:
            d = (f * math.cos(theta), math.sin(theta))
            if self.atk > 0 and 0.25 < p < 0.92:
                for off, col in ((22, (235, 242, 255)), (40, (170, 190, 225)), (58, (110, 130, 180))):
                    t2 = theta - math.radians(off)
                    d2 = (f * math.cos(t2), math.sin(t2))
                    pygame.draw.line(surf, col, P(hF), P((hF[0] + d2[0] * 64 * k, hF[1] + d2[1] * 64 * k)), max(2, int(3 * k)))
            draw_sword(surf, hF, d, k, C)
        elif wid == 2:
            draw_gun(surf, hF, f, k, C, self.firing > 0)
        elif wid == 3:
            d = (f * math.cos(theta), math.sin(theta))
            if self.atk > 0 and 0.6 < p < 0.9:
                for off, col in ((18, (255, 235, 200)), (36, (220, 170, 120))):
                    t2 = theta - math.radians(off)
                    d2 = (f * math.cos(t2), math.sin(t2))
                    pygame.draw.line(surf, col, P(hF), P((hF[0] + d2[0] * 88 * k, hF[1] + d2[1] * 88 * k)), max(3, int(4 * k)))
            draw_club(surf, hF, d, k, C)
        # off-hand grips the club
        if wid == 3:
            pygame.draw.circle(surf, ED, P(hB), max(2, int(6.4 * k)))
            pygame.draw.circle(surf, gcol, P(hB), max(2, int(5 * k)))

    def _boot(self, surf, a, f, k, C, col):
        ax, ay = a
        pts = [(ax - f * 6 * k, ay - 6 * k), (ax + f * 4.5 * k, ay - 6 * k), (ax + f * 7 * k, ay - 1 * k),
               (ax + f * 15 * k, ay + 1 * k), (ax + f * 15.5 * k, ay + 5.5 * k), (ax - f * 7 * k, ay + 5.5 * k)]
        poly(surf, pts, col, EDGE)
        pygame.draw.line(surf, shade(col, 0.55), (ax - f * 7 * k, ay + 4.2 * k), (ax + f * 15 * k, ay + 4.2 * k), max(1, int(2 * k)))
        pygame.draw.line(surf, shade(col, 1.3), (ax - f * 4 * k, ay - 4 * k), (ax + f * 3 * k, ay - 4 * k), max(1, int(1.5 * k)))

    def _head(self, surf, hc, sh, f, k, C, skin):
        L = self.look
        ED = EDGE
        hair = C(L["hair"])
        # neck
        seg(surf, (sh[0] + f * 1 * k, sh[1] + 1 * k), (hc[0] - f * 1 * k, hc[1] + 7 * k), 8.5 * k, 8 * k, shade(skin, 0.9), ED, hi=False)
        hx, hy = hc
        # base head
        blob(surf, (hx, hy), 10.5 * k, 12 * k, skin, ED)
        pygame.draw.circle(surf, shade(skin, 0.86), (int(hx - f * 6.5 * k), int(hy + 1 * k)), max(1, int(2.6 * k)))   # ear
        # hair
        helmet = L["helmet"]
        turban = L["turban"]
        st = L["hstyle"]
        if not helmet and not turban and st != "bald":
            cap = []
            for a in range(180, 361, 20):
                ra = math.radians(a)
                cap.append((hx + math.cos(ra) * 11.4 * k, hy - 0.5 * k + math.sin(ra) * 13 * k))
            cap.append((hx + f * 10.8 * k, hy - 5 * k))
            cap.append((hx + f * 4 * k, hy - 8 * k))
            cap.append((hx - f * 8 * k, hy - 3 * k))
            if f < 0:
                pass
            pygame.draw.polygon(surf, hair, cap)
            pygame.draw.polygon(surf, ED, cap, 2)
            if st == "spiky":
                for i in range(5):
                    bx = hx - 9 * k + i * 4.6 * k
                    pygame.draw.polygon(surf, hair, [(bx - 3 * k, hy - 11 * k), (bx + (i - 2) * 1.5 * k, hy - 21 * k), (bx + 3.4 * k, hy - 11 * k)])
            elif st == "mohawk":
                pygame.draw.polygon(surf, hair, [(hx - 8 * k, hy - 8 * k), (hx - 5 * k, hy - 20 * k), (hx + 1 * k, hy - 24 * k),
                                                (hx + 7 * k, hy - 19 * k), (hx + 9 * k, hy - 8 * k)])
            elif st == "ponytail":
                sw = math.sin(self.t * 0.12) * 3
                seg(surf, (hx - f * 9 * k, hy - 5 * k), (hx - f * (19 + sw) * k, hy + 9 * k), 6 * k, 2.5 * k, hair, ED, hi=False)
        if turban:
            tc = C(turban)
            blob(surf, (hx, hy - 7 * k), 13 * k, 8.5 * k, tc, ED)
            pygame.draw.line(surf, shade(tc, 0.7), (hx - 10 * k, hy - 6 * k), (hx + 9 * k, hy - 10 * k), max(1, int(1.6 * k)))
            pygame.draw.line(surf, shade(tc, 0.7), (hx - 9 * k, hy - 10 * k), (hx + 10 * k, hy - 5 * k), max(1, int(1.6 * k)))
            seg(surf, (hx - f * 9 * k, hy - 4 * k), (hx - f * (17 + math.sin(self.t * 0.1) * 2) * k, hy + 7 * k), 5 * k, 3 * k, tc, ED, hi=False)
        if helmet:
            hc_ = C(helmet)
            dome = []
            for a in range(180, 361, 15):
                ra = math.radians(a)
                dome.append((hx + math.cos(ra) * 12.8 * k, hy - 1 * k + math.sin(ra) * 14 * k))
            dome.append((hx + f * 12 * k, hy - 2 * k))
            dome.append((hx - f * 12 * k, hy - 2 * k))
            poly(surf, dome, hc_, ED)
            pygame.draw.line(surf, shade(hc_, 1.35), (hx - 7 * k, hy - 11 * k), (hx - 1 * k, hy - 13 * k), max(1, int(2 * k)))
            pygame.draw.rect(surf, shade(hc_, 0.8), (int(hx + f * 8 * k - 1.5 * k), int(hy - 3 * k), max(2, int(3 * k)), int(10 * k)))
            if L["horns"]:
                for sgn in (-1, 1):
                    bx = hx + sgn * 10 * k
                    pygame.draw.polygon(surf, C((240, 235, 220)), [(bx - sgn * 3 * k, hy - 6 * k), (bx + sgn * 12 * k, hy - 16 * k), (bx + sgn * 6 * k, hy - 22 * k), (bx + sgn * 1 * k, hy - 8 * k)])
                    pygame.draw.polygon(surf, ED, [(bx - sgn * 3 * k, hy - 6 * k), (bx + sgn * 12 * k, hy - 16 * k), (bx + sgn * 6 * k, hy - 22 * k), (bx + sgn * 1 * k, hy - 8 * k)], 2)
        elif L["horns"]:
            for sgn in (-1, 1):
                bx = hx + sgn * 9 * k
                pygame.draw.polygon(surf, C((235, 220, 190)), [(bx - sgn * 2 * k, hy - 8 * k), (bx + sgn * 10 * k, hy - 14 * k), (bx + sgn * 5 * k, hy - 22 * k), (bx + sgn * 1 * k, hy - 10 * k)])
        # headband
        if L["headband"] and not helmet and not turban:
            hbc = C(L["headband"])
            pygame.draw.line(surf, ED, (hx - 11 * k, hy - 5 * k), (hx + 11 * k, hy - 6 * k), max(3, int(5.5 * k)))
            pygame.draw.line(surf, hbc, (hx - 11 * k, hy - 5 * k), (hx + 11 * k, hy - 6 * k), max(2, int(3.5 * k)))
            fl = math.sin(self.t * 0.15) * 3 + (4 if self.moving else 0)
            pygame.draw.line(surf, hbc, (hx - f * 10 * k, hy - 5 * k), (hx - f * (22 + fl) * k, hy + (1 + fl * 0.4) * k), max(2, int(3 * k)))
            pygame.draw.line(surf, hbc, (hx - f * 10 * k, hy - 4 * k), (hx - f * (20 + fl) * k, hy + (6 + fl * 0.5) * k), max(2, int(3 * k)))
        # face
        ex = hx + f * 5.2 * k
        ey = hy - 1.2 * k
        hurt = self.stun > 0
        if hurt:
            pygame.draw.line(surf, ED, (ex - 2 * k, ey - 2 * k), (ex + 2 * k, ey + 2 * k), max(1, int(1.5 * k)))
            pygame.draw.line(surf, ED, (ex - 2 * k, ey + 2 * k), (ex + 2 * k, ey - 2 * k), max(1, int(1.5 * k)))
        else:
            pygame.draw.ellipse(surf, (250, 250, 250), (int(ex - 2.6 * k), int(ey - 2 * k), max(2, int(5.2 * k)), max(2, int(4 * k))))
            pygame.draw.circle(surf, (20, 18, 24), (int(ex + f * 1 * k), int(ey)), max(1, int(1.5 * k)))
            if self.redeyes:
                pygame.draw.circle(surf, (120, 0, 0), (int(ex + f * 1 * k), int(ey)), max(3, int(4.2 * k)))
                pygame.draw.circle(surf, (255, 30, 20), (int(ex + f * 1 * k), int(ey)), max(2, int(2.8 * k)))
                pygame.draw.circle(surf, (255, 200, 180), (int(ex + f * 1 * k), int(ey)), max(1, int(1 * k)))
        pygame.draw.line(surf, shade(L["hair"], 0.8) if L["hstyle"] != "bald" else shade(skin, 0.5),
                         (ex - 3.8 * k, ey - 4 * k - (1.5 * k if self.atk > 0 else 0)), (ex + 3.8 * k, ey - 5 * k + (1.5 * k if self.atk > 0 else 0)), max(1, int(1.8 * k)))
        pygame.draw.polygon(surf, shade(skin, 0.82), [(hx + f * 9.5 * k, hy + 1 * k), (hx + f * 13 * k, hy + 4.5 * k), (hx + f * 9 * k, hy + 5 * k)])
        my = hy + 8 * k
        if hurt or self.atk > 0:
            pygame.draw.circle(surf, (90, 30, 40), (int(hx + f * 5.5 * k), int(my)), max(1, int(2.2 * k)))
        else:
            pygame.draw.line(surf, shade(skin, 0.5), (hx + f * 3 * k, my), (hx + f * 8 * k, my - 0.5 * k), max(1, int(1.4 * k)))
        if L["paint"]:
            pc = C(L["paint"])
            pygame.draw.line(surf, pc, (hx + f * 1 * k, hy - 5 * k), (hx + f * 9 * k, hy + 3 * k), max(2, int(2.6 * k)))
            pygame.draw.line(surf, pc, (hx + f * 1 * k, hy + 1 * k), (hx + f * 8 * k, hy + 8 * k), max(2, int(2.2 * k)))
        if L["scar"]:
            pygame.draw.line(surf, (160, 70, 70), (ex - 3 * k, ey - 7 * k), (ex + 2 * k, ey + 6 * k), max(1, int(1.5 * k)))
        if L["beard"] and not L["mask"]:
            bc = C(L["beard"])
            pts = [(hx - f * 5 * k, hy + 3 * k), (hx + f * 10 * k, hy + 3 * k), (hx + f * 9 * k, hy + 12 * k), (hx + f * 2 * k, hy + 19 * k), (hx - f * 4 * k, hy + 12 * k)]
            pygame.draw.polygon(surf, bc, pts)
            pygame.draw.polygon(surf, ED, pts, 2)
            pygame.draw.line(surf, shade(bc, 0.6), (hx + f * 3 * k, hy + 8 * k), (hx + f * 8 * k, hy + 7.5 * k), max(1, int(1.4 * k)))
        if L["mask"]:
            mc = C(L["mask"])
            pts = [(hx - f * 11 * k, hy - 1 * k), (hx + f * 11 * k, hy - 1 * k), (hx + f * 10 * k, hy + 6 * k), (hx + f * 3 * k, hy + 13 * k), (hx - f * 9 * k, hy + 8 * k)]
            pygame.draw.polygon(surf, mc, pts)
            pygame.draw.polygon(surf, ED, pts, 2)
        if self.crowns > 0:
            draw_crown(surf, hx, hy - 9 * k, 9 * k, min(5, 2 + self.crowns))


_SHADOWS = {}


def shadow_sprite(sw):
    s = _SHADOWS.get(sw)
    if s is None:
        s = pygame.Surface((sw * 2, 12), pygame.SRCALPHA)
        pygame.draw.ellipse(s, (0, 0, 0, 70), (0, 0, sw * 2, 12))
        pygame.draw.ellipse(s, (0, 0, 0, 55), (sw // 3, 2, sw * 2 - 2 * (sw // 3), 8))
        _SHADOWS[sw] = s
    return s


# ---------------------------------------------------------------- powers + dragon
def draw_vortex(surf, x, y, col, t, r=20):
    x, y = int(x), int(y)
    pygame.draw.circle(surf, shade(col, 0.45), (x, y), r + 5)
    pygame.draw.circle(surf, shade(col, 0.8), (x, y), r)
    for arm in range(3):
        base = t * 0.35 + arm * 2.094
        prev = None
        for i in range(9):
            a = base + i * 0.55
            rad = 3 + i * (r - 3) / 8.0
            pt = (x + math.cos(a) * rad, y + math.sin(a) * rad * 0.9)
            if prev:
                pygame.draw.line(surf, (255, 255, 255) if i > 4 else col, prev, pt, 3 if i > 3 else 2)
            prev = pt
    pygame.draw.circle(surf, (255, 255, 255), (x, y), 4)


def update_bullets(p, e):
    for b in BULLETS[:]:
        b["x"] += b["vx"]
        b["y"] += b.get("vy", 0)
        kind = b.get("kind")
        if b.get("g"):
            b["vy"] = b.get("vy", 0) + b["g"]
        b["t"] = b.get("t", 0) + 1
        target = e if b["owner"] is p else p
        gone = False
        if kind in ("vortex", "fire") and b["t"] % 2 == 0:
            spark(b["x"], b["y"], 1, b.get("col", (255, 160, 40)), 2)
        if kind == "fire" and b["y"] >= GROUND - 12:
            spark(b["x"], GROUND - 10, 14, (255, 150, 40), 7)
            SHAKE[0] = 8
            play("stomp")
            if abs(b["x"] - target.x) < 55 and target.y >= GROUND - 45:
                target.hit(1 if b["vx"] > 0 else -1, b["dmg"], True)
            gone = True
        elif target.rect.collidepoint(int(b["x"]), int(b["y"])) or (
                kind == "vortex" and target.rect.inflate(30, 30).collidepoint(int(b["x"]), int(b["y"]))):
            d = 1 if b["vx"] > 0 else -1
            if kind in ("vortex", "fire"):
                target.hit(d, b["dmg"], True)
                spark(b["x"], b["y"], 14, b.get("col", (255, 160, 40)), 7)
            else:
                target.hit(d, int(round(WEAPONS[2]["dmg"] * b["owner"].dmg_mult)), True)
            gone = True
        elif b["x"] < -40 or b["x"] > W + 40 or b["y"] > H:
            gone = True
        if gone and b in BULLETS:
            BULLETS.remove(b)


def draw_bullets(surf):
    for b in BULLETS:
        kind = b.get("kind")
        if kind == "vortex":
            for i in range(1, 6):
                pygame.draw.circle(surf, shade(b["col"], 0.9 - i * 0.12), (int(b["x"] - b["vx"] * i * 1.6), int(b["y"])), max(4, 24 - i * 4))
            draw_vortex(surf, b["x"], b["y"], b["col"], b["t"], 26)
        elif kind == "fire":
            x, y = int(b["x"]), int(b["y"])
            for i, (c, r) in enumerate(((  (170, 40, 20), 19), ((240, 110, 30), 14), ((255, 210, 80), 9), ((255, 250, 210), 4))):
                pygame.draw.circle(surf, c, (x + random.randint(-1, 1), y + random.randint(-1, 1)), r)
            pygame.draw.circle(surf, (255, 140, 40), (x - int(b["vx"] * 2), y - 3), 10)
        else:
            pygame.draw.rect(surf, (255, 230, 120), (int(b["x"]) - 9, int(b["y"]) - 2, 18, 4))
            pygame.draw.rect(surf, (255, 255, 220), (int(b["x"]) - 3, int(b["y"]) - 1, 6, 2))


class Dragon:
    """Final boss: a huge fire-breathing dragon."""
    SC = 0.82

    def __init__(self, x):
        self.k = 2.4
        self.giant = True
        self.dragon = True
        self.x, self.y = x, GROUND
        self.hp = self.maxhp = 1000
        self.weapon = 3
        self.facing = -1
        self.atk = self.atk_total = 0
        self.cd = 0
        self.stun = 0
        self.blocking = False
        self.t = 0
        self.flash = 0
        self.dmg_mult = 1.6
        self.armor = 0.0
        self.ai = {}
        self.name = "Ignis the Dragon"
        self.crowns = 0
        self.energy = 0.0
        self.can_cast = False
        self.want_cast = False
        self.cast = 0
        self.state = "idle"
        self.st = 60
        self.mouth = 0.0
        self.flame = 0.0
        self.dead_t = 0
        self.nxt = 0
        self.roar = 40
        self.base = (150, 32, 30)

    @property
    def rect(self):
        sc = self.SC
        a = self.x + self.facing * 118 * sc
        b = self.x - self.facing * 40 * sc
        l = int(min(a, b))
        return pygame.Rect(l, int(GROUND - 250 * sc), int(abs(a - b)), int(250 * sc))

    def pt(self, px, py):
        return (self.x + self.facing * px * self.SC, GROUND - py * self.SC)

    def mouth_pos(self):
        return self.pt(150, 232)

    def hit(self, direction, dmg, ranged=False):
        if self.hp <= 0:
            return
        self.hp -= max(1, int(dmg))
        self.flash = 5
        play("hit")
        cx, cy = self.pt(95, 130)
        spark(cx, cy, 8, (255, 190, 80))
        spark(cx, cy, 3, (255, 255, 255), 3)

    def update(self, *args):
        opp = args[-1]
        self.t += 1
        if self.hp <= 0:
            return
        if self.flash > 0:
            self.flash -= 1
        self.facing = 1 if opp.x > self.x else -1
        rage = 1.0 if self.hp > self.maxhp * 0.5 else 1.35
        if self.roar > 0:
            self.roar -= 1
            if self.roar == 38:
                play("roar")
            SHAKE[0] = max(SHAKE[0], 2)
            return
        self.st -= rage
        dist = abs(opp.x - self.x)
        mx, my = self.mouth_pos()
        if self.state == "idle":
            self.mouth = max(0.0, self.mouth - 0.08)
            self.flame = 0.0
            if self.st <= 0:
                self.nxt += 1
                if dist < 230 and self.nxt % 3 != 0:
                    self.state, self.st = "claw", 30
                elif self.nxt % 3 == 0:
                    self.state, self.st = "ball", 26
                else:
                    self.state, self.st = "wind", 28
        elif self.state == "wind":
            self.mouth = min(1.0, self.mouth + 0.06)
            if int(self.st) % 4 == 0:
                spark(mx, my, 1, (255, 120, 40), 3)
            if self.st <= 0:
                self.state, self.st = "breath", 80
                play("roar")
        elif self.state == "breath":
            self.mouth = 1.0
            ph = (80 - self.st) / 80.0
            self.flame = 150 + 230 * (0.5 - 0.5 * math.cos(ph * math.pi * 2))
            if int(self.st) % 3 == 0:
                if int(self.st) % 12 == 0:
                    play("hit")
                ex, ey = self.pt(150 + self.flame, 0)
                steps = 9
                for i in range(1, steps + 1):
                    fx = mx + (ex - mx) * i / steps
                    fy = my + (GROUND - my) * i / steps
                    r = 14 + 5 * i * 0.6
                    if opp.rect.inflate(int(r), int(r)).collidepoint(int(fx), int(fy)):
                        opp.hit(self.facing, int(round(3.2 * self.dmg_mult)), True)
                        break
            if self.st <= 0:
                self.state, self.st = "idle", 55
        elif self.state == "ball":
            self.mouth = min(1.0, self.mouth + 0.08)
            if self.st <= 0:
                T = max(10.0, abs(opp.x - mx) / 9.0)
                g = 0.14
                vy = (GROUND - 60 - my - 0.5 * g * T * T) / T
                BULLETS.append({"x": mx, "y": my, "vx": self.facing * 9, "vy": vy, "g": g, "owner": self,
                                "kind": "fire", "t": 0, "dmg": int(round(10 * self.dmg_mult)), "col": (255, 150, 40)})
                play("gun")
                self.state, self.st = "idle", 45
        elif self.state == "claw":
            self.mouth = min(0.7, self.mouth + 0.05)
            if int(self.st) == 8 or (self.st < 8 and self.st >= 7 - rage):
                cx, cy = self.pt(190, 40)
                spark(cx, cy, 6, (220, 200, 180), 5)
                SHAKE[0] = 6
                play("stomp")
                if dist < 235 and opp.y >= GROUND - 70:
                    opp.hit(self.facing, int(round(12 * self.dmg_mult)))
            if self.st <= 0:
                self.state, self.st = "idle", 40

    def _poly(self, surf, pts, col, edge=None):
        pygame.draw.polygon(surf, col, pts)
        if edge:
            pygame.draw.polygon(surf, edge, pts, 2)

    def draw(self, surf):
        sc = self.SC
        t = self.t
        dead = self.hp <= 0
        if dead:
            self.dead_t += 1
        sink = min(70, self.dead_t * 1.5) if dead else 0
        base = self.base
        if self.flash > 0 and not dead:
            base = (235, 120, 100)
        dark = shade(base, 0.55)
        light = shade(base, 1.3)
        belly = (225, 175, 95)
        EDG = (30, 10, 10)
        f = self.facing
        bob = math.sin(t * 0.07) * 3 if not dead else 0

        def P(px, py):
            return (int(self.x + f * px * sc), int(GROUND - (py + bob - sink * 0.0) * sc + sink))

        # ground shadow
        pygame.draw.ellipse(surf, (20, 20, 24), (int(self.x - 170 * sc), GROUND - 4, int(340 * sc), 14))
        # wings (behind body)
        flap = math.sin(t * 0.09) * 40 if not dead else -30
        wing_tip = P(-60, 300 + flap)
        wing_mid = P(70, 250 + flap * 0.6)
        for off, col in ((0, shade(base, 0.45)), (-1, shade(base, 0.7))):
            sh = P(-20, 185)
            tipx = P(-120 + off * 40, 270 + flap)
            self._poly(surf, [sh, wing_mid, P(40, 215 + flap * 0.4), tipx, P(-50, 230 + flap * 0.5),
                              P(-110, 175 + flap * 0.2)] if off == 0 else
                       [sh, P(-60, 250 + flap * .8), P(-130, 160)], col, EDG)
        pygame.draw.line(surf, EDG, P(-20, 185), wing_mid, 5)
        pygame.draw.line(surf, EDG, P(-20, 185), wing_tip, 5)
        # tail
        prev = P(-90, 105)
        for i in range(1, 9):
            px = -90 - i * 28
            py = 100 - i * 4 + math.sin(t * 0.06 + i * 0.7) * 9 * (i / 4.0)
            cur = P(px, py)
            r = max(3, int((26 - i * 2.8) * sc))
            pygame.draw.line(surf, EDG, prev, cur, r * 2 + 3)
            pygame.draw.line(surf, base if i % 2 else dark, prev, cur, r * 2)
            if i < 8:
                pygame.draw.polygon(surf, light, [(cur[0], cur[1] - r), (cur[0] - f * 6, cur[1] - r - 10), (cur[0] - f * 12, cur[1] - r)])
            prev = cur
        # rear leg
        for lx, shade_f in ((-70, 0.7), (35, 0.85)):
            hip = P(lx, 110)
            knee = P(lx + 12, 60)
            foot = P(lx + 22, 0)
            for a, b, w in ((hip, knee, 34), (knee, foot, 22)):
                pygame.draw.line(surf, EDG, a, b, int(w * sc) + 4)
                pygame.draw.line(surf, shade(base, shade_f), a, b, int(w * sc))
            pygame.draw.ellipse(surf, shade(base, shade_f), (foot[0] - int(22 * sc), foot[1] - int(10 * sc), int(52 * sc), int(14 * sc)))
            for c in range(3):
                cx = foot[0] + f * (int(26 * sc) + c * 5)
                pygame.draw.polygon(surf, (240, 235, 215), [(cx, foot[1] - 5), (cx + f * 8, foot[1] + 2), (cx, foot[1] + 3)])
        # body
        bc = P(-25, 130)
        pygame.draw.ellipse(surf, EDG, (bc[0] - int(124 * sc), bc[1] - int(66 * sc), int(248 * sc), int(132 * sc)))
        pygame.draw.ellipse(surf, base, (bc[0] - int(120 * sc), bc[1] - int(62 * sc), int(240 * sc), int(124 * sc)))
        pygame.draw.ellipse(surf, light, (bc[0] - int(90 * sc), bc[1] - int(60 * sc), int(170 * sc), int(40 * sc)))
        pygame.draw.ellipse(surf, belly, (bc[0] - int(100 * sc), bc[1] + int(8 * sc), int(190 * sc), int(48 * sc)))
        for i in range(6):
            sx = bc[0] - int(80 * sc) + i * int(30 * sc)
            pygame.draw.line(surf, shade(belly, 0.8), (sx, bc[1] + int(14 * sc)), (sx + 4, bc[1] + int(52 * sc)), 2)
        # back spikes
        for i in range(8):
            sp = P(-130 + i * 24, 188 - abs(i - 3) * 3)
            self._poly(surf, [(sp[0] - 8, sp[1] + 6), (sp[0] + f * 3, sp[1] - int(26 * sc)), (sp[0] + 10, sp[1] + 8)], dark, EDG)
        # neck
        prev = P(35, 160)
        for i in range(1, 7):
            cur = P(35 + i * 17, 160 + i * 11 + math.sin(t * 0.05 + i) * 2)
            r = int((24 - i * 1.6) * sc)
            pygame.draw.line(surf, EDG, prev, cur, r * 2 + 4)
            pygame.draw.line(surf, base if i % 2 else shade(base, 1.1), prev, cur, r * 2)
            pygame.draw.line(surf, belly, (prev[0] + f * 2, prev[1] + r // 2), (cur[0] + f * 2, cur[1] + r // 2), max(2, r // 2))
            prev = cur
        # front leg/arm
        sh = P(30, 120)
        el = P(70, 80)
        hd = P(112 + (30 if self.state == "claw" and self.st < 14 else 0), 20)
        for a, b, w in ((sh, el, 28), (el, hd, 20)):
            pygame.draw.line(surf, EDG, a, b, int(w * sc) + 4)
            pygame.draw.line(surf, shade(base, 0.95), a, b, int(w * sc))
        for c in range(3):
            cx, cy = hd[0] + f * c * 6, hd[1]
            pygame.draw.polygon(surf, (245, 240, 220), [(cx, cy - 6), (cx + f * 14, cy + 6), (cx, cy + 6)])
            pygame.draw.polygon(surf, EDG, [(cx, cy - 6), (cx + f * 14, cy + 6), (cx, cy + 6)], 1)
        # head
        hc = P(135, 238)
        m = self.mouth
        jaw_drop = int(24 * m * sc)
        # lower jaw
        jaw = [(hc[0] - f * 30 * sc, hc[1] + 8 * sc), (hc[0] + f * 62 * sc, hc[1] + 12 * sc + jaw_drop),
               (hc[0] + f * 64 * sc, hc[1] + 22 * sc + jaw_drop), (hc[0] - f * 20 * sc, hc[1] + 28 * sc + jaw_drop * 0.4)]
        self._poly(surf, jaw, shade(base, 0.8), EDG)
        if m > 0.3:
            pygame.draw.polygon(surf, (255, 140, 40) if m > 0.8 else (90, 20, 20),
                                [(hc[0] + f * 10 * sc, hc[1] + 14 * sc), (hc[0] + f * 60 * sc, hc[1] + 14 * sc + jaw_drop * 0.8),
                                 (hc[0] + f * 55 * sc, hc[1] + 12 * sc)])
        for i in range(4):
            tx = hc[0] + f * (18 + i * 12) * sc
            pygame.draw.polygon(surf, (250, 245, 225), [(tx, hc[1] + 12 * sc + jaw_drop * 0.5), (tx + f * 4, hc[1] + 3 * sc),
                                                       (tx - f * 4, hc[1] + 12 * sc + jaw_drop * 0.5)])
        # skull + snout
        self._poly(surf, [(hc[0] - f * 34 * sc, hc[1] - 20 * sc), (hc[0] + f * 20 * sc, hc[1] - 26 * sc),
                          (hc[0] + f * 68 * sc, hc[1] - 6 * sc), (hc[0] + f * 70 * sc, hc[1] + 8 * sc),
                          (hc[0] - f * 30 * sc, hc[1] + 12 * sc)], base, EDG)
        pygame.draw.line(surf, light, (hc[0] - f * 20 * sc, hc[1] - 18 * sc), (hc[0] + f * 60 * sc, hc[1] - 6 * sc), 3)
        for i in range(3):
            tx = hc[0] + f * (28 + i * 14) * sc
            pygame.draw.polygon(surf, (250, 245, 225), [(tx, hc[1] + 8 * sc), (tx + f * 3, hc[1] + 16 * sc + jaw_drop * 0.2), (tx - f * 4, hc[1] + 8 * sc)])
        pygame.draw.circle(surf, (20, 10, 10), (int(hc[0] + f * 62 * sc), int(hc[1] - 2 * sc)), 3)
        # horns
        for hx, hy, ln in ((-24, -18, 62), (-6, -22, 48)):
            a = (hc[0] + f * hx * sc, hc[1] + hy * sc)
            self._poly(surf, [(a[0], a[1]), (a[0] - f * ln * sc, a[1] - 22 * sc), (a[0] - f * 4, a[1] + 8)], (225, 215, 185), EDG)
        # eye
        ex, ey = int(hc[0] + f * 28 * sc), int(hc[1] - 9 * sc)
        pygame.draw.circle(surf, (255, 190, 30) if not dead else (60, 40, 30), (ex, ey), int(8 * sc) + 1)
        pygame.draw.line(surf, (20, 0, 0), (ex, ey - 6), (ex, ey + 6), 3)
        pygame.draw.line(surf, EDG, (ex - f * 10, ey - 11), (ex + f * 10, ey - 6), 3)
        # fire breath
        if self.state == "breath" and not dead:
            mx, my = hc[0] + f * 66 * sc, hc[1] + 12 * sc + jaw_drop * 0.5
            ex2, ey2 = self.pt(150 + self.flame, 0)
            for layer, (col, rm) in enumerate((((200, 50, 20), 1.0), ((250, 130, 30), 0.75), ((255, 220, 90), 0.5), ((255, 250, 220), 0.25))):
                for i in range(11):
                    u = i / 10.0
                    fx = mx + (ex2 - mx) * u + random.randint(-4, 4)
                    fy = my + (GROUND - 6 - my) * u + random.randint(-4, 4)
                    r = int((8 + 26 * u) * rm * (0.8 + 0.4 * random.random()))
                    pygame.draw.circle(surf, col, (int(fx), int(fy)), max(2, r))
            for i in range(5):
                pygame.draw.circle(surf, (255, 120, 30), (int(ex2 + random.randint(-40, 40)), GROUND - random.randint(2, 30)), random.randint(3, 8))
        elif self.state in ("wind", "ball") and not dead:
            mx, my = hc[0] + f * 66 * sc, hc[1] + 12 * sc
            r = int(5 + 9 * (1 - max(0.0, self.st) / 28.0))
            pygame.draw.circle(surf, (255, 140, 40), (int(mx), int(my)), r + 3)
            pygame.draw.circle(surf, (255, 240, 180), (int(mx), int(my)), r)


def go_super(f, hair, aura):
    f.sup = True
    lk = dict(f.look)
    lk["hair"] = hair
    lk["hstyle"] = "spiky"
    lk["helmet"] = None
    lk["turban"] = None
    f.look = lk
    f.aura_col = aura
    f.pcol = aura
    f.can_cast = True
    f.regen = max(f.regen, 0.32)
    f.pdmg = int(f.pdmg * 1.6) + 10
    f.energy = max(f.energy, 60.0)


def draw_aura(surf, f):
    if f.hp <= 0:
        return
    k = f.k
    t = f.t
    inten = f.aura
    if f.sup and inten >= 1.0:
        inten = 0.85 + 0.15 * math.sin(t * 0.3)
    cx, y = int(f.x), int(f.y)
    col = f.aura_col
    layers = ((1.0, shade(col, 0.55)), (0.78, col), (0.52, lerp(col, (255, 255, 255), 0.65)))
    for sc, c in layers:
        wd = 40 * k * sc
        pts = [(cx - wd, y)]
        n = 9
        for j in range(n):
            x = cx - wd + 2 * wd * (j + 0.5) / n
            h = (105 + 60 * abs(math.sin(t * 0.22 + j * 1.9 + sc * 3))) * k * inten * sc
            pts.append((x - wd / n * 0.5, y - h * 0.45))
            pts.append((x, y - h))
        pts.append((cx + wd, y))
        pygame.draw.polygon(surf, c, pts)
    if inten > 0.6 and (t // 2) % 2 == 0:
        for _ in range(2):
            x0 = cx + random.randint(-30, 30) * k
            y0 = y - random.randint(20, 150) * k
            m1 = (x0 + random.randint(-14, 14), y0 - 14 * k)
            pygame.draw.line(surf, (255, 255, 230), (x0, y0), m1, 2)
            pygame.draw.line(surf, (255, 255, 230), m1, (m1[0] + random.randint(-14, 14), y0 - 28 * k), 2)


# ---------------------------------------------------------------- worlds and levels
WORLDS = ["Training Yard", "Bamboo Dojo", "Desert Duel", "Snow Peak",
          "Harbor Docks", "Jungle Temple", "Volcano Forge", "Sky Citadel",
          "Neon Alley", "Frozen Palace", "Lost Ruins", "Storm Coast",
          "Shadow Grove", "Magma Throne", "Star Temple", "Final Realm"]
OPP_NAMES = [
    ["Rocco", "Big Tony", "Vince", "Jax"], ["Master Ren", "Shadow Kai", "Sensei Moto", "Night Blade"],
    ["Sand Rat", "Jabar", "Dune Raider", "Scorpion Ali"], ["Bjorn", "Ulf the Red", "Sigrid", "Axel Frost"],
    ["Salty Pete", "Captain Jack", "Anchor Dan", "Dockhand Lou"], ["Tiku", "Mbala", "Jungle Zul", "Chief Kaya"],
    ["Cinder", "Forge Ash", "Magma Vex", "Ember Kane"], ["Guard Lux", "Sir Aurel", "Knight Orion", "Captain Halo"],
]


def level_info(L):
    """Everything about level L (0-based): who you fight and how strong they are."""
    L = max(0, min(NUM_LEVELS - 1, L))
    w = L // 5
    boss = (L % 5 == 4)
    t = L / float(NUM_LEVELS - 1)
    info = {"L": L, "world": w, "world_name": WORLDS[w], "boss": boss}
    if L == 39:
        info.update(name="Ignis the Dragon", look=None, k=1.0, weapon=3, hp=1100, speed=0, dmg=2.0,
                    ai={"atk": 0, "blk": 0, "jump": 0}, dragon=True)
    elif L == NUM_LEVELS - 1:
        info.update(name="Ignis Prime, Dragon King", look=None, k=1.0, weapon=3, hp=2300, speed=0, dmg=2.6,
                    ai={"atk": 0, "blk": 0, "jump": 0}, dragon=True, prime=True)
    elif boss:
        k = w
        k7 = min(k, 7)
        info.update(name=GIANT_NAMES[k], look=make_giant_look(k), k=1.75 + 0.04 * k7, weapon=3,
                    hp=int(200 + 45 * k), speed=(3.2 + 0.28 * k7) * 1.2, dmg=1.0 + 0.31 * k7 + 0.12 * max(0, k - 7),
                    ai={"atk": 0.05 + 0.01 * k, "blk": 0.08 + 0.025 * k, "jump": 0.0})
    else:
        r = random.Random(500 + L)
        weapon = 0 if L < 4 else r.choice([0, 1, 1, 2])
        info.update(name=("Dark " if w >= 8 else "") + OPP_NAMES[w % 8][L % 5 % 4], look=make_look(L), k=1.0, weapon=weapon,
                    hp=int(75 + 225 * t), speed=(5.0 + 3.2 * t) * 1.2, dmg=0.85 + 1.25 * t,
                    ai={"atk": 0.035 + 0.11 * t, "blk": 0.06 + 0.34 * t, "jump": 0.003 + 0.015 * t})
    return info


def player_stats(L):
    return 100 + 3 * L, 1.0 + 0.02 * L


# ---------------------------------------------------------------- enemy brain
def ai_input(me, foe):
    ai = me.ai
    dist = abs(foe.x - me.x)
    to_right = foe.x > me.x
    left = right = jump = attack = block = False
    w = me.weapon
    rnd = random.random
    me.want_cast = bool(me.can_cast and me.energy >= 100 and dist > 150 and rnd() < 0.06)
    if me.giant:
        reach = WEAPONS[3]["reach"]
        if dist > reach * 0.8:
            right, left = to_right, not to_right
        if dist <= reach + 10 and rnd() < ai["atk"]:
            attack = True
        if foe.atk > 0 and dist < reach + 60 and rnd() < ai["blk"]:
            block = True
        return left, right, jump, attack, block
    if w == 2:
        if dist > 330:
            right, left = to_right, not to_right
        elif dist < 190:
            right, left = (not to_right), to_right
        if dist > 100 and rnd() < ai["atk"] * 0.8:
            attack = True
    else:
        reach = WEAPONS[w]["reach"]
        if dist > reach + 28:
            right, left = to_right, not to_right
        elif dist < 40 and rnd() < 0.1:
            right, left = (not to_right), to_right
        if dist <= reach + 32 and rnd() < ai["atk"]:
            attack = True
    if foe.atk > 0 and foe.weapon != 2 and dist < WEAPONS[foe.weapon]["reach"] + 50:
        if rnd() < ai["blk"]:
            block = True
    for b in BULLETS:
        if b["owner"] is foe and abs(b["x"] - me.x) < 170 and rnd() < ai["blk"] * 0.6:
            block = True
    if rnd() < ai["jump"]:
        jump = True
    return left, right, jump, attack, block


# ---------------------------------------------------------------- backgrounds
def vgrad(s, y0, y1, c0, c1):
    n = float(max(1, y1 - y0))
    for y in range(y0, y1, 2):
        pygame.draw.rect(s, lerp(c0, c1, (y - y0) / n), (0, y, W, 3))


def ground_fill(s, base, r, tex, edge):
    pygame.draw.rect(s, base, (0, GROUND, W, H - GROUND))
    pygame.draw.rect(s, shade(base, 0.8), (0, GROUND + 60, W, H - GROUND - 60))
    pygame.draw.line(s, edge, (0, GROUND), (W, GROUND), 3)
    for _ in range(130):
        x = r.randint(0, W)
        y = r.randint(GROUND + 5, H - 2)
        pygame.draw.line(s, tex if r.random() < 0.5 else shade(base, 0.7), (x, y), (x + r.randint(2, 10), y), 1)


def bg_yard(s, r):
    vgrad(s, 0, GROUND, (12, 16, 38), (58, 64, 104))
    for _ in range(70):
        pygame.draw.circle(s, (230, 230, 255), (r.randint(0, W), r.randint(0, 200)), 1)
    pygame.draw.circle(s, (235, 235, 215), (650, 80), 30)
    pygame.draw.circle(s, (205, 205, 190), (640, 72), 6)
    pygame.draw.polygon(s, (30, 36, 70), [(0, GROUND), (110, 200), (230, 250), (340, 190), (470, GROUND)])
    pygame.draw.polygon(s, (36, 42, 80), [(380, GROUND), (560, 205), (700, 245), (800, 215), (800, GROUND)])
    for x in range(0, W, 40):
        pygame.draw.rect(s, (74, 54, 38), (x + 4, 262, 8, 48))
    pygame.draw.rect(s, (92, 68, 46), (0, 272, W, 6))
    pygame.draw.rect(s, (92, 68, 46), (0, 292, W, 6))
    for x in (130, 670):   # training dummies
        pygame.draw.rect(s, (96, 70, 46), (x - 5, 220, 10, 90))
        pygame.draw.circle(s, (200, 170, 110), (x, 205), 16)
        pygame.draw.rect(s, (200, 170, 110), (x - 28, 232, 56, 12))
        pygame.draw.line(s, (120, 80, 50), (x - 12, 200), (x + 12, 210), 3)
    for x in (50, 750):    # torches
        pygame.draw.rect(s, (80, 56, 40), (x - 3, 232, 6, 78))
        for rr, c in ((34, (90, 50, 30)), (22, (170, 90, 30)), (12, (255, 170, 60))):
            pygame.draw.circle(s, c, (x, 226), rr)
        pygame.draw.circle(s, (255, 240, 170), (x, 228), 6)
    ground_fill(s, (96, 78, 58), r, (130, 108, 82), (150, 125, 95))


def bg_dojo(s, r):
    vgrad(s, 0, GROUND, (38, 70, 62), (160, 178, 112))
    pygame.draw.circle(s, (240, 235, 190), (610, 90), 34)
    pygame.draw.polygon(s, (60, 86, 82), [(0, GROUND), (140, 190), (300, GROUND)])
    pygame.draw.polygon(s, (66, 94, 88), [(260, GROUND), (460, 170), (700, GROUND)])
    # dojo building
    pygame.draw.rect(s, (120, 80, 56), (250, 215, 300, 95))
    pygame.draw.rect(s, (230, 215, 170), (270, 235, 260, 75))
    for x in range(270, 531, 52):
        pygame.draw.rect(s, (90, 56, 40), (x, 235, 5, 75))
    pygame.draw.polygon(s, (110, 36, 36), [(215, 222), (400, 150), (585, 222), (555, 222), (400, 172), (245, 222)])
    pygame.draw.polygon(s, (86, 26, 28), [(235, 222), (400, 160), (565, 222), (545, 232), (400, 186), (255, 232)])
    for x in (320, 400, 480):
        pygame.draw.circle(s, (200, 50, 50), (x, 250), 12)
        pygame.draw.line(s, (60, 30, 20), (x, 238), (x, 232), 2)
    # bamboo
    for _ in range(26):
        x = r.randint(0, W)
        if 230 < x < 570:
            continue
        top = r.randint(40, 120)
        g = r.randint(80, 150)
        pygame.draw.line(s, (40, g, 70), (x, top), (x, GROUND), 7)
        pygame.draw.line(s, (90, g + 60, 100), (x - 2, top), (x - 2, GROUND), 2)
        for yy in range(top + 30, GROUND, 38):
            pygame.draw.line(s, (30, 80, 50), (x - 4, yy), (x + 4, yy), 2)
        for _ in range(3):
            yy = r.randint(top, top + 120)
            pygame.draw.polygon(s, (60, g + 40, 80), [(x, yy), (x + r.choice((-26, 26)), yy - 8), (x + r.choice((-14, 14)), yy + 4)])
    pygame.draw.rect(s, (150, 110, 72), (0, GROUND, W, H - GROUND))
    for y in range(GROUND + 14, H, 20):
        pygame.draw.line(s, (110, 78, 50), (0, y), (W, y), 2)
    for x in range(0, W, 96):
        pygame.draw.line(s, (110, 78, 50), (x + (y_off(x)), GROUND), (x + 30, H), 1)
    pygame.draw.line(s, (190, 150, 105), (0, GROUND), (W, GROUND), 3)


def y_off(x):
    return (x * 7) % 23


def bg_desert(s, r):
    vgrad(s, 0, GROUND, (230, 150, 90), (255, 225, 160))
    pygame.draw.circle(s, (255, 245, 190), (580, 120), 56)
    pygame.draw.circle(s, (255, 252, 225), (580, 120), 40)
    pygame.draw.polygon(s, (214, 160, 100), [(0, GROUND), (0, 240), (150, 215), (320, GROUND)])
    pygame.draw.polygon(s, (190, 130, 80), [(250, GROUND), (430, 235), (620, 205), (800, 250), (800, GROUND)])
    pygame.draw.polygon(s, (176, 118, 72), [(60, 250), (130, 175), (200, 250)])     # pyramid
    pygame.draw.polygon(s, (150, 98, 60), [(130, 175), (200, 250), (150, 250)])
    for x in (330, 700):    # cacti
        pygame.draw.rect(s, (60, 120, 70), (x, 250, 14, 60), border_radius=6)
        pygame.draw.rect(s, (60, 120, 70), (x - 14, 270, 8, 22), border_radius=4)
        pygame.draw.rect(s, (60, 120, 70), (x - 14, 288, 20, 7), border_radius=3)
        pygame.draw.rect(s, (60, 120, 70), (x + 20, 262, 8, 24), border_radius=4)
        pygame.draw.rect(s, (60, 120, 70), (x + 6, 282, 20, 7), border_radius=3)
    ground_fill(s, (226, 184, 124), r, (246, 210, 150), (240, 205, 150))
    for i in range(6):
        y = GROUND + 16 + i * 20
        pygame.draw.arc(s, (205, 160, 100), (r.randint(-100, 600), y, 380, 26), 0.2, 2.9, 2)


def bg_snow(s, r):
    vgrad(s, 0, GROUND, (120, 150, 205), (226, 236, 252))
    pygame.draw.circle(s, (250, 250, 255), (160, 90), 26)
    for pts, cap in (([(0, GROUND), (130, 130), (300, GROUND)], [(130, 130), (100, 170), (160, 170)]),
                     ([(220, GROUND), (420, 100), (640, GROUND)], [(420, 100), (370, 170), (470, 170)]),
                     ([(520, GROUND), (680, 150), (800, 215), (800, GROUND)], [(680, 150), (640, 195), (720, 195)])):
        pygame.draw.polygon(s, (110, 128, 170), pts)
        pygame.draw.polygon(s, (240, 245, 255), cap)
    for x in range(10, W, 46):
        h = r.randint(40, 76)
        y = GROUND - 5
        pygame.draw.rect(s, (60, 44, 34), (x - 3, y - 12, 6, 14))
        for i in range(3):
            yy = y - 12 - i * h // 3
            wd = 24 - i * 6
            pygame.draw.polygon(s, (26, 78, 62), [(x - wd, yy), (x + wd, yy), (x, yy - h // 2)])
            pygame.draw.polygon(s, (230, 240, 250), [(x - wd // 2, yy - h // 6), (x + wd // 2, yy - h // 6), (x, yy - h // 2)])
    ground_fill(s, (236, 242, 252), r, (190, 205, 232), (200, 214, 240))


def bg_harbor(s, r):
    vgrad(s, 0, 200, (54, 46, 108), (236, 140, 98))
    pygame.draw.circle(s, (255, 214, 150), (400, 196), 46)
    pygame.draw.rect(s, (46, 70, 120), (0, 196, W, GROUND - 196))
    for y in range(204, GROUND, 9):
        for x in range(r.randint(0, 30), W, 56):
            pygame.draw.line(s, (96, 130, 180), (x, y), (x + 22, y), 2)
    pygame.draw.polygon(s, (28, 28, 48), [(80, 200), (330, 200), (300, 232), (110, 232)])
    pygame.draw.rect(s, (28, 28, 48), (170, 150, 90, 50))
    pygame.draw.rect(s, (28, 28, 48), (212, 100, 6, 52))
    pygame.draw.polygon(s, (60, 60, 90), [(218, 104), (218, 140), (260, 140)])
    for (x, y, c) in ((30, 255, (150, 108, 62)), (76, 255, (130, 92, 52)), (53, 214, (160, 118, 70)), (730, 255, (150, 108, 62)), (684, 255, (126, 88, 50))):
        pygame.draw.rect(s, c, (x - 20, y, 40, 55))
        pygame.draw.rect(s, shade(c, 0.6), (x - 20, y, 40, 55), 3)
        pygame.draw.line(s, shade(c, 0.6), (x - 20, y), (x + 20, y + 55), 3)
    for x in (300, 520):
        pygame.draw.rect(s, (40, 36, 36), (x - 3, 230, 6, 80))
        pygame.draw.circle(s, (255, 226, 150), (x, 226), 9)
    pygame.draw.rect(s, (112, 86, 60), (0, GROUND, W, H - GROUND))
    for y in range(GROUND + 12, H, 18):
        pygame.draw.line(s, (80, 60, 42), (0, y), (W, y), 2)
    for x in range(0, W, 70):
        pygame.draw.line(s, (80, 60, 42), (x, GROUND), (x - 12, H), 1)
    pygame.draw.line(s, (150, 120, 84), (0, GROUND), (W, GROUND), 3)


def bg_jungle(s, r):
    vgrad(s, 0, GROUND, (26, 70, 56), (130, 176, 110))
    pygame.draw.polygon(s, (100, 104, 92), [(260, GROUND), (330, 170), (470, 170), (540, GROUND)])
    for i in range(5):
        pygame.draw.rect(s, (118, 122, 108), (300 - i * 12, 190 + i * 24, 200 + i * 24, 24))
        pygame.draw.line(s, (80, 84, 74), (300 - i * 12, 190 + i * 24), (500 + i * 12, 190 + i * 24), 2)
    pygame.draw.rect(s, (30, 30, 30), (380, 190, 40, 50))
    for x in (30, 150, 640, 760):
        pygame.draw.rect(s, (60, 42, 32), (x - 12, 90, 24, GROUND - 90))
        for dx, dy, rr in ((-30, 80, 54), (30, 70, 58), (0, 40, 62), (-6, 100, 50)):
            pygame.draw.circle(s, (26, 92, 48), (x + dx, dy), rr)
            pygame.draw.circle(s, (40, 120, 62), (x + dx - 10, dy - 12), rr // 2)
    for _ in range(14):
        x = r.randint(0, W)
        pygame.draw.line(s, (40, 110, 60), (x, 0), (x + r.randint(-8, 8), r.randint(50, 170)), 3)
    ground_fill(s, (66, 96, 54), r, (90, 124, 70), (110, 150, 88))
    for x in range(0, W, 80):
        pygame.draw.rect(s, (96, 100, 86), (x + 6, GROUND + 30, 66, 26), 2)
        pygame.draw.rect(s, (96, 100, 86), (x - 30, GROUND + 70, 66, 26), 2)


def bg_volcano(s, r):
    vgrad(s, 0, GROUND, (30, 6, 8), (200, 56, 20))
    pygame.draw.polygon(s, (44, 26, 28), [(120, GROUND), (330, 130), (470, 130), (700, GROUND)])
    pygame.draw.polygon(s, (255, 130, 30), [(330, 130), (470, 130), (440, 150), (360, 150)])
    pygame.draw.polygon(s, (255, 190, 80), [(350, 134), (450, 134), (430, 144), (370, 144)])
    for x0 in (380, 420, 400):
        pygame.draw.line(s, (255, 120, 30), (x0, 150), (x0 + r.randint(-70, 70), GROUND - 30), 3)
    for _ in range(40):
        pygame.draw.circle(s, (70, 40, 38), (r.randint(0, W), r.randint(20, 150)), r.randint(2, 4))
    pygame.draw.polygon(s, (36, 22, 24), [(0, GROUND), (0, 220), (90, 250), (200, GROUND)])
    pygame.draw.polygon(s, (36, 22, 24), [(600, GROUND), (720, 235), (800, 200), (800, GROUND)])
    pygame.draw.rect(s, (255, 110, 20), (0, 286, W, 24))
    for x in range(0, W, 60):
        pygame.draw.line(s, (255, 200, 90), (x + r.randint(0, 20), 292), (x + 30, 292), 3)
    ground_fill(s, (50, 38, 40), r, (80, 60, 60), (110, 70, 56))
    for _ in range(14):
        x = r.randint(0, W)
        y = r.randint(GROUND + 8, H - 6)
        pygame.draw.line(s, (255, 120, 30), (x, y), (x + r.randint(-24, 24), y + r.randint(-8, 8)), 2)


def bg_citadel(s, r):
    vgrad(s, 0, GROUND, (96, 156, 236), (232, 242, 255))
    for _ in range(9):
        cx, cy = r.randint(0, W), r.randint(30, 200)
        for dx, dy, rr in ((-26, 4, 18), (0, -6, 24), (26, 4, 18), (0, 8, 20)):
            pygame.draw.circle(s, (250, 252, 255), (cx + dx, cy + dy), rr)
    pygame.draw.polygon(s, (214, 218, 236), [(250, 250), (550, 250), (520, 270), (280, 270)])
    for x, h in ((290, 90), (340, 120), (400, 150), (460, 120), (510, 90)):
        pygame.draw.rect(s, (236, 238, 250), (x - 18, 250 - h, 36, h))
        pygame.draw.polygon(s, (226, 190, 80), [(x - 22, 250 - h), (x + 22, 250 - h), (x, 250 - h - 34)])
        pygame.draw.rect(s, (110, 120, 170), (x - 4, 250 - h + 20, 8, 18))
    pygame.draw.circle(s, (255, 235, 150), (400, 250 - 150 - 36), 5)
    for x in (60, 740):
        pygame.draw.rect(s, (240, 240, 250), (x - 18, 120, 36, GROUND - 120))
        for yy in range(130, GROUND, 24):
            pygame.draw.line(s, (200, 204, 224), (x - 8, yy), (x - 8, yy + 14), 2)
        pygame.draw.rect(s, (226, 190, 80), (x - 26, 112, 52, 12))
        pygame.draw.rect(s, (226, 190, 80), (x - 26, GROUND - 10, 52, 12))
    pygame.draw.rect(s, (226, 228, 240), (0, GROUND, W, H - GROUND))
    for y in range(GROUND + 20, H, 26):
        pygame.draw.line(s, (186, 190, 214), (0, y), (W, y), 2)
    for x in range(-100, W + 100, 90):
        pygame.draw.line(s, (186, 190, 214), (x, GROUND), (x - 60, H), 2)
    pygame.draw.line(s, (226, 190, 80), (0, GROUND), (W, GROUND), 4)


BG_BUILDERS = [bg_yard, bg_dojo, bg_desert, bg_snow, bg_harbor, bg_jungle, bg_volcano, bg_citadel]
BG_CACHE = {}


def draw_bg(surf, world):
    bg = BG_CACHE.get(world)
    if bg is None:
        bg = pygame.Surface((W, H))
        BG_BUILDERS[world % 8](bg, random.Random(world * 100 + 7))
        if world >= 8:
            try:
                bg.fill((190, 160, 255), special_flags=pygame.BLEND_MULT)
            except Exception:
                pass
        BG_CACHE[world] = bg
    surf.blit(bg, (0, 0))


_FLAKES = [(random.Random(i).randint(0, W), random.Random(i + 99).randint(0, H), random.Random(i + 5).uniform(0.6, 1.8)) for i in range(34)]


def draw_overlay(surf, world, frame):
    world = world % 8
    if world == 3:      # snow
        for i, (x, y, v) in enumerate(_FLAKES):
            yy = (y + frame * v) % H
            xx = (x + math.sin((frame + i * 17) * 0.03) * 14) % W
            pygame.draw.circle(surf, (255, 255, 255), (int(xx), int(yy)), 2 if v > 1.2 else 1)
    elif world == 6:    # embers
        for i, (x, y, v) in enumerate(_FLAKES):
            yy = (H - (frame * v * 0.9 + y)) % H
            xx = (x + math.sin((frame + i * 11) * 0.04) * 20) % W
            pygame.draw.circle(surf, (255, 150 + int(v * 40), 40), (int(xx), int(yy)), 2 if v > 1.2 else 1)
    elif world == 1:    # drifting leaves
        for i, (x, y, v) in enumerate(_FLAKES[:14]):
            yy = (y + frame * v * 0.6) % H
            xx = (x + frame * 0.8 + math.sin((frame + i * 13) * 0.05) * 20) % W
            pygame.draw.circle(surf, (110, 190, 100), (int(xx), int(yy)), 2)
# ---------------------------------------------------------------- button art
def draw_icon(surf, name, cx, cy, col=(245, 245, 245)):
    if name == "left":
        pygame.draw.polygon(surf, col, [(cx + 14, cy - 20), (cx - 16, cy), (cx + 14, cy + 20)])
    elif name == "right":
        pygame.draw.polygon(surf, col, [(cx - 14, cy - 20), (cx + 16, cy), (cx - 14, cy + 20)])
    elif name == "jump":
        pygame.draw.polygon(surf, col, [(cx - 22, cy + 14), (cx + 22, cy + 14), (cx, cy - 20)])
    elif name == "block":
        pygame.draw.polygon(surf, col, [(cx - 20, cy - 20), (cx + 20, cy - 20), (cx + 20, cy + 2),
                                        (cx, cy + 24), (cx - 20, cy + 2)])
    elif name == "attack":
        pts = []
        for i in range(16):
            ang = i * math.pi / 8
            rad = 32 if i % 2 == 0 else 15
            pts.append((cx + rad * math.cos(ang), cy + rad * math.sin(ang)))
        pygame.draw.polygon(surf, col, pts)
    elif name == "swap":
        pygame.draw.line(surf, col, (cx - 14, cy + 14), (cx + 12, cy - 12), 5)
        pygame.draw.line(surf, col, (cx - 12, cy + 2), (cx - 2, cy + 12), 5)
        pygame.draw.line(surf, col, (cx - 16, cy + 16), (cx - 11, cy + 11), 6)
    elif name == "exit":
        pygame.draw.line(surf, col, (cx - 12, cy - 12), (cx + 12, cy + 12), 6)
        pygame.draw.line(surf, col, (cx + 12, cy - 12), (cx - 12, cy + 12), 6)
    elif name == "power":
        for arm in range(3):
            prev = None
            for i in range(9):
                ang = arm * 2.094 + i * 0.6
                rad = 3 + i * 2.6
                pt = (cx + math.cos(ang) * rad, cy + math.sin(ang) * rad)
                if prev:
                    pygame.draw.line(surf, col, prev, pt, 4)
                prev = pt
    elif name == "lock":
        pygame.draw.rect(surf, col, (cx - 12, cy - 2, 24, 18), border_radius=3)
        pygame.draw.circle(surf, col, (cx, cy - 6), 8, 4)
    elif name == "crown":
        draw_crown(surf, cx, cy + 12, 17, 3)
    elif name in ("sound_on", "sound_off"):
        pygame.draw.rect(surf, col, (cx - 15, cy - 6, 8, 12))
        pygame.draw.polygon(surf, col, [(cx - 8, cy - 6), (cx + 3, cy - 15), (cx + 3, cy + 15), (cx - 8, cy + 6)])
        if name == "sound_on":
            pygame.draw.line(surf, col, (cx + 8, cy - 6), (cx + 8, cy + 6), 3)
            pygame.draw.line(surf, col, (cx + 15, cy - 11), (cx + 15, cy + 11), 3)
        else:
            pygame.draw.line(surf, (255, 110, 110), (cx + 8, cy - 11), (cx + 20, cy + 11), 4)
            pygame.draw.line(surf, (255, 110, 110), (cx + 20, cy - 11), (cx + 8, cy + 11), 4)


def icon_with_shadow(surf, name, cx, cy):
    if name == "crown":
        draw_icon(surf, name, cx, cy)
        return
    draw_icon(surf, name, cx + 2, cy + 3, (20, 20, 30))
    draw_icon(surf, name, cx, cy)


PAD = 10
SPR = {}


def flat_sprite(w, h, base, pressed, icon, label, is_round):
    key = ("f", w, h, base, pressed, icon, label, is_round)
    if key in SPR:
        return SPR[key]
    s = pygame.Surface((w + 2 * PAD, h + 2 * PAD + 4))
    s.fill((255, 0, 255))
    s.set_colorkey((255, 0, 255))
    yo = 4 if pressed else 0
    col = shade(base, 0.8) if pressed else base
    if is_round:
        r = w // 2
        cx, cy = PAD + r, PAD + r + yo
        pygame.draw.circle(s, shade(base, 0.35), (cx, cy + (0 if pressed else 5)), r)
        pygame.draw.circle(s, col, (cx, cy), r)
        pygame.draw.circle(s, shade(col, 0.6), (cx, cy), r, 3)
    else:
        cx, cy = PAD + w // 2, PAD + h // 2 + yo
        pygame.draw.rect(s, shade(base, 0.35), (PAD, PAD + (0 if pressed else 5), w, h))
        pygame.draw.rect(s, col, (PAD, PAD + yo, w, h))
        pygame.draw.rect(s, shade(col, 0.6), (PAD, PAD + yo, w, h), 3)
    if icon:
        icon_with_shadow(s, icon, cx, cy)
    if label:
        text(s, label, font if not is_round else mid, (255, 255, 255), (cx, cy))
    SPR[key] = s
    return s


def make_round(w, base, pressed, icon=None, label=None):
    if SAFE_UI:
        return flat_sprite(w, w, base, pressed, icon, label, True)
    key = ("r", w, base, pressed, icon, label)
    if key in SPR:
        return SPR[key]
    size = w + 2 * PAD
    s = pygame.Surface((size, size + 4), pygame.SRCALPHA)
    r = w // 2
    cx = size // 2
    cy = size // 2 + (4 if pressed else 0)
    pygame.draw.circle(s, (0, 0, 0, 100), (size // 2, size // 2 + (3 if pressed else 8)), r + 2)
    pygame.draw.circle(s, shade(base, 0.3), (cx, cy), r)
    pygame.draw.circle(s, shade(base, 0.55), (cx, cy), r - 3)
    fr = r - 7
    hi = shade(base, 1.55 if not pressed else 1.1)
    lo = shade(base, 0.72 if not pressed else 0.5)
    for k in range(fr, 0, -2):
        t = k / float(fr)
        sh = (fr - k) * (0.4 if not pressed else 0.15)
        pygame.draw.circle(s, lerp(hi, lo, t), (int(cx - sh), int(cy - sh)), k)
    if not pressed:
        pygame.draw.ellipse(s, lerp(hi, (255, 255, 255), 0.35),
                            (int(cx - fr * 0.5), int(cy - fr * 0.82), int(fr * 1.0), int(fr * 0.42)))
    if icon:
        icon_with_shadow(s, icon, cx, cy)
    if label:
        text(s, label, mid, (255, 255, 255), (cx, cy))
    SPR[key] = s
    return s


def make_pill(w, h, base, pressed, icon=None, label=None):
    if SAFE_UI:
        return flat_sprite(w, h, base, pressed, icon, label, False)
    key = ("p", w, h, base, pressed, icon, label)
    if key in SPR:
        return SPR[key]
    s = pygame.Surface((w + 2 * PAD, h + 2 * PAD + 4), pygame.SRCALPHA)
    yo = 4 if pressed else 0
    rad = min(22, h // 2)
    pygame.draw.rect(s, (0, 0, 0, 100), (PAD, PAD + (3 if pressed else 8), w, h), border_radius=rad)
    n = max(3, min(h // 2 - 3, 9))
    for i in range(n):
        t = i / float(n)
        if pressed:
            t = 1 - t * 0.6
            col = lerp(shade(base, 0.4), shade(base, 0.95), 1 - t)
        else:
            col = lerp(shade(base, 0.35), shade(base, 1.4), t)
        pygame.draw.rect(s, col, (PAD + i, PAD + i + yo, w - 2 * i, h - 2 * i), border_radius=max(4, rad - i))
    cx, cy = PAD + w // 2, PAD + h // 2 + yo
    if icon:
        icon_with_shadow(s, icon, cx, cy)
    if label:
        text(s, label, font, (255, 255, 255), (cx, cy))
    SPR[key] = s
    return s


def draw_control(surf, name, on):
    rc = BUTTONS[name]
    if name in PILL:
        spr = make_pill(rc.w, rc.h, COLORS[name], on, icon=name)
    else:
        spr = make_round(rc.w, COLORS[name], on, icon=name)
    surf.blit(spr, (rc.x - PAD, rc.y - PAD))


def draw_ui_button(surf, rc, label, base, pressed):
    surf.blit(make_pill(rc.w, rc.h, base, pressed, label=label), (rc.x - PAD, rc.y - PAD))


def draw_ui_round(surf, rc, base, pressed, icon=None, label=None):
    surf.blit(make_round(rc.w, base, pressed, icon=icon, label=label), (rc.x - PAD, rc.y - PAD))




# ---------------------------------------------------------------- controls layout
BUTTONS = {
    "left": pygame.Rect(15, 335, 100, 100),
    "right": pygame.Rect(125, 335, 100, 100),
    "block": pygame.Rect(440, 352, 90, 90),
    "jump": pygame.Rect(545, 340, 100, 100),
    "attack": pygame.Rect(655, 315, 125, 125),
    "swap": pygame.Rect(20, 55, 62, 62),
    "power": pygame.Rect(338, 356, 84, 84),
    "exit": pygame.Rect(W // 2 - 24, 55, 48, 48),
}
PILL = ("left", "right", "exit")
HIT_PAD = {"attack": 30, "block": 20, "jump": 18, "left": 14, "right": 14, "swap": 10, "exit": 10, "power": 14}
COLORS = {
    "left": (75, 80, 115), "right": (75, 80, 115),
    "block": (50, 110, 210), "jump": (60, 170, 90),
    "attack": (215, 55, 55), "exit": (150, 45, 45),
    "swap": (205, 140, 40), "power": (130, 70, 200),
}

# menu layout
MENU_PLAY = pygame.Rect(280, 150, 240, 74)
MENU_LEVELS = pygame.Rect(232, 236, 160, 56)
MENU_SHOP = pygame.Rect(408, 236, 160, 56)
MENU_QUIT = pygame.Rect(340, 304, 120, 46)
MENU_SOUND = pygame.Rect(W - 76, 16, 52, 52)
BTN_BACK = pygame.Rect(W // 2 - 60, 392, 120, 44)
BTN_A = pygame.Rect(W // 2 - 175, 235, 165, 62)
BTN_B = pygame.Rect(W // 2 + 10, 235, 165, 62)
BTN_C = pygame.Rect(W // 2 - 82, 235, 165, 62)
BTN_D = BTN_C.move(0, 78)
BTN_E = pygame.Rect(W // 2 - 100, 360, 200, 62)
BTN_E2 = pygame.Rect(W // 2 - 100, 386, 200, 52)
SHOP_ROWS = [pygame.Rect(90, 104 + i * 86, 620, 74) for i in range(3)]
SHOP_BUY = [pygame.Rect(548, 112 + i * 86, 152, 58) for i in range(3)]
GRID = [pygame.Rect(26 + (i % 16) * 47, 84 + (i // 16) * 56, 42, 42) for i in range(NUM_LEVELS)]


class S:
    pass


S.state = "menu"
S.level = 0
S.cleared = 0
S.round = 1
S.pieces = []
S.hide_e = False
S.fin = None
S.zoom = 1.0
S.info = None
S.player = None
S.enemy = None
S.banner_t = 0
S.tap_lock = 0
S.frame = 0
S.anim = 0
S.fingers = {}
S.prev_swap = False
S.running = True
S.tap = None
S.held = []
S.win_t = 0
S.slow = 0
S.prog = {"coins": 0, "power": 0, "health": 0, "armor": 0}
S.reward = 0
S.msg_t = 0


def draw_coin(surf, cx, cy, r):
    cx, cy = int(cx), int(cy)
    pygame.draw.circle(surf, (120, 80, 10), (cx, cy), r + 1)
    pygame.draw.circle(surf, (240, 190, 50), (cx, cy), r)
    pygame.draw.circle(surf, (255, 225, 110), (cx - max(1, r // 4), cy - max(1, r // 4)), max(2, r * 2 // 3))
    pygame.draw.circle(surf, (225, 165, 30), (cx, cy), max(2, r // 2), max(1, r // 6))


def up_cost(kind, lvl):
    base = {"power": 40, "health": 40, "armor": 60}[kind]
    step = {"power": 30, "health": 30, "armor": 40}[kind]
    return base + step * lvl


def level_reward(L, first):
    boss = (L % 5 == 4)
    r = 10 + 3 * L + (50 + 10 * (L // 5) if boss else 0)
    return r if first else max(5, r // 2)


def text(surf, s, fnt, col, center, shadow=True):
    if shadow:
        t0 = fnt.render(s, True, (0, 0, 0))
        surf.blit(t0, t0.get_rect(center=(center[0] + 3, center[1] + 3)))
    t = fnt.render(s, True, col)
    surf.blit(t, t.get_rect(center=center))


def boot_flags():
    global FLAGS, SAFE_UI
    FLAGS = set(x for x in _rd(FLAGS_FILE).split(",") if x)
    last = _rd(STAGE_FILE)
    if last == "audio":
        FLAGS.add("nosound")
    elif last in ("ui", "game"):
        FLAGS.add("safeui")
    if last in ("audio", "ui", "game"):
        _wr(FLAGS_FILE, ",".join(sorted(FLAGS)))
    if not USE_SOUND:
        FLAGS.add("nosound")
    if not FANCY_BUTTONS:
        FLAGS.add("safeui")
    SAFE_UI = "safeui" in FLAGS
    mark("init")
    print("fighter: start, flags =", sorted(FLAGS))


def setup():
    global screen, SW, SH, canvas, scale, scale_y, ox, oy, font, big, mid, small, clock, dim, f20, f22, f24, f26, title_f
    pygame.display.init()
    pygame.font.init()
    screen = pygame.display.set_mode((0, 0))
    SW, SH = screen.get_size()
    canvas = pygame.Surface((W, H))
    scale = SW / float(W)
    scale_y = SH / float(H)
    ox, oy = 0.0, 0.0
    font = pygame.font.Font(None, 56)
    big = pygame.font.Font(None, 96)
    mid = pygame.font.Font(None, 40)
    small = pygame.font.Font(None, 30)
    title_f = pygame.font.Font(None, 76)
    f20 = pygame.font.Font(None, 20)
    f22 = pygame.font.Font(None, 22)
    f24 = pygame.font.Font(None, 24)
    f26 = pygame.font.Font(None, 26)
    clock = pygame.time.Clock()
    screen.fill((15, 18, 35))
    lt = font.render("Loading...", True, (255, 255, 255))
    screen.blit(lt, lt.get_rect(center=(SW // 2, SH // 2)))
    pygame.display.flip()
    if SAFE_UI:
        dim = pygame.Surface((W, H))
        dim.fill((0, 0, 0))
        dim.set_alpha(140)
    else:
        dim = pygame.Surface((W, H), pygame.SRCALPHA)
        dim.fill((0, 0, 0, 140))
    init_audio()
    start_audio_thread()
    mark("ui")


# ---------------------------------------------------------------- flow helpers
def music_for_state():
    st = S.state
    if st in ("banner", "play", "transform", "finish", "lose"):
        if S.info and S.info["boss"]:
            return "boss"
        return "battleA" if (S.info and S.info["world"] % 2 == 0) else "battleB"
    return "menu"


def go(state, lock=10):
    S.state = state
    S.tap_lock = lock
    S.anim = 0
    if state == "play":
        mark("game")
    set_music(music_for_state())


def new_round():
    info = S.info
    pw = S.player.weapon if S.player else 0
    php, pdm = player_stats(info["L"])
    p = Fighter(200, PLAYER_LOOK, 12, pw)
    p.maxhp = p.hp = php + 10 * S.prog["health"]
    p.dmg_mult = pdm * (1.0 + 0.08 * S.prog["power"])
    p.armor = 0.04 * S.prog["armor"]
    p.use_buf = True
    p.crowns = min(16, S.cleared // 5)
    p.can_cast = True
    p.regen = 0.14
    p.pcol = (110, 220, 255)
    p.pdmg = 30 + int(0.6 * info["L"])
    if info.get("dragon"):
        e = Dragon(655)
        e.maxhp = e.hp = info["hp"]
        e.dmg_mult = info["dmg"]
    else:
        e = Fighter(620 if info["boss"] else 600, info["look"], info["speed"], info["weapon"], info["k"])
        e.maxhp = e.hp = info["hp"]
        e.dmg_mult = info["dmg"]
        e.ai = info["ai"]
        e.name = info["name"]
        if info["L"] >= 4:
            e.can_cast = True
            e.regen = 0.05 + 0.05 * (info["L"] / 39.0)
            e.pdmg = 14 + int(0.5 * info["L"])
            e.pcol = (255, 120, 90) if info["boss"] else (200, 120, 255)
    S.player, S.enemy = p, e
    BULLETS[:] = []
    PARTICLES[:] = []


def start_level(L, retry=False):
    S.level = L
    S.info = level_info(L)
    S.round = 1
    new_round()
    S.banner_t = 110 if S.info["boss"] else 70
    if retry:
        S.banner_t = 45
    if S.info["boss"]:
        play("roar")
    go("banner")


def crowns_earned():
    return min(16, S.cleared // 5)


def win_level():
    first = S.level >= S.cleared
    S.cleared = max(S.cleared, S.level + 1)
    save_cleared(S.cleared)
    S.reward = level_reward(S.level, first)
    S.prog["coins"] += S.reward
    save_prog(S.prog)
    if S.info["boss"]:
        play("crown")
        go("crown", 40)
    else:
        play("win")
        go("clear", 30)


def cut_piece(snap, rc, e, p, up=1.0):
    rc = pygame.Rect(int(rc[0]), int(rc[1]), int(rc[2]), int(rc[3])).clip(pygame.Rect(0, 0, W, H))
    if rc.w < 3 or rc.h < 3:
        return None
    try:
        img = snap.subsurface(rc).copy()
    except Exception:
        return None
    d = 1 if e.x >= p.x else -1
    return {"img": img, "x": rc.centerx, "y": rc.centery, "vx": d * random.uniform(2, 7) + random.uniform(-2, 2),
            "vy": -random.uniform(9, 16) * up, "rot": 0.0, "spin": random.uniform(-14, 14), "r": rc.h / 2.0}


def regions(e):
    k, x, y = e.k, e.x, e.y
    return {"arms": [(x - 52 * k, y - 110 * k, 34 * k, 70 * k), (x + 18 * k, y - 110 * k, 34 * k, 70 * k)],
            "legs": [(x - 26 * k, y - 48 * k, 26 * k, 54 * k), (x, y - 48 * k, 26 * k, 54 * k)]}


def draw_heart(surf, x, y, r, t):
    r = r * (1.0 + 0.12 * abs(math.sin(t * 0.18)))
    x, y, r = int(x), int(y), int(r)
    for c, rr in (((90, 0, 10), r + 3), ((220, 20, 40), r)):
        pygame.draw.circle(surf, c, (x - rr // 2, y - rr // 3), rr // 2 + 1)
        pygame.draw.circle(surf, c, (x + rr // 2, y - rr // 3), rr // 2 + 1)
        pygame.draw.polygon(surf, c, [(x - rr, y - rr // 4), (x + rr, y - rr // 4), (x, y + rr)])
    pygame.draw.circle(surf, (255, 150, 160), (x - r // 2, y - r // 2), max(2, r // 5))


def update_pieces():
    for pc in S.pieces:
        pc["x"] += pc["vx"]
        pc["y"] += pc["vy"]
        pc["vy"] += 0.9
        pc["rot"] += pc["spin"]
        floor = GROUND + 6 - min(14, pc["r"] * 0.3)
        if pc["y"] > floor:
            pc["y"] = floor
            pc["vy"] = -pc["vy"] * 0.35 if abs(pc["vy"]) > 3 else 0
            pc["vx"] *= 0.7
            pc["spin"] *= 0.6


def draw_pieces(surf):
    for pc in S.pieces:
        try:
            im = pygame.transform.rotate(pc["img"], pc["rot"])
            surf.blit(im, (int(pc["x"] - im.get_width() / 2), int(pc["y"] - im.get_height() / 2)))
        except Exception:
            pass


# ---------------------------------------------------------------- drawing helpers
def draw_hud():
    p, e = S.player, S.enemy
    pygame.draw.rect(canvas, (70, 18, 18), (20, 20, 300, 20))
    wv = int(300 * max(p.hp, 0) / float(p.maxhp))
    pygame.draw.rect(canvas, (60, 200, 90), (20, 20, wv, 20))
    pygame.draw.rect(canvas, (20, 20, 30), (20, 20, 300, 20), 2)
    pygame.draw.rect(canvas, (70, 18, 18), (480, 20, 300, 20))
    wv = int(300 * max(e.hp, 0) / float(e.maxhp))
    fill = (225, 70, 45) if S.info["boss"] else (60, 200, 90)
    pygame.draw.rect(canvas, fill, (780 - wv, 20, wv, 20))
    pygame.draw.rect(canvas, (20, 20, 30), (480, 20, 300, 20), 2)
    text(canvas, "LEVEL %d / %d" % (S.level + 1, NUM_LEVELS), small, (255, 255, 255), (W // 2, 24))
    text(canvas, S.info["world_name"], f22, (230, 230, 200), (W // 2, 44), True)
    pygame.draw.rect(canvas, (40, 30, 70), (20, 44, 150, 8))
    pygame.draw.rect(canvas, (255, 255, 120) if p.energy >= 100 else (140, 90, 230), (20, 44, int(150 * p.energy / 100.0), 8))
    pygame.draw.rect(canvas, (20, 20, 30), (20, 44, 150, 8), 1)
    nm = ("" if getattr(e, "dragon", False) else ("GIANT  " if S.info["boss"] else "")) + e.name
    ew = small.render(nm, True, (255, 200, 190) if S.info["boss"] else (255, 225, 200))
    canvas.blit(ew, (780 - ew.get_width(), 46))
    pw = small.render(WEAPONS[p.weapon]["name"], True, (255, 235, 170))
    canvas.blit(pw, (92, 77))
    draw_coin(canvas, 760, 84, 9)
    cn = f24.render(str(S.prog["coins"]), True, (255, 230, 130))
    canvas.blit(cn, (746 - cn.get_width(), 75))
    if p.crowns > 0:
        draw_crown(canvas, 108, 108, 9, 3)
        cw = f24.render("x%d" % p.crowns, True, (255, 230, 150))
        canvas.blit(cw, (122, 98))


def draw_crown_row(surf, y, earned, size=15):
    for i in range(16):
        cx = int(W / 2 + (i - 7.5) * (size * 3.4))
        draw_crown(surf, cx, y, size, 3 + (i % 3), muted=(i >= earned))


def sparkle(surf, cx, cy, r, col):
    pts = []
    for i in range(8):
        a = i * math.pi / 4
        rr = r if i % 2 == 0 else r * 0.3
        pts.append((cx + math.cos(a) * rr, cy + math.sin(a) * rr))
    pygame.draw.polygon(surf, col, pts)


def draw_world_scene(world):
    draw_bg(canvas, world)
    draw_overlay(canvas, world, S.frame)


def tapped(rc):
    return S.tap is not None and rc.collidepoint(int(S.tap[0]), int(S.tap[1]))


def down(rc):
    return any(rc.collidepoint(int(hx), int(hy)) for hx, hy in S.held)


# ---------------------------------------------------------------- the game
def main():
    boot_flags()
    setup()
    print("fighter: loaded, entering menu")
    S.cleared = load_cleared()
    S.prog = load_prog()
    # menu demo: hero vs a giant
    demo_p = Fighter(150, PLAYER_LOOK, 9, 1)
    demo_g = Fighter(690, make_giant_look(3), 4, 3, 1.35)
    demo_p.facing, demo_g.facing = 1, -1
    demo_p.crowns = min(16, S.cleared // 5)
    set_music("menu")

    while S.running:
        S.frame += 1
        if S.tap_lock > 0:
            S.tap_lock -= 1
        poll_audio()

        taps, mouse_taps, saw_finger = [], [], False
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                S.running = False
            elif e.type == pygame.FINGERDOWN:
                S.fingers[e.finger_id] = (e.x * SW, e.y * SH)
                taps.append((e.x * SW, e.y * SH))
                saw_finger = True
            elif e.type == pygame.FINGERMOTION:
                S.fingers[e.finger_id] = (e.x * SW, e.y * SH)
                saw_finger = True
            elif e.type == pygame.FINGERUP:
                S.fingers.pop(e.finger_id, None)
            elif e.type == pygame.MOUSEBUTTONDOWN:
                mouse_taps.append(e.pos)
        if not saw_finger and not S.fingers:
            taps += mouse_taps
        points = list(S.fingers.values())
        if not points and pygame.mouse.get_pressed()[0]:
            points = [pygame.mouse.get_pos()]
        S.held = [((px - ox) / scale, (py - oy) / scale_y) for px, py in points]
        S.tap = None
        if taps and S.tap_lock == 0:
            S.tap = ((taps[0][0] - ox) / scale, (taps[0][1] - oy) / scale_y)

        active = set()
        for hx, hy in S.held:
            best = None
            for name, rc in BUTTONS.items():
                pad = HIT_PAD.get(name, 10)
                if rc.inflate(pad * 2, pad * 2).collidepoint(int(hx), int(hy)):
                    d = (hx - rc.centerx) ** 2 + (hy - rc.centery) ** 2
                    if best is None or d < best[0]:
                        best = (d, name)
            if best is not None:
                active.add(best[1])
        swap_now = "swap" in active and not S.prev_swap
        S.prev_swap = "swap" in active
        st = S.state

        # ------------------------------------------------ logic
        if st == "menu":
            for d in (demo_p, demo_g):
                if d.atk > 0:
                    d.atk -= 1
            if S.frame % 110 == 20:
                demo_p.atk = demo_p.atk_total = 12
            if S.frame % 160 == 70:
                demo_g.atk = demo_g.atk_total = 30
            demo_p.t += 1
            demo_g.t += 1
            if tapped(MENU_PLAY):
                play("click")
                start_level(min(S.cleared, NUM_LEVELS - 1))
            elif tapped(MENU_LEVELS):
                play("click")
                go("levels")
            elif tapped(MENU_SHOP):
                play("click")
                go("shop")
            elif tapped(MENU_SOUND):
                toggle_sound()
                play("click")
                S.tap_lock = 8
            elif tapped(MENU_QUIT):
                S.running = False

        elif st == "shop":
            if S.msg_t > 0:
                S.msg_t -= 1
            if tapped(BTN_BACK):
                play("click")
                go("menu")
            else:
                for i, rc in enumerate(SHOP_BUY):
                    kind = UP_NAMES[i]
                    if tapped(rc):
                        lvl = S.prog[kind]
                        cost = up_cost(kind, lvl)
                        if lvl < UP_MAX and S.prog["coins"] >= cost:
                            S.prog["coins"] -= cost
                            S.prog[kind] = lvl + 1
                            save_prog(S.prog)
                            play("crown")
                            S.msg_t = 0
                        else:
                            play("block")
                            S.msg_t = 40
                        S.tap_lock = 8

        elif st == "levels":
            if tapped(BTN_BACK):
                play("click")
                go("menu")
            else:
                for i, rc in enumerate(GRID):
                    if tapped(rc) and i <= S.cleared and i < NUM_LEVELS:
                        play("click")
                        start_level(i)
                        break

        elif st == "banner":
            S.banner_t -= 1
            S.anim += 1
            if S.banner_t <= 0 or (S.tap is not None and S.anim > 20):
                go("play", 8)

        elif st == "play":
            p, e = S.player, S.enemy
            if tapped(BUTTONS["exit"]):
                play("click")
                go("menu")
            else:
                p.want_cast = "power" in active
                p.update("left" in active, "right" in active, "jump" in active,
                         "attack" in active, "block" in active, swap_now, e)
                if getattr(e, "dragon", False):
                    e.update(p)
                else:
                    e.update(*ai_input(e, p), False, p)
                dx = p.x - e.x
                sep = 18 * (p.k + e.k)
                if getattr(e, "dragon", False):
                    p.x = max(30, min(p.x, e.x - 70) if p.x < e.x else p.x)
                elif abs(dx) < sep:
                    push = 3 if dx >= 0 else -3
                    p.x += push
                    e.x -= push
                update_bullets(p, e)
                update_particles()
                if SHAKE[0] > 0:
                    SHAKE[0] -= 1
                if S.frame % 150 == 0:
                    mark("ok")
                if S.frame % 120 == 0 and not LITE[0]:
                    if clock.get_fps() < 38:
                        S.slow += 1
                        if S.slow >= 3:
                            LITE[0] = True
                    else:
                        S.slow = 0
                if e.hp <= 0 and S.round == 1 and not S.info.get("dragon"):
                    BULLETS[:] = []
                    S.round = 2
                    e.hp = 1
                    e.dead_img = None
                    go("transform", 0)
                elif e.hp <= 0 and not S.info.get("dragon"):
                    BULLETS[:] = []
                    e.hp = 1
                    S.pieces = []
                    S.hide_e = False
                    S.fin = None
                    S.zoom = 1.0
                    go("finish", 0)
                elif e.hp <= 0:
                    BULLETS[:] = []
                    win_level()
                elif p.hp <= 0:
                    BULLETS[:] = []
                    play("ko")
                    S.reward = 5
                    S.prog["coins"] += S.reward
                    save_prog(S.prog)
                    go("lose", 30)

        elif st == "finish":
            p, e = S.player, S.enemy
            S.anim += 1
            a = S.anim
            p.t += 1
            e.t += 1
            e.atk = 0
            e.blocking = False
            f = 1 if e.x > p.x else -1
            p.facing = f
            p.moving = False
            S.zoom = 1.0 + 1.15 * min(1.0, a / 80.0) ** 0.7
            p.stun = 0
            e.stun = 0
            p.energy = e.energy = 0.0
            p.cast = e.cast = 0
            if a == 1:
                e.aura = 0.0
                e.moving = False
                snap = pygame.Surface((W, H), pygame.SRCALPHA)
                e.hp = 1
                e.draw(snap)
                S.fin = {"snap": snap, "dy": 0.0, "drop": False, "heart": None, "hx": 0, "hy": 0, "arms": False, "legs": False}
                S.hide_e = True
                S.pieces = []
                play("rumble")
            if a == 8:
                play("finishhim")
            if a == 26:
                p.redeyes = True
                p.aura_col = (255, 30, 30)
                p.aura = 1.0
                play("heart")
            if a == 50:
                play("heart")
            if 40 <= a < 66:
                tx = e.x - f * 85
                if abs(tx - p.x) > 4:
                    p.x += 6 * (1 if tx > p.x else -1)
                    p.moving = True
                    p.walk += 0.5
            fin = S.fin
            if fin is not None:
                snap = fin["snap"]
                rg = regions(e)
                if a in (70, 82):
                    p.atk = p.atk_total = 14
                if a == 74 and not fin["arms"]:
                    fin["arms"] = True
                    for rc in rg["arms"]:
                        pc = cut_piece(snap, rc, e, p)
                        if pc:
                            S.pieces.append(pc)
                        snap.fill((0, 0, 0, 0), pygame.Rect(int(rc[0]), int(rc[1]), int(rc[2]), int(rc[3])))
                    play("rip")
                    SHAKE[0] = 10
                    spark(e.x, e.y - 90, 12, (255, 245, 170), 9)
                if a in (105, 117):
                    p.atk = p.atk_total = 14
                if a == 109 and not fin["legs"]:
                    fin["legs"] = True
                    fin["drop"] = True
                    for rc in rg["legs"]:
                        pc = cut_piece(snap, rc, e, p, 0.7)
                        if pc:
                            S.pieces.append(pc)
                        snap.fill((0, 0, 0, 0), pygame.Rect(int(rc[0]), int(rc[1]), int(rc[2]), int(rc[3])))
                    play("rip")
                    SHAKE[0] = 10
                    spark(e.x, e.y - 30, 12, (255, 245, 170), 9)
                if fin["drop"] and fin["dy"] < 48 * e.k:
                    fin["dy"] = min(48 * e.k, fin["dy"] + 5 * e.k)
                if a == 140:
                    p.atk = p.atk_total = 14
                    play("rip")
                    SHAKE[0] = 14
                    fin["heart"] = 0
                    fin["hx"], fin["hy"] = e.x, e.y - (70 - 48) * e.k
                    spark(e.x, e.y - 60 * e.k, 14, (255, 80, 90), 9)
                if fin["heart"] is not None:
                    fin["heart"] += 1
                    tx, ty = p.x + f * 52 * p.k, p.y - 108 * p.k
                    q = min(1.0, fin["heart"] / 25.0)
                    fin["hx"] += (tx - fin["hx"]) * (0.2 + 0.3 * q)
                    fin["hy"] += (ty - fin["hy"]) * (0.2 + 0.3 * q)
                    if a >= 150:
                        p.atk = max(p.atk, 1)
                        p.atk_total = 2 * p.atk
                if a == 172:
                    play("fatality")
                    SHAKE[0] = 16
                    play("stomp")
            if a < 60 and p.atk > 0:
                p.atk -= 1
            elif 60 <= a < 150 and p.atk > 0:
                p.atk -= 1
            if S.pieces:
                update_pieces()
            if a % 6 == 0 and 66 < a < 160:
                spark(p.x + f * 40, p.y - 100, 2, (255, 60, 60), 5)
            if SHAKE[0] > 0:
                SHAKE[0] -= 1
            update_particles()
            if a >= 310:
                S.hide_e = False
                S.pieces = []
                S.fin = None
                S.zoom = 1.0
                p.redeyes = False
                p.aura = 0.0
                win_level()

        elif st == "transform":
            p, e = S.player, S.enemy
            S.anim += 1
            a = S.anim
            for fx in (p, e):
                fx.t += 1
                fx.atk = 0
                fx.moving = False
                fx.blocking = False
            p.aura = e.aura = min(1.0, a / 50.0)
            if a == 2:
                play("scream")
            if a == 22:
                play("scream2")
            if a % 6 == 0:
                spark(p.x, p.y - 60, 4, (255, 230, 120), 7)
                spark(e.x, e.y - 60, 4, e.aura_col if e.sup else (200, 220, 255), 7)
            if a < 70:
                SHAKE[0] = max(SHAKE[0], 3)
            if a == 70:
                play("flash")
                SHAKE[0] = 14
                go_super(p, (255, 225, 80), (255, 205, 40))
                ecols = [((230, 250, 255), (120, 200, 255)), ((255, 120, 100), (255, 70, 70)),
                         ((235, 205, 255), (190, 120, 255)), ((215, 255, 225), (90, 255, 160))]
                eh, ea = ecols[S.level % 4]
                go_super(e, eh, ea)
                p.hp = p.maxhp
                e.maxhp = int(e.maxhp * 1.25)
                e.hp = e.maxhp
                e.dmg_mult *= 1.25
                e.speed *= 1.15
                p.speed *= 1.1
                if isinstance(e.ai, dict):
                    e.ai = dict(e.ai, atk=e.ai.get("atk", 0.05) * 1.4, blk=e.ai.get("blk", 0.1) * 1.2)
                p.dead_img = e.dead_img = None
                for _ in range(2):
                    spark(p.x, p.y - 70, 14, (255, 240, 160), 9)
                    spark(e.x, e.y - 70, 14, ea, 9)
            if SHAKE[0] > 0:
                SHAKE[0] -= 1
            update_particles()
            if a >= 100:
                go("play", 8)

        elif st == "clear":
            update_particles()
            if tapped(BTN_C):
                play("click")
                start_level(S.level + 1)
            elif tapped(BTN_D):
                play("click")
                go("menu")

        elif st == "crown":
            S.anim += 1
            if tapped(BTN_E2):
                play("click")
                if S.level >= NUM_LEVELS - 1:
                    go("victory", 30)
                else:
                    start_level(S.level + 1)

        elif st == "lose":
            update_particles()
            if tapped(BTN_A):
                play("click")
                start_level(S.level, retry=True)
            elif tapped(BTN_B):
                play("click")
                go("menu")

        elif st == "victory":
            S.anim += 1
            if tapped(BTN_E):
                play("click")
                go("menu")

        # ------------------------------------------------ drawing
        st = S.state
        sx = sy = 0
        if st == "menu":
            draw_world_scene(0)
            demo_p.draw(canvas)
            demo_g.draw(canvas)
            text(canvas, "SHADOW FIGHTER", title_f, (255, 225, 120), (W // 2, 54))
            text(canvas, "WAR OF THE GIANTS", mid, (235, 235, 235), (W // 2, 100))
            draw_ui_button(canvas, MENU_PLAY, "PLAY" if S.cleared == 0 else "CONTINUE", (60, 170, 90), down(MENU_PLAY))
            draw_ui_button(canvas, MENU_LEVELS, "LEVELS", (70, 90, 160), down(MENU_LEVELS))
            draw_ui_button(canvas, MENU_SHOP, "SHOP", (190, 140, 30), down(MENU_SHOP))
            draw_coin(canvas, 30, 428, 13)
            text(canvas, str(S.prog["coins"]), mid, (255, 230, 130), (78, 428))
            draw_ui_button(canvas, MENU_QUIT, "QUIT", (150, 50, 50), down(MENU_QUIT))
            draw_ui_round(canvas, MENU_SOUND, (205, 140, 40), down(MENU_SOUND),
                          icon="sound_on" if SOUND_ON[0] else "sound_off")
            draw_crown_row(canvas, 402, crowns_earned(), 14)
            text(canvas, "Level %d / %d    Crowns %d / 16" % (min(S.cleared + 1, NUM_LEVELS), NUM_LEVELS, crowns_earned()),
                 f26, (255, 240, 200), (W // 2, 430))
            if FLAGS:
                text(canvas, "mode: " + " ".join(sorted(FLAGS)), f20, (255, 200, 120), (90, 440))
        elif st == "shop":
            draw_world_scene(min(15, S.cleared // 5))
            canvas.blit(dim, (0, 0))
            text(canvas, "SHOP", font, (255, 225, 120), (W // 2 - 30, 44))
            draw_coin(canvas, W // 2 + 56, 44, 14)
            text(canvas, str(S.prog["coins"]), mid, (255, 230, 130), (W // 2 + 110, 44))
            info_rows = [("POWER", "Hit harder  +8%", (215, 80, 60)),
                         ("HEALTH", "More life  +10", (70, 190, 100)),
                         ("ARMOR", "Take less damage  -4%", (70, 130, 220))]
            for i in range(3):
                kind = UP_NAMES[i]
                rc = SHOP_ROWS[i]
                lvl = S.prog[kind]
                pygame.draw.rect(canvas, (25, 28, 45), rc, 0, 10)
                pygame.draw.rect(canvas, info_rows[i][2], rc, 3, 10)
                canvas.blit(mid.render(info_rows[i][0], True, (255, 255, 255)), (rc.x + 16, rc.y + 8))
                canvas.blit(f22.render(info_rows[i][1], True, (210, 215, 230)), (rc.x + 16, rc.y + 44))
                for k2 in range(UP_MAX):
                    col = info_rows[i][2] if k2 < lvl else (60, 62, 80)
                    pygame.draw.rect(canvas, col, (rc.x + 210 + k2 * 22, rc.y + 28, 18, 18), 0, 4)
                brc = SHOP_BUY[i]
                if lvl >= UP_MAX:
                    draw_ui_button(canvas, brc, "MAX", (90, 90, 100), False)
                else:
                    cost = up_cost(kind, lvl)
                    ok = S.prog["coins"] >= cost
                    draw_ui_button(canvas, brc, " %d" % cost, (60, 170, 90) if ok else (110, 70, 70), down(brc))
                    draw_coin(canvas, brc.x + 26, brc.centery, 11)
            if S.msg_t > 0:
                text(canvas, "Not enough coins!", mid, (255, 130, 110), (W // 2, 372))
            draw_ui_button(canvas, BTN_BACK, "BACK", (70, 90, 150), down(BTN_BACK))
        elif st == "levels":
            draw_world_scene(min(15, S.cleared // 5))
            canvas.blit(dim, (0, 0))
            text(canvas, "SELECT LEVEL", font, (255, 225, 120), (W // 2, 44))
            for i, rc in enumerate(GRID):
                boss = (i % 5 == 4)
                if i > S.cleared:
                    draw_ui_round(canvas, rc, (95, 95, 105), False, icon="lock")
                elif boss:
                    draw_ui_round(canvas, rc, (200, 60, 50) if i >= S.cleared else (190, 140, 30), down(rc), icon="crown")
                else:
                    draw_ui_round(canvas, rc, (60, 160, 90) if i < S.cleared else (70, 120, 210), down(rc), label=str(i + 1))
            text(canvas, "Crown = giant boss", f24, (255, 220, 200), (W // 2, 376))
            draw_ui_button(canvas, BTN_BACK, "BACK", (70, 90, 150), down(BTN_BACK))
        else:
            info = S.info
            draw_world_scene(info["world"])
            if S.state in ("play", "banner", "transform", "finish", "clear", "crown", "lose", "victory"):
                if st == "finish":
                    black = pygame.Surface((W, H))
                    black.fill((0, 0, 0))
                    black.set_alpha(int(255 * min(1.0, S.anim / 36.0)))
                    canvas.blit(black, (0, 0))
                    if S.anim > 36:
                        pygame.draw.rect(canvas, (22, 0, 0), (0, GROUND, W, H - GROUND))
                        pygame.draw.line(canvas, (90, 0, 0), (0, GROUND), (W, GROUND), 2)
                S.player.draw(canvas)
                if not (st == "finish" and S.hide_e):
                    S.enemy.draw(canvas)
                if st == "finish" and S.fin is not None:
                    canvas.blit(S.fin["snap"], (0, int(S.fin["dy"])))
                    if S.fin["heart"] is not None:
                        draw_heart(canvas, S.fin["hx"], S.fin["hy"], 15, S.anim)
                if st == "finish" and S.pieces:
                    draw_pieces(canvas)
                draw_bullets(canvas)
                if st == "finish" and S.zoom > 1.01:
                    z = S.zoom
                    cx = (S.player.x + S.enemy.x) / 2.0
                    ww, hh = W / z, H / z
                    x0 = max(0, min(W - ww, cx - ww / 2.0))
                    y0 = max(0, min(H - hh, GROUND - 78 - hh / 2.0))
                    try:
                        sub = canvas.subsurface(pygame.Rect(int(x0), int(y0), int(ww), int(hh)))
                        canvas.blit(pygame.transform.scale(sub, (W, H)), (0, 0))
                    except Exception:
                        pass
                draw_particles(canvas)
            if st not in ("crown", "victory") and not (st == "finish" and S.anim > 6):
                draw_hud()
            if st in ("play", "banner"):
                for name in BUTTONS:
                    draw_control(canvas, name, name in active)
            if st in ("play", "transform") and S.round == 2:
                text(canvas, "ROUND 2  -  SUPER FORM", small, (255, 230, 120), (W // 2, 116))
            elif st == "play":
                text(canvas, "ROUND 1 / 2", small, (230, 230, 230), (W // 2, 116))
            if st == "finish":
                a = S.anim
                if 8 <= a < 150:
                    text(canvas, "FINISH HIM", big, (225, 25, 25), (W // 2 + random.randint(-3, 3), 70 + random.randint(-2, 2)))
                if a >= 172:
                    sh = 4 if a < 200 else 1
                    text(canvas, "FATALITY", big, (255, 40, 30) if (a // 4) % 2 == 0 else (255, 235, 210),
                         (W // 2 + random.randint(-sh, sh), 80 + random.randint(-sh, sh)))
            if st == "transform":
                a = S.anim
                if a > 12:
                    text(canvas, "POWER UP!" if a < 70 else "SUPER FORM!", big, (255, 235, 110),
                         (W // 2 + random.randint(-3, 3), 160 + random.randint(-2, 2)))
                if 68 <= a <= 78:
                    fl = pygame.Surface((W, H))
                    fl.fill((255, 255, 255))
                    fl.set_alpha(int(255 * (1 - abs(a - 70) / 9.0)))
                    canvas.blit(fl, (0, 0))
            if SHAKE[0] > 0 and st in ("play", "transform", "finish"):
                sx, sy = random.randint(-4, 4), random.randint(-3, 3)
            if st == "banner":
                canvas.blit(dim, (0, 0))
                jit = 0
                if info["boss"]:
                    jit = random.randint(-3, 3) if S.anim < 40 else 0
                    text(canvas, "FINAL BOSS" if info.get("dragon") else "GIANT BOSS", big, (255, 90, 70), (W // 2 + jit, 130))
                    text(canvas, info["name"], font, (255, 225, 120), (W // 2, 195))
                    text(canvas, "Level %d  -  %s" % (info["L"] + 1, info["world_name"]), mid, (255, 255, 255), (W // 2, 240))
                else:
                    text(canvas, "LEVEL %d" % (info["L"] + 1), big, (255, 225, 120), (W // 2, 130))
                    text(canvas, info["world_name"], font, (255, 255, 255), (W // 2, 195))
                    text(canvas, "VS  " + info["name"], mid, (255, 200, 190), (W // 2, 240))
                text(canvas, "FIGHT!" if S.banner_t < 25 else "Get ready", mid, (255, 255, 255), (W // 2, 290))
            elif st == "clear":
                canvas.blit(dim, (0, 0))
                text(canvas, "LEVEL CLEAR!", big, (130, 240, 150), (W // 2, 140))
                draw_coin(canvas, W // 2 - 50, 196, 13)
                text(canvas, "+%d" % S.reward, font, (255, 230, 130), (W // 2 + 10, 196))
                draw_ui_button(canvas, BTN_C, "NEXT", (60, 170, 90), down(BTN_C))
                draw_ui_button(canvas, BTN_D, "MENU", (70, 90, 150), down(BTN_D))
            elif st == "lose":
                canvas.blit(dim, (0, 0))
                text(canvas, "K.O.!", big, (255, 110, 110), (W // 2, 140))
                draw_coin(canvas, W // 2 - 40, 196, 13)
                text(canvas, "+%d" % S.reward, font, (255, 230, 130), (W // 2 + 10, 196))
                draw_ui_button(canvas, BTN_A, "RETRY", (205, 140, 40), down(BTN_A))
                draw_ui_button(canvas, BTN_B, "MENU", (70, 90, 150), down(BTN_B))
            elif st == "crown":
                canvas.blit(dim, (0, 0))
                a = S.anim
                for i in range(14):
                    ang = i * math.pi / 7 + a * 0.012
                    pygame.draw.line(canvas, (120, 96, 40), (W // 2, 170),
                                     (int(W // 2 + math.cos(ang) * 420), int(170 + math.sin(ang) * 420)), 3)
                text(canvas, "GIANT DEFEATED!", font, (255, 120, 90), (W // 2, 38))
                text(canvas, info["name"], mid, (255, 225, 190), (W // 2, 78))
                size = 62 + 5 * math.sin(a * 0.12)
                draw_crown(canvas, W // 2, 205, int(size), 5)
                for i in range(9):
                    ang = i * 0.7 + a * 0.03
                    rr = 118 + 12 * math.sin(a * 0.1 + i)
                    sparkle(canvas, int(W // 2 + math.cos(ang) * rr * 1.5), int(160 + math.sin(ang) * rr * 0.6),
                            6 + (i % 3) * 3, (255, 240, 170) if i % 2 == 0 else (255, 255, 255))
                text(canvas, "YOU GOT A CROWN!   %d / 16" % crowns_earned(), font, (255, 230, 120), (W // 2, 292))
                draw_coin(canvas, W // 2 - 40, 322, 11)
                text(canvas, "+%d" % S.reward, mid, (255, 230, 130), (W // 2 + 14, 322))
                draw_crown_row(canvas, 372, crowns_earned(), 12)
                draw_ui_button(canvas, BTN_E2, "CONTINUE", (60, 170, 90), down(BTN_E2))
            elif st == "victory":
                canvas.blit(dim, (0, 0))
                a = S.anim
                for i in range(14):
                    ang = i * math.pi / 7 + a * 0.012
                    pygame.draw.line(canvas, (120, 96, 40), (W // 2, 150),
                                     (int(W // 2 + math.cos(ang) * 420), int(150 + math.sin(ang) * 420)), 3)
                text(canvas, "CHAMPION!", big, (255, 225, 120), (W // 2, 70))
                draw_crown(canvas, W // 2, 180, int(70 + 4 * math.sin(a * 0.1)), 7)
                text(canvas, "All 80 levels. Giants and Dragons!", font, (255, 255, 255), (W // 2, 250))
                draw_crown_row(canvas, 322, 16, 14)
                draw_ui_button(canvas, BTN_E, "MENU", (70, 90, 150), down(BTN_E))

        screen.fill((0, 0, 0))
        scaled = pygame.transform.scale(canvas, (int(W * scale) + 1, int(H * scale_y) + 1))
        screen.blit(scaled, (int(ox) + sx, int(oy) + sy))
        pygame.display.flip()
        if S.frame == 45:
            mark("ok")
        clock.tick(60)

    mark("ok")
    pygame.quit()


try:
    if __name__ == "__main__":
        main()
except BaseException:
    import traceback
    show_error(traceback.format_exc())
    try:
        pygame.quit()
    except Exception:
        pass
