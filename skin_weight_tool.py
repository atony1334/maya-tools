# -*- coding: utf-8 -*-
"""
Skin Weight 複製/貼上工具
支援 Python 2/3，Maya 2020+，PySide2 UI
權重讀寫使用 OpenMaya API 2 批次操作以提升效能
"""

from __future__ import print_function, division
import maya.cmds as cmds
import maya.api.OpenMaya as om2
import maya.api.OpenMayaAnim as oma2

from PySide2 import QtWidgets, QtCore

# 全域暫存 weight 資料
_weight_data = {}


# ---------------------------------------------------------------------------
# 核心工具函式
# ---------------------------------------------------------------------------

def get_skin_cluster(mesh):
    """透過 API 取得 mesh 上的 skinCluster MObject"""
    sel = om2.MSelectionList()
    sel.add(mesh)
    dag = sel.getDagPath(0)

    # 取得 mesh shape
    dag.extendToShape()

    # 走訪 DG history 找 skinCluster
    it = om2.MItDependencyGraph(
        dag.node(),
        om2.MFn.kSkinClusterFilter,
        om2.MItDependencyGraph.kUpstream,
    )
    if it.isDone():
        return None
    return it.currentNode()


def copy_weights(mesh):
    """使用 om2 批次讀取 skin weight，存入全域暫存"""
    global _weight_data
    _weight_data = {}

    skin_node = get_skin_cluster(mesh)
    if skin_node is None:
        raise RuntimeError(u'{} 上找不到 skinCluster'.format(mesh))

    skin_fn = oma2.MFnSkinCluster(skin_node)

    # 取得 mesh 的 dag path 與所有頂點 component
    sel = om2.MSelectionList()
    sel.add(mesh)
    dag = sel.getDagPath(0)
    dag.extendToShape()

    vtx_comp = om2.MFnSingleIndexedComponent()
    all_vtx = vtx_comp.create(om2.MFn.kMeshVertComponent)
    vertex_count = cmds.polyEvaluate(mesh, vertex=True)
    vtx_comp.addElements(list(range(vertex_count)))

    # 一次性批次取得所有頂點的全部 weight
    weights, influence_count = skin_fn.getWeights(dag, all_vtx)

    # 取得 influence joint 名稱
    inf_paths = skin_fn.influenceObjects()
    influences = [p.fullPathName() for p in inf_paths]

    _weight_data = {
        'mesh': mesh,
        'influences': influences,
        'weights': weights,           # om2.MDoubleArray，長度 = 頂點數 * influence 數
        'influence_count': influence_count,
        'vertex_count': vertex_count,
    }
    return vertex_count


def paste_weights(target_mesh):
    """使用 om2 批次寫入 skin weight 到目標 mesh"""
    global _weight_data

    if not _weight_data:
        raise RuntimeError(u'請先複製 weight')

    skin_node = get_skin_cluster(target_mesh)
    if skin_node is None:
        raise RuntimeError(u'{} 上找不到 skinCluster'.format(target_mesh))

    tgt_count = cmds.polyEvaluate(target_mesh, vertex=True)
    src_count = _weight_data['vertex_count']

    if src_count != tgt_count:
        raise RuntimeError(
            u'頂點數不符：來源 {} 個，目標 {} 個'.format(src_count, tgt_count)
        )

    skin_fn = oma2.MFnSkinCluster(skin_node)

    sel = om2.MSelectionList()
    sel.add(target_mesh)
    dag = sel.getDagPath(0)
    dag.extendToShape()

    vtx_comp = om2.MFnSingleIndexedComponent()
    all_vtx = vtx_comp.create(om2.MFn.kMeshVertComponent)
    vtx_comp.addElements(list(range(tgt_count)))

    # 比對 influence 順序，建立來源到目標的 index 對應
    tgt_inf_paths = skin_fn.influenceObjects()
    tgt_influences = [p.fullPathName() for p in tgt_inf_paths]
    src_influences = _weight_data['influences']
    src_inf_count = _weight_data['influence_count']
    src_weights = _weight_data['weights']

    # 建立重新排列後的 weight 陣列
    tgt_inf_count = len(tgt_influences)
    new_weights = om2.MDoubleArray(tgt_count * tgt_inf_count, 0.0)

    # 建立來源 influence 名稱到 index 的查詢表
    src_inf_index = {name: i for i, name in enumerate(src_influences)}

    for tgt_i, tgt_inf in enumerate(tgt_influences):
        src_i = src_inf_index.get(tgt_inf, None)
        if src_i is None:
            continue
        for vtx in range(tgt_count):
            new_weights[vtx * tgt_inf_count + tgt_i] = \
                src_weights[vtx * src_inf_count + src_i]

    # 一次性批次寫入所有 weight
    all_inf_indices = om2.MIntArray(list(range(tgt_inf_count)))
    skin_fn.setWeights(dag, all_vtx, all_inf_indices, new_weights, normalize=True)

    return tgt_count


# ---------------------------------------------------------------------------
# PySide2 UI
# ---------------------------------------------------------------------------

class SkinWeightTool(QtWidgets.QDialog):
    """Skin Weight 複製貼上工具主視窗"""

    def __init__(self, parent=None):
        super(SkinWeightTool, self).__init__(parent)
        self.setWindowTitle(u'Skin Weight 工具')
        self.setMinimumWidth(320)
        self.setWindowFlags(self.windowFlags() | QtCore.Qt.Tool)

        self.create_widget()
        self.create_layout()
        self.create_connect()

    def create_widget(self):
        """建立所有 UI 元件"""
        # 來源區
        self.src_group = QtWidgets.QGroupBox(u'來源 Mesh')
        self.src_line = QtWidgets.QLineEdit()
        self.src_line.setPlaceholderText(u'選取 mesh 後點擊取得')
        self.src_pick_btn = QtWidgets.QPushButton(u'取得選取')

        # 複製按鈕
        self.copy_btn = QtWidgets.QPushButton(u'複製 Weight')
        self.copy_btn.setFixedHeight(32)

        # 目標區
        self.tgt_group = QtWidgets.QGroupBox(u'目標 Mesh')
        self.tgt_line = QtWidgets.QLineEdit()
        self.tgt_line.setPlaceholderText(u'選取 mesh 後點擊取得')
        self.tgt_pick_btn = QtWidgets.QPushButton(u'取得選取')

        # 貼上按鈕
        self.paste_btn = QtWidgets.QPushButton(u'貼上 Weight')
        self.paste_btn.setFixedHeight(32)

        # 狀態列
        self.status_label = QtWidgets.QLabel(u'就緒')
        self.status_label.setAlignment(QtCore.Qt.AlignCenter)

    def create_layout(self):
        """建立版面配置"""
        # 來源群組內部
        src_inner = QtWidgets.QHBoxLayout(self.src_group)
        src_inner.addWidget(self.src_line)
        src_inner.addWidget(self.src_pick_btn)

        # 目標群組內部
        tgt_inner = QtWidgets.QHBoxLayout(self.tgt_group)
        tgt_inner.addWidget(self.tgt_line)
        tgt_inner.addWidget(self.tgt_pick_btn)

        # 主版面
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setSpacing(8)
        main_layout.setContentsMargins(12, 12, 12, 12)
        main_layout.addWidget(self.src_group)
        main_layout.addWidget(self.copy_btn)
        main_layout.addWidget(self.tgt_group)
        main_layout.addWidget(self.paste_btn)
        main_layout.addWidget(self.status_label)

    def create_connect(self):
        """建立所有訊號連接"""
        self.src_pick_btn.clicked.connect(self._pick_source)
        self.copy_btn.clicked.connect(self._copy)
        self.tgt_pick_btn.clicked.connect(self._pick_target)
        self.paste_btn.clicked.connect(self._paste)

    # -----------------------------------------------------------------------
    # 事件處理
    # -----------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# 開啟視窗
# ---------------------------------------------------------------------------

_tool_window = None


def show():
    """開啟工具視窗"""
    global _tool_window

    try:
        from shiboken2 import wrapInstance
        import maya.OpenMayaUI as omui
        main_window_ptr = omui.MQtUtil.mainWindow()
        parent = wrapInstance(int(main_window_ptr), QtWidgets.QWidget)
    except Exception:
        parent = None

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
