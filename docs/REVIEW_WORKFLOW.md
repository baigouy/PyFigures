# Figure review workflow

PyFigures has an optional way to collect feedback from colleagues on a figure
without giving them edit access, without any server, and without both of you
needing to be online at the same time. It lives under the **Review** menu and
is off by default — nothing about it runs unless you use it.

## What it is (and isn't)

- It is **asynchronous and single-writer**: you are always the only person who
  edits the `.pyf`. Reviewers never touch the real file.
- Reviewers get a **flattened snapshot** of the figure (a picture), not the
  editable project. They leave comments pinned to a location on that picture.
- There is **no live sync, no lock, no merge**. You export a snapshot, send it
  out, and import whatever comments come back whenever you're ready.

This was a deliberate simplification: PyFigures' `.pyf` format has no stable
per-element IDs, so real concurrent multi-editor collaboration (with 3-way
merge) isn't practical without a much larger rewrite. A review/comment loop
where you remain the sole editor sidesteps that entirely.

## Step by step

**1. Export for review.**
`File > Review comments > Export for review…` renders the current figure to an image and
packages it into a single self-contained HTML file (the image is embedded as
base64 — no separate image files, nothing to keep track of).

**2. Send that one file to your reviewer(s).**
Any way you like — email, Slack, a shared folder. Each reviewer gets their own
copy of the same file. After exporting, PyFigures offers to speed this up: if
you say yes and enter their email address(es), it opens a draft in your
default email client with the subject/body pre-filled and opens the file's
folder so you can drag it in as an attachment — you still hit Send yourself.
PyFigures never sends email on its own; there are no stored credentials and
nothing is transmitted without your final click.

**3. Reviewer opens it in a browser.**
No install, no account, no network connection required — it's a static HTML
file. They can type their name in a field at the top (optional, attaches to
their comments), then click anywhere on the figure to drop a numbered pin and
type a comment.

**4. Reviewer clicks "Save reviewed copy" (or "Send back by email").**
"Save reviewed copy" downloads a new HTML file with their comments baked in,
which they can send back however they like. "Send back by email" does the
same download, then opens an email draft — addressed to you directly if you
entered your email when exporting — with the comments listed in the body and
a reminder to attach the file that was just downloaded. Same rule as the
owner side: it only opens a compose window, it never sends anything by
itself.

**5. Import their comments.**
`File > Review comments > Import review comments…`, pick the file they sent back. Their
comments are extracted and merged into a small sidecar file next to your
`.pyf` (`<name>.review.json`) — never inside the `.pyf` itself, so this never
touches PyFigures' own save/load format. A dialog immediately shows the
figure with all pins overlaid plus the comment text.

**6. Repeat for each reviewer.**
Importing multiple reviewers' files just appends to the same sidecar.
Re-importing the same file twice is harmless — duplicate comments (same
position + text + timestamp) are skipped.

**7. Act on the feedback.**
Edit the figure normally with PyFigures' regular tools. The imported comments
are just a reference list — nothing here edits the figure automatically.

**8. Clean up or go again.**
`File > Review comments > View review comments` reopens the pin/comment dialog at any time;
"Clear all (resolved)" wipes the sidecar once you're done with a round. For a
second pass, just export again — nothing carries over unless you explicitly
re-import.

## Things worth knowing

- **Pin numbers are per-session, not stable IDs.** If a reviewer says "see my
  comment #2", that's #2 in *their* browser tab. In your combined view (after
  importing multiple reviewers) it may show up under a different number,
  since numbering there is just "order imported."
- **Snapshots go stale.** If you re-export after making changes, reviewers who
  still have an older file are commenting against that older version. Their
  pin positions are still meaningful (mapped as a 0–1 fraction of the image),
  but tell them when you've sent a newer round.
- **No image files need to be shared.** Because the snapshot is a flattened
  raster embedded directly in the HTML, reviewers never need access to your
  source images, mounted drives, or the `.pyf` file itself — this is what
  makes it work equally well over a LAN or over the internet with zero extra
  setup.

## Where the code lives

`pyfigures/gui/review/` — `html_export.py` (export/import/sidecar logic, no
Qt dependency), `dialog.py` (the Qt viewer dialog), `send.py` (the `mailto:`
compose-and-attach helper — builds the URL and reveals the file in the OS
file manager; never sends anything itself), `_template.py` (the
reviewer-facing HTML/JS page, including its own inline copy of the
"send back by email" logic since that side has no Python/Qt). Wired into
the "Review" menu in `pyfigures/gui/pfgui.py`.
