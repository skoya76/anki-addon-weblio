from re import A
from aqt import mw
from aqt.qt import *
from aqt import editor
from anki import notes

from . import downloader


def doDownload() -> None:
    downloader.Download_Ui(mw=mw,title="Japanese Word Meanings and Pronunciations Downloader",)

action = QAction("Japanese Word Meanings and Pronunciations Downloader", mw)
qconnect(action.triggered, doDownload)
mw.form.menuTools.addAction(action)
