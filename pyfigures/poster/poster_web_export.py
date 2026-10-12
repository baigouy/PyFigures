"""Builds the self-contained HTML "flip book" viewer for a poster/album —
see PosterCanvas.export_album_web(). Pure string/template code, no Qt: the
caller (poster_canvas.py) does all the rendering and hands this module a
plain list of already-encoded page images.

One file, no external assets (fonts/JS/CSS all inline, images embedded as
base64 data URIs) — safe to email, drop on a USB stick, or upload to any
plain web host/static-file share, unlike the source .pyfposter/.pyfalbum
which needs PyFigures installed to open.
"""
import html as _html
import json

_TEMPLATE = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
  :root {{
    --bg: #15161a;
    --stage: #0b0c0e;
    --ink: #eceef1;
    --muted: #9aa0ab;
    --accent: #d8b46a;
  }}
  * {{ box-sizing: border-box; }}
  html, body {{
    margin: 0; padding: 0; height: 100%;
    background: var(--bg); color: var(--ink);
    font-family: -apple-system, "Segoe UI", Helvetica, Arial, sans-serif;
    overflow: hidden;
  }}
  #stage {{
    position: relative; width: 100%; height: 100%;
    display: flex; align-items: center; justify-content: center;
    background: radial-gradient(ellipse at center, var(--stage) 0%, #000 130%);
  }}
  #perspective {{
    perspective: 2600px;
    width: min(92vw, 1100px);
    height: min(78vh, 900px);
    position: relative;
  }}
  .book {{
    position: absolute; inset: 0;
    transform-style: preserve-3d;
  }}
  .page {{
    position: absolute; inset: 0;
    transform-style: preserve-3d;
    transform-origin: left center;
    transition: transform 0.85s cubic-bezier(.45,.05,.2,1);
    will-change: transform;
    cursor: pointer;
  }}
  .page img {{
    position: absolute; inset: 0;
    width: 100%; height: 100%;
    object-fit: contain;
    background: #fff;
    box-shadow: 0 10px 40px rgba(0,0,0,.55);
    border-radius: 3px;
    backface-visibility: hidden;
  }}
  .page.flipped {{ transform: rotateY(-180deg); }}
  .hint {{
    position: absolute; inset: 0;
    display: flex;
  }}
  .hint div {{ flex: 1; }}

  #chrome {{
    position: fixed; left: 0; right: 0; bottom: 0;
    display: flex; align-items: center; justify-content: center;
    gap: 18px; padding: 14px 18px 20px;
    background: linear-gradient(to top, rgba(0,0,0,.55), transparent);
    z-index: 50;
  }}
  #title-bar {{
    position: fixed; top: 0; left: 0; right: 0;
    display: flex; align-items: center; justify-content: space-between;
    padding: 14px 20px;
    background: linear-gradient(to bottom, rgba(0,0,0,.5), transparent);
    z-index: 50;
    pointer-events: none;
  }}
  #title-bar .name {{ font-size: 15px; letter-spacing: .02em; color: var(--muted); }}
  #title-bar .count {{ font-size: 13px; color: var(--muted); font-variant-numeric: tabular-nums; }}
  button.nav {{
    appearance: none; border: none; cursor: pointer;
    width: 46px; height: 46px; border-radius: 50%;
    background: rgba(255,255,255,.08); color: var(--ink);
    font-size: 20px; display: flex; align-items: center; justify-content: center;
    transition: background .15s, transform .15s;
  }}
  button.nav:hover {{ background: rgba(255,255,255,.18); }}
  button.nav:active {{ transform: scale(0.92); }}
  button.nav:disabled {{ opacity: .25; cursor: default; }}
  button.nav:disabled:hover {{ background: rgba(255,255,255,.08); }}
  #dots {{
    display: flex; gap: 6px; align-items: center;
    max-width: 44vw; overflow-x: auto; padding: 4px 2px;
  }}
  #dots::-webkit-scrollbar {{ height: 4px; }}
  #dots::-webkit-scrollbar-thumb {{ background: rgba(255,255,255,.2); border-radius: 2px; }}
  .dot {{
    flex: 0 0 auto;
    width: 8px; height: 8px; border-radius: 50%;
    background: rgba(255,255,255,.25); cursor: pointer;
    transition: background .15s, transform .15s;
  }}
  .dot.current {{ background: var(--accent); transform: scale(1.35); }}
  #fs-btn {{ font-size: 16px; }}
  .fade-msg {{
    position: fixed; left: 50%; top: 50%; transform: translate(-50%,-50%);
    color: var(--muted); font-size: 14px; pointer-events: none;
    opacity: 0; transition: opacity .4s;
  }}
  .fade-msg.show {{ opacity: 1; }}
  @media (max-width: 640px) {{
    #perspective {{ width: 96vw; height: 72vh; }}
    button.nav {{ width: 40px; height: 40px; font-size: 17px; }}
    #dots {{ max-width: 36vw; }}
  }}
</style>
</head>
<body>
  <div id="title-bar">
    <span class="name">{title_escaped}</span>
    <span class="count" id="count"></span>
  </div>

  <div id="stage">
    <div id="perspective">
      <div class="book" id="book"></div>
      <div class="fade-msg" id="hintmsg">tap a side, use ← → , or swipe</div>
    </div>
  </div>

  <div id="chrome">
    <button class="nav" id="prev" title="Previous page (←)">&#10094;</button>
    <div id="dots"></div>
    <button class="nav" id="next" title="Next page (→)">&#10095;</button>
    <button class="nav" id="fs-btn" title="Full screen">&#10021;</button>
  </div>

<script>
(function() {{
  var PAGES = {pages_json};
  var book = document.getElementById('book');
  var dotsEl = document.getElementById('dots');
  var countEl = document.getElementById('count');
  var prevBtn = document.getElementById('prev');
  var nextBtn = document.getElementById('next');
  var fsBtn = document.getElementById('fs-btn');
  var hintMsg = document.getElementById('hintmsg');
  var current = 0;
  var n = PAGES.length;

  PAGES.forEach(function(p, i) {{
    var el = document.createElement('div');
    el.className = 'page';
    el.style.zIndex = (n - i);
    var img = document.createElement('img');
    img.src = p.src;
    img.alt = 'Page ' + (i + 1);
    img.draggable = false;
    el.appendChild(img);
    var hint = document.createElement('div');
    hint.className = 'hint';
    var left = document.createElement('div');
    var right = document.createElement('div');
    left.addEventListener('click', function(e) {{ e.stopPropagation(); goTo(current - 1); }});
    right.addEventListener('click', function(e) {{ e.stopPropagation(); goTo(current + 1); }});
    hint.appendChild(left);
    hint.appendChild(right);
    el.appendChild(hint);
    book.appendChild(el);

    var dot = document.createElement('div');
    dot.className = 'dot';
    dot.title = 'Page ' + (i + 1);
    dot.addEventListener('click', function() {{ goTo(i); }});
    dotsEl.appendChild(dot);
  }});

  function render() {{
    var pageEls = book.querySelectorAll('.page');
    pageEls.forEach(function(el, i) {{
      el.classList.toggle('flipped', i < current);
    }});
    var dotEls = dotsEl.querySelectorAll('.dot');
    dotEls.forEach(function(d, i) {{ d.classList.toggle('current', i === current); }});
    countEl.textContent = (current + 1) + ' / ' + n;
    prevBtn.disabled = current <= 0;
    nextBtn.disabled = current >= n - 1;
    var cur = dotEls[current];
    if (cur && cur.scrollIntoView) cur.scrollIntoView({{block: 'nearest', inline: 'center'}});
  }}

  function goTo(i) {{
    if (i < 0 || i >= n || i === current) return;
    current = i;
    render();
  }}

  prevBtn.addEventListener('click', function() {{ goTo(current - 1); }});
  nextBtn.addEventListener('click', function() {{ goTo(current + 1); }});

  document.addEventListener('keydown', function(e) {{
    if (e.key === 'ArrowRight' || e.key === ' ') {{ goTo(current + 1); e.preventDefault(); }}
    else if (e.key === 'ArrowLeft') {{ goTo(current - 1); e.preventDefault(); }}
  }});

  var touchStartX = null;
  document.getElementById('stage').addEventListener('touchstart', function(e) {{
    touchStartX = e.changedTouches[0].clientX;
  }}, {{passive: true}});
  document.getElementById('stage').addEventListener('touchend', function(e) {{
    if (touchStartX === null) return;
    var dx = e.changedTouches[0].clientX - touchStartX;
    if (Math.abs(dx) > 40) {{ dx < 0 ? goTo(current + 1) : goTo(current - 1); }}
    touchStartX = null;
  }}, {{passive: true}});

  fsBtn.addEventListener('click', function() {{
    if (!document.fullscreenElement) document.documentElement.requestFullscreen().catch(function(){{}});
    else document.exitFullscreen();
  }});

  setTimeout(function() {{ hintMsg.classList.add('show'); }}, 400);
  setTimeout(function() {{ hintMsg.classList.remove('show'); }}, 4200);

  render();
}})();
</script>
</body>
</html>
"""


def build_album_html(pages_data, title):
    """*pages_data*: list of {'src': data-uri-or-url string}, front cover
    first. *title* is shown in the top bar and <title>."""
    pages_json = json.dumps([{'src': p['src']} for p in pages_data], ensure_ascii=False)
    return _TEMPLATE.format(
        title=_html.escape(title),
        title_escaped=_html.escape(title),
        pages_json=pages_json,
    )
