# Copyright: Ankitects Pty Ltd and contributors
# License: GNU AGPL, version 3 or later; http://www.gnu.org/licenses/agpl.html

from __future__ import annotations
from calendar import formatstring

from typing import Callable

import aqt
import aqt.forms
import aqt.operations
from anki.collection import OpChangesWithId
from anki.decks import DeckId
from aqt import gui_hooks
from aqt.operations.deck import add_deck_dialog
from aqt.qt import *
from aqt.utils import (
    HelpPage,
    HelpPageArgument,
    disable_help_button,
    openHelp,
    restoreGeom,
    saveGeom,
    shortcut,
    showInfo,
    tr,
)

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
        #buttons: list[str | QPushButton] | None = None,
        #geomKey: str = "default",
        callback: Callable[[StudyDeck], None] | None = None,
    ) -> None:
        super().__init__(parent)
        if not parent:
            mw.garbage_collect_on_dialog_finish(self)
        self.mw = mw
        self.form = aqt.forms.studydeck.Ui_Dialog()
        self.form.setupUi(self)
        self.form.filter.installEventFilter(self)
        gui_hooks.state_did_reset.append(self.onReset)
        #self.geomKey = f"studyDeck-{geomKey}"
        #restoreGeom(self, self.geomKey)
        #disable_help_button(self)
        #if not cancel:
        #    self.form.buttonBox.removeButton(
        #        self.form.buttonBox.button(QDialogButtonBox.StandardButton.Cancel)
        #    )
        #if buttons is not None:
        #    for button_or_label in buttons:
        #        self.form.buttonBox.addButton(
        #            button_or_label, QDialogButtonBox.ButtonRole.ActionRole
        #        )
        #else:
        #    b = QPushButton(tr.actions_add())
        #    b.setShortcut(QKeySequence("Ctrl+N"))
        #    b.setToolTip(shortcut(tr.decks_add_new_deck_ctrlandn()))
        #    self.form.buttonBox.addButton(b, QDialogButtonBox.ButtonRole.ActionRole)
        #    qconnect(b.clicked, self.onAddDeck)
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
        #self.form.buttonBox.addButton(
        #    accept or tr.decks_study(), QDialogButtonBox.ButtonRole.AcceptRole
        #)
        #self.setModal(True)
        #qconnect(self.form.buttonBox.helpRequested, lambda: openHelp(help))
        qconnect(self.form.filter.textEdited, self.redraw)
        qconnect(self.form.list.itemDoubleClicked, self.accept)
        #qconnect(self.finished, self.on_finished)
        self.show()
        # redraw after show so position at center correct
        self.redraw("", current)
        self.callback = callback
        if callback:
            self.show()
        else:
            self.exec()

    def eventFilter(self, obj: QObject, evt: QEvent) -> bool:
        if isinstance(evt, QKeyEvent) and evt.type() == QEvent.Type.KeyPress:
            new_row = current_row = self.form.list.currentRow()
            rows_count = self.form.list.count()
            key = evt.key()

            if key == Qt.Key.Key_Up:
                new_row = current_row - 1
            elif key == Qt.Key.Key_Down:
                new_row = current_row + 1
            elif (
                evt.modifiers() & Qt.KeyboardModifier.ControlModifier
                and Qt.Key.Key_1 <= key <= Qt.Key.Key_9
            ):
                row_index = key - Qt.Key.Key_1
                if row_index < rows_count:
                    new_row = row_index

            if rows_count:
                new_row %= rows_count  # don't let row index overflow/underflow
            if new_row != current_row:
                self.form.list.setCurrentRow(new_row)
                return True
        return False

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

    def onReset(self) -> None:
        # model updated?
        if self.nameFunc:
            self.origNames = self.nameFunc()
        self.redraw(self.filt, self.focus)

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
        #super().accept()
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

    #def on_finished(self) -> None:
    #    saveGeom(self, self.geomKey)
    #    gui_hooks.state_did_reset.remove(self.onReset)
