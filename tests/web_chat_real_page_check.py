"""The web chat panel against real Qt WebEngine pages (run by
test_web_chat_real_page.py in a process of its own: Qt WebEngine must be
imported before the QApplication, and may crash when the process ends).

Local pages only, in an off-the-record profile: nothing of the user's chat
login is read or written. Prints one JSON object: for each page, what the
page received and the panel's status line.
"""
import json
import sys

from qtpy.QtCore import QCoreApplication, QSettings, Qt, QTimer, QUrl
QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_ShareOpenGLContexts)
from qtpy.QtWidgets import QApplication
app = QApplication(sys.argv)
import pyfigures.gui.web_chat_panel as wcp

# the user's own choices (Automatic ticked, their chat address) stay out of it
wcp.QSettings = lambda org, name: QSettings(org + "-tests", name)

PAGES = {
    # sends on a real Enter key
    "enter": ('<div contenteditable="true" id=t style="min-height:40px"></div><script>var sent="";'
              'document.getElementById("t").addEventListener("keydown",e=>{if(e.key==="Enter"&&e.isTrusted){'
              'e.preventDefault();sent=e.target.innerText;e.target.innerText="";}});</script>'),
    # sends with its button only, named by its label
    "button": ('<textarea id=t></textarea><button aria-label="Send message" '
               'onclick="sent=t.value;t.value=\'\'">&gt;</button><script>var sent="";var t=document.getElementById("t");'
               '</script>'),
    # a search form's submit button, a Stop button, and the chat form's own unnamed submit button:
    # only the last one may be clicked
    "form": ('<form onsubmit="wrong=\'search\';return false"><input name=q><button type=submit>Go</button></form>'
             '<button aria-label="Stop sending" onclick="wrong=\'stop\'">x</button>'
             '<form onsubmit="sent=t.value;t.value=\'\';return false"><textarea id=t></textarea>'
             '<button type=submit>&gt;</button></form>'
             '<script>var sent="",wrong="";var t=document.getElementById("t");</script>'),
    # no button that sends: the user is told
    "none": ('<textarea id=t></textarea><form onsubmit="wrong=\'search\';return false"><button type=submit>Go</button>'
             '</form><script>var sent="",wrong="";</script>'),
    # a pasted preview reaches the page as a picture
    "image": ('<div contenteditable="true" id=t style="min-height:40px"></div><script>var sent="",pasted="";'
              'document.addEventListener("paste",e=>{var items=e.clipboardData.items;'
              'for(var i=0;i<items.length;i++){if(items[i].type.indexOf("image/")===0)pasted=items[i].type;}});'
              '</script>'),
}


class Panel(wcp.WebChatPanel):
    def _make_view(self, view_class, page_class, profile_class):
        self.profile = profile_class(self)           # no name: off the record
        self.popups = []
        self.view = view_class(self)
        self.view.setPage(page_class(self.profile, self.view))
        self._paste_action = page_class.WebAction.Paste

    def go(self):
        pass


panel = Panel(None)
panel.automatic.setChecked(False)
panel.resize(700, 600)
panel.show()
results = {}
order = list(PAGES)


def png():
    from qtpy.QtCore import QBuffer, QIODevice
    from qtpy.QtGui import QImage
    image = QImage(8, 8, QImage.Format.Format_RGB32)
    image.fill(0xff0000)
    buffer = QBuffer()
    buffer.open(QIODevice.OpenModeFlag.WriteOnly)
    image.save(buffer, "PNG")
    return bytes(buffer.data())


def run(i=0):
    if i == len(order):
        print("RESULTS " + json.dumps(results), flush=True)
        panel.timer.stop()
        app.quit()
        return
    name = order[i]

    def loaded(_ok):
        panel.view.loadFinished.disconnect(loaded)
        panel.write_to_chat("Hello from PyFigures\nline 2", "Test", send=name != "image",
                            image=png() if name == "image" else None)
        wait = 9500 if name == "none" else 4000      # "none": every try for the button is used up

        def read():
            panel.view.page().runJavaScript(
                "JSON.stringify({sent:sent, wrong:(typeof wrong==='undefined'?'':wrong), "
                "pasted:(typeof pasted==='undefined'?'':pasted), box:(document.getElementById('t').value||"
                "document.getElementById('t').innerText||'')})", 0,
                lambda value: (results.__setitem__(name, dict(json.loads(value), status=panel.status.text())),
                               run(i + 1)))
        QTimer.singleShot(wait, read)
    panel.view.loadFinished.connect(loaded)
    panel.view.setHtml("<html><body>" + PAGES[name] + "</body></html>", QUrl("https://example.org/"))


QTimer.singleShot(500, run)
QTimer.singleShot(90000, app.quit)
app.exec()
