"""Regenerate every animated SVG panel for the comic-book profile README.

    pip install fonttools brotli
    python3 tools/generate_comic_assets.py

Fonts are fetched from Google Fonts on first run and cached in
tools/.fontcache/ (git-ignored). Each panel embeds only the glyphs it
actually uses, which is why the whole set is ~130KB rather than ~800KB.

Why the fonts are embedded at all: an SVG loaded through an <img> tag
cannot fetch external resources, so a Google Fonts <link> would silently
fall back to a system font and the comic lettering would be lost.
"""
import base64, io, math, os, urllib.request
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

INK, RED, YEL, BLU, CREAM = "#141418", "#E0241B", "#FFCB05", "#1E5FD0", "#FFFBF0"

_cache = {}

def font_b64(path, text):
    """Subset a font to just the glyphs `text` needs, return base64 woff2."""
    key = (path, "".join(sorted(set(text))))
    if key in _cache:
        return _cache[key]
    font = TTFont(path)
    opts = subset.Options()
    opts.flavor = "woff2"
    opts.desubroutinize = True
    opts.layout_features = ["*"]
    opts.notdef_outline = True
    sub = subset.Subsetter(options=opts)
    sub.populate(text=text)
    sub.subset(font)
    buf = io.BytesIO()
    font.flavor = "woff2"
    font.save(buf)
    font.close()
    out = base64.b64encode(buf.getvalue()).decode("ascii")
    _cache[key] = out
    return out

BANGERS_SRC = os.path.join(CACHE, "bangers-latin.woff2")
COMIC_SRC = os.path.join(CACHE, "comicneue-700-latin.woff2")

# --------------------------------------------------------------------------- css

KEYFRAMES = """
@keyframes pop { 0%, 100% { transform: scale(1) rotate(__ROT__); } 46% { transform: scale(1.06) rotate(__ROT__); } }
@keyframes breathe { 0%, 100% { transform: scale(1); } 48% { transform: scale(1.022); } }
@keyframes spin { to { transform: rotate(360deg); } }
@keyframes pulse { 0%, 100% { opacity: 0.40; } 50% { opacity: 0.80; } }
@keyframes drift { to { transform: translate(180px, 180px); } }
@keyframes bob { 0%, 100% { transform: translateY(0); } 50% { transform: translateY(-9px); } }
@keyframes blink { 0%, 49% { opacity: 1; } 50%, 100% { opacity: 0.1; } }
@keyframes march { to { transform: translateX(44px); } }
"""

def css(fonts, extra="", rot="0deg"):
    face = ""
    for fam, b64 in fonts:
        face += (f'@font-face {{ font-family: "{fam}"; font-style: normal; font-weight: 400; '
                 f'src: url(data:font/woff2;base64,{b64}) format("woff2"); }}\n')
    base = """
.bang { font-family: "Bangers", Impact, "Haettenschweiler", sans-serif; }
.body { font-family: "ComicNeue", "Trebuchet MS", Verdana, sans-serif; font-weight: 700; }
.pop { animation: pop 2.6s ease-in-out infinite; }
.breathe { animation: breathe 5.5s ease-in-out infinite; }
.spin { animation: spin 26s linear infinite; }
.pulse { animation: pulse 3.2s ease-in-out infinite; }
.drift { animation: drift 44s linear infinite; }
.bob { animation: bob 4.6s ease-in-out infinite; }
.bob2 { animation: bob 5.9s ease-in-out infinite; }
.blink { animation: blink 1.4s steps(1, end) infinite; }
.march { animation: march 2.2s linear infinite; }
@media (prefers-reduced-motion: reduce) {
  .pop, .breathe, .spin, .pulse, .drift, .bob, .bob2, .blink, .march { animation: none; }
}
"""
    return (face + KEYFRAMES.replace("__ROT__", rot) + base + extra)

def doc(w, h, defs, body, aria, title):
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}" role="img" aria-label="{aria}">
<title>{title}</title>
<defs>
{defs}
</defs>
{body}
</svg>
'''

def dots_pattern(pid="dots", fill=CREAM, op="0.32"):
    return (f'<pattern id="{pid}" width="11" height="11" patternUnits="userSpaceOnUse">'
            f'<circle cx="2.6" cy="2.6" r="2" fill="{fill}" opacity="{op}"></circle></pattern>')

def frame(w, h, sw=8):
    return f'<rect x="{sw//2}" y="{sw//2}" width="{w-sw}" height="{h-sw}" fill="none" stroke="{INK}" stroke-width="{sw}"></rect>'

def burst_path(r_out=94, r_in=68, points=12):
    d = []
    for i in range(points * 2):
        a = math.pi * i / points - math.pi / 2
        r = r_out if i % 2 == 0 else r_in
        d.append(("M" if i == 0 else "L") + f"{r*math.cos(a):.1f} {r*math.sin(a):.1f}")
    return "".join(d) + "Z"

def rays(cx, cy, n=18, skip_left=True, reach=1600):
    out = []
    for i in range(n):
        a = 2 * math.pi * i / n + 0.18
        if skip_left and math.cos(a) < -0.30:
            continue
        out.append(f"M{cx} {cy}L{cx + reach*math.cos(a):.0f} {cy + reach*math.sin(a):.0f}")
    return " ".join(out)

def shadow_text(txt, x, y, size, ls, top, mid, bot, cls="bang"):
    """Three-pass comic lettering: ink block, colour lift, face."""
    return (f'<text class="{cls}" x="{x+12}" y="{y+12}" font-size="{size}" letter-spacing="{ls}" fill="{bot}">{txt}</text>'
            f'<text class="{cls}" x="{x+6}" y="{y+6}" font-size="{size}" letter-spacing="{ls}" fill="{mid}">{txt}</text>'
            f'<text class="{cls}" x="{x}" y="{y}" font-size="{size}" letter-spacing="{ls}" fill="{top}">{txt}</text>')

written = []
def write(name, svg):
    p = f"{OUT}/{name}"
    open(p, "w").write(svg)
    written.append((name, os.path.getsize(p)))

# =========================================================================== COVER

def cover():
    W, H, AT, AH = 1200, 680, 56, 548
    txt = "THE AMAZINGHAKKNFULSCIER.NO2KLATDIOFRW<>/!SHPD"
    bang = font_b64(BANGERS_SRC, txt + "0123456789")
    body = f'''
<rect width="{W}" height="{H}" fill="{BLU}"></rect>
<g clip-path="url(#art)">
  <rect x="0" y="{AT}" width="{W}" height="{AH}" fill="{BLU}"></rect>
  <g class="drift"><rect x="-220" y="-220" width="1700" height="1180" fill="url(#dots)"></rect></g>
  <path class="pulse" d="{rays(880, 320)}" stroke="{CREAM}" stroke-width="6" fill="none"></path>

  <g>
    <path d="M848 344C726 378 664 476 648 604L748 604C756 482 786 406 856 364Z" fill="{RED}" stroke="{INK}" stroke-width="5" stroke-linejoin="round"></path>
    <path d="M912 344C1034 378 1096 476 1112 604L1012 604C1004 482 974 406 904 364Z" fill="{RED}" stroke="{INK}" stroke-width="5" stroke-linejoin="round"></path>
    <rect x="862" y="282" width="36" height="52" fill="#07070A"></rect>
    <path d="M880 330C820 330 786 360 776 410L766 604H994L984 410C974 360 940 330 880 330Z" fill="{INK}"></path>
    <circle cx="880" cy="240" r="52" fill="{INK}"></circle>
    <path d="M828 240a52 52 0 0 1 104 0z" fill="#07070A"></path>
    <path d="M818 242a62 62 0 0 1 124 0" fill="none" stroke="{YEL}" stroke-width="9" stroke-linecap="round"></path>
    <rect x="806" y="230" width="23" height="44" rx="9" fill="{YEL}" stroke="{INK}" stroke-width="5"></rect>
    <rect x="931" y="230" width="23" height="44" rx="9" fill="{YEL}" stroke="{INK}" stroke-width="5"></rect>
    <rect x="774" y="558" width="212" height="16" rx="4" fill="{RED}" stroke="{INK}" stroke-width="5"></rect>
    <path d="M792 558l18-68h140l18 68z" fill="{YEL}" stroke="{INK}" stroke-width="6" stroke-linejoin="round"></path>
    <rect x="826" y="506" width="50" height="7" fill="{INK}"></rect>
    <rect x="826" y="520" width="80" height="7" fill="{INK}"></rect>
    <rect x="826" y="534" width="38" height="7" fill="{INK}"></rect>
  </g>

  <g class="bob">
    <circle cx="1092" cy="150" r="44" fill="{YEL}" stroke="{INK}" stroke-width="6"></circle>
    <text class="bang" x="1092" y="166" text-anchor="middle" font-size="40" fill="{INK}">AI</text>
  </g>
  <g class="bob2">
    <circle cx="1046" cy="352" r="32" fill="{YEL}" stroke="{INK}" stroke-width="6"></circle>
    <text class="bang" x="1046" y="365" text-anchor="middle" font-size="26" fill="{INK}">&#60;/&#62;</text>
  </g>

  <g transform="translate(160 500)">
    <g class="spin"><path d="{burst_path()}" fill="{YEL}" stroke="{INK}" stroke-width="6" stroke-linejoin="round"></path></g>
    <text class="bang" x="0" y="-16" text-anchor="middle" font-size="32" fill="{INK}">SHIPS</text>
    <text class="bang" x="0" y="16" text-anchor="middle" font-size="32" fill="{INK}">IN</text>
    <text class="bang" x="0" y="48" text-anchor="middle" font-size="32" fill="{INK}">PROD!</text>
  </g>

  <g transform="translate(48 172)">
    <g class="breathe">
      <text class="bang" x="4" y="4" font-size="60" letter-spacing="5" fill="{INK}">THE AMAZING</text>
      <text class="bang" x="0" y="0" font-size="60" letter-spacing="5" fill="{YEL}">THE AMAZING</text>
      {shadow_text("HAKKAN", 0, 132, 142, 2, CREAM, YEL, INK)}
    </g>
  </g>

  <g transform="translate(48 338)">
    <rect x="0" y="0" width="512" height="62" fill="{INK}" stroke="{CREAM}" stroke-width="5"></rect>
    <text class="bang" x="256" y="43" text-anchor="middle" font-size="32" letter-spacing="4" fill="{YEL}">FULL STACK AI ENGINEER</text>
  </g>
</g>

<rect x="0" y="0" width="{W}" height="{AT}" fill="{RED}"></rect>
<rect x="0" y="{AT - 3}" width="{W}" height="6" fill="{INK}"></rect>
<text class="bang" x="40" y="39" font-size="25" letter-spacing="3" fill="{CREAM}">NO. 22</text>
<text class="bang" x="600" y="39" text-anchor="middle" font-size="25" letter-spacing="3" fill="{CREAM}">KOLKATA EDITION</text>
<text class="bang" x="1160" y="39" text-anchor="end" font-size="25" letter-spacing="3" fill="{CREAM}">FREE TO FORK</text>

<rect x="0" y="604" width="{W}" height="76" fill="{CREAM}"></rect>
<rect x="0" y="601" width="{W}" height="6" fill="{INK}"></rect>
<text class="bang" x="40" y="664" font-size="46" letter-spacing="2" fill="{RED}">AT LAST!</text>
<text class="bang" x="286" y="664" font-size="46" letter-spacing="2" fill="{INK}">AN ENGINEER WHO SHIPS.</text>
{frame(W, H)}
'''
    defs = (f'<style>{css([("Bangers", bang)])}</style>' + dots_pattern()
            + f'<clipPath id="art"><rect x="0" y="{AT}" width="{W}" height="{AH}"></rect></clipPath>')
    write("comic-cover.svg", doc(W, H, defs, body,
        "THE AMAZING HAKKAN, issue 22. Hakkan Parbej Shah, Full Stack AI Engineer. Comic book cover.",
        "THE AMAZING HAKKAN &#8212; No. 22"))

# ========================================================================== BANNERS

def banner(name, label, bg, fg, motif="dots"):
    W, H = 1200, 124
    bang = font_b64(BANGERS_SRC, label + "0123456789")
    if motif == "burst":
        art = (f'<g transform="translate(1092 62)"><g class="spin">'
               f'<path d="{burst_path(44, 31, 10)}" fill="{YEL}" stroke="{INK}" stroke-width="5" stroke-linejoin="round"></path></g></g>')
    elif motif == "march":
        art = ('<g class="march">' + "".join(
            f'<rect x="{980 + i*44}" y="46" width="24" height="32" fill="{INK}" opacity="0.5"></rect>'
            for i in range(6)) + '</g>')
    else:
        art = (f'<g class="bob"><circle cx="1104" cy="62" r="30" fill="{INK}"></circle>'
               f'<circle cx="1104" cy="62" r="14" fill="{bg}"></circle></g>')
    body = f'''
<rect width="{W}" height="{H}" fill="{bg}"></rect>
<g clip-path="url(#bclip)">
  <g class="drift"><rect x="-220" y="-220" width="1700" height="700" fill="url(#dots)"></rect></g>
  {art}
</g>
<text class="bang" x="44" y="90" font-size="72" letter-spacing="4" fill="{fg}">{label}</text>
{frame(W, H)}
'''
    defs = (f'<style>{css([("Bangers", bang)])}</style>' + dots_pattern(fill=INK, op="0.12")
            + f'<clipPath id="bclip"><rect width="{W}" height="{H}"></rect></clipPath>')
    write(name, doc(W, H, defs, body, f"Section heading: {label}", label))

# ========================================================================== PANELS

def panel(name, sfx, title, tag, bg, sfx_face, sfx_mid, art, rot="-5deg"):
    W, H = 1200, 300
    chars = sfx + title + tag + "0123456789"
    bang = font_b64(BANGERS_SRC, chars)
    body = f'''
<rect width="{W}" height="{H}" fill="{bg}"></rect>
<g clip-path="url(#pclip)">
  <g class="drift"><rect x="-220" y="-220" width="1700" height="900" fill="url(#dots)"></rect></g>
  {art}
</g>
<g transform="translate(56 132)"><g class="pop">{shadow_text(sfx, 0, 0, 108, 3, sfx_face, sfx_mid, INK)}</g></g>
<g transform="translate(48 196)">
  <rect x="0" y="0" width="{int(len(title) * 29 + 56)}" height="66" fill="{INK}" stroke="{CREAM}" stroke-width="5"></rect>
  <text class="bang" x="28" y="48" font-size="46" letter-spacing="3" fill="{CREAM}">{title}</text>
</g>
<g transform="translate({W - int(len(tag) * 19 + 60)} 36)">
  <rect x="0" y="0" width="{int(len(tag) * 19 + 24)}" height="46" fill="{YEL}" stroke="{INK}" stroke-width="4"></rect>
  <text class="bang" x="{int(len(tag) * 19 + 24) // 2}" y="34" text-anchor="middle" font-size="30" letter-spacing="2" fill="{INK}">{tag}</text>
</g>
{frame(W, H)}
'''
    defs = (f'<style>{css([("Bangers", bang)], rot=rot)}</style>' + dots_pattern(op="0.22")
            + f'<clipPath id="pclip"><rect width="{W}" height="{H}"></rect></clipPath>')
    write(name, doc(W, H, defs, body, f"{title} panel &#8212; {sfx}", f"{title} &#8212; {sfx}"))

def art_speed():
    return ('<g class="pulse" stroke="' + CREAM + '" stroke-width="7" opacity="0.5">'
            + "".join(f'<path d="M{620 + (i%3)*70} {40 + i*32}h520"></path>' for i in range(8)) + '</g>')

def art_impact():
    return f'<path class="pulse" d="{rays(1020, 150, 16, skip_left=True, reach=900)}" stroke="{CREAM}" stroke-width="7" fill="none"></path>'

def art_rings():
    return ('<g class="pulse" fill="none" stroke="' + INK + '" stroke-width="7" opacity="0.45">'
            + "".join(f'<circle cx="1000" cy="150" r="{48 + i*46}"></circle>' for i in range(5)) + '</g>')

def art_grid():
    cells = []
    palette = [RED, YEL, RED, "#3A3A42", RED, YEL, "#3A3A42", RED]
    for r in range(5):
        for c in range(12):
            fill = palette[(r * 7 + c * 3) % len(palette)]
            cells.append(f'<rect x="{700 + c*38}" y="{60 + r*36}" width="28" height="28" fill="{fill}"></rect>')
    return '<g class="pulse" opacity="0.65">' + "".join(cells) + '</g>'

# ====================================================================== NEXT ISSUE

def next_issue():
    W, H = 1200, 170
    label, soon = "NEXT ISSUE...", "COMING SOON"
    bang = font_b64(BANGERS_SRC, label + soon)
    body = f'''
<rect width="{W}" height="{H}" fill="{INK}"></rect>
<g clip-path="url(#nclip)">
  <g class="drift"><rect x="-220" y="-220" width="1700" height="800" fill="url(#dots)"></rect></g>
  <path class="pulse" d="{rays(300, 85, 14, skip_left=False, reach=800)}" stroke="{BLU}" stroke-width="6" fill="none"></path>
</g>
<text class="bang" x="48" y="112" font-size="76" letter-spacing="4" fill="{YEL}">{label}</text>
<g class="blink" transform="translate(830 52)">
  <rect x="0" y="0" width="316" height="66" fill="{RED}" stroke="{CREAM}" stroke-width="5"></rect>
  <text class="bang" x="158" y="48" text-anchor="middle" font-size="40" letter-spacing="3" fill="{CREAM}">{soon}</text>
</g>
{frame(W, H)}
'''
    defs = (f'<style>{css([("Bangers", bang)])}</style>' + dots_pattern(op="0.14")
            + f'<clipPath id="nclip"><rect width="{W}" height="{H}"></rect></clipPath>')
    write("comic-next.svg", doc(W, H, defs, body, "Next issue teaser banner", "NEXT ISSUE"))

# ========================================================================== FOOTER

def footer():
    W, H = 1200, 140
    line1, line2 = "APPROVED BY THE", "COMMITS CODE AUTHORITY"
    tail = "PRINTED IN KOLKATA - ALL BUGS RESERVED"
    bang = font_b64(BANGERS_SRC, line1 + line2 + tail)
    bars = []
    widths = [4, 3, 6, 3, 5, 3, 8, 3, 5, 6, 3, 5, 3, 6, 3]
    x = 0
    for wdt in widths:
        bars.append(f'<rect x="{x}" y="0" width="{wdt}" height="54" fill="{INK}"></rect>')
        x += wdt + 5
    body = f'''
<rect width="{W}" height="{H}" fill="{CREAM}"></rect>
<g clip-path="url(#fclip)"><g class="drift"><rect x="-220" y="-220" width="1700" height="700" fill="url(#dots)"></rect></g></g>
<g transform="translate(40 32)">
  <rect x="0" y="0" width="330" height="76" fill="{CREAM}" stroke="{INK}" stroke-width="5"></rect>
  <text class="bang" x="165" y="32" text-anchor="middle" font-size="24" letter-spacing="1" fill="{INK}">{line1}</text>
  <text class="bang" x="165" y="62" text-anchor="middle" font-size="24" letter-spacing="1" fill="{INK}">{line2}</text>
</g>
<text class="bang" x="402" y="80" font-size="30" letter-spacing="2" fill="#6A6252">{tail}</text>
<g transform="translate(1056 43)">{"".join(bars)}</g>
{frame(W, H)}
'''
    defs = (f'<style>{css([("Bangers", bang)])}</style>' + dots_pattern(fill=INK, op="0.10")
            + f'<clipPath id="fclip"><rect width="{W}" height="{H}"></rect></clipPath>')
    write("comic-footer.svg", doc(W, H, defs, body, "Comics code stamp and barcode footer", "Colophon"))

# ============================================================================= run

ensure_fonts()
os.makedirs(OUT, exist_ok=True)
cover()
banner("comic-banner-origin.svg",  "ORIGIN STORY...",  YEL,   INK,  "dots")
banner("comic-banner-issue.svg",   "IN THIS ISSUE...", RED,   CREAM, "burst")
banner("comic-banner-arsenal.svg", "THE UTILITY BELT", BLU,   YEL,  "march")
banner("comic-banner-powers.svg",  "KNOWN POWERS",     YEL,   INK,  "burst")
banner("comic-banner-letters.svg", "LETTERS PAGE",     CREAM, INK,  "dots")

panel("comic-ohm.svg",       "TEACH!",     "OHM SCHOOL",  "FIRST APPEARANCE", BLU,  YEL,  RED,   art_speed(),  "-5deg")
panel("comic-aura.svg",      "AUTOMATE!",  "AURA DESKTOP","IN DEVELOPMENT",   RED,  YEL,  INK,   art_impact(), "4deg")
panel("comic-portfolio.svg", "TYPE!",      "PORTFOLIO",   "FAN FAVOURITE",    YEL,  RED,  CREAM, art_rings(),  "-3deg")
panel("comic-commit.svg",    "COMMIT!",    "COMMITHABIT", "DAILY SERIAL",     INK,  YEL,  RED,   art_grid(),   "5deg")

next_issue()
footer()

total = sum(s for _, s in written)
for n, s in written:
    print(f"  {n:30s} {s/1024:6.1f} KB")
print(f"  {'TOTAL':30s} {total/1024:6.1f} KB")
