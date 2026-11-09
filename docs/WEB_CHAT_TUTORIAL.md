# Editing a figure from a chat web page (PyFigures web chat)

> **Experimental, not recommended: a last resort.** If you can, use the chat
> sidebar instead (**Tools → Chat sidebar**, with an API key, a local model or
> LM Studio): it works far better. Use the web page only if really nothing
> else is possible.
>
> **Before using it**, make sure it respects the **terms of service of the
> chat site** and **your institution's rules**: PyFigures types into the page
> and, with *Automatic* ticked, sends messages for you.

The web chat docks a chat site (Mistral Le Chat, ChatGPT, Claude, Gemini, or
your institute's chat page) beside the figure. You sign in to that site
yourself; no API key is needed. The model asks PyFigures for operations, and
PyFigures runs them on the open figure.

## 1. Install (once)

**Without Python:** download the **PyFigures Web Chat** app from the
[releases page](https://github.com/baigouy/PyFigures/releases)
(`PyFigures-WebChat-Windows.zip`, `PyFigures-WebChat-macOS-*.dmg`). It opens
with the web chat already docked; skip to step 3. (The plain PyFigures apps
leave the web page out: there the web chat only works through the clipboard.)

**With Python** (3.10 or newer), in a new environment:

```bash
pip install -U pyfigures PyQt6-WebEngine
```

The web chat needs PyFigures 0.2.6 or newer.

If PyQt6 is already installed in that environment, install the WebEngine that
matches its version instead (for PyQt6 6.4.x, for example):

```bash
pip show PyQt6
pip install "PyQt6-WebEngine==6.4.*"
```

Without PyQt6-WebEngine the panel still works through the clipboard (see the
end of this page).

## 2. Launch it

```bash
python -m pyfigures --web-chat
```

Or open PyFigures normally and choose **Tools → Chat in a web page
(experimental, not recommended)…**. Open or create your figure first: the chat
works on the figure in that window.

## 3. Choose the chat page and sign in

- At the top of the panel, choose a page in the address list (Mistral Le Chat,
  ChatGPT, Claude, Gemini), or type the address of another chat page (for
  example your institute's) and press **Enter**. Addresses you type are
  remembered.
- Sign in on the page as you would in your browser. The sign-in is kept for
  next time.
- Use the site's plain **chat** mode. "Agent" or "code" modes have tools of
  their own and tend to use them instead of answering PyFigures.

## 4. Ask for a change

**The simple way:** type your request in the panel's own box, for example
`make channel 2 yellow in panel a`, and click **Send** (or press Enter). The
first request also gives the chat the instructions and the figure.

**Step by step (the manual way):**

1. Click **Start: give the chat the figure**. PyFigures writes its
   instructions and the figure into the page's message box. Add your request
   after it and press the page's Send button.
2. When the model wants something done, the panel lists the operations it
   asks for. Click **Apply** to run them (each one can be undone with Ctrl+Z)
   or **Dismiss** to refuse them. Look-ups that change nothing run by
   themselves (untick *Run look-ups without asking* to stop that).
3. The results go into the page's message box: press Send so the model sees
   them and carries on.

## 5. Automatic mode (optional)

Tick **Automatic** to let PyFigures do the clicking:

- once you are signed in and the chat's message box shows, it sends the
  instructions and the figure by itself (once per conversation);
- it applies every operation the model asks for and sends the results back,
  round after round, until the model answers without operations (at most 20
  rounds per request);
- **Stop** pauses it at once; Ctrl+Z undoes each change.

Automatic is off by default: sending messages for you is scripted use of the
site, which some sites' terms or institutions' rules do not allow.

## 6. Tips and problems

- **Start over with a new sign-in:** close PyFigures, then delete the folder
  `pyfigures-web-chat` in `%APPDATA%\python\QtWebEngine\` (Windows).
- **Copy the last preview** puts the latest figure preview on the clipboard,
  to paste into the chat if the site accepts images.
- **Clipboard mode** (no PyQt6-WebEngine): choosing a page in the address list
  opens it in your usual browser. Click **Start**, paste (Ctrl+V) into the
  chat and send; copy the model's answer and click **Read a copied reply**.
  Results are put on the clipboard for you to paste back.
- What the panel did (operations found, results, statuses; no page text, no
  passwords) is written to `web_chat.log` in PyFigures' live folder, which
  helps when something went wrong.
