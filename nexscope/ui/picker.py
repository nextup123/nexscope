"""
SDO object picker: searchable preset table -> selected list.

The same object set is recorded on every selected slave.
"""

from __future__ import annotations

from PyQt6 import QtGui, QtWidgets
from PyQt6.QtCore import Qt, pyqtSignal

from ..core.model import SdoObject
from .theme import Theme

# Common tracking pairs, by (index, subindex).
QUICK_SETS = {
    "Target vs Actual Pos": [("0x607A", 0), ("0x6064", 0)],
    "Vel + Torque": [("0x606C", 0), ("0x6077", 0)],
    "Following error": [("0x60F4", 0), ("0x6062", 0)],
    "Status + Mode": [("0x6041", 0), ("0x6061", 0)],
}


class ObjectPicker(QtWidgets.QWidget):
    selection_changed = pyqtSignal()

    def __init__(self, presets: list[SdoObject], favourites: list[str],
                 parent=None):
        super().__init__(parent)
        self.presets = presets
        self.selected: list[SdoObject] = []
        self.favourites: set[str] = set(favourites)
        self._by_key = {o.key: o for o in presets}
        self._build()

    # ------------------------------------------------------------------ #
    def _build(self):
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(10)

        # ---- left: search + table --------------------------------------- #
        left = QtWidgets.QVBoxLayout()
        left.setSpacing(6)

        search_row = QtWidgets.QHBoxLayout()
        self.search = QtWidgets.QLineEdit()
        self.search.setPlaceholderText(
            "Search name or index — e.g. 'position', '607A', 'velocity'…")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._filter)
        search_row.addWidget(self.search, 1)

        self.numeric_only = QtWidgets.QCheckBox("Numeric only")
        self.numeric_only.setToolTip(
            "Hide String objects — they can be logged but not plotted.")
        self.numeric_only.setChecked(True)
        self.numeric_only.stateChanged.connect(self._filter)
        search_row.addWidget(self.numeric_only)

        self.fav_only = QtWidgets.QCheckBox("★ Favourites")
        self.fav_only.setToolTip("Show only starred objects.")
        self.fav_only.stateChanged.connect(self._filter)
        search_row.addWidget(self.fav_only)
        left.addLayout(search_row)

        self.avail = QtWidgets.QTableWidget(0, 4)
        self.avail.setHorizontalHeaderLabels(["★", "Name", "Index", "Type"])
        hh = self.avail.horizontalHeader()
        hh.setSectionResizeMode(0, QtWidgets.QHeaderView.ResizeMode.Fixed)
        hh.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeMode.Stretch)
        hh.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        hh.setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self.avail.setColumnWidth(0, 30)
        self.avail.verticalHeader().setVisible(False)
        self.avail.setAlternatingRowColors(True)
        self.avail.setSelectionBehavior(
            QtWidgets.QAbstractItemView.SelectionBehavior.SelectRows)
        self.avail.setSelectionMode(
            QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection)
        self.avail.setEditTriggers(
            QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self.avail.doubleClicked.connect(self._on_double_click)
        left.addWidget(self.avail, 1)

        self.add_btn = QtWidgets.QPushButton("Add  →")
        self.add_btn.clicked.connect(self._add_selected)
        left.addWidget(self.add_btn)

        # ---- right: chosen ---------------------------------------------- #
        right = QtWidgets.QVBoxLayout()
        right.setSpacing(6)

        self.chosen_label = QtWidgets.QLabel("<b>Recording set</b>")
        right.addWidget(self.chosen_label)

        self.chosen = QtWidgets.QListWidget()
        self.chosen.setSelectionMode(
            QtWidgets.QAbstractItemView.SelectionMode.ExtendedSelection)
        self.chosen.setAlternatingRowColors(True)
        self.chosen.setMinimumHeight(150)
        self.chosen.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Expanding,
            QtWidgets.QSizePolicy.Policy.Expanding)
        right.addWidget(self.chosen, 1)

        btn_row = QtWidgets.QHBoxLayout()
        rm = QtWidgets.QPushButton("Remove")
        rm.clicked.connect(self._remove_selected)
        clr = QtWidgets.QPushButton("Clear all")
        clr.clicked.connect(self.clear)
        btn_row.addWidget(rm)
        btn_row.addWidget(clr)
        right.addLayout(btn_row)

        quick_box = QtWidgets.QGroupBox("Quick sets")
        qg = QtWidgets.QGridLayout(quick_box)
        qg.setSpacing(4)
        qg.setContentsMargins(8, 4, 8, 6)
        # 2 cols x 2 rows keeps this compact so the recording set gets the
        # vertical space instead.
        for i, label in enumerate(QUICK_SETS):
            b = QtWidgets.QPushButton(label)
            b.clicked.connect(lambda _=False, l=label: self._apply_quick(l))
            qg.addWidget(b, i // 2, i % 2)
        quick_box.setSizePolicy(
            QtWidgets.QSizePolicy.Policy.Preferred,
            QtWidgets.QSizePolicy.Policy.Fixed)
        right.addWidget(quick_box, 0)

        layout.addLayout(left, 3)
        layout.addLayout(right, 2)

        self._filter()

    # ------------------------------------------------------------------ #
    def apply_theme(self, theme: Theme):
        self._theme = theme
        self._filter()

    # -- filtering -------------------------------------------------------- #
    def _filter(self):
        q = self.search.text().strip().lower()
        num_only = self.numeric_only.isChecked()
        fav_only = self.fav_only.isChecked()

        rows = []
        for o in self.presets:
            if num_only and not o.is_numeric:
                continue
            if fav_only and o.key not in self.favourites:
                continue
            if q:
                hay = f"{o.name} {o.index} {o.index_hex} {o.display}".lower()
                if q not in hay:
                    continue
            rows.append(o)

        self._rows = rows
        self.avail.setRowCount(len(rows))
        for i, o in enumerate(rows):
            star = QtWidgets.QTableWidgetItem("★" if o.key in self.favourites else "☆")
            star.setTextAlignment(Qt.AlignmentFlag.AlignCenter)
            star.setToolTip("Click to toggle favourite")
            self.avail.setItem(i, 0, star)

            self.avail.setItem(i, 1, QtWidgets.QTableWidgetItem(o.name))
            self.avail.setItem(i, 2, QtWidgets.QTableWidgetItem(o.display))
            t = QtWidgets.QTableWidgetItem(o.data_type)
            if not o.is_numeric:
                t.setToolTip("Non-numeric — logged but not plotted.")
            self.avail.setItem(i, 3, t)

    def _on_double_click(self, index):
        if index.column() == 0:
            self._toggle_fav(index.row())
        else:
            self._add_selected()

    def _toggle_fav(self, row: int):
        o = self._rows[row]
        if o.key in self.favourites:
            self.favourites.discard(o.key)
        else:
            self.favourites.add(o.key)
        self._filter()

    # -- add / remove ----------------------------------------------------- #
    def add_object(self, obj: SdoObject):
        if any(o.key == obj.key for o in self.selected):
            return
        self.selected.append(obj)
        item = QtWidgets.QListWidgetItem(obj.label)
        item.setData(Qt.ItemDataRole.UserRole, obj.key)
        if not obj.is_numeric:
            item.setToolTip("Non-numeric — logged to CSV but not plotted.")
        self.chosen.addItem(item)
        self._refresh_count()
        self.selection_changed.emit()

    def add_by_key(self, key: str):
        o = self._by_key.get(key)
        if o:
            self.add_object(o)

    def _add_selected(self):
        rows = sorted({i.row() for i in self.avail.selectedIndexes()})
        for r in rows:
            self.add_object(self._rows[r])

    def _remove_selected(self):
        for item in self.chosen.selectedItems():
            key = item.data(Qt.ItemDataRole.UserRole)
            self.selected = [o for o in self.selected if o.key != key]
            self.chosen.takeItem(self.chosen.row(item))
        self._refresh_count()
        self.selection_changed.emit()

    def clear(self):
        self.selected.clear()
        self.chosen.clear()
        self._refresh_count()
        self.selection_changed.emit()

    def _refresh_count(self):
        n = len(self.selected)
        self.chosen_label.setText(
            f"<b>Recording set</b>  <span style='opacity:.6'>({n})</span>")

    # -- quick sets ------------------------------------------------------- #
    def _find(self, index_hex: str, sub: int) -> SdoObject | None:
        return self._by_key.get(f"{index_hex.upper()}:{sub}") or next(
            (o for o in self.presets
             if o.index_hex.upper() == index_hex.upper()
             and o.subindex_int == sub),
            None,
        )

    def _apply_quick(self, label: str):
        missing = []
        for idx, sub in QUICK_SETS[label]:
            o = self._find(idx, sub)
            if o:
                self.add_object(o)
            else:
                missing.append(f"{idx}:{sub:02d}")
        if missing:
            QtWidgets.QMessageBox.information(
                self, "Not in dictionary",
                "These objects aren't in the loaded preset file:\n  "
                + "\n  ".join(missing))