from __future__ import annotations

from typing import Callable

import aqt
import aqt.forms
from aqt.qt import *

import urllib.request
import requests
from bs4 import BeautifulSoup
import re

class StudyDeck(QDialog):
    def __init__(
        self,
        mw: aqt.AnkiQt,
        names: Callable[[], list[str]] | None = None,
        accept: str | None = None,
        title: str | None = None,
        current: str | None = None,
        cancel: bool = True,
        parent: QWidget | None = None,
        dyn: bool = False,
        callback: Callable[[StudyDeck], None] | None = None,
    ) -> None:
        super().__init__(parent)
        if not parent:
            mw.garbage_collect_on_dialog_finish(self)
        self.mw = mw
        self.form = aqt.forms.studydeck.Ui_Dialog()
        self.form.setupUi(self)
        self.form.filter.installEventFilter(self)
        if title:
            self.setWindowTitle(title)
        if not names:
            names_ = [
                d.name
                for d in self.mw.col.decks.all_names_and_ids(
                    include_filtered=dyn, skip_empty_default=True
                )
            ]
            self.nameFunc = None
            self.origNames = names_
        else:
            self.nameFunc = names
            self.origNames = names()
        self.name: str | None = None
        qconnect(self.form.filter.textEdited, self.redraw)
        qconnect(self.form.list.itemDoubleClicked, self.accept)
        self.show()
        self.redraw("", current)
        self.callback = callback
        if callback:
            self.show()
        else:
            self.exec()

    def redraw(self, filt: str, focus: str | None = None) -> None:
        self.filt = filt
        self.focus = focus
        self.names = [n for n in self.origNames if self._matches(n, filt)]
        l = self.form.list
        l.clear()
        l.addItems(self.names)
        if focus in self.names:
            idx = self.names.index(focus)
        else:
            idx = 0
        l.setCurrentRow(idx)
        l.scrollToItem(l.item(idx), QAbstractItemView.ScrollHint.PositionAtCenter)

    def _matches(self, name: str, filt: str) -> bool:
        name = name.lower()
        filt = filt.lower()
        if not filt:
            return True
        for word in filt.split(" "):
            if word not in name:
                return False
        return True

    def accept(self) -> None:
        row = self.form.list.currentRow()
        if row < 0:
            showInfo(tr.decks_please_select_something())
            return
        self.name = self.names[self.form.list.currentRow()]
        self.accept_with_callback()

    def accept_with_callback(self) -> None:
        if self.callback:
            self.callback(self)
        self.downloader()
    
    def formatting(self, st):
        pattern = '</style>*'
        result = st.split('</style>')[1]
        return result

    def mp3_collector(self, soup):
        elm = soup.find('source').get('src')
        pattern = 'audio/(.*\.mp3)'
        result = re.findall(pattern, elm, re.S)
        name = result[0]
        r = requests.get(elm)
        open(name, 'wb').write(r.content)
        return name

    def req_weblio(self, value):
        word = value.replace(' ','+')
        url = "https://ejje.weblio.jp/content/{}".format(word)
        page = urllib.request.urlopen(url)
        soup = BeautifulSoup(page, 'html.parser')
        mean_elm = soup.find('span', class_='content-explanation ej')
        if not mean_elm:
            return 'error'
        try:
            mp3_elm = self.mp3_collector(soup)
        except:
            return '{}'.format(mean_elm.text)
        return '{}[sound:{}]'.format(mean_elm.text, mp3_elm)
    
    def downloader(self):
        ids = self.mw.col.findCards("deck:{}".format(self.name))
        for id in ids:
            card = self.mw.col.getCard(id)
            note = card.note()
            reversed(note.items())
            for (name, value) in note.items():
                if not value:
                    word = self.formatting(card.q())
                    note[name] = self.req_weblio(word)
            note.flush()