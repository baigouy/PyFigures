"""The self-contained reviewer-facing HTML page (image + click-to-pin comment UI).

Kept isolated from html_export.py so the ~150-line markup/JS blob doesn't
clutter the actual export/import logic.
"""

TEMPLATE = """<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>PyFigures review — __SOURCE_NAME__</title>
<style>
  body { font-family: -apple-system, Segoe UI, Arial, sans-serif; margin: 0; display: flex; height: 100vh; background: #1e1e1e; color: #eee; }
  #main { flex: 1; overflow: auto; display: flex; align-items: flex-start; justify-content: center; padding: 20px; }
  #imgwrap { position: relative; display: inline-block; cursor: crosshair; }
  #imgwrap img { max-width: 100%; display: block; box-shadow: 0 0 12px rgba(0,0,0,0.6); }
  .pin { position: absolute; width: 22px; height: 22px; margin-left: -11px; margin-top: -11px;
         background: #e0442b; color: white; border-radius: 50% 50% 50% 0; transform: rotate(-45deg);
         display: flex; align-items: center; justify-content: center; font-size: 12px; font-weight: bold;
         box-shadow: 0 1px 3px rgba(0,0,0,0.5); }
  .pin span { transform: rotate(45deg); }
  .box { position: absolute; border: 2px solid #e0442b; box-shadow: 0 0 0 1px rgba(0,0,0,0.5);
         pointer-events: none; }
  .box span { position: absolute; left: -2px; top: -20px; background: #e0442b; color: white;
              font-size: 12px; font-weight: bold; padding: 1px 5px; border-radius: 3px; }
  #drawing { position: absolute; border: 2px dashed #ffd400; pointer-events: none; display: none; }
  #general { width: 100%; box-sizing: border-box; padding: 6px; margin: 4px 0 4px; background: #2a2a2a;
             border: 1px solid #555; color: #eee; border-radius: 4px; min-height: 54px; font-family: inherit; }
  #copied { font-size: 11px; color: #7fd47f; margin-top: 6px; display: none; }
  #sidebar { width: 320px; border-left: 1px solid #444; padding: 14px; overflow-y: auto; box-sizing: border-box; }
  #sidebar h2 { font-size: 15px; margin: 0 0 10px; }
  #sidebar input[type=text] { width: 100%; box-sizing: border-box; padding: 6px; margin-bottom: 12px;
                               background: #2a2a2a; border: 1px solid #555; color: #eee; border-radius: 4px; }
  .comment { background: #2a2a2a; border: 1px solid #444; border-radius: 6px; padding: 8px; margin-bottom: 8px; }
  .comment .head { display: flex; justify-content: space-between; font-size: 11px; color: #999; margin-bottom: 4px; }
  .comment .body { font-size: 13px; white-space: pre-wrap; }
  .comment .del { cursor: pointer; color: #e0442b; }
  #hint { font-size: 12px; color: #999; margin-bottom: 14px; }
  #dl, #mail, #copy { width: 100%; padding: 10px; margin-top: 10px; background: #3a7afe; color: white; border: none;
        border-radius: 4px; cursor: pointer; font-size: 13px; }
  #dl:hover, #mail:hover, #copy:hover { background: #2a63e0; }
  #mail, #copy { background: #3a3a3a; }
  #mail:hover, #copy:hover { background: #4a4a4a; }
</style>
</head>
<body>
<div id="main">
  <div id="imgwrap">
    <img id="figimg" src="__IMAGE_DATA_URI__" alt="figure" draggable="false">
    <div id="drawing"></div>
  </div>
</div>
<div id="sidebar">
  <h2>Review: __SOURCE_NAME__</h2>
  <div id="hint">Click on the figure to pin a numbered comment, or drag to draw a box around a
    region and comment on it. When you're done, click "Save reviewed copy" and send that file back.</div>
  <input type="text" id="author" placeholder="Your name (optional)">
  <div style="font-size:12px;color:#bbb;">About the whole figure:</div>
  <textarea id="general" placeholder="A general comment (optional)"></textarea>
  <div id="list"></div>
  <button id="dl">Save reviewed copy</button>
  <button id="copy" title="Copies your comments as text, to paste into any email or chat">Copy my comments</button>
  <div id="copied">Copied: paste them into your email or chat.</div>
  <button id="mail" title="Opens your computer's default mail program">Send back by email</button>
  <div id="mailhint" style="font-size:11px;color:#999;margin-top:8px;display:none;">
    A reviewed copy was saved to your downloads and an email draft was opened
    with your comments — please attach that downloaded file before sending.
  </div>
</div>
<script id="pyfigures-review-data" type="application/json">__COMMENTS_JSON__</script>
<script>
(function() {
  var dataEl = document.getElementById('pyfigures-review-data');
  var data = JSON.parse(dataEl.textContent || '{"comments":[]}');
  var comments = data.comments || [];
  var wrap = document.getElementById('imgwrap');
  var img = document.getElementById('figimg');
  var list = document.getElementById('list');
  var authorInput = document.getElementById('author');
  if (data.author) authorInput.value = data.author;

  var general = document.getElementById('general');
  if (data.general) general.value = data.general;

  function render() {
    Array.prototype.slice.call(wrap.querySelectorAll('.pin, .box')).forEach(function(p) { p.remove(); });
    list.innerHTML = '';
    comments.forEach(function(c, i) {
      var pin = document.createElement('div');
      if (c.w && c.h) {
        // a comment on a region: its box, numbered
        pin.className = 'box';
        pin.style.left = (c.x * 100) + '%';
        pin.style.top = (c.y * 100) + '%';
        pin.style.width = (c.w * 100) + '%';
        pin.style.height = (c.h * 100) + '%';
      } else {
        pin.className = 'pin';
        pin.style.left = (c.x * 100) + '%';
        pin.style.top = (c.y * 100) + '%';
      }
      pin.innerHTML = '<span>' + (i + 1) + '</span>';
      wrap.appendChild(pin);

      var item = document.createElement('div');
      item.className = 'comment';
      var head = document.createElement('div');
      head.className = 'head';
      head.innerHTML = '<span>#' + (i + 1) + (c.author ? ' — ' + escapeHtml(c.author) : '') + '</span>';
      var del = document.createElement('span');
      del.className = 'del';
      del.textContent = 'remove';
      del.onclick = function() { comments.splice(i, 1); render(); };
      head.appendChild(del);
      var body = document.createElement('div');
      body.className = 'body';
      body.textContent = c.text;
      item.appendChild(head);
      item.appendChild(body);
      list.appendChild(item);
    });
  }

  function escapeHtml(s) {
    var d = document.createElement('div');
    d.textContent = s;
    return d.innerHTML;
  }

  // click: a pin; drag: a box around a region
  var drawing = document.getElementById('drawing');
  var start = null;
  function frac(ev) {
    var rect = img.getBoundingClientRect();
    return {x: Math.min(1, Math.max(0, (ev.clientX - rect.left) / rect.width)),
            y: Math.min(1, Math.max(0, (ev.clientY - rect.top) / rect.height)),
            px: ev.clientX, py: ev.clientY};
  }
  wrap.addEventListener('mousedown', function(ev) {
    if (ev.button !== 0) return;
    start = frac(ev);
    ev.preventDefault();
  });
  window.addEventListener('mousemove', function(ev) {
    if (!start) return;
    var p = frac(ev);
    drawing.style.display = 'block';
    drawing.style.left = (Math.min(start.x, p.x) * 100) + '%';
    drawing.style.top = (Math.min(start.y, p.y) * 100) + '%';
    drawing.style.width = (Math.abs(p.x - start.x) * 100) + '%';
    drawing.style.height = (Math.abs(p.y - start.y) * 100) + '%';
  });
  window.addEventListener('mouseup', function(ev) {
    if (!start) return;
    var p = frac(ev), s = start;
    start = null;
    drawing.style.display = 'none';
    var dragged = Math.abs(p.px - s.px) > 6 || Math.abs(p.py - s.py) > 6;
    var text = window.prompt(dragged ? 'Comment on this region:' : 'Comment:');
    if (!text) return;
    var c = {x: dragged ? Math.min(s.x, p.x) : s.x, y: dragged ? Math.min(s.y, p.y) : s.y,
             text: text, author: authorInput.value || '', ts: new Date().toISOString()};
    if (dragged) { c.w = Math.abs(p.x - s.x); c.h = Math.abs(p.y - s.y); }
    comments.push(c);
    render();
  });

  function commentLines() {
    var lines = ['Review comments for __SOURCE_NAME__:', ''];
    if (general.value.trim()) lines.push('Whole figure: ' + general.value.trim(), '');
    comments.forEach(function(c, i) {
      lines.push('#' + (i + 1) + (c.w ? ' (region)' : '') + (c.author ? ' (' + c.author + ')' : '') +
                 ': ' + c.text);
    });
    return lines;
  }

  function downloadReviewedCopy() {
    dataEl.textContent = JSON.stringify({
      comments: comments, author: authorInput.value || '', owner_email: data.owner_email || '',
      general: general.value || ''
    });
    var html = '<!doctype html>\\n' + document.documentElement.outerHTML;
    var blob = new Blob([html], {type: 'text/html'});
    var a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = 'reviewed___SOURCE_NAME__.html';
    a.click();
  }

  document.getElementById('dl').addEventListener('click', downloadReviewedCopy);

  document.getElementById('copy').addEventListener('click', function() {
    var text = commentLines().join('\\n');
    function shown() { document.getElementById('copied').style.display = 'block'; }
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(shown, function() { fallback(text); shown(); });
    } else { fallback(text); shown(); }
  });
  function fallback(text) {
    var t = document.createElement('textarea');
    t.value = text;
    document.body.appendChild(t);
    t.select();
    try { document.execCommand('copy'); } catch (e) {}
    t.remove();
  }

  document.getElementById('mail').addEventListener('click', function() {
    if (!comments.length && !general.value.trim()) {
      window.alert('Add at least one comment first.');
      return;
    }
    downloadReviewedCopy();
    var lines = commentLines();
    lines.push('', 'A reviewed copy (with pins) is attached — please attach the file ' +
               'just downloaded to your Downloads folder ("reviewed___SOURCE_NAME__.html") before sending.');
    var subject = 'Figure review comments — __SOURCE_NAME__';
    var mailto = 'mailto:' + (data.owner_email || '') +
                 '?subject=' + encodeURIComponent(subject) +
                 '&body=' + encodeURIComponent(lines.join('\\n'));
    window.location.href = mailto;
    document.getElementById('mailhint').style.display = 'block';
  });

  render();
})();
</script>
</body>
</html>
"""
