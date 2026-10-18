# Animation test — comic cover

This page exists for one reason: to prove that an animated SVG survives GitHub's
image pipeline. If the cover below is moving, the whole comic concept is buildable.

<img alt="THE AMAZING HAKKAN — No. 22 — Full Stack AI Engineer" src="assets/comic-cover.svg" width="100%">

### What should be moving

| | |
|:---|:---|
| Halftone dots | drifting diagonally, 44s loop |
| Action rays | pulsing brighter and dimmer, 3.2s |
| Starburst | rotating once every 26s |
| `AI` and `</>` roundels | bobbing on separate rhythms |
| Title | breathing very slightly, 5.5s |

Nothing moves if your system is set to **reduce motion** — that is deliberate.

### Why it works

The SVG is fully self-contained. Both fonts (Bangers for the lettering, Comic Neue
for the blurb) are embedded directly in the file as base64 WOFF2, because an SVG
loaded through an `<img>` tag is not allowed to fetch anything external — a Google
Fonts link would silently fall back to a system font. The animation is plain CSS
`@keyframes` inside the SVG, which runs fine in an image context. No JavaScript,
because JavaScript would not run here.

### Links stay in markdown

Links inside an SVG do not survive GitHub, so every clickable thing lives in the
markdown underneath the art — like this:

[Portfolio](https://hakkan.is-a.dev) &nbsp;·&nbsp;
[Persist](https://hakkan.persist.org) &nbsp;·&nbsp;
[Email](mailto:hakkanparbej@gmail.com) &nbsp;·&nbsp;
[LinkedIn](https://linkedin.com/in/Hakkan)

---

Fonts are Bangers and Comic Neue, both SIL Open Font License, which permits embedding.
