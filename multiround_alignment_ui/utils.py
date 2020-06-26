import contextlib
import json
import multiprocessing

from functools import partial

import gunicorn.app.base
import os
import neuroglancer
import pathlib
from concurrent.futures import Future

from gunicorn.arbiter import Arbiter
from gunicorn.config import Config

from precomputed_tif.wsgi_webserver import serve_precomputed
import tqdm
import threading
import traceback
from PyQt5.QtWidgets import QPushButton, QMessageBox, QApplication

from multiround_alignment_ui.model import Model

PROGRESS = None
MESSAGE = None
CANCEL:QPushButton = None
STATUS_BAR = None

class QTqdm(tqdm.tqdm):
    def __init__(self, *args, **kwargs):
        super(QTqdm, self).__init__(*args, **kwargs)
        del self.sp
        self.cancelled = False
        self.mininterval

    def cancel(self, *args):
        self.cancelled = True

    def refresh(self, *args, **kwargs):
        PROGRESS.setValue(self.n)

    def __iter__(self):
        CANCEL.clicked.connect(self.cancel)
        try:
            PROGRESS.setMinimum(0)
            PROGRESS.setMaximum(self.total)
            self.start_t = self._time()
            for obj in self.iterable:
                yield obj
                if self.disable:
                    return
                n = 1
                if n < 0:
                    raise ValueError("n ({0}) cannot be negative".format(n))
                self.n += n

                # check counter first to reduce calls to time()
                if self.n - self.last_print_n >= self.miniters:
                    delta_t = self._time() - self.last_print_t
                    if delta_t >= self.mininterval:
                        cur_t = self._time()
                        delta_it = self.n - self.last_print_n  # >= n
                        # elapsed = cur_t - self.start_t
                        # EMA (not just overall average)
                        if self.smoothing and delta_t and delta_it:
                            self.avg_time = delta_t / delta_it \
                                if self.avg_time is None \
                                else self.smoothing * delta_t / delta_it + \
                                     (1 - self.smoothing) * self.avg_time
                        QApplication.processEvents()
                        PROGRESS.setValue(self.n)
                        elapsed = self._time() - self.start_t
                        remaining = (self.total - self.n) * elapsed / self.n
                        self.last_print_t = cur_t
                        msg = '{0:d}/{1:d} [{2}<{3}]'.format(
                            self.n, self.total, self.format_interval(elapsed),
                            self.format_interval(remaining))
                        MESSAGE.setText(msg)
                        if self.cancelled:
                            raise KeyboardInterrupt("Interrupt in tqdm loop")
        finally:
            CANCEL.clicked.disconnect()

def setup_tqdm_progress(progress, message, cancel_button, status_bar):
    global PROGRESS, MESSAGE, CANCEL, STATUS_BAR
    PROGRESS = progress
    MESSAGE = message
    CANCEL = cancel_button
    STATUS_BAR = status_bar
    progress.hide()
    message.hide()
    cancel_button.hide()


def set_status_bar_message(message):
    STATUS_BAR.showMessage(message)


def clear_status_bar_message():
    STATUS_BAR.clearMessage()


@contextlib.contextmanager
def tqdm_progress():
    PROGRESS.show()
    MESSAGE.show()
    CANCEL.show()
    QApplication.processEvents()
    old = tqdm.tqdm
    tqdm.tqdm = QTqdm
    future = Future()
    try:
        yield future
    except KeyboardInterrupt:
        QMessageBox.information(PROGRESS, "Operation cancelled",
                                "Operation cancelled by user")
        future.set_result(False)
    except:
        why = traceback.format_exc()
        QMessageBox.critical(None, "Error during execution", why)
        future.set_result(False)
    finally:
        tqdm.tqdm = old
        PROGRESS.hide()
        MESSAGE.hide()
        CANCEL.hide()
        future.set_result(True)


def moving_neuroglancer_url(model:Model) -> str:
    """
    Return a file URL for the location of the moving neuroglancer volume

    :param model: the application model
    :return: the URL as a string
    :rtype:
    """
    return pathlib.Path(
        model.moving_precomputed_path.get()).as_uri()


def moving_neuroglancer_path_is_valid(model:Model) -> bool:
    """
    Return True if the moving neuroglancer URL appears to point to a valid URL
    :param model:
    :type model:
    :return:
    :rtype:
    """
    return os.path.exists(
        os.path.join(model.moving_precomputed_path.get(),
                     "2_2_2", "precomputed.blockfs"))


def fixed_neuroglancer_url(model:Model) -> str:
    """
    Return a file URL for the location of the fixed neuroglancer volume

    :param model: the application model
    :return: the URL as a string
    :rtype:
    """
    return pathlib.Path(
        model.fixed_precomputed_path.get()).as_uri()


def fixed_neuroglancer_path_is_valid(model:Model) -> bool:
    """
    Return True if the fixed neuroglancer URL appears to point to a valid URL
    :param model:
    :type model:
    :return:
    :rtype:
    """
    return os.path.exists(
        os.path.join(model.fixed_precomputed_path.get(),
                     "2_2_2", "precomputed.blockfs"))


class WSGIServer(gunicorn.app.base.BaseApplication):
    def __init__(self, model:Model):
        self.model = model
        with open(model.config_file.get(), "w") as fd:
            json.dump([
                {
                    "name":"fixed",
                    "directory":model.fixed_precomputed_path.get(),
                    "format":"blockfs"
                },
                {
                    "name":"moving",
                    "directory":model.moving_precomputed_path.get(),
                    "format":"blockfs"
                }
            ], fd)
        self.application = partial(
            serve_precomputed,
            config_file=model.config_file.get())
        self.options = {
            "bind": "127.0.0.1:%d" % self.model.img_server_port_number.get(),
            "workers": self.model.n_workers.get()
        }
        super(WSGIServer, self).__init__()
        self.arbiter = None
        self.config = None

    def init(self, parser, opts, args):
        pass

    def load_config(self):
        self.cfg = Config(self.usage, self.prog)
        for key, value in self.options.items():
            self.cfg.set(key, value)

    def load(self):
        return self.application

    def run(self):
        try:
            self.arbiter = Arbiter(self)
            self.arbiter.run()
        except:
            message = traceback.format_exc()
            QMessageBox.critical(None, "Error in image webserver",
                                 message)

    def stop(self):
        self.arbiter.stop()

    @staticmethod
    def go_wsgiserver_go(model):
        server = WSGIServer(model)
        server.run()


@contextlib.contextmanager
def wsgi_server(model:Model):
    my_process = multiprocessing.Process(
        target=WSGIServer.go_wsgiserver_go,
        args=(model,))
    my_process.start()
    yield
    my_process.terminate()


def create_neuroglancer_viewer(model:Model) -> neuroglancer.Viewer:
    """
    Create a viewer for a Neuroglancer instance

    :param model: has the details for the static Neuroglancer elements
    :return: a Neuroglancer viewer that can be used to display volumes
    """
    if not model.neuroglancer_initialized.get():
        neuroglancer.set_static_content_source(
            url=model.static_content_source.get())
        neuroglancer.set_server_bind_address(
            model.bind_address.get(),
            model.port_number.get())
        model.neuroglancer_initialized.set(True)
    return neuroglancer.Viewer()

class OnActivateMixin:
    def on_activated(self):
        """Do something when the tab is uncovered"""

if __name__ == "__main__":
    import time
    from PyQt5.QtWidgets import QMainWindow, QWidget, QVBoxLayout
    from PyQt5.QtWidgets import QPushButton, QProgressBar, QHBoxLayout, QLabel
    import sys

    app = QApplication(sys.argv)


    class MyWindow(QMainWindow):
        def __init__(self):
            QMainWindow.__init__(self)
            self.setGeometry(0, 0, 640, 240)
            main_widget = QWidget()
            layout = QVBoxLayout()
            main_widget.setLayout(layout)
            hlayout = QHBoxLayout()
            layout.addLayout(hlayout)
            self.progressbar = QProgressBar()
            hlayout.addWidget(self.progressbar)
            self.message = QLabel()
            hlayout.addWidget(self.message)
            cancel_button = QPushButton("cancel")
            hlayout.addWidget(cancel_button)
            setup_tqdm_progress(self.progressbar, self.message, cancel_button)
            button = QPushButton("Go")
            layout.addWidget(button)
            button.clicked.connect(self.go)

            self.setCentralWidget(main_widget)

        def go(self):
            with tqdm_progress():
                for i in tqdm.tqdm(range(100)):
                    time.sleep(1)
    window = MyWindow()
    window.show()
    app.exec()
