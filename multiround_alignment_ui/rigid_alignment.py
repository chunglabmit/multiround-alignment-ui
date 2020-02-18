#
# Some code derived from
# https://github.com/vispy/vispy/blob/master/examples/basics/scene/volume.py
# (BSD license)
#
import os

import uuid

import numpy as np
import pathlib

from PyQt5.QtWidgets import QWidget, QSplitter, QHBoxLayout, QVBoxLayout, QPushButton
from PyQt5.QtWidgets import QLabel, QSpinBox, QDoubleSpinBox, QGroupBox
from PyQt5 import QtCore
from vispy import scene
from vispy.color import BaseColormap, get_colormap
from vispy.visuals.transforms import STTransform, MatrixTransform, ChainTransform

from precomputed_tif.client import get_info, ArrayReader
from phathom.registration.pcloud import rotation_matrix
from vispy.scene import SceneCanvas
from .model import Model
from .utils import OnActivateMixin, fixed_neuroglancer_path_is_valid, fixed_neuroglancer_url, \
    moving_neuroglancer_path_is_valid, moving_neuroglancer_url

VOLUME_RENDERING_METHOD = "translucent"


class TranslucentFixedColormap(BaseColormap):
    glsl_map = """
    vec4 translucent_fixed(float t) {
        return vec4(t * 2.0, 0, 0, t*0.05);
    }
    """

class TranslucentMovingColormap(BaseColormap):
    glsl_map = """
    vec4 translucent_moving(float t) {
        return vec4(0, t * 2.0, 0, t*0.05);
    }
    """

class RigidAlignmentWidget(QWidget, OnActivateMixin):
    def __init__(self, model:Model):
        QWidget.__init__(self)
        self.model = model
        self.fixed_url = None
        self.level = None
        self.fixed_volume = None
        self.moving_url = None
        self.moving_volume = None
        self.canvas_shape = None
        self.view = None

        top_layout = QVBoxLayout()
        self.setLayout(top_layout)
        splitter = QSplitter(QtCore.Qt.Horizontal)
        top_layout.addWidget(splitter)
        left_widget = QWidget()
        splitter.addWidget(left_widget)
        left_layout = QVBoxLayout()
        left_widget.setLayout(left_layout)
        #
        # ------ Center coordinates
        #
        center_group_box = QGroupBox("Center coordinates")
        left_layout.addWidget(center_group_box)
        center_layout = QVBoxLayout()
        center_group_box.setLayout(center_layout)
        hlayout = QHBoxLayout()
        center_layout.addLayout(hlayout)
        hlayout.addWidget(QLabel("X:"))
        self.center_x_spin_box = QSpinBox()
        model.center_x.bind_spin_box(self.center_x_spin_box)
        model.center_x.register_callback("centering", self.apply_translation)
        hlayout.addWidget(self.center_x_spin_box)

        hlayout = QHBoxLayout()
        center_layout.addLayout(hlayout)
        hlayout.addWidget(QLabel("Y:"))
        self.center_y_spin_box = QSpinBox()
        model.center_y.bind_spin_box(self.center_y_spin_box)
        model.center_y.register_callback("centering", self.apply_translation)
        hlayout.addWidget(self.center_y_spin_box)

        hlayout = QHBoxLayout()
        center_layout.addLayout(hlayout)
        hlayout.addWidget(QLabel("Z:"))
        self.center_z_spin_box = QSpinBox()
        model.center_z.bind_spin_box(self.center_z_spin_box)
        model.center_z.register_callback("centering", self.apply_translation)
        hlayout.addWidget(self.center_z_spin_box)
        center_button = QPushButton("Set center")
        center_layout.addWidget(center_button)
        center_button.clicked.connect(self.set_center)
        #
        # ------ Offsets
        #
        offset_group_box = QGroupBox("Offsets")
        left_layout.addWidget(offset_group_box)
        offset_layout = QVBoxLayout()
        offset_group_box.setLayout(offset_layout)
        hlayout = QHBoxLayout()
        offset_layout.addLayout(hlayout)
        hlayout.addWidget(QLabel("X:"))
        self.offset_x_spin_box = QSpinBox()
        model.offset_x.bind_spin_box(self.offset_x_spin_box)
        model.offset_x.register_callback(uuid.uuid4(), self.apply_translation)
        hlayout.addWidget(self.offset_x_spin_box)

        hlayout = QHBoxLayout()
        offset_layout.addLayout(hlayout)
        hlayout.addWidget(QLabel("Y:"))
        self.offset_y_spin_box = QSpinBox()
        model.offset_y.bind_spin_box(self.offset_y_spin_box)
        model.offset_y.register_callback(uuid.uuid4(), self.apply_translation)
        hlayout.addWidget(self.offset_y_spin_box)

        hlayout = QHBoxLayout()
        offset_layout.addLayout(hlayout)
        hlayout.addWidget(QLabel("Z:"))
        self.offset_z_spin_box = QSpinBox()
        model.offset_z.bind_spin_box(self.offset_z_spin_box)
        model.offset_z.register_callback(uuid.uuid4(), self.apply_translation)
        hlayout.addWidget(self.offset_z_spin_box)
        #
        # ------ Angles
        #
        angle_group_box = QGroupBox("Rotation angles (-180° to 180°)")
        left_layout.addWidget(angle_group_box)
        angle_layout = QVBoxLayout()
        angle_group_box.setLayout(angle_layout)
        hlayout = QHBoxLayout()
        angle_layout.addLayout(hlayout)
        hlayout.addWidget(QLabel("X:"))
        self.angle_x_spin_box = QDoubleSpinBox()
        self.angle_x_spin_box.setRange(-180, 180)
        model.angle_x.bind_double_spin_box(self.angle_x_spin_box)
        model.angle_x.register_callback("rotation", self.apply_translation)
        hlayout.addWidget(self.angle_x_spin_box)

        hlayout = QHBoxLayout()
        angle_layout.addLayout(hlayout)
        hlayout.addWidget(QLabel("Y:"))
        self.angle_y_spin_box = QDoubleSpinBox()
        self.angle_y_spin_box.setRange(-180, 180)
        model.angle_y.bind_double_spin_box(self.angle_y_spin_box)
        model.angle_y.register_callback("rotation", self.apply_translation)
        hlayout.addWidget(self.angle_y_spin_box)

        hlayout = QHBoxLayout()
        angle_layout.addLayout(hlayout)
        hlayout.addWidget(QLabel("Z:"))
        self.angle_z_spin_box = QDoubleSpinBox()
        self.angle_z_spin_box.setRange(-180, 180)
        model.angle_z.bind_double_spin_box(self.angle_z_spin_box)
        model.angle_z.register_callback("rotation", self.apply_translation)
        hlayout.addWidget(self.angle_z_spin_box)
        #
        # Display parameters
        #
        display_group_box = QGroupBox("Display")
        left_layout.addWidget(display_group_box)
        dgb_layout = QVBoxLayout()
        display_group_box.setLayout(dgb_layout)
        hlayout = QHBoxLayout()
        dgb_layout.addLayout(hlayout)
        hlayout.addWidget(QLabel("Fixed threshold (0 to 1)"))
        fixed_display_threshold_widget = QDoubleSpinBox()
        hlayout.addWidget(fixed_display_threshold_widget)
        fixed_display_threshold_widget.setRange(0, 1)
        self.model.fixed_display_threshold.bind_double_spin_box(
            fixed_display_threshold_widget)
        self.model.fixed_display_threshold.register_callback(
            "try_to_draw", self.try_to_draw)
        hlayout = QHBoxLayout()
        dgb_layout.addLayout(hlayout)
        hlayout.addWidget(QLabel("Moving threshold (0 to 1)"))
        moving_display_threshold_widget = QDoubleSpinBox()
        hlayout.addWidget(moving_display_threshold_widget)
        moving_display_threshold_widget.setRange(0, 1)
        self.model.moving_display_threshold.bind_double_spin_box(
            moving_display_threshold_widget)
        self.model.moving_display_threshold.register_callback(
            "try_to_draw", self.try_to_draw)

        self.scene = SceneCanvas(keys='interactive')
        splitter.addWidget(self.scene.native)
        self.view = self.scene.central_widget.add_view()

    def on_activated(self):
        self.try_to_draw()

    def set_center(self, *args):
        if not os.path.exists(self.model.fixed_precomputed_path.get()):
            return False
        fixed_url = pathlib.Path(
            self.model.fixed_precomputed_path.get()).as_uri()
        try:
            fixed_shape = \
                ArrayReader(fixed_url, format="blockfs", level=1).shape
        except:
            return False
        self.model.center_x.set(fixed_shape[2] // 2)
        self.model.center_y.set(fixed_shape[1] // 2)
        self.model.center_z.set(fixed_shape[0] // 2)

    def try_to_draw(self, *args):
        if not fixed_neuroglancer_path_is_valid(self.model):
            return
        if not moving_neuroglancer_path_is_valid(self.model):
            return
        fixed_url = fixed_neuroglancer_url(self.model)
        moving_url = moving_neuroglancer_url(self.model)
        canvas_shape = (self.scene.native.contentsRect().height(),
                        self.scene.native.contentsRect().width())
        if fixed_url != self.fixed_url or \
                self.canvas_shape != canvas_shape:
            # We have to update the fixed volume
            fixed_array = None
            fixed_shape = \
                ArrayReader(fixed_url, format="blockfs", level=1).shape
            self.center_x_spin_box.setMinimum(0)
            self.center_x_spin_box.setMaximum(fixed_shape[2])
            self.offset_x_spin_box.setMinimum(-fixed_shape[2])
            self.offset_x_spin_box.setMaximum(fixed_shape[2])
            self.center_y_spin_box.setMinimum(0)
            self.center_y_spin_box.setMaximum(fixed_shape[1])
            self.offset_y_spin_box.setMinimum(-fixed_shape[1])
            self.offset_y_spin_box.setMaximum(fixed_shape[1])
            self.center_z_spin_box.setMinimum(0)
            self.center_z_spin_box.setMaximum(fixed_shape[0])
            self.offset_z_spin_box.setMinimum(-fixed_shape[0])
            self.offset_z_spin_box.setMaximum(fixed_shape[0])
            for level_idx in range(0, 6):
                level = 2 ** level_idx
                try:
                    test_fixed_array = ArrayReader(fixed_url,
                                                   format="blockfs",
                                                   level = level)
                    test_shape = test_fixed_array.shape
                    fixed_array = test_fixed_array
                    self.level = level
                    if test_shape[1] < canvas_shape[0] // 2 or \
                       test_shape[2] < canvas_shape[1] // 2:
                        break
                except:
                    break
            if not fixed_array:
                return
            self.fixed_volume = fixed_array[0:test_shape[0],
                                            0:test_shape[1],
                                            0:test_shape[2]]
            self.fixed_volume = (np.clip(
                self.fixed_volume.astype(np.float32), 100, 1000) / 1000 * 255
                                 ).astype(np.uint8)
            self.fixed_url = fixed_url
            need_to_do_moving = True
        else:
            need_to_do_moving = False
        if need_to_do_moving or moving_url != self.moving_url:
            try:
                moving_array = ArrayReader(moving_url,
                                           format="blockfs",
                                           level=self.level)
                moving_shape = moving_array.shape
                self.moving_volume = \
                    moving_array[0:moving_shape[0], 0:moving_shape[1],
                                 0:moving_shape[2]]
                self.moving_volume = (np.clip(
                    self.moving_volume.astype(np.float32), 100, 1000) /
                                      1000 * 255
                                     ).astype(np.uint8)
                self.moving_url = moving_url
            except:
                return
        self.draw_scene()

    def apply_translation(self, *args):
        if self.view and self.level:
            translation_transform = STTransform(
                translate=(
                    self.model.offset_x.get() / self.level,
                    self.model.offset_y.get() / self.level,
                    self.model.offset_z.get() / self.level
                )
            )
            rmatrix = np.eye(4)
            rmatrix[:3, :3] = rotation_matrix((
                self.model.angle_z.get() * np.pi / 180,
                self.model.angle_y.get() * np.pi / 180,
                self.model.angle_x.get() * np.pi / 180
            ))[::-1, ::-1]
            tmatrix = np.array([
                self.model.center_x.get() / self.level,
                self.model.center_y.get() / self.level,
                self.model.center_z.get() / self.level
            ])
            #
            # The last of 4 columns of the affine transform is the
            # translation. The translation is the rotated center minus the
            # offset plus the center, not rotated.
            #
            rmatrix[3, :3] = rmatrix[:3, :3].dot(-tmatrix)
            rmatrix[3, 0] += self.model.offset_x.get() / self.level
            rmatrix[3, 1] += self.model.offset_y.get() / self.level
            rmatrix[3, 2] += self.model.offset_z.get() / self.level
            rmatrix[3, :3] += tmatrix
            rotate_transform = MatrixTransform(rmatrix)
            self.translation_frame.transform = rotate_transform
            self.center_frame.transform = MatrixTransform(
                np.array([[1, 0, 0, tmatrix[0]],
                          [0, 1, 0, tmatrix[1]],
                          [0, 0, 1, tmatrix[2]],
                          [0, 0, 0, 1]])
            )
            self.scene.update()

    def draw_scene(self):
        self.fixed_frame = scene.node.Node(self.view.scene)
        fixed_volume = scene.visuals.Volume(
            self.fixed_volume,
            parent = self.fixed_frame,
            threshold = self.model.fixed_display_threshold.get(),
            emulate_texture=False)
        fixed_volume.cmap = TranslucentFixedColormap()
        fixed_volume.method = VOLUME_RENDERING_METHOD
        #
        # The transformation is done as follows:
        #
        # The translation frame handles the offset
        #
        # The centering frame picks the center of the moving frame
        #
        # The rotation frame rotates about the center
        #
        # The uncentering frame readjusts the coordinates so that 0, 0 is
        # placed away from the center.
        #
        self.translation_frame = scene.node.Node(
            self.view.scene)

        moving_volume = scene.visuals.Volume(
            self.moving_volume,
            parent = self.translation_frame,
            threshold = self.model.moving_display_threshold.get(),
            emulate_texture=False)
        moving_volume.cmap = TranslucentMovingColormap()
        moving_volume.method = VOLUME_RENDERING_METHOD
        self.camera = scene.cameras.TurntableCamera(
            parent=self.view.scene,
            fov = 60.,
            elevation=self.fixed_volume.shape[2] // 2,
            name="Turntable")
        self.view.camera = self.camera
        self.center_frame = scene.node.Node(parent=self.view)
        self.axis = scene.visuals.XYZAxis(parent=self.center_frame)
        axis_t = STTransform(
            scale=(50, 50, 50, 1)
        )
        self.axis.transform = axis_t.as_matrix()
        self.apply_translation()
        self.scene.events.mouse_move.connect(self.on_mouse_move)

    def on_mouse_move(self, event):
        if event.button == 1 and event.is_dragging:
            self.axis.transform.reset()

            self.axis.transform.rotate(self.camera.roll, (0, 0, 1))
            self.axis.transform.rotate(self.camera.elevation, (1, 0, 0))
            self.axis.transform.rotate(self.camera.azimuth, (0, 1, 0))
            self.axis.transform.translate((
                self.model.center_x.get() / self.level,
                self.model.center_y.get() / self.level,
                self.model.center_z.get() / self.level
            ))
            self.axis.transform.scale((50, 50, 0.001))
            #axis.transform.translate((50., 50.))
            self.axis.update()
