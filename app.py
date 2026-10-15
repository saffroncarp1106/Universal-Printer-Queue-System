######################

import tkinter as tk
from tkinter import filedialog, messagebox
import os, math, io, threading, re as re_, random

try:
    from tkinterdnd2 import TkinterDnD, DND_FILES
    HAS_DND = True
except ImportError:
    HAS_DND = False

try:
    from PIL import Image, ImageTk
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

from processor import generate_queue, get_file_info, suggest_queue_output_path

# ── Palette ───────────────────────────────────────────────────────────────────
BG      = "#08080f"
PANEL   = "#0e0e1c"
PANEL2  = "#141428"
PANEL3  = "#0a0a16"
BORDER  = "#20203a"
BORDER2 = "#30305a"
ACC     = "#8866ff"
ACC2    = "#aa88ff"
ACCDIM  = "#2a1a66"
ACC_B   = "#44aaff"
ACC_B2  = "#88ccff"
DIM     = "#303050"
TEXT    = "#dde0f0"
TEXTDIM = "#555578"
RED     = "#ff3355"
GREEN   = "#33ffaa"

MONO_SM = ("Courier New", 8)
MONO    = ("Courier New", 10)
UI      = ("Segoe UI", 9)

SPOOL_MAX_G_DEFAULT = 1000.0
ANIM_ENABLED = True   # global flag


def trunc(s, n=10):
    return (s[:n] + "…") if len(s) > n + 1 else s

def lerp(a, b, t):
    return a + (b - a) * t

def lerp_color(a, b, t):
    def h2r(h):
        h = h.lstrip("#")
        return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
    ra,ga,ba = h2r(a); rb,gb,bb = h2r(b)
    r = int(ra+(rb-ra)*t); g = int(ga+(gb-ga)*t); bl = int(ba+(bb-ba)*t)
    return f"#{max(0,min(255,r)):02x}{max(0,min(255,g)):02x}{max(0,min(255,bl)):02x}"

def parse_drop_paths(data):
    paths = re_.findall(r'\{([^}]+)\}', data)
    paths += re_.sub(r'\{[^}]+\}', '', data).split()
    return [p.strip() for p in paths if p.strip().lower().endswith(".gcode")]


# ── Animated Header ───────────────────────────────────────────────────────────

class AnimHeader(tk.Canvas):
    """Starfield + sweeping gradient + pulsing title."""
    def __init__(self, parent, **kw):
        super().__init__(parent, height=66, bg="#04040c",
                         highlightthickness=0, **kw)
        self._t  = random.uniform(0, 6.28)
        self._stars = []
        self.bind("<Configure>", lambda e: self._init_stars())
        self._init_stars()
        self._tick()

    def _init_stars(self):
        W = self.winfo_width() or 820
        rng = random.Random(99)
        self._stars = [
            {"x": rng.uniform(0, W), "y": rng.uniform(6, 60),
             "v": rng.uniform(0.08, 0.45), "r": rng.uniform(0.5, 1.8),
             "b": rng.uniform(0.25, 1.0), "ph": rng.uniform(0, 6.28)}
            for _ in range(70)
        ]

    def _tick(self):
        self._t += 0.016
        if ANIM_ENABLED:
            W = self.winfo_width() or 820
            for s in self._stars:
                s["x"] = (s["x"] + s["v"]) % W
        self._draw()
        self.after(25, self._tick)

    def _draw(self):
        self.delete("all")
        W = self.winfo_width() or 820
        H = 66
        self.create_rectangle(0, 0, W, H, fill="#04040c", outline="")

        # Sweeping nebula glow
        if ANIM_ENABLED:
            gx = int(W * (0.5 + 0.5 * math.sin(self._t * 0.28)))
            for xi in range(max(0, gx-140), min(W, gx+140), 2):
                d = abs(xi - gx) / 140
                a = int((1-d*d) * 18)
                self.create_line(xi, 0, xi, H,
                                 fill=f"#{a//3:02x}{a//6:02x}{min(255,a*2):02x}", width=2)

        # Stars
        for s in self._stars:
            bv = (int(s["b"] * (150 + 60 * math.sin(self._t + s["ph"])))
                  if ANIM_ENABLED else int(s["b"] * 140))
            col = f"#{bv//5:02x}{bv//5:02x}{min(255,bv):02x}"
            r = s["r"]
            self.create_oval(s["x"]-r, s["y"]-r, s["x"]+r, s["y"]+r,
                             fill=col, outline="")

        # Diagonal slash deco
        for i in range(16):
            x = 14 + i*15
            self.create_line(x+16, 2, x, 64, fill="#0d0d22", width=9)

        # Left glow bar
        if ANIM_ENABLED:
            pulse = 0.55 + 0.45 * math.sin(self._t * 2.2)
            bv = int(pulse * 255)
            pcol = f"#{int(bv*0.53):02x}{int(bv*0.40):02x}{bv:02x}"
        else:
            pcol = ACC
        self.create_rectangle(0, 0, 4, H, fill=pcol, outline="")

        # Ghost glow behind title
        if ANIM_ENABLED:
            gv = int((0.3 + 0.2*math.sin(self._t*1.3)) * 40)
            self.create_text(25, 22,
                             text="PrintFarmQueue",
                             font=("Courier New", 15, "bold"),
                             fill=f"#{gv//3:02x}{gv//5:02x}{gv:02x}",
                             anchor="w")

        # Main title
        self.create_text(25, 22, text="PrintFarmQueue",
                         font=("Courier New", 15, "bold"), fill=ACC, anchor="w")
        self.create_text(26, 44, text="Saffroncarp1106  //  V0.1.0",
                         font=("Courier New", 8), fill=TEXTDIM, anchor="w")

        # Right badge
        self.create_rectangle(W-120, 10, W-8, 56, fill=PANEL, outline=BORDER2)
        if ANIM_ENABLED:
            glow = int((0.3+0.25*math.sin(self._t*0.7+1.5))*60)
            self.create_rectangle(W-120, 10, W-8, 56, fill="",
                                  outline=f"#{glow//6:02x}{glow//6:02x}{glow:02x}")
        self.create_text(W-64, 28, text="PRINT FARM",
                         font=MONO_SM, fill=TEXTDIM, anchor="center")
        self.create_text(W-64, 42, text="QUEUE",
                         font=("Courier New", 10, "bold"), fill=ACC_B, anchor="center")


# ── Animated Status Bar ───────────────────────────────────────────────────────

class AnimStatusBar(tk.Canvas):
    def __init__(self, parent, textvar, **kw):
        super().__init__(parent, height=26, bg="#030309",
                         highlightthickness=0, **kw)
        self._tv = textvar
        self._t  = 0.0
        self._shine_x = 0
        self.bind("<Configure>", lambda e: self._draw())
        textvar.trace_add("write", lambda *a: self._draw())
        self._tick()

    def _tick(self):
        if ANIM_ENABLED:
            self._t += 0.05
            self._shine_x = (self._shine_x + 3) % (self.winfo_width() + 80 or 900)
        self._draw()
        self.after(30, self._tick)

    def _draw(self):
        self.delete("all")
        W = self.winfo_width() or 820
        H = 26
        self.create_rectangle(0, 0, W, H, fill="#030309", outline="")

        if ANIM_ENABLED:
            # Scanlines
            for y in range(0, H, 3):
                self.create_line(0, y, W, y, fill="#05050d", width=1)
            # Moving shine
            sx = self._shine_x - 40
            for xi in range(max(0, sx), min(W, sx+50)):
                d = abs(xi-sx-25)/25
                a = int((1-d)*8)
                self.create_line(xi, 0, xi, H,
                                 fill=f"#{a:02x}{a//2:02x}{a*2:02x}", width=1)

        # Left accent bar
        self.create_rectangle(0, 0, 3, H, fill=ACC, outline="")

        # Animated pulse dot
        if ANIM_ENABLED:
            pr = 3 + int((math.sin(self._t*3.5)+1)*1.5)
            pcol = lerp_color(ACC, ACC_B, (math.sin(self._t*1.8)+1)/2)
        else:
            pr, pcol = 4, ACC
        self.create_oval(9-pr, H//2-pr, 9+pr, H//2+pr, fill=pcol, outline="")

        self.create_text(22, H//2, text=self._tv.get(),
                         font=("Courier New", 9), fill=TEXTDIM, anchor="w")


# ── Glow Button ───────────────────────────────────────────────────────────────

class GlowButton(tk.Canvas):
    """Animated generate button with pulsing glow and shimmer on hover."""
    def __init__(self, parent, text, command, **kw):
        super().__init__(parent, height=44, bg=BG,
                         highlightthickness=0, **kw)
        self._text = text
        self._cmd  = command
        self._hover = False
        self._enabled = True
        self._t = random.uniform(0, 6.28)
        self._shimmer_x = 0
        self.bind("<Configure>", lambda e: self._draw())
        self.bind("<Button-1>",  self._click)
        self.bind("<Enter>",     lambda e: self._set_hover(True))
        self.bind("<Leave>",     lambda e: self._set_hover(False))
        self.config(cursor="hand2")
        self._tick()

    def _tick(self):
        if ANIM_ENABLED:
            self._t += 0.055
            if self._hover:
                self._shimmer_x = (self._shimmer_x + 6) % (
                    self.winfo_width() + 60 or 500)
            self._draw()
        self.after(28, self._tick)

    def _set_hover(self, v):
        self._hover = v; self._draw()

    def set_enabled(self, v, text=None):
        self._enabled = v
        if text: self._text = text
        self._draw()

    def _click(self, e):
        if self._enabled: self._cmd()

    def _draw(self):
        self.delete("all")
        W = self.winfo_width() or 400
        H = 44
        if not self._enabled:
            self.create_rectangle(2, 2, W-2, H-2, fill=PANEL2, outline=BORDER)
            self.create_text(W//2, H//2, text=self._text,
                             font=("Courier New", 11, "bold"),
                             fill=TEXTDIM, anchor="center")
            return

        # Outer glow rings
        if ANIM_ENABLED:
            pulse = 0.45 + 0.55 * abs(math.sin(self._t * 1.4))
            for gi in range(6, 0, -1):
                gv = int(pulse * 38 * gi / 6)
                self.create_rectangle(-gi, -gi, W+gi, H+gi, fill="",
                                      outline=f"#{gv//4:02x}{gv//5:02x}{gv:02x}")

        # Fill gradient
        if ANIM_ENABLED:
            t_col = (math.sin(self._t * 0.8) + 1) / 2
            fill = lerp_color(ACC, ACC2, 0.3 + 0.3 * t_col)
        else:
            fill = ACC2 if self._hover else ACC

        for yi in range(H):
            t = yi / H
            row_col = lerp_color(fill, lerp_color(fill, "#111133", 0.4), t)
            self.create_line(0, yi, W, yi, fill=row_col, width=1)

        # Hover shimmer
        if ANIM_ENABLED and self._hover:
            sx = self._shimmer_x - 30
            for xi in range(max(0, sx), min(W, sx+50)):
                d = abs(xi - sx - 25) / 25
                a = int((1-d*d) * 45)
                self.create_line(xi, 0, xi, H,
                                 fill=f"#{min(255,a+180):02x}{min(255,a+180):02x}ff",
                                 width=1)

        # Top highlight
        self.create_line(1, 1, W-1, 1, fill="#555566", width=1)
        # Bottom shadow
        self.create_line(1, H-1, W-1, H-1, fill="#000000", width=1)

        self.create_text(W//2, H//2, text=self._text,
                         font=("Courier New", 11, "bold"),
                         fill="#111111", anchor="center")


# ── Panel with animated border ────────────────────────────────────────────────

class GlowPanel(tk.Frame):
    """A frame with a canvas border that pulses when active."""
    def __init__(self, parent, **kw):
        outer = tk.Frame(parent, bg=BG)
        # We expose outer as the geometry-managed widget
        self._outer = outer
        self._canvas_border = tk.Canvas(outer, height=2, bg=BG,
                                        highlightthickness=0)
        self._canvas_border.pack(fill="x", side="bottom")
        super().__init__(outer, bg=PANEL, **kw)
        self.pack(fill="both", expand=True)
        self._t = 0.0
        self._tick()

    def grid(self, **kw):
        self._outer.grid(**kw)

    def pack(self, **kw):
        # If called externally, route to outer
        if kw:
            self._outer.pack(**kw)
        else:
            super().pack(**kw)

    def _tick(self):
        if ANIM_ENABLED:
            self._t += 0.04
            self._canvas_border.delete("all")
            W = self._canvas_border.winfo_width() or 400
            gv = int((0.4 + 0.3*math.sin(self._t))*60)
            self._canvas_border.create_line(
                0, 0, W, 0,
                fill=f"#{gv//4:02x}{gv//4:02x}{gv:02x}", width=2)
        self._canvas_border.after(40, self._tick)


# ── Spool Widget ──────────────────────────────────────────────────────────────

class SpoolWidget(tk.Canvas):
    def __init__(self, parent, **kw):
        super().__init__(parent, bg=BG, highlightthickness=0, **kw)
        self._total_grams = 0.0
        self._max_g       = SPOOL_MAX_G_DEFAULT
        self._anim_pct    = 0.0
        self._target_pct  = 0.0
        self._rot         = 0.0
        self._t           = 0.0
        self.bind("<Configure>", lambda e: self._redraw())
        self._tick()

    def set_max(self, g):
        self._max_g = max(1.0, g); self._update_target()

    def set_total(self, g):
        self._total_grams = g; self._update_target()

    def _update_target(self):
        self._target_pct = min(self._total_grams / self._max_g, 1.0)

    def _tick(self):
        changed = abs(self._anim_pct - self._target_pct) > 0.001
        if changed:
            self._anim_pct += (self._target_pct - self._anim_pct) * 0.10
        if ANIM_ENABLED:
            self._rot = (self._rot + 0.7) % 360
            self._t  += 0.03
            self._redraw()
        elif changed:
            self._redraw()
        self.after(28, self._tick)

    def _redraw(self):
        self.delete("all")
        W  = self.winfo_width()  or 200
        H  = self.winfo_height() or 300
        SH = 80   # stats panel height
        PAD = 12
        sh  = max(90, H - SH - PAD * 2)
        R_o = min(W//2 - 14, sh//2 - 8)
        R_o = max(R_o, 30)
        R_i = max(int(R_o * 0.28), 12)
        R_h = max(int(R_o * 0.16), 7)
        cx  = W // 2
        cy  = PAD + sh // 2
        c   = self._anim_pct
        R_f = R_o - c * (R_o - R_i)

        # Outer glow
        if ANIM_ENABLED:
            gv = int((0.5 + 0.3*math.sin(self._t))*255)
            for gi in range(5, 0, -1):
                gvi = int(gv * gi / 5 * 0.25)
                self.create_oval(cx-R_o-gi*2, cy-R_o-gi*2,
                                 cx+R_o+gi*2, cy+R_o+gi*2,
                                 fill="", outline=f"#{gvi//5:02x}{gvi//5:02x}{gvi//2:02x}")

        # Shadow
        self.create_oval(cx-R_o+7, cy-R_o+7, cx+R_o+7, cy+R_o+7,
                         fill="#020208", outline="")

        # Filament body
        if R_f > R_i + 2:
            self.create_oval(cx-R_f, cy-R_f, cx+R_f, cy+R_f,
                             fill=ACCDIM, outline="")
            r = R_f - 2
            step = max(3, R_o // 24)
            while r > R_i + 2:
                col = lerp_color(ACCDIM, ACC, r / R_o)
                self.create_oval(cx-r, cy-r, cx+r, cy+r,
                                 fill="", outline=col, width=1)
                r -= step

        # Outer rim
        self.create_oval(cx-R_o, cy-R_o, cx+R_o, cy+R_o,
                         fill="", outline=BORDER2, width=3)
        self.create_oval(cx-R_o+4, cy-R_o+4, cx+R_o-4, cy+R_o-4,
                         fill="", outline=DIM, width=1)

        # Core hub
        self.create_oval(cx-R_i, cy-R_i, cx+R_i, cy+R_i,
                         fill=PANEL2, outline=BORDER2, width=2)
        rot_r = math.radians(self._rot if ANIM_ENABLED else 30)
        for i in range(6):
            a = rot_r + math.radians(i * 60)
            self.create_line(cx + R_h*math.cos(a), cy + R_h*math.sin(a),
                             cx + (R_i-3)*math.cos(a), cy + (R_i-3)*math.sin(a),
                             fill=BORDER2, width=2)
        self.create_oval(cx-R_h, cy-R_h, cx+R_h, cy+R_h,
                         fill=PANEL, outline=BORDER, width=2)

        # Consumed arc
        if c > 0.005:
            ext = c * 360
            self.create_arc(cx-R_o+6, cy-R_o+6, cx+R_o-6, cy+R_o-6,
                            start=90, extent=-ext, outline=ACC_B, width=2, style="arc")
            a  = math.radians(90 - ext)
            dx = (R_o-6)*math.cos(a)
            dy = -(R_o-6)*math.sin(a)
            if ANIM_ENABLED:
                gp = 3 + int((math.sin(self._t*4)+1)*2)
                dot_col = lerp_color(ACC_B, ACC_B2, (math.sin(self._t*3)+1)/2)
            else:
                gp, dot_col = 4, ACC_B2
            self.create_oval(cx+dx-gp, cy+dy-gp, cx+dx+gp, cy+dy+gp,
                             fill=dot_col, outline=ACC_B, width=1)

        # Hub text
        pct = c * 100
        col = RED if pct >= 100 else (ACC if pct > 75 else TEXT)
        if ANIM_ENABLED:
            col = lerp_color(col, ACC2, 0.15*math.sin(self._t*2))
        self.create_text(cx, cy-7, text=f"{pct:.0f}%",
                         font=("Courier New", max(8, R_h), "bold"),
                         fill=col, anchor="center")
        self.create_text(cx, cy+9, text="used",
                         font=MONO_SM, fill=TEXTDIM, anchor="center")

        # Stats panel
        py  = H - SH
        pl  = 8; pr = W - 8
        mid = W // 2

        # Panel bg with top glow line
        self.create_rectangle(pl, py, pr, py+SH-4, fill=PANEL, outline=BORDER2)
        if ANIM_ENABLED:
            gv2 = int((0.4 + 0.25*math.sin(self._t+1))*70)
            self.create_line(pl+2, py, pr-2, py,
                             fill=f"#{gv2//5:02x}{gv2//5:02x}{gv2:02x}", width=2)

        total = self._total_grams
        rem   = max(0.0, self._max_g - total)
        over  = total > self._max_g

        row1y = py + (SH-4) * 0.36
        self.create_text(mid//2 + pl//2, py + (SH-4)*0.14,
                         text="CONSUMED", font=MONO_SM, fill=TEXTDIM, anchor="center")
        self.create_text(mid//2 + pl//2, row1y,
                         text=f"{total:.1f}g",
                         font=("Courier New", 12, "bold"),
                         fill=RED if over else ACC, anchor="center")

        self.create_line(mid, py+4, mid, py+SH-8, fill=BORDER2)

        self.create_text(mid+(pr-mid)//2, py+(SH-4)*0.14,
                         text="REMAINING", font=MONO_SM, fill=TEXTDIM, anchor="center")
        self.create_text(mid+(pr-mid)//2, row1y,
                         text=f"{rem:.1f}g",
                         font=("Courier New", 12, "bold"),
                         fill=RED if over else TEXT, anchor="center")

        if over:
            self.create_text(mid, py+(SH-4)*0.72,
                             text=f"⚠ +{total-self._max_g:.0f}g over",
                             font=MONO_SM, fill=RED, anchor="center")
        else:
            bw  = pr - pl - 16
            bx  = pl + 8
            by2 = int(py + (SH-4)*0.72)
            self.create_rectangle(bx, by2, bx+bw, by2+5,
                                   fill=PANEL2, outline=BORDER2)
            fw = int(bw * min(c, 1.0))
            for xi in range(fw):
                t = xi / max(fw, 1)
                col2 = lerp_color(ACCDIM, ACC2, t) if ANIM_ENABLED else ACC
                self.create_line(bx+xi, by2, bx+xi, by2+5, fill=col2)
            self.create_text(mid, by2+13,
                             text=f"{total:.1f}g / {self._max_g:.0f}g",
                             font=MONO_SM, fill=DIM, anchor="center")


# ── Thumbnail Preview ─────────────────────────────────────────────────────────

class ThumbPreview(tk.Canvas):
    def __init__(self, parent, **kw):
        super().__init__(parent, bg=PANEL, highlightthickness=1,
                         highlightbackground=BORDER2, **kw)
        self._photo = None
        self._no_img = True
        self._raw = None
        self._t = 0.0
        self.bind("<Configure>", lambda e: self._redraw())
        self._tick()

    def _tick(self):
        # Only animate corner brackets color — no scanlines or shimmer
        if ANIM_ENABLED and not self._no_img:
            self._t += 0.035
            self._redraw()
        self.after(80, self._tick)

    def set_image_bytes(self, png_bytes):
        if not HAS_PIL or not png_bytes:
            self._no_img = True; self._redraw(); return
        try:
            self._raw = Image.open(io.BytesIO(png_bytes)).convert("RGBA")
            self._no_img = False; self._redraw()
        except:
            self._no_img = True; self._redraw()

    def clear(self):
        self._no_img = True; self._photo = None; self._raw = None; self._redraw()

    def _redraw(self):
        self.delete("all")
        W = self.winfo_width() or 180
        H = self.winfo_height() or 160

        # Checkerboard bg
        for y in range(0, H, 12):
            for x in range(0, W, 12):
                if (x//12 + y//12) % 2 == 0:
                    self.create_rectangle(x, y, x+12, y+12,
                                          fill="#09091a", outline="")

        if self._no_img or not HAS_PIL:
            msg = ("pip install Pillow\nfor previews" if not HAS_PIL
                   else "load a .gcode\nfor preview")
            self.create_text(W//2, H//2, text=msg, font=MONO_SM,
                             fill=DIM, anchor="center", justify="center")
            return

        pad = 10
        img = self._raw.copy()
        img.thumbnail((W - pad*2, H - pad*2), Image.LANCZOS)
        self.create_rectangle(0, 0, W, H, fill=PANEL3, outline="")

        # Animated corner brackets
        if ANIM_ENABLED:
            t = (math.sin(self._t * 1.1) + 1) / 2
            col = lerp_color(ACC, ACC_B, t)
        else:
            col = ACC

        s = 12
        for bx1, bx2 in [(pad, pad+s), (W-pad-s, W-pad)]:
            for by1, by2 in [(pad, pad+s), (H-pad-s, H-pad)]:
                self.create_line(bx1, by1, bx1, by2, fill=col, width=2)
                self.create_line(bx1, by1, bx2, by1, fill=col, width=2)

        self._photo = ImageTk.PhotoImage(img)
        self.create_image((W - img.width)//2, (H - img.height)//2,
                          image=self._photo, anchor="nw")



# ── Drop Zone ─────────────────────────────────────────────────────────────────

class DropZone(tk.Canvas):
    def __init__(self, parent, on_files, **kw):
        super().__init__(parent, bg=PANEL, highlightthickness=1,
                         highlightbackground=BORDER2, **kw)
        self.on_files  = on_files
        self._hovering = False
        self._t = 0.0
        self._particles = [
            {"x": random.uniform(0, 400), "y": random.uniform(0, 54),
             "vx": random.uniform(-0.3, 0.3), "vy": random.uniform(-0.4, -0.1),
             "life": random.uniform(0, 1.0), "r": random.uniform(1, 2.5)}
            for _ in range(18)
        ]
        self.bind("<Configure>", lambda e: self._draw())
        self.bind("<Button-1>",  lambda e: self._click())
        if HAS_DND:
            self.drop_target_register(DND_FILES)
            self.dnd_bind("<<Drop>>",      self._on_drop)
            self.dnd_bind("<<DragEnter>>", lambda e: self._hover(True))
            self.dnd_bind("<<DragLeave>>", lambda e: self._hover(False))
        self._tick()

    def _tick(self):
        if ANIM_ENABLED:
            self._t += 0.04
            W = self.winfo_width() or 400
            H = self.winfo_height() or 54
            for p in self._particles:
                p["x"] += p["vx"]; p["y"] += p["vy"]
                p["life"] -= 0.008
                if p["life"] <= 0 or p["y"] < -4:
                    p["x"] = random.uniform(0, W)
                    p["y"] = H + 2
                    p["vx"] = random.uniform(-0.3, 0.3)
                    p["vy"] = random.uniform(-0.5, -0.15)
                    p["life"] = random.uniform(0.6, 1.0)
            self._draw()
        self.after(35, self._tick)

    def _hover(self, s):
        self._hovering = s
        self.config(highlightbackground=ACC if s else BORDER2)
        self._draw()

    def _on_drop(self, e):
        self._hover(False)
        paths = parse_drop_paths(e.data)
        if paths: self.on_files(paths)

    def _click(self):
        paths = filedialog.askopenfilenames(
            title="Select GCode File(s)",
            filetypes=[("GCode files", "*.gcode *.gc *.g"), ("All files", "*.*")])
        if paths: self.on_files(list(paths))

    def _draw(self):
        self.delete("all")
        W = self.winfo_width() or 400
        H = self.winfo_height() or 54
        bg_col = "#12122a" if self._hovering else PANEL
        self.create_rectangle(0, 0, W, H, fill=bg_col, outline="")

        # Particles
        if ANIM_ENABLED:
            for p in self._particles:
                a = int(p["life"] * 120)
                if a <= 0: continue
                col = (f"#{a//3:02x}{a//4:02x}{min(255,a):02x}" if not self._hovering
                       else f"#{min(255,a+40):02x}{a//3:02x}{min(255,a):02x}")
                r = p["r"]
                self.create_oval(p["x"]-r, p["y"]-r, p["x"]+r, p["y"]+r,
                                 fill=col, outline="")

        # Animated dashed border
        if ANIM_ENABLED:
            off = int(self._t * 10) % 16
            col = ACC if self._hovering else lerp_color(BORDER2, ACC, 0.35 + 0.2*math.sin(self._t))
        else:
            off = 0
            col = ACC if self._hovering else BORDER2

        d = 8
        for x in range(-off, W, d*2):
            self.create_line(x, 0, min(x+d, W), 0, fill=col, width=1)
            self.create_line(x, H-1, min(x+d, W), H-1, fill=col, width=1)
        for y in range(0, H, d*2):
            self.create_line(0, y, 0, min(y+d, H), fill=col, width=1)
            self.create_line(W-1, y, W-1, min(y+d, H), fill=col, width=1)

        cy = H // 2
        hint = ("⊕  DROP .GCODE FILES HERE  or  CLICK TO BROWSE"
                if HAS_DND else "⊕  CLICK TO BROWSE .GCODE FILES")
        self.create_text(W//2, cy-8, text=hint,
                         font=("Courier New", 9, "bold"),
                         fill=TEXT if self._hovering else TEXTDIM, anchor="center")
        self.create_text(W//2, cy+8,
                         text="multiple files supported — or drop anywhere on the window",
                         font=MONO_SM,
                         fill=ACC if self._hovering else DIM, anchor="center")


# ── Queue Row ─────────────────────────────────────────────────────────────────

class QueueRow(tk.Frame):
    def __init__(self, parent, job, index,
                 on_remove, on_change, on_move_up, on_move_down,
                 on_select, is_selected=False, **kw):
        bg = PANEL2 if is_selected else PANEL
        super().__init__(parent, bg=bg, pady=4, padx=5, **kw)
        self.job = job; self.on_change = on_change
        self._sel = is_selected; self._bg = bg
        self._build(index, on_remove, on_move_up, on_move_down, on_select)
        self.bind("<Button-1>", lambda e: on_select())

    def _bind_children(self, on_select):
        def rec(w):
            if w.winfo_class() not in ("Button", "Entry", "Spinbox"):
                try: w.bind("<Button-1>", lambda e: on_select())
                except: pass
            for c in w.winfo_children(): rec(c)
        rec(self)

    def _build(self, index, on_remove, on_move_up, on_move_dn, on_select):
        bg = self._bg

        # Accent bar — color shifts per index
        bar_col = lerp_color(ACC, ACC_B, (index * 0.18) % 1) if self._sel else DIM
        tk.Frame(self, bg=bar_col, width=4).pack(side="left", fill="y", padx=(0, 5))

        # Up/down arrows
        arrows = tk.Frame(self, bg=bg)
        arrows.pack(side="left", padx=(0, 4))
        for txt, cmd in [("▲", on_move_up), ("▼", on_move_dn)]:
            tk.Button(arrows, text=txt, font=("Courier New", 6),
                      bg=PANEL, fg=TEXTDIM, activeforeground=ACC,
                      relief="flat", cursor="hand2", padx=2, pady=0, bd=0,
                      command=cmd).pack()

        # Info block
        info = tk.Frame(self, bg=bg)
        info.pack(side="left", fill="x", expand=True)

        # Top: index, name, grams
        top = tk.Frame(info, bg=bg)
        top.pack(fill="x", anchor="w")

        tk.Label(top, text=f"{index+1:02d}",
                 font=("Courier New", 9, "bold"),
                 bg=bg, fg=ACC if self._sel else ACCDIM, width=2).pack(side="left")

        name = trunc(self.job["filename"], 10)
        fg_name = TEXT if self._sel else TEXTDIM
        tk.Label(top, text=name, font=("Courier New", 8, "bold"),
                 bg=bg, fg=fg_name, anchor="w").pack(side="left", padx=(4, 6))

        g = self.job.get("grams_per_print")
        copies = self.job["copies"]
        meta = f"{g*copies:.1f}g" if g else f"{self.job['size_kb']:.0f}K"
        tk.Label(top, text=meta, font=MONO_SM,
                 bg=bg, fg=ACC_B if self._sel else TEXTDIM).pack(side="left")

        # Bottom: controls
        bot = tk.Frame(info, bg=bg)
        bot.pack(anchor="w", pady=(3, 0))

        btn_cfg = dict(font=("Courier New", 10, "bold"), bg=PANEL,
                       fg=TEXT, activeforeground=ACC,
                       relief="flat", cursor="hand2", padx=5, pady=0, bd=0)
        tk.Button(bot, text="−", **btn_cfg,
                  command=lambda: self._adjust(-1)).pack(side="left")

        self.count_lbl = tk.Label(bot, text=str(copies),
                                   font=("Courier New", 11, "bold"),
                                   bg=bg, fg=ACC, width=2)
        self.count_lbl.pack(side="left")

        tk.Button(bot, text="+", **btn_cfg,
                  command=lambda: self._adjust(1)).pack(side="left")

        tk.Label(bot, text="copies", font=MONO_SM, bg=bg, fg=DIM).pack(
            side="left", padx=(4, 8))

        tk.Button(bot, text="✕ remove",
                  font=("Courier New", 7, "bold"),
                  bg=PANEL, fg=DIM, activeforeground=RED,
                  relief="flat", cursor="hand2", padx=3, pady=0, bd=0,
                  command=on_remove).pack(side="left")

        self.after_idle(lambda: self._bind_children(on_select))

    def _adjust(self, delta):
        self.job["copies"] = max(1, self.job["copies"] + delta)
        self.count_lbl.config(text=str(self.job["copies"]))
        self.on_change()


# ── Main App ──────────────────────────────────────────────────────────────────

class App:
    def __init__(self, root):
        self.root = root
        self.root.title("PrintFarmQueue V0.1.0 — Saffroncarp1106")
        self.root.minsize(620, 680)
        self.root.configure(bg=BG)
        self._queue = []
        self._selected_idx = None
        self.status_var = tk.StringVar(value="[ drop a .gcode file or click to browse ]")
        self._build()
        if HAS_DND:
            self.root.drop_target_register(DND_FILES)
            self.root.dnd_bind("<<Drop>>",      self._window_drop)
            self.root.dnd_bind("<<DragEnter>>", lambda e: self._overlay_show())
            self.root.dnd_bind("<<DragLeave>>", lambda e: self._overlay_hide())

    def _window_drop(self, e):
        self._overlay_hide()
        paths = parse_drop_paths(e.data)
        if paths: self._add_files(paths)

    def _build(self):
        global ANIM_ENABLED

        # Header
        self._hdr = AnimHeader(self.root)
        self._hdr.pack(fill="x", side="top")

        # Bottom controls (perf toggle + status)
        ctrl = tk.Frame(self.root, bg=PANEL3)
        ctrl.pack(fill="x", side="bottom")
        self._perf_var = tk.BooleanVar(value=False)

        def toggle_perf():
            global ANIM_ENABLED
            ANIM_ENABLED = not self._perf_var.get()

        tk.Checkbutton(
            ctrl,
            text="⚡ Low Performance Mode  (disables animations)",
            variable=self._perf_var, command=toggle_perf,
            font=("Courier New", 8), bg=PANEL3, fg=TEXTDIM,
            activebackground=PANEL3, activeforeground=TEXT,
            selectcolor=PANEL2, relief="flat"
        ).pack(side="right", padx=10, pady=3)

        self._sb = AnimStatusBar(self.root, self.status_var)
        self._sb.pack(fill="x", side="bottom")

        # Body
        body = tk.Frame(self.root, bg=BG)
        body.pack(fill="both", expand=True, padx=12, pady=8)
        body.columnconfigure(0, weight=3)
        body.columnconfigure(1, weight=2)
        body.rowconfigure(0, weight=1)

        # ── Left: queue ───────────────────────────────────────────────────────
        left = tk.Frame(body, bg=BG)
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        left.rowconfigure(2, weight=1)
        left.columnconfigure(0, weight=1)

        dz = DropZone(left, self._add_files)
        dz.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        dz.config(height=54)

        # Queue header
        qhdr = tk.Frame(left, bg=BG)
        qhdr.grid(row=1, column=0, sticky="ew", pady=(0, 3))
        tk.Label(qhdr, text="▸ PRINT QUEUE",
                 font=("Courier New", 10, "bold"), bg=BG, fg=ACC).pack(side="left")
        self.queue_meta_lbl = tk.Label(qhdr, text="empty",
                                        font=MONO_SM, bg=BG, fg=DIM)
        self.queue_meta_lbl.pack(side="left", padx=6)
        tk.Button(qhdr, text="CLEAR ALL",
                  font=("Courier New", 8, "bold"), bg=PANEL, fg=DIM,
                  relief="flat", activeforeground=RED, cursor="hand2",
                  padx=5, pady=1, command=self._clear_queue).pack(side="right")

        # Scrollable list
        lo = tk.Frame(left, bg=BORDER, padx=1, pady=1)
        lo.grid(row=2, column=0, sticky="nsew")
        lo.rowconfigure(0, weight=1); lo.columnconfigure(0, weight=1)
        self._lcanvas = tk.Canvas(lo, bg=PANEL3, highlightthickness=0)
        vsb = tk.Scrollbar(lo, orient="vertical", command=self._lcanvas.yview)
        self._lcanvas.configure(yscrollcommand=vsb.set)
        vsb.pack(side="right", fill="y")
        self._lcanvas.pack(side="left", fill="both", expand=True)
        self._lframe = tk.Frame(self._lcanvas, bg=PANEL3)
        self._lwin   = self._lcanvas.create_window((0,0), window=self._lframe, anchor="nw")
        self._lframe.bind("<Configure>",
            lambda e: self._lcanvas.configure(scrollregion=self._lcanvas.bbox("all")))
        self._lcanvas.bind("<Configure>",
            lambda e: self._lcanvas.itemconfig(self._lwin, width=e.width))
        self._lcanvas.bind_all("<MouseWheel>",
            lambda e: self._lcanvas.yview_scroll(-1*(e.delta//120), "units"))

        # Output file row
        ofr = tk.Frame(left, bg=BG)
        ofr.grid(row=3, column=0, sticky="ew", pady=(6, 3))
        ofr.columnconfigure(0, weight=1)
        tk.Label(ofr, text="▸ OUTPUT FILE",
                 font=("Courier New", 10, "bold"), bg=BG, fg=ACC).grid(
                     row=0, column=0, columnspan=2, sticky="w")
        wrap = tk.Frame(ofr, bg=BORDER, padx=1, pady=1)
        wrap.grid(row=1, column=0, sticky="ew", padx=(0, 6))
        ofr.columnconfigure(0, weight=1)
        self.output_var = tk.StringVar()
        tk.Entry(wrap, textvariable=self.output_var,
                 font=("Courier New", 9), bg=PANEL2, fg=TEXT,
                 insertbackground=ACC, relief="flat", bd=4).pack(fill="x", ipady=4)
        tk.Button(ofr, text="BROWSE",
                  font=("Courier New", 9, "bold"), bg=PANEL2, fg=TEXT,
                  relief="flat", activebackground=ACC, activeforeground="#111",
                  cursor="hand2", padx=8, pady=5,
                  command=self._browse_output).grid(row=1, column=1)

        self.gen_btn = GlowButton(left, text="▶  GENERATE QUEUE FILE",
                                   command=self._generate)
        self.gen_btn.grid(row=4, column=0, sticky="ew", pady=(6, 0))

        # ── Right: preview + spool ────────────────────────────────────────────
        right = tk.Frame(body, bg=BG)
        right.grid(row=0, column=1, sticky="nsew")
        right.rowconfigure(1, weight=1)
        right.rowconfigure(4, weight=2)
        right.columnconfigure(0, weight=1)

        tk.Label(right, text="▸ PREVIEW",
                 font=("Courier New", 10, "bold"), bg=BG, fg=ACC_B).grid(
                     row=0, column=0, sticky="w")
        self.thumb = ThumbPreview(right)
        self.thumb.grid(row=1, column=0, sticky="nsew", pady=(3, 8))

        tk.Label(right, text="▸ SPOOL USAGE",
                 font=("Courier New", 10, "bold"), bg=BG, fg=ACC).grid(
                     row=2, column=0, sticky="w")

        # Spool size config
        scfg = tk.Frame(right, bg=BG)
        scfg.grid(row=3, column=0, sticky="ew", pady=(2, 4))
        scfg.columnconfigure(1, weight=1)
        tk.Label(scfg, text="SPOOL SIZE:",
                 font=MONO_SM, bg=BG, fg=TEXTDIM).grid(row=0, column=0, sticky="w")
        self.spool_size_var = tk.StringVar(value="1000")
        sw = tk.Frame(scfg, bg=BORDER, padx=1, pady=1)
        sw.grid(row=0, column=1, sticky="ew", padx=(4, 4))
        tk.Entry(sw, textvariable=self.spool_size_var,
                 font=("Courier New", 9), bg=PANEL2, fg=ACC,
                 insertbackground=ACC, relief="flat", bd=2,
                 width=6, justify="right").pack(fill="x", ipady=2)
        tk.Label(scfg, text="g",
                 font=MONO_SM, bg=BG, fg=TEXTDIM).grid(row=0, column=2, sticky="w")
        tk.Button(scfg, text="SET",
                  font=("Courier New", 8, "bold"), bg=ACCDIM, fg=ACC2,
                  relief="flat", activebackground=ACC, activeforeground="#111",
                  cursor="hand2", padx=6, pady=1,
                  command=self._apply_spool_size).grid(row=0, column=3, padx=(4, 0))
        self.spool_size_var.trace_add("write", lambda *a: self._apply_spool_size())

        self.spool = SpoolWidget(right)
        self.spool.grid(row=4, column=0, sticky="nsew")

        # Full-window drop overlay
        self._overlay = tk.Canvas(self.root, bg="#05050f",
                                  highlightthickness=3,
                                  highlightbackground=ACC)
        self._overlay_t = 0.0
        self._overlay.bind("<Configure>", self._draw_overlay)
        if HAS_DND:
            self._overlay.drop_target_register(DND_FILES)
            self._overlay.dnd_bind("<<Drop>>",      self._window_drop)
            self._overlay.dnd_bind("<<DragLeave>>", lambda e: self._overlay_hide())

        self._rebuild_list()

    def _draw_overlay(self, e=None):
        self._overlay.delete("all")
        W = self._overlay.winfo_width() or 700
        H = self._overlay.winfo_height() or 500
        self._overlay.create_rectangle(0, 0, W, H, fill="#05050f", outline="")

        if ANIM_ENABLED:
            self._overlay_t += 0.03
            rng = random.Random(42)
            for _ in range(60):
                x = rng.uniform(0, W); y = rng.uniform(0, H)
                r = rng.uniform(0.5, 2)
                ph = rng.uniform(0, 6.28)
                bv = int(80 + 60*math.sin(self._overlay_t + ph + x*0.015))
                self._overlay.create_oval(x-r, y-r, x+r, y+r,
                                          fill=f"#{bv//6:02x}{bv//6:02x}{bv//2:02x}",
                                          outline="")

        col = ACC; d = 14
        for x in range(0, W, d*2):
            self._overlay.create_line(x, 8, min(x+d, W), 8, fill=col, width=2)
            self._overlay.create_line(x, H-8, min(x+d, W), H-8, fill=col, width=2)
        for y in range(0, H, d*2):
            self._overlay.create_line(8, y, 8, min(y+d, H), fill=col, width=2)
            self._overlay.create_line(W-8, y, W-8, min(y+d, H), fill=col, width=2)

        cx, cy = W//2, H//2
        if ANIM_ENABLED:
            fs = int(38 + 4*math.sin(self._overlay_t*2.5))
        else:
            fs = 38
        self._overlay.create_text(cx, cy-30, text="⊕",
                                   font=("Courier New", fs), fill=ACC, anchor="center")
        self._overlay.create_text(cx, cy+20,
                                   text="DROP .GCODE FILES ANYWHERE",
                                   font=("Courier New", 14, "bold"),
                                   fill=TEXT, anchor="center")
        self._overlay.create_text(cx, cy+44,
                                   text="release to add to queue",
                                   font=MONO_SM, fill=TEXTDIM, anchor="center")

        if ANIM_ENABLED and self._overlay.winfo_ismapped():
            self._overlay.after(30, self._draw_overlay)

    def _overlay_show(self):
        self._overlay_t = 0.0
        self._overlay.place(relx=0, rely=0, relwidth=1, relheight=1)
        self._overlay.lift()
        self._draw_overlay()

    def _overlay_hide(self):
        self._overlay.place_forget()

    # ── Queue management ──────────────────────────────────────────────────────

    def _add_files(self, paths):
        added = 0
        for path in paths:
            if not path.lower().endswith(".gcode"): continue
            info = get_file_info(path)
            if not info["valid"]: continue
            self._queue.append({
                "path": path, "filename": info["filename"],
                "size_kb": info["size_kb"],
                "grams_per_print": info["grams_per_print"],
                "thumbnail_png": info["thumbnail_png"],
                "copies": 1
            })
            added += 1
        if added:
            self._selected_idx = len(self._queue) - 1
            self._rebuild_list(); self._update_spool(); self._update_preview()
            if not self.output_var.get() and self._queue:
                self.output_var.set(suggest_queue_output_path(self._queue[0]["path"]))
            self.status_var.set(f"added {added} file(s)  ·  queue: {len(self._queue)} job(s)")

    def _select(self, idx):
        self._selected_idx = idx; self._rebuild_list(); self._update_preview()

    def _update_preview(self):
        if self._selected_idx is None or self._selected_idx >= len(self._queue):
            self.thumb.clear(); return
        png = self._queue[self._selected_idx].get("thumbnail_png")
        if png: self.thumb.set_image_bytes(png)
        else: self.thumb.clear()

    def _rebuild_list(self):
        for w in self._lframe.winfo_children(): w.destroy()
        if not self._queue:
            tk.Label(self._lframe,
                     text="\n  queue is empty — add files above\n",
                     font=MONO_SM, bg=PANEL3, fg=DIM).pack()
            self.queue_meta_lbl.config(text="empty"); return
        for i, job in enumerate(self._queue):
            row = QueueRow(
                self._lframe, job, i,
                on_remove    = lambda idx=i: self._remove(idx),
                on_change    = self._on_queue_change,
                on_move_up   = lambda idx=i: self._move(idx, -1),
                on_move_down = lambda idx=i: self._move(idx, 1),
                on_select    = lambda idx=i: self._select(idx),
                is_selected  = (i == self._selected_idx))
            row.pack(fill="x", pady=1)
        self._update_queue_meta()

    def _remove(self, idx):
        self._queue.pop(idx)
        if self._selected_idx is not None:
            if self._selected_idx >= len(self._queue):
                self._selected_idx = len(self._queue)-1 if self._queue else None
        self._rebuild_list(); self._update_spool(); self._update_preview()

    def _move(self, idx, direction):
        new = idx + direction
        if 0 <= new < len(self._queue):
            self._queue[idx], self._queue[new] = self._queue[new], self._queue[idx]
            if self._selected_idx == idx: self._selected_idx = new
            self._rebuild_list()

    def _clear_queue(self):
        if self._queue and messagebox.askyesno("Clear Queue", "Remove all jobs?"):
            self._queue.clear(); self._selected_idx = None
            self._rebuild_list(); self._update_spool(); self.thumb.clear()
            self.status_var.set("queue cleared")

    def _on_queue_change(self):
        self._update_spool(); self._rebuild_list()

    def _apply_spool_size(self, *_):
        try:
            val = float(self.spool_size_var.get())
            if val > 0: self.spool.set_max(val); self._update_spool()
        except ValueError: pass

    def _update_spool(self):
        total = sum((j["grams_per_print"] or 0) * j["copies"] for j in self._queue)
        self.spool.set_total(total)

    def _update_queue_meta(self):
        if not self._queue:
            self.queue_meta_lbl.config(text="empty"); return
        tp = sum(j["copies"] for j in self._queue)
        tg = sum((j["grams_per_print"] or 0)*j["copies"] for j in self._queue)
        txt = f"{len(self._queue)} job(s)  ·  {tp} prints"
        if tg: txt += f"  ·  {tg:.1f}g"
        self.queue_meta_lbl.config(text=txt)

    def _browse_output(self):
        path = filedialog.asksaveasfilename(
            title="Save Queue GCode As", defaultextension=".gcode",
            filetypes=[("GCode files", "*.gcode"), ("All files", "*.*")])
        if path: self.output_var.set(path)

    def _generate(self):
        if not self._queue:
            messagebox.showerror("Empty Queue", "Add at least one .gcode file first."); return
        out = self.output_var.get().strip()
        if not out:
            out = suggest_queue_output_path(self._queue[0]["path"])
            self.output_var.set(out)
        jobs = [{"path": j["path"], "copies": j["copies"]} for j in self._queue]
        total = sum(j["copies"] for j in self._queue)
        self.gen_btn.set_enabled(False, "  WORKING...")
        self.status_var.set(f"generating {total} total prints — please wait...")
        self.root.update()

        def run():
            result = generate_queue(jobs, out)
            self.root.after(0, lambda: self._on_done(result))
        threading.Thread(target=run, daemon=True).start()

    def _on_done(self, result):
        self.gen_btn.set_enabled(True, "▶  GENERATE QUEUE FILE")
        if result["success"]:
            kb   = result["output_size_kb"]
            size = f"{kb/1024:.1f} MB" if kb >= 1024 else f"{kb:.0f} KB"
            name = os.path.basename(result["output_path"])
            g_ln = (f"\nFilament: {result['total_grams']:.1f}g total"
                    if result["total_grams"] else "")
            self.status_var.set(f"✓  {name}  ({size})  —  copy to USB")
            messagebox.showinfo("Queue Ready",
                f"{result['job_count']} job(s)  ·  {result['total_copies']} prints.\n\n"
                f"File: {result['output_path']}\nSize: {size}" + g_ln +
                "\n\nCopy to USB and print!")
        else:
            self.status_var.set(f"error: {result['message']}")
            messagebox.showerror("Error", result["message"])


# ── Entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    root = TkinterDnD.Tk() if HAS_DND else tk.Tk()
    root.geometry("820x860")
    root.minsize(620, 680)
    App(root)
    root.mainloop()