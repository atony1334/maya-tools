# -*- coding: utf-8 -*-
from __future__ import print_function
import sys
import maya.cmds as cmds
import maya.OpenMayaUI as omui
import maya.api.OpenMaya as om
import re

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
            try:
                return text.decode('mbcs')
            except UnicodeDecodeError:
                return text.decode('big5', errors='replace')
    return text


# ==========================================
# 核心邏輯：空間距離對比（檢查用）
# ==========================================
def check_symmetry_spatial(obj_path, axis='x', tolerance_val=0.001):
    sel_list = om.MSelectionList()
    try:
        sel_list.add(obj_path)
        dag_path = sel_list.getDagPath(0)
    except:
        return False, u_str("找不到物件"), []

    if not dag_path.hasFn(om.MFn.kMesh):
        try:
            dag_path.extendToShape()
        except:
            return False, u_str("無網格形狀"), []

    mesh_fn = om.MFnMesh(dag_path)
    points = mesh_fn.getPoints(om.MSpace.kObject)

    if axis == 'x':
        chk_idx, k_idx1, k_idx2 = 0, 1, 2
    elif axis == 'y':
        chk_idx, k_idx1, k_idx2 = 1, 0, 2
    else:
        chk_idx, k_idx1, k_idx2 = 2, 0, 1

    if tolerance_val >= 0.1:
        round_dec = 1
    elif tolerance_val >= 0.01:
        round_dec = 2
    else:
        round_dec = 3

    pos_list, neg_dict = [], {}
    for i in range(len(points)):
        pt = points[i]
        chk_val = pt[chk_idx]
        k1 = round(pt[k_idx1], round_dec)
        k2 = round(pt[k_idx2], round_dec)
        if abs(chk_val) <= tolerance_val:
            continue
        if chk_val > 0:
            pos_list.append((chk_val, k1, k2, i))
        else:
            key = (k1, k2)
            if key not in neg_dict:
                neg_dict[key] = []
            neg_dict[key].append((chk_val, i))

    matched_neg = set()
    asymmetrical = []

    for p_val, pk1, pk2, p_idx in pos_list:
        key, found = (pk1, pk2), False
        if key in neg_dict:
            for n_val, n_idx in neg_dict[key]:
                if n_idx in matched_neg:
                    continue
                if abs(p_val + n_val) <= tolerance_val:
                    found = True
                    matched_neg.add(n_idx)
                    break
        if not found:
            asymmetrical.append(p_idx)

    for key, n_list in neg_dict.items():
        for n_val, n_idx in n_list:
            if n_idx not in matched_neg:
                asymmetrical.append(n_idx)

    return True, "", asymmetrical


# ==========================================
# 核心邏輯：Rounded 座標配對鏡射修正
# ==========================================
def fix_symmetry(obj_path, axis='x', direction=1, tolerance_val=0.001, use_topo=True, selected_vtx=None):
    """
    用跟 check 一樣的 rounded 座標配對策略找對應頂點，
    再將 source 的鏡射位置寫回 target。
    這樣即使 target 在完全錯誤的位置也能正確配對。
    """
    sel_list = om.MSelectionList()
    try:
        sel_list.add(obj_path)
        dag_path = sel_list.getDagPath(0)
    except:
        return False, 0

    if not dag_path.hasFn(om.MFn.kMesh):
        try:
            dag_path.extendToShape()
        except:
            return False, 0

    mesh_fn = om.MFnMesh(dag_path)
    points = mesh_fn.getPoints(om.MSpace.kObject)

    if axis == 'x':
        chk_idx, k_idx1, k_idx2 = 0, 1, 2
    elif axis == 'y':
        chk_idx, k_idx1, k_idx2 = 1, 0, 2
    else:
        chk_idx, k_idx1, k_idx2 = 2, 0, 1

    if tolerance_val >= 0.1:
        round_dec = 1
    elif tolerance_val >= 0.01:
        round_dec = 2
    else:
        round_dec = 3

    # 分類頂點，同時以 rounded 非軸座標作為配對 key
    center_idx = set()
    source_dict = {}  # key -> [(chk_val, vtx_idx), ...]
    target_dict = {}  # key -> [(chk_val, vtx_idx), ...]

    for i in range(len(points)):
        pt = points[i]
        chk_val = pt[chk_idx]
        key = (round(pt[k_idx1], round_dec), round(pt[k_idx2], round_dec))

        if abs(chk_val) <= tolerance_val:
            center_idx.add(i)
        elif (direction == 1 and chk_val > tolerance_val) or \
             (direction == -1 and chk_val < -tolerance_val):
            source_dict.setdefault(key, []).append((chk_val, i))
        else:
            target_dict.setdefault(key, []).append((chk_val, i))

    changes_dict = {}
    good_map = {}
    locked_target = set()

    print("[SymFix] source 頂點數: %d, target 頂點數: %d" % (
        sum(len(v) for v in source_dict.values()),
        sum(len(v) for v in target_dict.values())
    ))

    # 用 rounded key 配對 source -> target，再記錄鏡射位置
    for key, src_list in source_dict.items():
        if key not in target_dict:
            continue
        tgt_list = target_dict[key]
        # 按軸向值排序，確保一對一配對穩定
        src_sorted = sorted(src_list, key=lambda x: abs(x[0]))
        tgt_sorted = sorted(tgt_list, key=lambda x: abs(x[0]))
        for (s_val, s_idx), (t_val, t_idx) in zip(src_sorted, tgt_sorted):
            if t_idx in locked_target:
                continue
            good_map[s_idx] = t_idx
            locked_target.add(t_idx)
            mirror_pt = om.MPoint(points[s_idx])
            mirror_pt[chk_idx] *= -1.0
            changes_dict[t_idx] = [mirror_pt.x, mirror_pt.y, mirror_pt.z]

    rounding_count = len(good_map)

    # ARI 單圈擴散：從已知好配對往外推一環（1-hop），外層遞迴處理多環
    if use_topo and good_map:
        bad_source = set(idx for lst in source_dict.values() for _, idx in lst
                         if idx not in good_map)
        bad_target = set(idx for lst in target_dict.values() for _, idx in lst
                         if idx not in locked_target)

        if bad_source and bad_target:
            vtx_connect = [set() for _ in range(len(points))]
            edge_iter = om.MItMeshEdge(dag_path)
            while not edge_iter.isDone():
                v1, v2 = edge_iter.vertexId(0), edge_iter.vertexId(1)
                vtx_connect[v1].add(v2)
                vtx_connect[v2].add(v1)
                edge_iter.next()

            # 持續擴散直到無法再推進為止
            while True:
                ring_matched = 0
                for s_good in list(good_map.keys()):
                    t_good = good_map[s_good]
                    bad_n_s = vtx_connect[s_good] & bad_source
                    bad_n_t = vtx_connect[t_good] & bad_target
                    if len(bad_n_s) == 1 and len(bad_n_t) == 1:
                        bvs = next(iter(bad_n_s))
                        bvt = next(iter(bad_n_t))
                        if bvs not in good_map and bvt not in locked_target:
                            good_map[bvs] = bvt
                            locked_target.add(bvt)
                            bad_source.discard(bvs)
                            bad_target.discard(bvt)
                            mp = om.MPoint(points[bvs])
                            mp[chk_idx] *= -1.0
                            changes_dict[bvt] = [mp.x, mp.y, mp.z]
                            ring_matched += 1
                if ring_matched == 0:
                    break

    ari_count = len(good_map) - rounding_count

    print("[SymFix] 配對 %d 對（rounding %d + ARI 1圈 %d）, 中心點 %d 個, 未配對 %d 個" % (
        len(good_map), rounding_count, ari_count, len(center_idx),
        sum(len(v) for v in source_dict.values()) - len(good_map)
    ))

    # 中心頂點 snap 到軸平面
    for c in center_idx:
        if abs(points[c][chk_idx]) > 1e-6:
            pt = om.MPoint(points[c])
            pt[chk_idx] = 0.0
            changes_dict[c] = [pt.x, pt.y, pt.z]

    # 若有 selected_vtx，只套用與選取頂點相關的修正
    source_idx = set(idx for lst in source_dict.values() for _, idx in lst)
    target_idx = set(idx for lst in target_dict.values() for _, idx in lst)

    if selected_vtx is None:
        final_changes = changes_dict
    else:
        final_changes = {}
        for v in selected_vtx:
            if v in center_idx:
                if v in changes_dict:
                    final_changes[v] = changes_dict[v]
            elif v in source_idx:
                t = good_map.get(v)
                if t is not None:
                    final_changes[t] = changes_dict[t]
            elif v in target_idx:
                if v in changes_dict:
                    final_changes[v] = changes_dict[v]

    if final_changes:
        obj_name = dag_path.partialPathName()
        for v_idx, pos in final_changes.items():
            cmds.xform(
                "%s.vtx[%d]" % (obj_name, v_idx),
                translation=pos,
                objectSpace=True
            )

    return True, len(final_changes)


# ==========================================
# UI 介面設計
# ==========================================
def get_maya_main_window():
    ptr = omui.MQtUtil.mainWindow()
    return wrapInstance(int(ptr), QtWidgets.QWidget)


class SymmetryBatchCheckerUI(QtWidgets.QDialog):

    def __init__(self, parent=None):
        if parent is None:
            try:
                parent = get_maya_main_window()
            except Exception:
                pass

        super(SymmetryBatchCheckerUI, self).__init__(parent)
        self.setWindowTitle("Symmetry Batch Checker & Fixer")
        self.resize(380, 580)
        self.setWindowFlags(self.windowFlags() | QtCore.Qt.Tool)
        self.cached_transforms = []

        self.apply_style()
        self.create_widgets()
        self.create_layouts()
        self.create_connections()

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
            QSlider::groove:horizontal {
                border: 1px solid #444; height: 6px;
                background: #1E1E1E; border-radius: 3px;
            }
            QSlider::handle:horizontal {
                background: #5D8A5D; border: 1px solid #4A724A;
                width: 14px; margin: -5px 0; border-radius: 7px;
            }
            QDoubleSpinBox {
                background-color: #1E1E1E; color: #5D8A5D;
                border: 1px solid #444; border-radius: 4px;
                font-weight: bold; padding: 2px 5px; font-size: 13px;
            }
            QPushButton {
                font-weight: bold; font-size: 13px;
                border-radius: 6px; padding: 8px;
                background-color: #444; color: white;
            }
            QPushButton:hover { background-color: #666; }
            #btn_load {
                background-color: #3572A5; font-size: 14px; margin-top: 5px;
            }
            #btn_load:hover { background-color: #4A89C3; }
            #btn_fix { background-color: #8B5A2B; font-size: 14px; }
            #btn_fix:hover { background-color: #A06932; }
            #btn_snap {
                background-color: #333333; color: #999999;
                font-size: 11px; padding: 4px 10px;
                border-radius: 4px; border: 1px solid #444444;
            }
            #btn_snap:hover { background-color: #444444; color: #CCCCCC; }
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
        """)

    def create_widgets(self):
        self.settings_group = QtWidgets.QGroupBox("Settings")

        self.axis_group = QtWidgets.QButtonGroup(self)
        self.radio_x = QtWidgets.QRadioButton("X")
        self.radio_y = QtWidgets.QRadioButton("Y")
        self.radio_z = QtWidgets.QRadioButton("Z")
        self.axis_group.addButton(self.radio_x)
        self.axis_group.addButton(self.radio_y)
        self.axis_group.addButton(self.radio_z)
        self.radio_x.setChecked(True)

        self.dir_group = QtWidgets.QButtonGroup(self)
        self.radio_pos_to_neg = QtWidgets.QRadioButton("+ to -")
        self.radio_neg_to_pos = QtWidgets.QRadioButton("- to +")
        self.dir_group.addButton(self.radio_pos_to_neg)
        self.dir_group.addButton(self.radio_neg_to_pos)
        self.radio_pos_to_neg.setChecked(True)

        self.chk_topo = QtWidgets.QCheckBox(u_str("Use Border Shrinkage"))
        self.chk_topo.setChecked(True)
        self.chk_topo.setStyleSheet("color: #4EC9B0;")

        self.tol_slider = QtWidgets.QSlider(QtCore.Qt.Horizontal)
        self.tol_slider.setRange(1, 100)
        self.tol_slider.setValue(1)
        self.tol_slider.setCursor(QtCore.Qt.PointingHandCursor)

        self.tol_spin = QtWidgets.QDoubleSpinBox()
        self.tol_spin.setRange(0.001, 0.1)
        self.tol_spin.setDecimals(3)
        self.tol_spin.setSingleStep(0.001)
        self.tol_spin.setFixedWidth(75)
        self.tol_spin.setValue(0.001)

        self.load_btn = QtWidgets.QPushButton(u_str("1. 掃描與檢查 (Check)"))
        self.load_btn.setObjectName("btn_load")
        self.load_btn.setCursor(QtCore.Qt.PointingHandCursor)

        self.fix_btn = QtWidgets.QPushButton(u_str("2. 單向鏡射修正 (Directed Fix)"))
        self.fix_btn.setObjectName("btn_fix")
        self.fix_btn.setCursor(QtCore.Qt.PointingHandCursor)

        self.snap_btn = QtWidgets.QPushButton(u_str("Snap Center"))
        self.snap_btn.setObjectName("btn_snap")
        self.snap_btn.setCursor(QtCore.Qt.PointingHandCursor)

        self.list_widget = QtWidgets.QListWidget()
        self.list_widget.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)

        self.status_lbl = QtWidgets.QLabel(u_str("準備就緒"))
        self.status_lbl.setAlignment(QtCore.Qt.AlignRight)

    def create_layouts(self):
        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.setContentsMargins(15, 10, 15, 15)
        main_layout.setSpacing(10)

        sg_layout = QtWidgets.QGridLayout(self.settings_group)
        sg_layout.setSpacing(10)

        sg_layout.addWidget(QtWidgets.QLabel("Axis : "), 0, 0)
        ax_ly = QtWidgets.QHBoxLayout()
        ax_ly.addWidget(self.radio_x)
        ax_ly.addWidget(self.radio_y)
        ax_ly.addWidget(self.radio_z)
        ax_ly.addStretch()
        sg_layout.addLayout(ax_ly, 0, 1, 1, 2)

        sg_layout.addWidget(QtWidgets.QLabel("Direction : "), 1, 0)
        dr_ly = QtWidgets.QHBoxLayout()
        dr_ly.addWidget(self.radio_pos_to_neg)
        dr_ly.addWidget(self.radio_neg_to_pos)
        dr_ly.addStretch()
        sg_layout.addLayout(dr_ly, 1, 1, 1, 2)

        sg_layout.addWidget(QtWidgets.QLabel("Detail : "), 2, 0)
        sg_layout.addWidget(self.tol_slider, 2, 1)
        sg_layout.addWidget(self.tol_spin, 2, 2)

        main_layout.addWidget(self.settings_group)
        main_layout.addWidget(self.load_btn)
        main_layout.addWidget(self.fix_btn)

        snap_ly = QtWidgets.QHBoxLayout()
        snap_ly.addWidget(self.chk_topo)
        snap_ly.addStretch()
        snap_ly.addWidget(self.snap_btn)
        main_layout.addLayout(snap_ly)

        main_layout.addWidget(self.list_widget, 1)
        main_layout.addWidget(self.status_lbl)

    def create_connections(self):
        self.tol_slider.valueChanged.connect(self.sync_slider_to_spin)
        self.tol_spin.valueChanged.connect(self.sync_spin_to_slider)
        self.load_btn.clicked.connect(self.run_new_scan)
        self.fix_btn.clicked.connect(self.do_directed_fix)
        self.snap_btn.clicked.connect(self.do_force_snap_center)
        self.list_widget.itemSelectionChanged.connect(self.on_selection_changed)

    def sync_slider_to_spin(self, val):
        self.tol_spin.blockSignals(True)
        self.tol_spin.setValue(val / 1000.0)
        self.tol_spin.blockSignals(False)

    def sync_spin_to_slider(self, val):
        self.tol_slider.blockSignals(True)
        self.tol_slider.setValue(int(val * 1000))
        self.tol_slider.blockSignals(False)

    def run_new_scan(self, *args):
        self.refresh_list(use_cache=False)

    def refresh_list(self, use_cache=False):
        sel_vtx = cmds.ls(selection=True, flatten=True)
        vtx_dict = {}
        for v in sel_vtx:
            if ".vtx[" in v:
                try:
                    obj_name = v.split('.vtx')[0]
                    full_path = cmds.ls(obj_name, long=True)[0]
                    v_idx = int(re.search(r'\[(\d+)\]', v).group(1))
                    vtx_dict.setdefault(full_path, set()).add(v_idx)
                except Exception:
                    continue

        is_local = len(vtx_dict) > 0

        if not use_cache:
            if is_local:
                self.cached_transforms = list(vtx_dict.keys())
            else:
                selection = cmds.ls(selection=True, long=True)
                if not selection:
                    self.status_lbl.setText(u_str("請選取物件"))
                    return

                mesh_shapes = set()
                for sel in selection:
                    if cmds.nodeType(sel) == 'mesh':
                        mesh_shapes.add(sel)
                    else:
                        shps = cmds.listRelatives(
                            sel, allDescendents=True, type='mesh', fullPath=True
                        ) or []
                        mesh_shapes.update(shps)

                if not mesh_shapes:
                    return

                self.cached_transforms = list(set(
                    cmds.listRelatives(m, parent=True, fullPath=True)[0]
                    for m in mesh_shapes
                ))

        if not self.cached_transforms:
            return

        self.list_widget.blockSignals(True)
        self.list_widget.clear()

        axis = 'x' if self.radio_x.isChecked() else ('y' if self.radio_y.isChecked() else 'z')
        tolerance = self.tol_spin.value()

        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
        pass_count, fail_count = 0, 0

        try:
            for obj_path in sorted(self.cached_transforms):
                short_name = obj_path.split('|')[-1]
                success, _, bad_indices = check_symmetry_spatial(obj_path, axis, tolerance)

                if not success:
                    continue

                if is_local and obj_path in vtx_dict:
                    bad_indices = list(set(bad_indices) & vtx_dict[obj_path])

                item = QtWidgets.QListWidgetItem()
                item.setData(QtCore.Qt.UserRole, {"path": obj_path, "bad_indices": bad_indices})

                if bad_indices:
                    fail_count += 1
                    item.setText(u_str("[不對稱] %s (%d 個錯誤點)") % (short_name, len(bad_indices)))
                    item.setBackground(QtGui.QColor(139, 46, 46))
                    item.setForeground(QtGui.QColor(255, 200, 200))
                else:
                    pass_count += 1
                    item.setText(u_str("[對稱] %s") % short_name)
                    item.setBackground(QtGui.QColor(46, 92, 46))
                    item.setForeground(QtGui.QColor(200, 255, 200))

                self.list_widget.addItem(item)

            self.status_lbl.setText(
                u_str("掃描完成：%d 對稱, %d 不對稱") % (pass_count, fail_count)
            )
        finally:
            self.list_widget.blockSignals(False)
            QtWidgets.QApplication.restoreOverrideCursor()

    def do_directed_fix(self):
        axis = 'x' if self.radio_x.isChecked() else ('y' if self.radio_y.isChecked() else 'z')
        direction = 1 if self.radio_pos_to_neg.isChecked() else -1
        tolerance = self.tol_spin.value()
        use_topo = self.chk_topo.isChecked()

        sel_vtx = cmds.ls(selection=True, flatten=True)
        vtx_dict = {}
        for v in sel_vtx:
            if ".vtx[" in v:
                try:
                    obj_name = v.split('.vtx')[0]
                    full_path = cmds.ls(obj_name, long=True)[0]
                    v_idx = int(re.search(r'\[(\d+)\]', v).group(1))
                    vtx_dict.setdefault(full_path, []).append(v_idx)
                except Exception:
                    continue

        QtWidgets.QApplication.setOverrideCursor(QtCore.Qt.WaitCursor)
        cmds.undoInfo(openChunk=True)

        try:
            total_fixed = 0

            if vtx_dict:
                # 優先：viewport 選取的頂點
                for m_path, indices in vtx_dict.items():
                    success, count = fix_symmetry(m_path, axis, direction, tolerance, use_topo, indices)
                    if success:
                        total_fixed += count
            else:
                # 次優：清單選取的項目；若清單也沒選，就修正所有不對稱項目
                items = self.list_widget.selectedItems()
                if not items:
                    items = [
                        self.list_widget.item(i)
                        for i in range(self.list_widget.count())
                        if self.list_widget.item(i).data(QtCore.Qt.UserRole)["bad_indices"]
                    ]
                if not items:
                    self.status_lbl.setText(u_str("清單是空的，請先執行掃描"))
                    return

                for it in items:
                    m_path = it.data(QtCore.Qt.UserRole)["path"]
                    _, _, remaining = check_symmetry_spatial(m_path, axis, tolerance)
                    print("[SymFix] 開始修正 %s，初始壞點 %d 個" % (
                        m_path.split('|')[-1], len(remaining)
                    ))
                    stall_count = 0
                    pass_idx = 0
                    MAX_PASS = 100
                    while remaining and pass_idx < MAX_PASS:
                        success, count = fix_symmetry(
                            m_path, axis, direction, tolerance, use_topo, None
                        )
                        if not success:
                            break
                        total_fixed += count
                        _, _, remaining = check_symmetry_spatial(m_path, axis, tolerance)
                        print("[SymFix] Pass %d：修正 %d 個，還剩 %d 個壞點" % (
                            pass_idx + 1, count, len(remaining)
                        ))
                        if count == 0:
                            stall_count += 1
                            if stall_count >= 3:
                                # 連續 3 圈無進展，ARI 擴散到極限，停止
                                print("[SymFix] 連續 3 圈無進展，停止（剩餘 %d 個無法配對）" % len(remaining))
                                break
                        else:
                            stall_count = 0
                        pass_idx += 1
                    if not remaining:
                        print("[SymFix] 全部修正完成")
                    elif pass_idx >= MAX_PASS:
                        print("[SymFix] 已達 %d pass 上限，停止（剩餘 %d 個）" % (MAX_PASS, len(remaining)))

            self.refresh_list(use_cache=True)

            if total_fixed > 0:
                self.status_lbl.setText(u_str("修復完成，共更新 %d 個頂點") % total_fixed)
                cmds.inViewMessage(
                    amg=u_str("<hl>修復完成（共更新 %d 個頂點）</hl>") % total_fixed,
                    pos='bottomCenter', fade=True
                )
            else:
                self.status_lbl.setText(u_str("未找到可修正的頂點，請確認方向設定"))
                cmds.inViewMessage(
                    amg=u_str("<hl>未找到可修正的頂點</hl>"),
                    pos='bottomCenter', fade=True
                )

        except Exception as e:
            import traceback
            traceback.print_exc()
            cmds.warning(u_str("修正錯誤: %s") % str(e))
        finally:
            cmds.undoInfo(closeChunk=True)
            QtWidgets.QApplication.restoreOverrideCursor()

    def do_force_snap_center(self):
        axis = 'x' if self.radio_x.isChecked() else ('y' if self.radio_y.isChecked() else 'z')
        sel_vtx = cmds.ls(selection=True, flatten=True)

        if not sel_vtx:
            return

        cmds.undoInfo(openChunk=True)
        try:
            for v in sel_vtx:
                if ".vtx[" in v:
                    pos = cmds.xform(v, query=True, translation=True, objectSpace=True)
                    if axis == 'x':   pos[0] = 0.0
                    elif axis == 'y': pos[1] = 0.0
                    else:             pos[2] = 0.0
                    cmds.xform(v, translation=pos, objectSpace=True)

            if self.cached_transforms:
                self.refresh_list(use_cache=True)
        finally:
            cmds.undoInfo(closeChunk=True)

    def on_selection_changed(self):
        items = self.list_widget.selectedItems()
        if not items:
            cmds.select(clear=True)
            return

        to_sel = []
        for it in items:
            dat = it.data(QtCore.Qt.UserRole)
            if not cmds.objExists(dat["path"]):
                continue
            if dat["bad_indices"]:
                to_sel.extend(
                    ["%s.vtx[%d]" % (dat["path"], idx) for idx in dat["bad_indices"]]
                )
            else:
                to_sel.append(dat["path"])

        if to_sel:
            cmds.select(to_sel, replace=True)


def show_ui():
    global _sym_checker_ui
    try:
        _sym_checker_ui.close()
        _sym_checker_ui.deleteLater()
    except Exception:
        pass

    _sym_checker_ui = SymmetryBatchCheckerUI()
    _sym_checker_ui.show()


if __name__ == "__main__":
    show_ui()
