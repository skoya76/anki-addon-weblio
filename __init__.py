from re import A
from aqt import mw
from aqt.utils import showInfo, qconnect
from aqt.qt import *
from aqt import editor
from anki import notes

from . import downloader


def doDownload() -> None:
    downloader.StudyDeck(mw=mw,title="Get meanning and mp3 form weblio",)

action = QAction("Japanese Word Meanings and Pronunciations Downloader", mw)
qconnect(action.triggered, doDownload)
mw.form.menuTools.addAction(action)
