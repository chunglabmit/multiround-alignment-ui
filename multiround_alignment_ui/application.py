import os
import matplotlib
matplotlib.use("Qt5Agg")
matplotlib.use = lambda *args: 0

import time
import traceback

import sys
from PyQt5 import QtCore
from PyQt5.QtGui import QKeySequence

from PyQt5.QtWidgets import QApplication, QMainWindow, QTabWidget, QWidget, QFileDialog, QMessageBox
from PyQt5.QtWidgets import QVBoxLayout, QStatusBar, QProgressBar, QLabel
from PyQt5.QtWidgets import QPushButton, QMenu, QShortcut
import vispy
vispy.use("PyQt5", "gl2")
from .model import Model
from .cell_detection import CellDetectionWidget
from .configuration import ConfigurationWidget
from .fine_alignment import FineAlignmentWidget
from .preprocessing import PreprocessingWidget
from .rigid_alignment import RigidAlignmentWidget
from .rough_alignment import RoughAlignmentWidget
from .utils import setup_tqdm_progress, OnActivateMixin

class ApplicationWindow(QMainWindow):
    def __init__(self):
        super(ApplicationWindow, self).__init__()
        self.setGeometry(0, 0, 1024, 768)
        self.model = Model()
        #
        # Menus
        #
        self.file_menu = QMenu("&File", self)
        self.file_menu.addAction("&Open", self.open)
        self.open_shortcut = QShortcut(QKeySequence("Ctrl+O"), self)
        self.open_shortcut.activated.connect(self.open)
        self.file_menu.addAction("&Save", self.save)
        self.save_shortcut = QShortcut(QKeySequence("Ctrl+S"), self)
        self.save_shortcut.activated.connect(self.save)
        self.file_menu.addAction("&Quit", self.quit,
                                 QtCore.Qt.CTRL + QtCore.Qt.Key_Q)
        self.menuBar().addMenu(self.file_menu)
        self.state_path = ""
        #
        # Widgets
        #
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout()
        main_widget.setLayout(layout)
        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)
        for name, widget_class in (
                ("Configuration", ConfigurationWidget),
                ("Preprocessing", PreprocessingWidget),
                ("Rigid alignment", RigidAlignmentWidget),
                ("Rough alignment", RoughAlignmentWidget),
                ("Cell detection", CellDetectionWidget),
                ("Fine alignment", FineAlignmentWidget)
        ):
            tab_widget = widget_class(self.model)
            self.tabs.addTab(tab_widget, name)
        self.tabs.currentChanged.connect(self.on_tab_changed)
        self.status_bar = QStatusBar()
        layout.addWidget(self.status_bar)
        progress = QProgressBar()
        self.status_bar.addWidget(progress)
        message = QLabel()
        self.status_bar.addWidget(message)
        cancel_button = QPushButton("Cancel")
        self.status_bar.addWidget(cancel_button)
        setup_tqdm_progress(progress, message, cancel_button, self.status_bar)

    def on_tab_changed(self, *args):
        widget = self.tabs.currentWidget()
        if isinstance(widget, OnActivateMixin):
            widget.on_activated()

    def open(self, event=None):
        open_name, file_type = QFileDialog.getOpenFileName(
            self,
            "Open session",
            self.state_path,
            "Session state (*.maui)"
        )
        if len(open_name) == 0:
            return
        self.status_bar.showMessage("Loading %s" % os.path.split(open_name)[1])
        try:
            self.model.read(open_name)
            self.state_path = open_name
        except:
            why = traceback.format_exc()
            QMessageBox.critical(self, "Error opening file", why)
        finally:
            self.status_bar.showMessage("")

    def save(self, event=None):
        save_name, file_type = QFileDialog.getSaveFileName(
            self,
            "Save session state",
            self.state_path,
            "Session state (*.maui)"
        )
        if len(save_name) > 0:
            if "." not in os.path.split(save_name)[1]:
                save_name += ".maui"
            try:
                self.model.write(save_name)
                self.state_path = save_name
            except:
                why = traceback.format_exc()
                QMessageBox.critical(None, "Error saving file", why)

    def quit(self):
        self.status_bar.showMessage("I'm not fired, I quit!", msecs=250)
        time.sleep(.250)
        self.close()


def run_application():
    app = QApplication(sys.argv)
    window = ApplicationWindow()
    window.setWindowTitle("Multiround alignment")
    window.show()
    sys.exit(app.exec())

