"""Generate the comic-book profile README as a stack of flush, clickable SVG slices.

    pip install fonttools brotli
    python3 tools/generate_comic_readme.py

The page looks like one unbroken comic page but is cut into horizontal
slices so regions can be links.

Why slices at all: an SVG loaded through an <img> tag runs in the browser's
secure static mode, which allows no scripts, no external fetches and no
links. An <a> inside the SVG can therefore never be clicked. The only way
to get clickable regions is one <img> per region, each wrapped in <a>.

Why they do not show seams: plain inline images sit on a text baseline, and
the line box leaves a ~7px gap under each one. Floating them with
align="left" takes them out of the line box entirely, so consecutive slices
stack perfectly flush. Measured, not assumed. `align` is on GitHub's
allowed-attribute list; `style` is not, which is why this is the only
available lever.

Other constraints:

  * Both fonts are embedded as base64 WOFF2, subset per slice to just the
    glyphs that slice uses. A Google Fonts <link> would silently fall back
    to a system font.
  * A 900px page scales to roughly 370px on a phone, so body copy is set at
    29px (~3% of page width, about what real comics use).
  * The paper halftone is static. Each slice is a separate image whose
    animations start when it loads, so a drifting page-wide texture would
    desync between slices. Animations that live inside one slice are fine.
"""
import base64, glob, hashlib, io, math, os, urllib.request
from fontTools import subset
from fontTools.ttLib import TTFont

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
OUT = os.path.join(REPO, "assets")
CACHE = os.path.join(HERE, ".fontcache")

# Bangers and Comic Neue, both SIL Open Font License (embedding permitted).
FONT_URLS = {
    "bangers-latin.woff2":
        "https://fonts.gstatic.com/s/bangers/v25/FeVQS0BTqb0h60ACH55Q2A.woff2",
    "comicneue-700-latin.woff2":
        "https://fonts.gstatic.com/s/comicneue/v9/4UaErEJDsxBrF37olUeD_xHM8pxULg.woff2",
}

def ensure_fonts():
    os.makedirs(CACHE, exist_ok=True)
    for name, url in FONT_URLS.items():
        dest = os.path.join(CACHE, name)
        if not os.path.exists(dest):
            print(f"  fetching {name}")
            urllib.request.urlretrieve(url, dest)

ensure_fonts()
BANGERS_SRC = os.path.join(CACHE, "bangers-latin.woff2")
COMIC_SRC = os.path.join(CACHE, "comicneue-700-latin.woff2")

INK, RED, YEL, BLU, CREAM = "#141418", "#E0241B", "#FFCB05", "#1E5FD0", "#FFFBF0"
PAPER, DIM = "#F5ECD8", "#6A6252"

W, PAD = 900, 36
CONTENT = W - PAD * 2

# ----------------------------------------------------------------- font metrics

def metrics(path):
    f = TTFont(path)
    upm = f["head"].unitsPerEm
    hmtx = f["hmtx"]
    return {chr(cp): hmtx[n][0] / upm for cp, n in f.getBestCmap().items()}

MB = metrics(BANGERS_SRC)
MC = metrics(COMIC_SRC)

def wide(table, text, size, ls=0.0):
    return sum(table.get(c, 0.5) for c in text) * size + ls * max(0, len(text) - 1)

def wrap(table, text, size, maxw, ls=0.0):
    words, lines, cur = text.split(), [], ""
    for word in words:
        trial = f"{cur} {word}".strip()
        if cur and wide(table, trial, size, ls) > maxw:
            lines.append(cur)
            cur = word
        else:
            cur = trial
    if cur:
        lines.append(cur)
    return lines

def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def font_b64(path, text):
    font = TTFont(path)
    opts = subset.Options()
    opts.flavor = "woff2"
    opts.desubroutinize = True
    opts.notdef_outline = True
    sub = subset.Subsetter(options=opts)
    sub.populate(text=text)
    sub.subset(font)
    buf = io.BytesIO()
    font.flavor = "woff2"
    font.save(buf)
    font.close()
    return base64.b64encode(buf.getvalue()).decode("ascii")

# --------------------------------------------------------------------- geometry

def burst_path(r_out, r_in, points=12):
    d = []
    for i in range(points * 2):
        a = math.pi * i / points - math.pi / 2
        r = r_out if i % 2 == 0 else r_in
        d.append(("M" if i == 0 else "L") + f"{r*math.cos(a):.1f} {r*math.sin(a):.1f}")
    return "".join(d) + "Z"

def rays(cx, cy, n=18, skip_left=True, reach=1400):
    out = []
    for i in range(n):
        a = 2 * math.pi * i / n + 0.18
        if skip_left and math.cos(a) < -0.30:
            continue
        out.append(f"M{cx} {cy}L{cx + reach*math.cos(a):.0f} {cy + reach*math.sin(a):.0f}")
    return " ".join(out)

# ----------------------------------------------------------------- slice machinery

SLICES = []
CUR = None
y = 0

def slice_begin(name, href=None, alt=""):
    global CUR
    CUR = {"name": name, "href": href, "alt": alt, "frags": [],
           "bg": set(), "cg": set(), "y0": y}
    SLICES.append(CUR)

def slice_end():
    CUR["y1"] = y

def add(frag):
    CUR["frags"].append(frag)

def bang(txt, x, y_, size, fill, ls=2, anchor="start", cls=""):
    CUR["bg"].update(txt)
    c = f"bang {cls}".strip()
    return (f'<text class="{c}" x="{x}" y="{y_}" font-size="{size}" letter-spacing="{ls}" '
            f'fill="{fill}" text-anchor="{anchor}">{esc(txt)}</text>')

def body(txt, x, y_, size, fill, anchor="start"):
    CUR["cg"].update(txt)
    c = "body"
    return (f'<text class="{c}" x="{x}" y="{y_}" font-size="{size}" fill="{fill}" '
            f'text-anchor="{anchor}">{esc(txt)}</text>')

def shadow(txt, x, y_, size, ls, face, mid, bot, cls=""):
    CUR["bg"].update(txt)
    c = f"bang {cls}".strip()
    def t(dx, dy, fill):
        return (f'<text class="{c}" x="{x+dx}" y="{y_+dy}" font-size="{size}" '
                f'letter-spacing="{ls}" fill="{fill}">{esc(txt)}</text>')
    return t(10, 10, bot) + t(5, 5, mid) + t(0, 0, face)

# ========================================================================= blocks

def para(lines, x, size, fill, lh):
    global y
    for i, ln in enumerate(lines):
        add(body(ln, x, y + lh * (i + 1) - lh * 0.28, size, fill))
    return lh * len(lines)

def banner(label, bg, fg, motif="dot"):
    global y
    h = 84
    if motif == "burst":
        bf = CREAM if bg == YEL else YEL
        art = (f'<g transform="translate({W-PAD-46} {y+h//2})"><g class="spin">'
               f'<path d="{burst_path(30, 21, 10)}" fill="{bf}" stroke="{INK}" '
               f'stroke-width="4" stroke-linejoin="round"></path></g></g>')
    elif motif == "march":
        art = ('<g class="march">' + "".join(
            f'<rect x="{W-PAD-170+i*34}" y="{y+34}" width="18" height="22" fill="{INK}" '
            f'opacity="0.45"></rect>' for i in range(5)) + '</g>')
    else:
        art = (f'<g class="bob"><circle cx="{W-PAD-44}" cy="{y+h//2}" r="21" fill="{INK}"></circle>'
               f'<circle cx="{W-PAD-44}" cy="{y+h//2}" r="10" fill="{bg}"></circle></g>')
    add(f'<rect x="{PAD}" y="{y}" width="{CONTENT}" height="{h}" fill="{bg}" '
        f'stroke="{INK}" stroke-width="6"></rect>')
    add(art)
    add(bang(label, PAD + 26, y + 60, 54, fg, 3))
    y += h

def project(sfx, title, tag, bgc, face, mid, art_fn, desc, tags, rot_cls, visit=None, thumb=None):
    global y
    ph = 252 if thumb else 212
    pid = f"clip{title.replace(' ', '')}"
    add(f'<clipPath id="{pid}"><rect x="{PAD}" y="{y}" width="{CONTENT}" height="{ph}"></rect></clipPath>')
    add(f'<rect x="{PAD}" y="{y}" width="{CONTENT}" height="{ph}" fill="{bgc}"></rect>')
    add(f'<g clip-path="url(#{pid})">{art_fn(y, ph)}</g>')
    add(f'<rect x="{PAD}" y="{y}" width="{CONTENT}" height="{ph}" fill="none" '
        f'stroke="{INK}" stroke-width="6"></rect>')
    sfx_y, chip_y = y + ph // 2 - 6, y + ph - 78
    add(f'<g transform="translate({PAD+34} {sfx_y})"><g class="{rot_cls}">'
        f'{shadow(sfx, 0, 0, 76, 3, face, mid, INK)}</g></g>')

    tw = wide(MB, title, 32, 3) + 44
    add(f'<rect x="{PAD+30}" y="{chip_y}" width="{tw:.0f}" height="50" fill="{INK}" '
        f'stroke="{CREAM}" stroke-width="4"></rect>')
    add(bang(title, PAD + 52, chip_y + 35, 32, CREAM, 3))

    gw = wide(MB, tag, 22, 2) + 28
    if thumb:
        # Real landing-page shot, framed like a panel inset. The image is
        # embedded because an SVG in an <img> cannot fetch anything external.
        tx, ty, tw2, th2 = 452, y + 32, 380, 200
        data = base64.b64encode(open(thumb, "rb").read()).decode("ascii")
        add(f'<rect x="{tx+9}" y="{ty+9}" width="{tw2}" height="{th2}" fill="{INK}"></rect>')
        add(f'<clipPath id="thumb{title.replace(" ", "")}"><rect x="{tx}" y="{ty}" '
            f'width="{tw2}" height="{th2}"></rect></clipPath>')
        add(f'<image x="{tx}" y="{ty}" width="{tw2}" height="{th2}" '
            f'preserveAspectRatio="xMidYMid slice" clip-path="url(#thumb{title.replace(" ", "")})" '
            f'href="data:image/jpeg;base64,{data}"></image>')
        add(f'<rect x="{tx}" y="{ty}" width="{tw2}" height="{th2}" fill="none" '
            f'stroke="{INK}" stroke-width="6"></rect>')
        # the status tag becomes a sticker slapped on the corner of the shot
        sx, sy = tx - 16, ty - 16
        add(f'<g transform="rotate(-4 {sx+gw/2:.0f} {sy+19})">'
            f'<rect x="{sx}" y="{sy}" width="{gw:.0f}" height="38" fill="{YEL}" '
            f'stroke="{INK}" stroke-width="4"></rect>'
            + bang(tag, sx + gw / 2, sy + 27, 22, INK, 2, "middle") + '</g>')
    else:
        add(f'<rect x="{W-PAD-30-gw:.0f}" y="{y+26}" width="{gw:.0f}" height="38" fill="{YEL}" '
            f'stroke="{INK}" stroke-width="4"></rect>')
        add(bang(tag, W - PAD - 30 - gw / 2, y + 53, 22, INK, 2, "middle"))
    y += ph + 20

    y += para(wrap(MC, desc, 29, CONTENT - 20), PAD + 8, 29, INK, 42) + 14

    x = PAD + 8
    for t in tags:
        tw2 = wide(MC, t, 23) + 26
        add(f'<rect x="{x:.0f}" y="{y}" width="{tw2:.0f}" height="38" fill="none" '
            f'stroke="{INK}" stroke-width="3"></rect>')
        add(body(t, x + tw2 / 2, y + 27, 23, INK, "middle"))
        x += tw2 + 10
    if visit:
        label = f"VISIT {visit}"
        tw3 = wide(MB, label, 25, 2)
        vw = tw3 + 38 + 30          # padding + room for the chevron
        bh = 46
        add(f'<rect x="{x+5:.0f}" y="{y+3}" width="{vw:.0f}" height="{bh}" fill="{INK}"></rect>')
        add(f'<rect x="{x:.0f}" y="{y-2}" width="{vw:.0f}" height="{bh}" fill="{RED}" '
            f'stroke="{INK}" stroke-width="4"></rect>')
        add(bang(label, x + 19, y + 30, 25, CREAM, 2))
        cx = x + 19 + tw3 + 18
        add(f'<path d="M{cx:.0f} {y+12}l11 9-11 9" fill="none" stroke="{CREAM}" '
            f'stroke-width="4" stroke-linecap="round" stroke-linejoin="round"></path>')
        y += bh + 32
    else:
        y += 38 + 34

def rows(data, label_w, size=27, lh=38):
    global y
    for i, (label, value) in enumerate(data):
        vlines = wrap(MC, value, size, CONTENT - label_w - 60)
        h = max(lh * len(vlines) + 26, 64)
        if i % 2 == 0:
            add(f'<rect x="{PAD}" y="{y}" width="{CONTENT}" height="{h}" fill="{INK}" opacity="0.055"></rect>')
        add(f'<rect x="{PAD}" y="{y+h-2}" width="{CONTENT}" height="2" fill="{INK}" opacity="0.18"></rect>')
        add(bang(label, PAD + 22, y + 44, 30, RED, 2))
        for j, ln in enumerate(vlines):
            add(body(ln, PAD + label_w, y + 42 + j * lh, size, INK))
        y += h
    y += 24

def contact_row(label, value, idx):
    """One clickable letters-page row, its own slice."""
    global y
    h = 66
    if idx % 2 == 0:
        add(f'<rect x="{PAD}" y="{y}" width="{CONTENT}" height="{h}" fill="{INK}" opacity="0.055"></rect>')
    add(f'<rect x="{PAD}" y="{y+h-2}" width="{CONTENT}" height="2" fill="{INK}" opacity="0.18"></rect>')
    add(body(f"{label}:", PAD + 30, y + 44, 27, INK))
    add(body(value, PAD + 206, y + 44, 27, RED))
    add(f'<path d="M{W-PAD-54} {y+28}l16 10-16 10" fill="none" stroke="{RED}" '
        f'stroke-width="4" stroke-linecap="round" stroke-linejoin="round"></path>')
    y += h

# ============================================================================ art

def art_speed(y0, h):
    return ('<g class="pulse" stroke="' + CREAM + '" stroke-width="6" opacity="0.45">'
            + "".join(f'<path d="M{440 + (i%3)*54} {y0+24+i*25}h{330-(i%3)*40}"></path>'
                      for i in range(7)) + '</g>')

def art_impact(y0, h):
    return (f'<path class="pulse" d="{rays(770, y0+100, 16, True, 700)}" stroke="{CREAM}" '
            f'stroke-width="6" fill="none"></path>')

def art_rings(y0, h):
    return ('<g class="pulse" fill="none" stroke="' + INK + '" stroke-width="6" opacity="0.40">'
            + "".join(f'<circle cx="748" cy="{y0+104}" r="{34+i*38}"></circle>' for i in range(5))
            + '</g>')

def art_grid(y0, h):
    pal = [RED, YEL, RED, "#3A3A42", RED, YEL, "#3A3A42", RED]
    cells = [f'<rect x="{500 + c*30}" y="{y0+38+r*30}" width="22" height="22" '
             f'fill="{pal[(r*7+c*3) % len(pal)]}"></rect>'
             for r in range(5) for c in range(11)]
    return '<g class="pulse" opacity="0.6">' + "".join(cells) + '</g>'

# ========================================================================== build

PORTFOLIO = "https://hakkan.is-a.dev"

# ---- SLICE 1: masthead, cover, tagline, origin, "in this issue"
slice_begin("01-cover", PORTFOLIO, "THE AMAZING HAKKAN No. 22 cover and origin story")
MAST, COVER, TAG = 52, 400, 62
add(f'<rect x="0" y="0" width="{W}" height="{MAST+COVER+TAG}" fill="{BLU}"></rect>')
add('<g clip-path="url(#cover)">')
add(f'<g class="drift"><rect x="-200" y="-200" width="1400" height="1100" fill="url(#dots)"></rect></g>')
add(f'<path class="pulse" d="{rays(640, 220)}" stroke="{CREAM}" stroke-width="5" fill="none"></path>')
add('<g transform="translate(18 11) scale(0.73)">'
    f'<path d="M848 344C726 378 664 476 648 604L748 604C756 482 786 406 856 364Z" fill="{RED}" stroke="{INK}" stroke-width="7" stroke-linejoin="round"></path>'
    f'<path d="M912 344C1034 378 1096 476 1112 604L1012 604C1004 482 974 406 904 364Z" fill="{RED}" stroke="{INK}" stroke-width="7" stroke-linejoin="round"></path>'
    f'<rect x="862" y="282" width="36" height="52" fill="#07070A"></rect>'
    f'<path d="M880 330C820 330 786 360 776 410L766 604H994L984 410C974 360 940 330 880 330Z" fill="{INK}"></path>'
    f'<circle cx="880" cy="240" r="52" fill="{INK}"></circle>'
    f'<path d="M828 240a52 52 0 0 1 104 0z" fill="#07070A"></path>'
    f'<path d="M818 242a62 62 0 0 1 124 0" fill="none" stroke="{YEL}" stroke-width="12" stroke-linecap="round"></path>'
    f'<rect x="806" y="230" width="23" height="44" rx="9" fill="{YEL}" stroke="{INK}" stroke-width="6"></rect>'
    f'<rect x="931" y="230" width="23" height="44" rx="9" fill="{YEL}" stroke="{INK}" stroke-width="6"></rect>'
    f'<rect x="774" y="558" width="212" height="16" rx="4" fill="{RED}" stroke="{INK}" stroke-width="6"></rect>'
    f'<path d="M792 558l18-68h140l18 68z" fill="{YEL}" stroke="{INK}" stroke-width="8" stroke-linejoin="round"></path>'
    f'<rect x="826" y="506" width="50" height="8" fill="{INK}"></rect>'
    f'<rect x="826" y="520" width="80" height="8" fill="{INK}"></rect>'
    f'<rect x="826" y="534" width="38" height="8" fill="{INK}"></rect>'
    '</g>')
add(f'<g class="bob"><circle cx="812" cy="128" r="33" fill="{YEL}" stroke="{INK}" stroke-width="5"></circle>'
    + bang("AI", 812, 140, 30, INK, 1, "middle") + '</g>')
add(f'<g class="bob2"><circle cx="782" cy="276" r="24" fill="{YEL}" stroke="{INK}" stroke-width="5"></circle>'
    + bang("</>", 782, 286, 20, INK, 0, "middle") + '</g>')
add(f'<g transform="translate(116 378)"><g class="spin">'
    f'<path d="{burst_path(70, 50)}" fill="{YEL}" stroke="{INK}" stroke-width="5" stroke-linejoin="round"></path></g>'
    + bang("SHIPS", 0, -12, 24, INK, 1, "middle")
    + bang("IN", 0, 14, 24, INK, 1, "middle")
    + bang("PROD!", 0, 40, 24, INK, 1, "middle") + '</g>')
add('<g class="breathe">'
    + bang("THE AMAZING", 44, 122, 46, YEL, 4)
    + shadow("HAKKAN", 40, 226, 110, 2, CREAM, YEL, INK) + '</g>')
cw = wide(MB, "FULL STACK AI ENGINEER", 26, 3) + 48
add(f'<rect x="40" y="254" width="{cw:.0f}" height="52" fill="{INK}" stroke="{CREAM}" stroke-width="4"></rect>')
add(bang("FULL STACK AI ENGINEER", 40 + cw / 2, 289, 26, YEL, 3, "middle"))
add('</g>')
add(f'<rect x="0" y="0" width="{W}" height="{MAST}" fill="{RED}"></rect>')
add(f'<rect x="0" y="{MAST-3}" width="{W}" height="6" fill="{INK}"></rect>')
add(bang("NO. 22", 30, 36, 23, CREAM, 3))
add(bang("KOLKATA EDITION", W / 2, 36, 23, CREAM, 3, "middle"))
add(bang("FREE TO FORK", W - 30, 36, 23, CREAM, 3, "end"))
add(f'<rect x="0" y="{MAST+COVER}" width="{W}" height="{TAG}" fill="{CREAM}"></rect>')
add(f'<rect x="0" y="{MAST+COVER-3}" width="{W}" height="6" fill="{INK}"></rect>')
add(bang("AT LAST!", 30, MAST + COVER + 44, 38, RED, 2))
add(bang("AN ENGINEER WHO SHIPS.", 212, MAST + COVER + 44, 38, INK, 2))
y = MAST + COVER + TAG + 34

banner("ORIGIN STORY...", YEL, INK)
y += 22
for lead, rest in [
    ("It began with one project that absolutely had to work.",
     "A deadline, no plan B, and the discovery that working beats clever every single time."),
    ("Then it met actual users.",
     "Demos are easy. Keeping something up at 3am, under load, with nobody watching turned out to be the real job."),
    ("And so a Full Stack AI Engineer was born.",
     "Now it is AI-first products in production at Persist Ventures: adaptive learning platforms, desktop agents, and automation that simply keeps running."),
]:
    n = len(wrap(MC, lead + " " + rest, 29, CONTENT - 40))
    add(f'<rect x="{PAD}" y="{y-6}" width="6" height="{42*n+10}" fill="{RED}"></rect>')
    y += para(wrap(MC, lead + " " + rest, 29, CONTENT - 40), PAD + 24, 29, INK, 42) + 26
y += 12
banner("IN THIS ISSUE...", RED, CREAM, "burst")
y += 24
slice_end()

# ---- SLICES 2-5: one per project
slice_begin("02-ohm", "https://ohmschool.org", "OHM School - AI learning platform")
project("TEACH!", "OHM SCHOOL", "FIRST APPEARANCE", BLU, YEL, RED, art_speed,
        "An AI learning platform that rearranges the lesson around whoever is sitting in "
        "front of it. Resident tutor Ollie, mastery tracking, assessments and recommendations "
        "that adapt as the learner moves.",
        ["Next.js", "TypeScript", "LLM"], "pop1", visit="OHMSCHOOL.ORG",
        thumb=os.path.join(HERE, "thumbs", "ohm.jpg"))
slice_end()

slice_begin("03-aura", "https://aura-website-ashen.vercel.app/",
            "Aura Desktop - the UI for OpenClaw, now in beta")
project("AUTOMATE!", "AURA DESKTOP", "BETA V0.2.0", RED, YEL, INK, art_impact,
        "A desktop AI assistant that can actually press the buttons. Chat or speak your "
        "intent and watch it book flights, apply to jobs, summarise your inbox and run "
        "anything else in the browser. No code, no setup.",
        ["Electron", "Node.js", "Voice"], "pop2", visit="AURA-WEBSITE.VERCEL.APP",
        thumb=os.path.join(HERE, "thumbs", "aura.jpg"))
slice_end()

slice_begin("04-portfolio", PORTFOLIO, "Portfolio - a terminal-driven portfolio")
project("TYPE!", "PORTFOLIO", "FAN FAVOURITE", YEL, RED, CREAM, art_rings,
        "A portfolio you drive from a command line. Built on the suspicion that a portfolio "
        "should ask something of the person reading it.",
        ["React", "Terminal UI", "Vercel"], "pop3", visit="HAKKAN.IS-A.DEV",
        thumb=os.path.join(HERE, "thumbs", "portfolio.jpg"))
slice_end()

slice_begin("05-commithabit", "https://commithabit.vercel.app", "CommitHabit - contribution streak automation")
project("COMMIT!", "COMMITHABIT", "DAILY SERIAL", INK, YEL, RED, art_grid,
        "Keeps the contribution streak alive. A tool about consistency has to be more "
        "consistent than the habit it is protecting, so it runs unattended.",
        ["Node.js", "GitHub API", "Cron"], "pop4", visit="COMMITHABIT.VERCEL.APP",
        thumb=os.path.join(HERE, "thumbs", "commithabit.jpg"))
slice_end()

# ---- SLICE 6: stack, powers, next issue, letters heading
slice_begin("06-stack", None, "The utility belt, known powers and next issue")
banner("THE UTILITY BELT", BLU, YEL, "march")
y += 20
rows([
    ("1", "Languages:  Java, TypeScript, JavaScript, Python, C"),
    ("2", "Frontend:  Next.js, React, Tailwind CSS, Shadcn UI, HTML, CSS"),
    ("3", "Backend:  Node.js, Express, REST APIs"),
    ("4", "Database:  MongoDB, PostgreSQL, MySQL, Redis, Firebase, Supabase"),
    ("5", "AI and LLMs:  OpenAI, Gemini, Claude, Groq, NVIDIA NIM"),
    ("6", "Cloud and DevOps:  Git, GitHub, Docker, Vercel, Netlify, Render"),
], label_w=78)

banner("KNOWN POWERS", YEL, INK, "burst")
y += 20
POWERS = ["AI agents and autonomy", "Electron desktop apps", "Full stack web platforms",
          "AI-powered education", "Developer tooling", "Voice interfaces",
          "RAG and knowledge systems", "Premium UI/UX detail", "Performance tuning"]
cw3 = (CONTENT - 24) / 3
for r in range(3):
    for c in range(3):
        t = POWERS[r * 3 + c]
        bx = PAD + c * (cw3 + 12)
        add(f'<rect x="{bx:.0f}" y="{y}" width="{cw3:.0f}" height="78" fill="{CREAM}" '
            f'stroke="{INK}" stroke-width="4"></rect>')
        for j, ln in enumerate(wrap(MC, t, 23, cw3 - 24)):
            add(body(ln, bx + cw3 / 2, y + 34 + j * 28, 23, INK, "middle"))
    y += 90
y += 22

NH = 118
add(f'<clipPath id="nx"><rect x="{PAD}" y="{y}" width="{CONTENT}" height="{NH}"></rect></clipPath>')
add(f'<rect x="{PAD}" y="{y}" width="{CONTENT}" height="{NH}" fill="{INK}"></rect>')
add(f'<g clip-path="url(#nx)"><path class="pulse" d="{rays(240, y+58, 14, False, 620)}" '
    f'stroke="{BLU}" stroke-width="5" fill="none"></path></g>')
add(f'<rect x="{PAD}" y="{y}" width="{CONTENT}" height="{NH}" fill="none" stroke="{INK}" stroke-width="6"></rect>')
add(bang("NEXT ISSUE...", PAD + 26, y + 74, 54, YEL, 3))
sw = wide(MB, "COMING SOON", 28, 3) + 44
add(f'<g class="blink"><rect x="{W-PAD-28-sw:.0f}" y="{y+36}" width="{sw:.0f}" height="46" '
    f'fill="{RED}" stroke="{CREAM}" stroke-width="4"></rect>'
    + bang("COMING SOON", W - PAD - 28 - sw / 2, y + 68, 28, CREAM, 3, "middle") + '</g>')
y += NH + 24
y += para(wrap(MC, "AI agents, MCP, RAG and LLM workflows. Desktop automation, system design, "
                   "and the daily grind of data structures and algorithms.", 29, CONTENT - 20),
          PAD + 8, 29, INK, 42) + 34
banner("LETTERS PAGE", CREAM, INK)
y += 20
y += para(wrap(MC, "Write in. Interesting problems get answered first. Every line below is a link.",
                29, CONTENT - 20), PAD + 8, 29, INK, 42) + 18
slice_end()

# ---- SLICES 7-11: one clickable contact row each
CONTACTS = [
    ("07-c-portfolio", "Portfolio", "hakkan.is-a.dev", PORTFOLIO),
    ("08-c-persist", "Persist", "hakkan.persist.org", "https://hakkan.persist.org"),
    ("09-c-email", "Email", "hakkanparbej@gmail.com", "mailto:hakkanparbej@gmail.com"),
    ("10-c-linkedin", "LinkedIn", "linkedin.com/in/Hakkan", "https://linkedin.com/in/Hakkan"),
    ("11-c-github", "GitHub", "github.com/HakkanShah", "https://github.com/HakkanShah"),
]
for i, (name, label, value, href) in enumerate(CONTACTS):
    slice_begin(name, href, f"{label} - {value}")
    contact_row(label, value, i)
    slice_end()

# ---- SLICE 12: colophon
slice_begin("12-colophon", None, "Approved by the Commits Code Authority - printed in Kolkata")
y += 24
FH = 96
add(f'<rect x="{PAD}" y="{y}" width="{CONTENT}" height="{FH}" fill="{CREAM}" stroke="{INK}" stroke-width="6"></rect>')
add(f'<rect x="{PAD+22}" y="{y+20}" width="250" height="56" fill="none" stroke="{INK}" stroke-width="4"></rect>')
add(bang("APPROVED BY THE", PAD + 147, y + 42, 19, INK, 1, "middle"))
add(bang("COMMITS CODE AUTHORITY", PAD + 147, y + 66, 19, INK, 1, "middle"))
add(bang("PRINTED IN KOLKATA - ALL BUGS RESERVED", PAD + 296, y + 58, 23, DIM, 2))
bx = W - PAD - 130
for bw in [3, 2, 5, 2, 4, 2, 6, 2, 4, 5, 2, 4, 2, 5, 2]:
    add(f'<rect x="{bx}" y="{y+28}" width="{bw}" height="42" fill="{INK}"></rect>')
    bx += bw + 4
y += FH + PAD
slice_end()

# ---------------------------------------------------------------------- assemble

KEYFRAMES = """
@keyframes breathe { 0%, 100% { transform: scale(1); } 48% { transform: scale(1.018); } }
@keyframes spin { to { transform: rotate(360deg); } }
@keyframes pulse { 0%, 100% { opacity: 0.40; } 50% { opacity: 0.80; } }
@keyframes drift { to { transform: translate(180px, 180px); } }
@keyframes bob { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-8px); } }
@keyframes blink { 0%, 49% { opacity: 1; } 50%, 100% { opacity: 0.1; } }
@keyframes march { to { transform: translateX(34px); } }
@keyframes pop1 { 0%, 100% { transform: scale(1) rotate(-5deg); } 46% { transform: scale(1.06) rotate(-5deg); } }
@keyframes pop2 { 0%, 100% { transform: scale(1) rotate(4deg); } 46% { transform: scale(1.06) rotate(4deg); } }
@keyframes pop3 { 0%, 100% { transform: scale(1) rotate(-3deg); } 46% { transform: scale(1.06) rotate(-3deg); } }
@keyframes pop4 { 0%, 100% { transform: scale(1) rotate(5deg); } 46% { transform: scale(1.06) rotate(5deg); } }
.bang { font-family: "Bangers", Impact, sans-serif; }
.body { font-family: "ComicNeue", "Trebuchet MS", Verdana, sans-serif; font-weight: 700; }
.breathe { animation: breathe 5.5s ease-in-out infinite; transform-origin: left center; }
.spin { animation: spin 26s linear infinite; }
.pulse { animation: pulse 3.2s ease-in-out infinite; }
.drift { animation: drift 44s linear infinite; }
.bob { animation: bob 4.6s ease-in-out infinite; }
.bob2 { animation: bob 5.9s ease-in-out infinite; }
.blink { animation: blink 1.4s steps(1, end) infinite; }
.march { animation: march 2.2s linear infinite; }
.pop1 { animation: pop1 2.4s ease-in-out infinite; }
.pop2 { animation: pop2 2.9s ease-in-out infinite; }
.pop3 { animation: pop3 2.6s ease-in-out infinite; }
.pop4 { animation: pop4 3.1s ease-in-out infinite; }
@media (prefers-reduced-motion: reduce) {
  .breathe, .spin, .pulse, .drift, .bob, .bob2, .blink, .march,
  .pop1, .pop2, .pop3, .pop4 { animation: none; }
}
"""

os.makedirs(OUT, exist_ok=True)
# Every slice filename carries a hash of its own content. GitHub proxies README
# images through camo, which caches by URL, so rewriting a file in place leaves
# the old picture on the page. A new hash means a new URL means a fresh fetch.
for stale in glob.glob(os.path.join(OUT, "page-*.svg")):
    os.remove(stale)
total = len(SLICES)
total_bytes = 0
rows_md = []

for idx, s in enumerate(SLICES):
    h = s["y1"] - s["y0"]
    faces = ""
    if s["bg"]:
        faces += (f'@font-face {{ font-family: "Bangers"; font-style: normal; font-weight: 400; '
                  f'src: url(data:font/woff2;base64,{font_b64(BANGERS_SRC, "".join(sorted(s["bg"])))}) format("woff2"); }}\n')
    if s["cg"]:
        faces += (f'@font-face {{ font-family: "ComicNeue"; font-style: normal; font-weight: 700; '
                  f'src: url(data:font/woff2;base64,{font_b64(COMIC_SRC, "".join(sorted(s["cg"])))}) format("woff2"); }}\n')

    # page edges: side bars always, cap the top of the first slice and the bottom of the last
    edges = (f'<rect x="0" y="0" width="8" height="{h}" fill="{INK}"></rect>'
             f'<rect x="{W-8}" y="0" width="8" height="{h}" fill="{INK}"></rect>')
    if idx == 0:
        edges += f'<rect x="0" y="0" width="{W}" height="8" fill="{INK}"></rect>'
    if idx == total - 1:
        edges += f'<rect x="0" y="{h-8}" width="{W}" height="8" fill="{INK}"></rect>'

    svg = f'''<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{h}" viewBox="0 0 {W} {h}" role="img" aria-label="{esc(s['alt'])}">
<title>{esc(s['alt'])}</title>
<defs>
<style>{faces}{KEYFRAMES}</style>
<pattern id="dots" width="11" height="11" patternUnits="userSpaceOnUse"><circle cx="2.6" cy="2.6" r="2" fill="{CREAM}" opacity="0.30"></circle></pattern>
<pattern id="pdots" width="11" height="11" patternUnits="userSpaceOnUse" patternTransform="translate(0 {-s['y0'] % 11})"><circle cx="2.6" cy="2.6" r="2" fill="{INK}" opacity="0.07"></circle></pattern>
<clipPath id="cover"><rect x="0" y="{MAST}" width="{W}" height="{COVER}"></rect></clipPath>
</defs>
<rect width="{W}" height="{h}" fill="{PAPER}"></rect>
<rect width="{W}" height="{h}" fill="url(#pdots)"></rect>
<g transform="translate(0 {-s['y0']})">{"".join(s["frags"])}</g>
{edges}
</svg>
'''
    fname = f"page-{s['name']}.{hashlib.sha1(svg.encode()).hexdigest()[:8]}.svg"
    path = os.path.join(OUT, fname)
    open(path, "w").write(svg)
    size = os.path.getsize(path)
    total_bytes += size
    print(f"  {fname:26s} {W}x{h:<5d} {size/1024:6.1f} KB  {'-> ' + s['href'] if s['href'] else ''}")

    img = f'<img alt="{esc(s["alt"])}" src="assets/{fname}" width="100%" align="left">'
    rows_md.append(f'<a href="{s["href"]}">{img}</a>' if s["href"] else img)

print(f"  {'TOTAL':26s} {'':11s} {total_bytes/1024:6.1f} KB  ({total} slices)")

readme = "\n".join(rows_md) + '\n<br clear="all">\n'
readme += '''
<div align="center">

<img width="358" alt="Contribution streak" src="https://streak-stats.demolab.com?user=HakkanShah&background=F5ECD8&border=141418&stroke=141418&ring=E0241B&fire=E0241B&currStreakNum=141418&sideNums=141418&currStreakLabel=E0241B&sideLabels=141418&dates=6A6252&border_radius=0">
<img width="358" alt="Most used languages" src="https://github-readme-stats.vercel.app/api/top-langs/?username=HakkanShah&layout=compact&langs_count=6&card_width=420&bg_color=F5ECD8&title_color=E0241B&text_color=141418&border_color=141418&border_radius=0&title=Most%20Used%20Languages">

<br><br>

<img alt="Readers" src="https://komarev.com/ghpvc/?username=HakkanShah&label=READERS&color=E0241B&style=flat-square">

</div>
'''
open(os.path.join(REPO, "README.md"), "w").write(readme)
print("  README.md written")
