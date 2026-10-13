"""Standalone launcher: `python -m pyfigures.album` opens the photo album
designer directly — the same window as the figure editor's
`Tools > Photo album designer…` menu.
"""
from pyfigures.poster.__main__ import run_poster_designer


def run_album_designer():
    run_poster_designer(album=True)


if __name__ == '__main__':
    run_album_designer()
