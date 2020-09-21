from PyQt5.QtWidgets import QWidget, QGroupBox, QVBoxLayout, QMessageBox, QHBoxLayout, QLineEdit
from PyQt5.QtWidgets import QLabel, QPushButton
from .model import Model, Variable
from .utils import tqdm_progress, connect_input_and_button
import glob
import os
import uuid
from phathom.pipeline.preprocess_cmd import main as preprocess_main
from precomputed_tif.main import main as precomputed_main

class PreprocessingWidget(QWidget):
    def __init__(self, model:Model):
        QWidget.__init__(self)
        self.model = model
        layout = QVBoxLayout()
        self.setLayout(layout)
        self.fixed_channel = PreprocessingChannel(
            model,
            model.fixed_stack_path,
            model.fixed_precomputed_path, "Fixed")
        layout.addWidget(self.fixed_channel)
        self.moving_channel = PreprocessingChannel(
            model,
            model.moving_stack_path,
            model.moving_precomputed_path, "Moving")
        layout.addWidget(self.moving_channel)
        do_everything_button = QPushButton("Run all")
        layout.addWidget(do_everything_button)
        do_everything_button.clicked.connect(self.do_everything)
        layout.addStretch(1)

    def do_everything(self):
        if self.fixed_channel.do_everything():
            self.moving_channel.do_everything()


class PreprocessingChannel(QGroupBox):

    def __init__(self,
                 model:Model,
                 src_variable:Variable,
                 precomputed_variable:Variable,
                 channel_name:str):
        QGroupBox.__init__(self, channel_name)
        hook_src_path_to_precomputed_path(model, src_variable,
                                          precomputed_variable)
        self.model = model
        self.src_variable = src_variable
        self.precomputed_variable = precomputed_variable
        self.channel_name = channel_name
        self.src_file_count = 0
        self.dest_file_count = 0
        self.precomputed_exists = False

        layout = QVBoxLayout()
        self.setLayout(layout)
        self.source_widget = QLabel()
        layout.addWidget(self.source_widget)

        self.dest_widget = QLabel()
        layout.addWidget(self.dest_widget)

        hlayout = QHBoxLayout()
        layout.addLayout(hlayout)
        hlayout.addWidget(QLabel("Precomputed path:"))
        self.precomputed_path_widget = QLineEdit()
        hlayout.addWidget(self.precomputed_path_widget)
        self.precomputed_path_button = QPushButton("...")
        hlayout.addWidget(self.precomputed_path_button)
        connect_input_and_button(self, "Precomputed path",
                                 self.precomputed_path_widget,
                                 self.precomputed_path_button,
                                 precomputed_variable)

        self.precomputed_widget = QLabel()
        layout.addWidget(self.precomputed_widget)

        self.precomputed_button = QPushButton()
        layout.addWidget(self.precomputed_button)

        self.message_widget = QLabel()
        layout.addWidget(self.message_widget)

        self.precomputed_variable.register_callback("preprocessing",
                                                    self.onDestChange)
        self.precomputed_button.clicked.connect(self.onPrecomputedButtonPressed)
        self.onDestChange()


    def onDestChange(self, *args):
        src_path = self.src_variable.get()
        precomputed_path = self.precomputed_variable.get()
        self.src_file_count = count_files(src_path)
        precomputed_test_file = os.path.join(
            precomputed_path, "1_1_1", "precomputed.blockfs")
        self.precomputed_exists = os.path.exists(precomputed_test_file)
        self.source_widget.setText(
            "Source:  (%d files) %s" % (self.src_file_count, src_path))
        self.precomputed_widget.setText(
            "Precomputed: (%s) %s" % (
                "Done" if self.precomputed_exists else "Not done",
                precomputed_path))
        if self.src_file_count == 0:
            self.message_widget.setText("No image files in source")
            self.message_widget.setStyleSheet("color: red;")
            self.precomputed_button.setDisabled(True)
        else:
            self.message_widget.setText("")
            self.message_widget.setStyleSheet("")
            self.precomputed_button.setDisabled(False)
            if self.precomputed_exists:
                self.precomputed_button.setText("Remake Neuroglancer volume")
            else:
                self.precomputed_button.setText("Make Neuroglancer volume")

    def onPrecomputedButtonPressed(self, *args):
        self.do_precomputed()

    def do_precomputed(self):
        with tqdm_progress() as result:
            precomputed_main([
                "--source",
                self.src_variable.get() + "/*.tif*",
                "--dest",
                self.precomputed_variable.get(),
                "--levels", "7",
                "--format", "blockfs",
                "--n-cores", str(self.model.n_workers.get())
            ])
        self.onDestChange()
        return result.result()

    def do_everything(self):
        return self.do_precomputed()

def count_files(path):
    files = glob.glob(os.path.join(path, "*.tif*"))
    return len(files)

def hook_src_path_to_precomputed_path(
        model:Model,
        src_variable:Variable,
        precomputed_variable:Variable):
    def on_src_changed(value):
        root = os.path.join(model.output_path.get(),
                            os.path.split(src_variable.get())[-1])
        precomputed_path = root+"_precomputed"
        precomputed_variable.set(precomputed_path)
    src_variable.register_callback("precomputed", on_src_changed)
    model.output_path.register_callback(uuid.uuid4(), on_src_changed)