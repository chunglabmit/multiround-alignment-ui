import numpy as np
import os

from PyQt5.QtCore import QProcess
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QPushButton, QTextEdit, QGroupBox

from multiround_alignment_ui.utils import fixed_neuroglancer_path_is_valid, moving_neuroglancer_path_is_valid, \
    fixed_neuroglancer_url, moving_neuroglancer_url
from precomputed_tif.client import ArrayReader


class RoughAlignmentWidget(QWidget):
    def __init__(self, model):
        QWidget.__init__(self)
        self.model = model
        self.running = False
        self.process = None

        def on_output_change(*args):
            self.model.rough_interpolator.set(
                os.path.join(self.model.output_path.get(),
                             "rough-alignment.pkl")
            )
        self.model.output_path.register_callback("rough-alignment",
                                                 on_output_change)
        self.model.fixed_precomputed_path.register_callback(
            "rough-alignment", self.decorate_go_button)
        self.model.moving_precomputed_path.register_callback(
            "rough-alignment", self.decorate_go_button)
        #
        # GUI
        #
        layout = QVBoxLayout()
        self.setLayout(layout)
        self.go_button = QPushButton()
        self.decorate_go_button()
        self.go_button.clicked.connect(self.on_go)
        layout.addWidget(self.go_button)
        group_box = QGroupBox("Elastix output")
        layout.addWidget(group_box)
        gb_layout = QVBoxLayout()
        group_box.setLayout(gb_layout)
        self.stdout = QTextEdit()
        self.stdout.setReadOnly(True)
        self.stdout.setAcceptRichText(False)
        gb_layout.addWidget(self.stdout)

    def decorate_go_button(self, *args):
        """
        Set the go button to enabled or disabled and set its label to
        either "run alignment" or "rerun alignment"
        """
        if self.running:
            return
        if fixed_neuroglancer_path_is_valid(self.model) and \
            moving_neuroglancer_path_is_valid(self.model):
            self.go_button.setDisabled(False)
        else:
            self.go_button.setDisabled(True)
        if os.path.exists(self.model.rough_interpolator.get()):
            self.go_button.setText("Rerun rough alignment")
        else:
            self.go_button.setText("Run rough alignment")

    def on_go(self, *args):
        if self.running:
            self.process.kill()
            return
        self.running = True
        url = fixed_neuroglancer_url(self.model)
        for level_idx in range(0, 6):
            level = 2 ** level_idx
            fixed_array = ArrayReader(url, format='blockfs', level = level)
            if np.min(fixed_array.shape) < 50 and \
                    np.max(fixed_array.shape) < 1000:
                break

        initial_rotation = "%f,%f,%f" % (
            self.model.angle_x.get(),
            self.model.angle_y.get(),
            self.model.angle_z.get())
        initial_translation = "%f,%f,%f" % (
            self.model.offset_x.get(),
            self.model.offset_y.get(),
            self.model.offset_z.get())
        rotation_center = "%f,%f,%f" % (
            self.model.center_x.get(),
            self.model.center_y.get(),
            self.model.center_z.get())
        self.stdout.clear()
        self.process = QProcess(self)
        self.process.readyReadStandardOutput.connect(self.on_stdout)
        self.process.readyReadStandardError.connect(self.on_stderr)
        self.process.started.connect(self.on_process_started)
        self.process.finished.connect(self.on_process_finished)
        working_dir = os.path.join(self.model.output_path.get(), "alignment")
        result = self.process.start(
                "phathom-non-rigid-registration",
                ["--fixed-url", fixed_neuroglancer_url(self.model),
                 "--fixed-url-format", "blockfs",
                 "--moving-url", moving_neuroglancer_url(self.model),
                 "--moving-url-format", "blockfs",
                 "--output", self.model.rough_interpolator.get(),
                 "--initial-rotation=" + initial_rotation,
                 "--initial-translation=" + initial_translation,
                 "--rotation-center=" + rotation_center,
                 "--mipmap-level=" + str(level),
                 "--working-dir", working_dir,
                 "--invert"]
            )
        self.go_button.setText("Cancel")

    def on_stdout(self):
        #
        # Code derived from
        # https://stackoverflow.com/questions/22069321/realtime-output-from-a-subprogram-to-stdout-of-a-pyqt-widget
        #
        cursor = self.stdout.textCursor()
        cursor.movePosition(cursor.End)
        btext:bytes = bytes(self.process.readAllStandardOutput())
        cursor.insertText(btext.decode("ascii"))
        self.stdout.ensureCursorVisible()

    def on_stderr(self):
        #
        # Code derived from
        # https://stackoverflow.com/questions/22069321/realtime-output-from-a-subprogram-to-stdout-of-a-pyqt-widget
        #
        cursor = self.stdout.textCursor()
        cursor.movePosition(cursor.End)
        btext:bytes = bytes(self.process.readAllStandardError())
        cursor.insertText(btext.decode("ascii"))
        self.stdout.ensureCursorVisible()

    def on_process_started(self):
        pass

    def on_process_finished(self):
        self.running = False
        self.process = None
        self.decorate_go_button()