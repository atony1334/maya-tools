# -*- coding: utf-8 -*-
from __future__ import print_function, division
import sys
import os
import glob
import maya.cmds as cmds
import maya.mel as mel

try:
    from PySide2 import QtWidgets, QtCore, QtGui
    from shiboken2 import wrapInstance
except ImportError:
    try:
        from PySide6 import QtWidgets, QtCore, QtGui
        from shiboken6 import wrapInstance
    except ImportError:
        from PySide import QtGui as QtWidgets
        from PySide import QtCore, QtGui
        from shiboken import wrapInstance


def u_str(text):
    if sys.version_info[0] < 3:
        if isinstance(text, unicode):
            return text
        try:
            return text.decode('utf-8')
        except UnicodeDecodeError:
            return text.decode('big5', errors='replace')
    return text


SCRIPT_PATH = "C:/Users/atony1334/Documents/maya/2022/scripts/"


class LoopTool(QtWidgets.QDialog):

    def __init__(self, parent=None):
        if parent is None:
            try:
                import maya.OpenMayaUI as omui
                ptr = omui.MQtUtil.mainWindow()
                parent = wrapInstance(int(ptr), QtWidgets.QWidget)
            except Exception:
                pass
        super(LoopTool, self).__init__(parent)

        self.setWindowTitle(u_str("Loop Tool"))
        self.resize(500, 660)
        self.setWindowFlags(self.windowFlags() | QtCore.Qt.Tool)

        if not os.path.exists(SCRIPT_PATH):
            os.makedirs(SCRIPT_PATH)

        self.apply_style()
        self.create_widgets()
        self.create_layouts()
        self.create_connections()
        self.update_library_combo()

    def apply_style(self):
        self.setStyleSheet("""
            QDialog {
                background-color: #252525;
                font-family: Consolas, 'Microsoft JhengHei';
                color: #D4D4D4;
            }
            QLabel { font-weight: bold; color: #CCC; font-size: 13px; }
            QRadioButton, QCheckBox { color: #E0E0E0; font-size: 12px; font-weight: bold; }
            QRadioButton::indicator, QCheckBox::indicator {
                width: 10px; height: 10px;
                border-radius: 5px;
                border: 1px solid #5D8A5D;
                background-color: #1E1E1E;
            }
            QRadioButton::indicator:checked, QCheckBox::indicator:checked {
                background-color: #4A724A;
                border: 1px solid #4A724A;
            }
            QPushButton {
                font-weight: bold; font-size: 13px;
                border-radius: 6px; padding: 8px;
                background-color: #444; color: white;
            }
            QPushButton:hover { background-color: #666; }
            #btn_connect {
                background-color: #3572A5; font-size: 14px; margin-top: 5px;
            }
            #btn_connect:hover { background-color: #4A89C3; }
            #btn_loop_lib, #btn_loop_below {
                background-color: #8B5A2B; font-size: 13px;
            }
            #btn_loop_lib:hover, #btn_loop_below:hover { background-color: #A06932; }
            #btn_store {
                background-color: #333333; color: #999999;
                font-size: 11px; padding: 4px 10px;
                border-radius: 4px; border: 1px solid #444444;
            }
            #btn_store:hover { background-color: #444444; color: #CCCCCC; }
            QListWidget {
                background-color: #1E1E1E; color: #D0D0D0;
                border: 1px solid #333; border-radius: 4px;
                font-size: 13px; padding: 5px; font-weight: bold;
            }
            QListWidget::item {
                padding: 6px; border-radius: 4px; margin-bottom: 2px;
            }
            QListWidget::item:selected { border: 1px solid #FFF; }
            QGroupBox {
                font-weight: bold; color: #888;
                border: 1px solid #333; border-radius: 8px;
                margin-top: 10px; padding-top: 15px;
            }
            QGroupBox::title { subcontrol-origin: margin; left: 15px; }
            QLineEdit, QComboBox {
                background-color: #1E1E1E; color: #D4D4D4;
                border: 1px solid #444; border-radius: 4px;
                padding: 4px; font-size: 13px;
            }
            QPlainTextEdit {
                background-color: #1A1A2E; color: #9CDCFE;
                border: 1px solid #444; border-radius: 4px;
                font-family: Consolas; font-size: 12px;
            }
        """)

    def create_widgets(self):
        # 清單區
        self.out_btn = QtWidgets.QPushButton(u_str("Out"))
        self.in_btn = QtWidgets.QPushButton(u_str("In"))

        self.out_list = QtWidgets.QListWidget()
        self.out_list.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.out_list.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)

        self.channel_list = QtWidgets.QListWidget()
        self.channel_list.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.channel_list.addItems([
            'translateX', 'translateY', 'translateZ',
            'rotateX', 'rotateY', 'rotateZ',
            'scaleX', 'scaleY', 'scaleZ', 'visibility'
        ])

        self.in_list = QtWidgets.QListWidget()
        self.in_list.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self.in_list.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)

        # Connect 按鈕
        self.connect_btn = QtWidgets.QPushButton(u_str("Connect..."))
        self.connect_btn.setObjectName("btn_connect")

        # Smart Loop 區
        self.loop_group = QtWidgets.QGroupBox(u_str("Smart Loop"))
        self.lib_combo = QtWidgets.QComboBox()
        self.loop_lib_btn = QtWidgets.QPushButton(u_str("Do Loop (Lib)"))
        self.loop_lib_btn.setObjectName("btn_loop_lib")
        self.loop_below_btn = QtWidgets.QPushButton(u_str("Do Loop (Below)"))
        self.loop_below_btn.setObjectName("btn_loop_below")

        # Script Library 區
        self.script_group = QtWidgets.QGroupBox(u_str("Script Library"))
        self.script_edit = QtWidgets.QPlainTextEdit()
        self.script_edit.setPlaceholderText(u_str("在此輸入 MEL 腳本，用 $a 代表 Out 物件，$b 代表 In 物件"))
        self.script_edit.setFixedHeight(140)
        self.script_name_le = QtWidgets.QLineEdit()
        self.script_name_le.setPlaceholderText(u_str("腳本名稱"))
        self.store_btn = QtWidgets.QPushButton(u_str("Store Script"))
        self.store_btn.setObjectName("btn_store")

        self.status_lbl = QtWidgets.QLabel(u_str("就緒"))
        self.status_lbl.setAlignment(QtCore.Qt.AlignCenter)

    def create_layouts(self):
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.setSpacing(8)

        # 三欄清單
        lists_layout = QtWidgets.QHBoxLayout()

        out_col = QtWidgets.QVBoxLayout()
        out_col.addWidget(self.out_btn)
        out_col.addWidget(self.out_list)

        ch_col = QtWidgets.QVBoxLayout()
        ch_col.addWidget(QtWidgets.QLabel(u_str("Channels")))
        ch_col.addWidget(self.channel_list)

        in_col = QtWidgets.QVBoxLayout()
        in_col.addWidget(self.in_btn)
        in_col.addWidget(self.in_list)

        lists_layout.addLayout(out_col)
        lists_layout.addLayout(ch_col)
        lists_layout.addLayout(in_col)
        main_layout.addLayout(lists_layout)
        main_layout.addWidget(self.connect_btn)

        # Smart Loop 群組
        loop_inner = QtWidgets.QVBoxLayout(self.loop_group)
        lib_row = QtWidgets.QHBoxLayout()
        lib_row.addWidget(self.lib_combo)
        lib_row.addWidget(self.loop_lib_btn)
        loop_inner.addLayout(lib_row)
        loop_inner.addWidget(self.loop_below_btn)
        main_layout.addWidget(self.loop_group)

        # Script Library 群組
        script_inner = QtWidgets.QVBoxLayout(self.script_group)
        name_row = QtWidgets.QHBoxLayout()
        name_row.addWidget(self.script_name_le)
        name_row.addWidget(self.store_btn)
        script_inner.addLayout(name_row)
        script_inner.addWidget(self.script_edit)
        main_layout.addWidget(self.script_group)

        main_layout.addWidget(self.status_lbl)

    def create_connections(self):
        self.out_btn.clicked.connect(lambda: self.add_to_list(self.out_list, replace=True))
        self.in_btn.clicked.connect(lambda: self.add_to_list(self.in_list, replace=True))
        self.connect_btn.clicked.connect(self.run_connect)
        self.loop_lib_btn.clicked.connect(lambda: self.run_smart_loop(from_lib=True))
        self.loop_below_btn.clicked.connect(lambda: self.run_smart_loop(from_lib=False))
        self.store_btn.clicked.connect(self.store_script)
        self.out_list.customContextMenuRequested.connect(
            lambda pos: self.show_context_menu(pos, self.out_list)
        )
        self.in_list.customContextMenuRequested.connect(
            lambda pos: self.show_context_menu(pos, self.in_list)
        )

    # ------------------------------------------------------------------

    def add_to_list(self, list_widget, replace=False):
        selection = cmds.ls(sl=True)
        if not selection:
            return
        active_attrs = cmds.channelBox('mainChannelBox', q=True, sma=True)
        suffix = ('.' + active_attrs[0]) if active_attrs else ''
        items = [obj + suffix for obj in selection]

        if replace:
            list_widget.clear()
            list_widget.addItems(items)
        else:
            existing = set(list_widget.item(i).text() for i in range(list_widget.count()))
            for item in items:
                if item not in existing:
                    list_widget.addItem(item)

    def show_context_menu(self, pos, list_widget):
        menu = QtWidgets.QMenu(self)
        act_select = menu.addAction(u_str("Select object"))
        act_add = menu.addAction(u_str("Add select"))
        act_clean_sel = menu.addAction(u_str("Clean select"))
        act_clean_all = menu.addAction(u_str("Clean all"))

        action = menu.exec_(list_widget.mapToGlobal(pos))

        if action == act_select:
            objs = [i.text().split('.')[0] for i in list_widget.selectedItems()]
            if objs:
                cmds.select(objs)
        elif action == act_add:
            self.add_to_list(list_widget, replace=False)
        elif action == act_clean_sel:
            for item in list_widget.selectedItems():
                list_widget.takeItem(list_widget.row(item))
        elif action == act_clean_all:
            list_widget.clear()

    def _get_list_items(self, list_widget):
        return [list_widget.item(i).text() for i in range(list_widget.count())]

    def run_connect(self):
        out_items = self._get_list_items(self.out_list)
        in_items = self._get_list_items(self.in_list)
        channels = [i.text() for i in self.channel_list.selectedItems()]

        if not out_items or not in_items or not channels:
            self._set_status(u_str("請確認 Out / In 清單不為空且已選取 Channel"), error=True)
            return

        cmds.undoInfo(openChunk=True)
        try:
            if len(out_items) == 1:
                # 一對多
                for in_obj in in_items:
                    for ch in channels:
                        try:
                            cmds.connectAttr('%s.%s' % (out_items[0], ch),
                                             '%s.%s' % (in_obj, ch), f=True)
                        except Exception:
                            pass
            elif len(out_items) == len(in_items):
                # 一對一
                for i in range(len(out_items)):
                    for ch in channels:
                        try:
                            cmds.connectAttr('%s.%s' % (out_items[i], ch),
                                             '%s.%s' % (in_items[i], ch), f=True)
                        except Exception:
                            pass
            else:
                self._set_status(u_str("數量不符：必須 1:N 或 N:N"), error=True)
                return
            self._set_status(u_str("Connect 完成"))
        finally:
            cmds.undoInfo(closeChunk=True)

    def run_smart_loop(self, from_lib=False):
        out_items = self._get_list_items(self.out_list)
        in_items = self._get_list_items(self.in_list)

        if not out_items:
            self._set_status(u_str("Out 清單不可為空"), error=True)
            return

        if from_lib:
            name = self.lib_combo.currentText()
            if not name:
                return
            full_path = os.path.join(SCRIPT_PATH, name + '.txt')
            if not os.path.exists(full_path):
                self._set_status(u_str("找不到腳本檔案"), error=True)
                return
            with open(full_path, 'r') as f:
                mel_cmd = f.read()
        else:
            mel_cmd = self.script_edit.toPlainText()

        if not mel_cmd.strip():
            self._set_status(u_str("腳本內容為空"), error=True)
            return

        cmds.undoInfo(openChunk=True)
        try:
            if not in_items:
                # 模式 A：只有 Out
                for obj in out_items:
                    cmds.select(obj)
                    try:
                        mel.eval(mel_cmd.replace('$a', obj))
                    except Exception:
                        pass
            elif len(out_items) == 1:
                # 模式 B：1 對多
                for in_obj in in_items:
                    cmds.select(out_items[0], in_obj)
                    try:
                        mel.eval(mel_cmd.replace('$a', out_items[0]).replace('$b', in_obj))
                    except Exception:
                        pass
            elif len(out_items) == len(in_items):
                # 模式 C：N 對 N
                for i in range(len(out_items)):
                    cmds.select(out_items[i], in_items[i])
                    try:
                        mel.eval(mel_cmd.replace('$a', out_items[i]).replace('$b', in_items[i]))
                    except Exception:
                        pass
            else:
                self._set_status(u_str("數量不符：必須 1:N 或 N:N"), error=True)
                return
            self._set_status(u_str("Loop 執行完成"))
        finally:
            cmds.undoInfo(closeChunk=True)

    def store_script(self):
        name = self.script_name_le.text().strip()
        content = self.script_edit.toPlainText()
        if not name or not content:
            self._set_status(u_str("請輸入名稱與腳本內容"), error=True)
            return
        full_path = os.path.join(SCRIPT_PATH, name + '.txt')
        if os.path.exists(full_path):
            self._set_status(u_str("同名腳本已存在"), error=True)
            return
        try:
            with open(full_path, 'w') as f:
                f.write(content)
            self.update_library_combo()
            self.lib_combo.setCurrentText(name)
            self._set_status(u_str("已儲存：%s") % name)
        except Exception as e:
            self._set_status(u_str("儲存失敗：%s") % str(e), error=True)

    def update_library_combo(self):
        self.lib_combo.clear()
        files = glob.glob(os.path.join(SCRIPT_PATH, '*.txt'))
        names = [os.path.basename(f)[:-4] for f in files]
        self.lib_combo.addItems(names)

    def _set_status(self, msg, error=False):
        color = '#cc3333' if error else '#33aa33'
        self.status_lbl.setStyleSheet('color: %s;' % color)
        self.status_lbl.setText(msg)


_tool_window = None


def show():
    global _tool_window
    try:
        _tool_window.close()
        _tool_window.deleteLater()
    except Exception:
        pass
    _tool_window = LoopTool()
    _tool_window.show()


if __name__ == '__main__':
    show()
