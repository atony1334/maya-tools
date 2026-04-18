# -*- coding: utf-8 -*-
"""
Skin Weight 複製/貼上工具
支援 Python 2/3，Maya 2020+，PySide2 UI
"""

from __future__ import print_function, division
import maya.cmds as cmds
import maya.mel as mel

from PySide2 import QtWidgets, QtCore

# 全域暫存 weight 資料
_weight_data = {}


def get_skin_cluster(mesh):
    """取得 mesh 上的 skinCluster 節點名稱"""
    history = cmds.listHistory(mesh, interestLevel=1) or []
    for node in history:
        if cmds.nodeType(node) == 'skinCluster':
            return node
    return None


def copy_weights(mesh):
    """複製指定 mesh 的 skin weight 資料"""
    global _weight_data
    _weight_data = {}

    skin = get_skin_cluster(mesh)
    if not skin:
        raise RuntimeError(u'{} 上找不到 skinCluster'.format(mesh))

    # 取得所有 influence joint
    influences = cmds.skinCluster(skin, query=True, influence=True)

    # 取得頂點數量
    vertex_count = cmds.polyEvaluate(mesh, vertex=True)

    # 逐頂點取得 weight
    weights = {}
    for i in range(vertex_count):
        vtx = '{}.vtx[{}]'.format(mesh, i)
        vtx_weights = {}
        for inf in influences:
            w = cmds.skinPercent(skin, vtx, transform=inf, query=True)
            if w > 0.0001:
                vtx_weights[inf] = w
        weights[i] = vtx_weights

    _weight_data = {
        'mesh': mesh,
        'influences': influences,
        'weights': weights,
        'vertex_count': vertex_count,
    }
    return len(weights)


def paste_weights(target_mesh):
    """將暫存的 weight 貼到目標 mesh"""
    global _weight_data

    if not _weight_data:
        raise RuntimeError(u'請先複製 weight')

    skin = get_skin_cluster(target_mesh)
    if not skin:
        raise RuntimeError(u'{} 上找不到 skinCluster'.format(target_mesh))

    src_count = _weight_data['vertex_count']
    tgt_count = cmds.polyEvaluate(target_mesh, vertex=True)

    if src_count != tgt_count:
        raise RuntimeError(
            u'頂點數不符：來源 {} 個，目標 {} 個'.format(src_count, tgt_count)
        )

    weights = _weight_data['weights']

    # 逐頂點套用 weight
    for i, vtx_weights in weights.items():
        if not vtx_weights:
            continue
        vtx = '{}.vtx[{}]'.format(target_mesh, i)
        transform_value = [
            (inf, w) for inf, w in vtx_weights.items()
        ]
        cmds.skinPercent(skin, vtx, transformValue=transform_value)

    return tgt_count


class SkinWeightTool(QtWidgets.QDialog):
    """Skin Weight 複製貼上工具主視窗"""

    def __init__(self, parent=None):
        super(SkinWeightTool, self).__init__(parent)
        self.setWindowTitle(u'Skin Weight 工具')
        self.setMinimumWidth(320)
        self.setWindowFlags(self.windowFlags() | QtCore.Qt.Tool)
        self._build_ui()

    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(8)
        layout.setContentsMargins(12, 12, 12, 12)

        # --- 來源區 ---
        src_group = QtWidgets.QGroupBox(u'來源 Mesh')
        src_layout = QtWidgets.QHBoxLayout(src_group)

        self.src_line = QtWidgets.QLineEdit()
        self.src_line.setPlaceholderText(u'選取 mesh 後點擊取得')
        src_layout.addWidget(self.src_line)

        src_pick_btn = QtWidgets.QPushButton(u'取得選取')
        src_pick_btn.clicked.connect(self._pick_source)
        src_layout.addWidget(src_pick_btn)

        layout.addWidget(src_group)

        # --- 複製按鈕 ---
        self.copy_btn = QtWidgets.QPushButton(u'複製 Weight')
        self.copy_btn.setFixedHeight(32)
        self.copy_btn.clicked.connect(self._copy)
        layout.addWidget(self.copy_btn)

        # --- 目標區 ---
        tgt_group = QtWidgets.QGroupBox(u'目標 Mesh')
        tgt_layout = QtWidgets.QHBoxLayout(tgt_group)

        self.tgt_line = QtWidgets.QLineEdit()
        self.tgt_line.setPlaceholderText(u'選取 mesh 後點擊取得')
        tgt_layout.addWidget(self.tgt_line)

        tgt_pick_btn = QtWidgets.QPushButton(u'取得選取')
        tgt_pick_btn.clicked.connect(self._pick_target)
        tgt_layout.addWidget(tgt_pick_btn)

        layout.addWidget(tgt_group)

        # --- 貼上按鈕 ---
        self.paste_btn = QtWidgets.QPushButton(u'貼上 Weight')
        self.paste_btn.setFixedHeight(32)
        self.paste_btn.clicked.connect(self._paste)
        layout.addWidget(self.paste_btn)

        # --- 狀態列 ---
        self.status_label = QtWidgets.QLabel(u'就緒')
        self.status_label.setAlignment(QtCore.Qt.AlignCenter)
        layout.addWidget(self.status_label)

    def _pick_source(self):
        """取得目前選取的 mesh 填入來源欄位"""
        sel = cmds.ls(selection=True, type='transform')
        if sel:
            self.src_line.setText(sel[0])
        else:
            self._set_status(u'請先在 Maya 選取一個 mesh', error=True)

    def _pick_target(self):
        """取得目前選取的 mesh 填入目標欄位"""
        sel = cmds.ls(selection=True, type='transform')
        if sel:
            self.tgt_line.setText(sel[0])
        else:
            self._set_status(u'請先在 Maya 選取一個 mesh', error=True)

    def _copy(self):
        """執行複製 weight"""
        mesh = self.src_line.text().strip()
        if not mesh:
            self._set_status(u'請先填入來源 mesh', error=True)
            return
        try:
            count = copy_weights(mesh)
            self._set_status(u'已複製 {} 個頂點的 weight'.format(count))
        except Exception as e:
            self._set_status(str(e), error=True)

    def _paste(self):
        """執行貼上 weight"""
        mesh = self.tgt_line.text().strip()
        if not mesh:
            self._set_status(u'請先填入目標 mesh', error=True)
            return
        try:
            count = paste_weights(mesh)
            self._set_status(u'已貼上 {} 個頂點的 weight'.format(count))
        except Exception as e:
            self._set_status(str(e), error=True)

    def _set_status(self, msg, error=False):
        """更新狀態列文字與顏色"""
        color = '#cc3333' if error else '#33aa33'
        self.status_label.setStyleSheet('color: {};'.format(color))
        self.status_label.setText(msg)


# 全域視窗實例，避免重複開啟
_tool_window = None


def show():
    """開啟工具視窗"""
    global _tool_window

    # 取得 Maya 主視窗作為 parent
    try:
        from shiboken2 import wrapInstance
        import maya.OpenMayaUI as omui
        main_window_ptr = omui.MQtUtil.mainWindow()
        parent = wrapInstance(int(main_window_ptr), QtWidgets.QWidget)
    except Exception:
        parent = None

    # 若視窗已存在則直接顯示
    if _tool_window is not None:
        try:
            _tool_window.show()
            _tool_window.raise_()
            return
        except Exception:
            pass

    _tool_window = SkinWeightTool(parent=parent)
    _tool_window.show()


if __name__ == '__main__':
    show()
