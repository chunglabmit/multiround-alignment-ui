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
            model.fixed_preprocessed_path,
            model.fixed_precomputed_path, "Fixed")
        layout.addWidget(self.fixed_channel)
        self.moving_channel = PreprocessingChannel(
            model,
            model.moving_stack_path,
            model.moving_preprocessed_path,
            model.moving_precomputed_path, "Moving")
        layout.addWidget(self.moving_channel)
        do_everything_button = QPushButton("Run all")
        layout.addWidget(do_everything_button)
        do_everything_button.clicked.connect(self.do_everything)

    def do_everything(self):
        if self.fixed_channel.do_everything():
            self.moving_channel.do_everything()


class PreprocessingChannel(QGroupBox):

    def __init__(self,
                 model:Model,
                 src_variable:Variable,
                 dest_variable:Variable,
                 precomputed_variable:Variable,
                 channel_name:str):
        QGroupBox.__init__(self, channel_name)
        hook_src_path_to_preprocessing_path(model, src_variable,
                                            dest_variable,
                                            precomputed_variable)
        self.model = model
        self.src_variable = src_variable
        self.dest_variable = dest_variable
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
        hlayout.addWidget(QLabel("Preprocessed path:"))
        self.dest_path_widget = QLineEdit()
        hlayout.addWidget(self.dest_path_widget)
        self.dest_path_button = QPushButton("...")
        hlayout.addWidget(self.dest_path_button)
        connect_input_and_button(self, "Preprocessed path",
                                 self.dest_path_widget,
                                 self.dest_path_button,
                                 dest_variable)

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

        self.preprocess_button = QPushButton()
        layout.addWidget(self.preprocess_button)

        self.precomputed_widget = QLabel()
        layout.addWidget(self.precomputed_widget)

        self.precomputed_button = QPushButton()
        layout.addWidget(self.precomputed_button)

        self.message_widget = QLabel()
        layout.addWidget(self.message_widget)

        self.dest_variable.register_callback("preprocessing",
                                             self.onDestChange)
        self.precomputed_variable.register_callback("preprocessing",
                                                    self.onDestChange)
        self.preprocess_button.clicked.connect(self.onPreprocessButtonPressed)
        self.precomputed_button.clicked.connect(self.onPrecomputedButtonPressed)
        self.onDestChange()


    def onDestChange(self, *args):
        src_path = self.src_variable.get()
        dest_path = self.dest_variable.get()
        precomputed_path = self.precomputed_variable.get()
        self.src_file_count = count_files(src_path)
        self.dest_file_count = count_files(dest_path)
        precomputed_test_file = os.path.join(
            precomputed_path, "1_1_1", "precomputed.blockfs")
        self.precomputed_exists = os.path.exists(precomputed_test_file)
        self.source_widget.setText(
            "Source:  (%d files) %s" % (self.src_file_count, src_path))
        self.dest_widget.setText(
            "Preprocessed: (%d files) %s" % (self.dest_file_count, dest_path))
        self.precomputed_widget.setText(
            "Precomputed: (%s) %s" % (
                "Done" if self.precomputed_exists else "Not done",
                precomputed_path))
        if self.src_file_count == 0:
            self.message_widget.setText("No image files in source")
            self.message_widget.setStyleSheet("color: red;")
            self.preprocess_button.setDisabled(True)
        else:
            self.message_widget.setText("")
            self.message_widget.setStyleSheet("")
            self.preprocess_button.setDisabled(False)
            if self.dest_file_count != self.src_file_count:
                self.preprocess_button.setText("Run preprocessing")
            else:
                self.preprocess_button.setText("Rerun preprocessing")
        if self.dest_file_count == 0:
            self.precomputed_button.setDisabled(True)
            self.precomputed_button.setText("Make Neuroglancer volume")
        else:
            self.precomputed_button.setDisabled(False)
            if self.precomputed_exists:
                self.precomputed_button.setText("Remake Neuroglancer volume")
            else:
                self.precomputed_button.setText("Make Neuroglancer volume")

    def onPreprocessButtonPressed(self, *args):
        self.do_preprocessing()

    def do_preprocessing(self):
        output_path = self.model.output_path.get()
        if not os.path.exists(output_path):
            try:
                os.mkdir(output_path)
            except:
                QMessageBox.critical(
                    self,
                    "Can't create directory",
                    ("Can't create \"%s\".\n" % output_path) +
                    "Please change the output path to be in an existing "
                    "directory"
                )
                return False
        with tqdm_progress() as result:
            preprocess_main([
                "--input",
                self.src_variable.get(),
                "--output",
                self.dest_variable.get(),
                "--n-workers",
                str(self.model.n_workers.get())
            ])
        self.onDestChange()
        return result.result()

    def onPrecomputedButtonPressed(self, *args):
        self.do_precomputed()

    def do_precomputed(self):
        with tqdm_progress() as result:
            precomputed_main([
                "--source",
                self.dest_variable.get() + "/*.tif*",
                "--dest",
                self.precomputed_variable.get(),
                "--levels", "7",
                "--format", "blockfs",
                "--n-cores", str(self.model.n_workers.get())
            ])
        self.onDestChange()
        return result.result()

    def do_everything(self):
        if not self.do_preprocessing():
            return False
        return self.do_precomputed()

def count_files(path):
    files = glob.glob(os.path.join(path, "*.tif*"))
    return len(files)

def hook_src_path_to_preprocessing_path(
        model:Model,
        src_variable:Variable,
        preprocessing_variable:Variable,
        precomputed_variable:Variable):
    def on_src_changed(value):
        root = os.path.join(model.output_path.get(),
                            os.path.split(src_variable.get())[-1])
        preprocessing_path = root+"_preprocessed"
        preprocessing_variable.set(preprocessing_path)
        precomputed_path = root+"_precomputed"
        precomputed_variable.set(precomputed_path)
    src_variable.register_callback("preprocessing", on_src_changed)
    model.output_path.register_callback(uuid.uuid4(), on_src_changed)