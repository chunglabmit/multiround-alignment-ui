import h5py
import json
import multiprocessing
import neuroglancer
import numpy as np
import os
import pickle
import webbrowser

import tqdm

from eflash_2018.detect_blobs import main as detect_blobs_main
from eflash_2018.collect_patches import main as collect_patches_main
from eflash_2018.train import ApplicationWindow as TrainWindow
from mp_shared_memory import SharedMemory
from nuggt.utils.ngutils import cubehelix_shader, layer
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QGroupBox, QHBoxLayout, \
    QLabel, QDoubleSpinBox, QSpinBox, QPushButton, QDialog, QApplication, \
    QDialogButtonBox, QMessageBox, QCheckBox

from .model import Model
from .utils import tqdm_progress, create_neuroglancer_viewer, \
    wsgi_server, set_status_bar_message, \
    clear_status_bar_message, OnActivateMixin


class CellDetectionWidget(QWidget, OnActivateMixin):
    def __init__(self, model:Model):
        QWidget.__init__(self)
        self.model = model
        #
        # Hook elements of the model together
        #    Fixed and moving cell recognition ML model.
        #
        def on_output_changed(*args):
            self.model.fixed_model_path.set(
                os.path.join(self.model.output_path.get(),
                             "fixed.model"))
            self.model.moving_model_path.set(
                os.path.join(self.model.output_path.get(),
                             "moving.model"))
            self.model.fixed_patches_path.set(
                os.path.join(self.model.output_path.get(),
                             "patches_fixed.h5"))
            self.model.moving_patches_path.set(
                os.path.join(self.model.output_path.get(),
                             "patches_moving.h5"))
            self.model.fixed_blob_path.set(
                os.path.join(self.model.output_path.get(),
                             "blobs_fixed.json"))
            self.model.moving_blob_path.set(
                os.path.join(self.model.output_path.get(),
                             "blobs_moving.json"))
            self.model.fixed_coords_path.set(
                os.path.join(self.model.output_path.get(),
                             "coords_fixed.json")
            )
            self.model.moving_coords_path.set(
                os.path.join(self.model.output_path.get(),
                             "coords_moving.json")
            )

        self.model.output_path.register_callback(
            "cell_detection", on_output_changed)
        #
        # Build the panel:
        #
        # Vertical layout
        #   Fixed group box
        #     Vertical layout
        #       Horizontal layout: sigma + label
        #       Horizontal layout: threshold + label
        #       Horizontal layout: min-distance + label
        #       Horizontal layout: detect blobs button + train gui button +
        #                          neuroglancer link.
        #   Moving group box
        #     same
        #
        top_layout = QVBoxLayout()
        self.setLayout(top_layout)
        group_box = QGroupBox("Strategy")
        top_layout.addWidget(group_box)
        layout = QVBoxLayout()
        group_box.setLayout(layout)
        bypass_training_checkbox = QCheckBox("Bypass training")
        layout.addWidget(bypass_training_checkbox)
        self.model.bypass_training.bind_checkbox(bypass_training_checkbox)
        self.model.bypass_training.register_callback(
            "cell-detection", self.update_controls)
        #
        # Fixed
        #
        group_box = QGroupBox("Fixed cell detection")
        top_layout.addWidget(group_box)
        layout = QVBoxLayout()
        group_box.setLayout(layout)
        hlayout = QHBoxLayout()
        layout.addLayout(hlayout)
        hlayout.addWidget(QLabel("Sigma"))
        fixed_sigma = QDoubleSpinBox()
        hlayout.addWidget(fixed_sigma)
        fixed_sigma.setMinimum(0)
        fixed_sigma.setMaximum(10)
        model.fixed_low_sigma.bind_double_spin_box(fixed_sigma)
        hlayout.addStretch(1)
        hlayout = QHBoxLayout()
        layout.addLayout(hlayout)
        hlayout.addWidget(QLabel("Threshold"))
        fixed_threshold = QSpinBox()
        hlayout.addWidget(fixed_threshold)
        fixed_threshold.setMinimum(1)
        fixed_threshold.setMaximum(1000)
        model.fixed_blob_threshold.bind_spin_box(fixed_threshold)
        hlayout.addStretch(1)
        hlayout = QHBoxLayout()
        layout.addLayout(hlayout)
        hlayout.addWidget(QLabel("Minimum distance"))
        fixed_minimum_distance = QDoubleSpinBox()
        fixed_minimum_distance.setMinimum(0.0)
        fixed_minimum_distance.setMaximum(100.0)
        hlayout.addWidget(fixed_minimum_distance)
        model.fixed_min_distance.bind_double_spin_box(fixed_minimum_distance)
        hlayout.addStretch(1)
        hlayout = QHBoxLayout()
        layout.addLayout(hlayout)
        self.fixed_detect_blobs_button = QPushButton("Run detect-blobs")
        self.fixed_detect_blobs_button.clicked.connect(
            self.run_fixed_detect_blobs)
        hlayout.addWidget(self.fixed_detect_blobs_button)
        self.fixed_collect_patches_button = QPushButton("Run collect-patches")
        self.fixed_collect_patches_button.clicked.connect(
            self.run_fixed_collect_patches)
        hlayout.addWidget(self.fixed_collect_patches_button)
        self.fixed_train_blobs_button = QPushButton("Run training")
        hlayout.addWidget(self.fixed_train_blobs_button)
        self.fixed_train_blobs_button.clicked.connect(
            self.run_fixed_training)
        #
        # Moving
        #
        group_box = QGroupBox("Moving cell detection")
        top_layout.addWidget(group_box)
        layout = QVBoxLayout()
        group_box.setLayout(layout)
        hlayout = QHBoxLayout()
        layout.addLayout(hlayout)
        hlayout.addWidget(QLabel("Sigma"))
        moving_sigma = QDoubleSpinBox()
        hlayout.addWidget(moving_sigma)
        moving_sigma.setMinimum(0)
        moving_sigma.setMaximum(10)
        model.moving_low_sigma.bind_double_spin_box(moving_sigma)
        hlayout.addStretch(1)
        hlayout = QHBoxLayout()
        layout.addLayout(hlayout)
        hlayout.addWidget(QLabel("Threshold"))
        moving_threshold = QSpinBox()
        hlayout.addWidget(moving_threshold)
        moving_threshold.setMinimum(1)
        moving_threshold.setMaximum(1000)
        model.moving_blob_threshold.bind_spin_box(moving_threshold)
        hlayout.addStretch(1)
        hlayout = QHBoxLayout()
        layout.addLayout(hlayout)
        hlayout.addWidget(QLabel("Minimum distance"))
        moving_minimum_distance = QDoubleSpinBox()
        moving_minimum_distance.setMinimum(0.0)
        moving_minimum_distance.setMaximum(100.0)
        hlayout.addWidget(moving_minimum_distance)
        model.moving_min_distance.bind_double_spin_box(moving_minimum_distance)
        hlayout.addStretch(1)
        hlayout = QHBoxLayout()
        layout.addLayout(hlayout)
        self.moving_detect_blobs_button = QPushButton("Run detect-blobs")
        self.moving_detect_blobs_button.clicked.connect(
            self.run_moving_detect_blobs)
        hlayout.addWidget(self.moving_detect_blobs_button)
        self.moving_collect_patches_button = QPushButton("Run collect-patches")
        self.moving_collect_patches_button.clicked.connect(
            self.run_moving_collect_patches)
        hlayout.addWidget(self.moving_collect_patches_button)
        self.moving_train_blobs_button = QPushButton("Run training")
        hlayout.addWidget(self.moving_train_blobs_button)
        self.moving_train_blobs_button.clicked.connect(
            self.run_moving_training)

        self.run_all_button = QPushButton(
            "Run all blob detection and patch collection")
        top_layout.addWidget(self.run_all_button)
        self.run_all_button.clicked.connect(self.run_all)
        top_layout.addStretch(1)

    def on_activated(self):
        self.update_controls()

    def update_controls(self, *args):
        """
        Update the button text and enabled status
        """
        can_run_all = True
        do_bypass = self.model.bypass_training.get()
        for src_path, blob_path, widget, name, bypass in (
                (self.model.fixed_preprocessed_path.get(),
                 self.model.fixed_blob_path.get(),
                 self.fixed_detect_blobs_button,
                 "fixed blob detection", False),
                (self.model.moving_preprocessed_path.get(),
                 self.model.moving_blob_path.get(),
                 self.moving_detect_blobs_button,
                 "moving blob detection", False),
                (self.model.fixed_blob_path.get(),
                 self.model.fixed_patches_path.get(),
                 self.fixed_collect_patches_button,
                 "fixed patch collection", True),
                (self.model.moving_blob_path.get(),
                 self.model.moving_patches_path.get(),
                 self.moving_collect_patches_button,
                 "moving patch collection", True),
                (self.model.fixed_patches_path.get(),
                 self.model.fixed_model_path.get(),
                 self.fixed_train_blobs_button,
                 "fixed training", True),
                (self.model.moving_patches_path.get(),
                 self.model.moving_model_path.get(),
                 self.moving_train_blobs_button,
                 "moving training", True)
        ):
            run_name = "Run %s" % name
            rerun_name = "Rerun %s" % name
            if not os.path.exists(src_path):
                widget.setDisabled(True)
                widget.setText(run_name)
                can_run_all = False
            else:
                widget.setDisabled(bypass and do_bypass)
                if os.path.exists(blob_path):
                    widget.setText(rerun_name)
                    can_run_all = False
                else:
                    widget.setText(run_name)
        self.run_all_button.setEnabled(can_run_all)

    def run_all(self):
        self.run_fixed_detect_blobs()
        self.run_fixed_collect_patches()
        self.run_moving_detect_blobs()
        self.run_moving_collect_patches()

    def scale_xy(self, input):
        return input / self.model.x_voxel_size.get()

    def scale_z(self, input):
        return input / self.model.z_voxel_size.get()

    def run_fixed_detect_blobs(self, *args):
        source_glob = os.path.join(self.model.fixed_preprocessed_path.get(),
                                   "*.tif*")
        dog_low = self.model.fixed_low_sigma.get()
        dog_high = dog_low * 3
        min_distance = self.model.fixed_min_distance.get()
        with tqdm_progress():
            args = [
                "--source", source_glob,
                "--output", self.model.fixed_blob_path.get(),
                "--dog-low-xy", str(self.scale_xy(dog_low)),
                "--dog-high-xy", str(self.scale_xy(dog_high)),
                "--dog-low-z", str(self.scale_z(dog_low)),
                "--dog-high-z", str(self.scale_z(dog_high)),
                "--threshold", str(self.model.fixed_blob_threshold.get()),
                "--min-distance-xy", str(self.scale_xy(min_distance)),
                "--min-distance-z", str(self.scale_z(min_distance)),
                "--n-cpus", str(self.model.n_workers.get()),
                "--n-io-cpus", str(self.model.n_io_workers.get())
            ]
            detect_blobs_main(args)
        self.update_controls()
        with open(self.model.fixed_blob_path.get()) as fd:
            n_blobs = len(json.load(fd))
        set_status_bar_message("Found %d blobs in fixed volume" % n_blobs)

    def run_moving_detect_blobs(self, *args):
        source_glob = os.path.join(self.model.moving_preprocessed_path.get(),
                                   "*.tif*")
        dog_low = self.model.moving_low_sigma.get()
        dog_high = dog_low * 3
        min_distance = self.model.moving_min_distance.get()
        with tqdm_progress():
            args = [
                "--source", source_glob,
                "--output", self.model.moving_blob_path.get(),
                "--dog-low-xy", str(self.scale_xy(dog_low)),
                "--dog-high-xy", str(self.scale_xy(dog_high)),
                "--dog-low-z", str(self.scale_z(dog_low)),
                "--dog-high-z", str(self.scale_z(dog_high)),
                "--threshold", str(self.model.moving_blob_threshold.get()),
                "--min-distance-xy", str(self.scale_xy(min_distance)),
                "--min-distance-z", str(self.scale_z(min_distance)),
                "--n-cpus", str(self.model.n_workers.get()),
                "--n-io-cpus", str(self.model.n_io_workers.get())
            ]
            detect_blobs_main(args)
        self.update_controls()
        with open(self.model.moving_blob_path.get()) as fd:
            n_blobs = len(json.load(fd))
        set_status_bar_message("Found %d blobs in moving volume" % n_blobs)

    def run_fixed_collect_patches(self, *args):
        source_glob = os.path.join(self.model.fixed_preprocessed_path.get(),
                                   "*.tif*")
        with tqdm_progress():
            args = [
                "--source", source_glob,
                "--points", self.model.fixed_blob_path.get(),
                "--output", self.model.fixed_patches_path.get()
            ]
            collect_patches_main(args)
        self.update_controls()

    def run_moving_collect_patches(self, *args):
        source_glob = os.path.join(self.model.moving_preprocessed_path.get(),
                                   "*.tif*")
        with tqdm_progress():
            args = [
                "--source", source_glob,
                "--points", self.model.moving_blob_path.get(),
                "--output", self.model.moving_patches_path.get()
            ]
            collect_patches_main(args)
        self.update_controls()

    def run_fixed_training(self, *args):
        run_training(
            self,
            self.model,
            "Fixed",
            self.model.fixed_patches_path.get(),
            self.model.fixed_model_path.get(),
            "precomputed://http://127.0.0.1:%d/fixed" %
            self.model.img_server_port_number.get()
        )
        self.on_fixed_training_done()
        self.update_controls()

    def run_moving_training(self, *args):
        run_training(
            self,
            self.model,
            "Moving",
            self.model.moving_patches_path.get(),
            self.model.moving_model_path.get(),
            "precomputed://http://127.0.0.1:%d/moving" %
            self.model.img_server_port_number.get()
        )
        self.on_moving_training_done()
        self.update_controls()

    def on_fixed_training_done(self, *args):
        if not os.path.exists(self.model.fixed_model_path.get()):
            return
        with open(self.model.fixed_model_path.get(), "rb") as fd:
            model = pickle.load(fd)
        pred_probs = model["pred_probs"]
        mask = pred_probs > .5
        x = model["x"][mask]
        y = model["y"][mask]
        z = model["z"][mask]
        coords = [(xx, yy, zz) for xx, yy, zz in zip(x, y, z)]
        with open(self.model.fixed_coords_path.get(), "w") as fd:
            json.dump(coords, fd)

    def on_moving_training_done(self, *args):
        if not os.path.exists(self.model.moving_model_path.get()):
            return
        with open(self.model.moving_model_path.get(), "rb") as fd:
            model = pickle.load(fd)
        pred_probs = model["pred_probs"]
        mask = pred_probs > .5
        x = model["x"][mask]
        y = model["y"][mask]
        z = model["z"][mask]
        coords = [(xx, yy, zz) for xx, yy, zz in zip(x, y, z)]
        with open(self.model.moving_coords_path.get(), "w") as fd:
            json.dump(coords, fd)


def read_array(shm:SharedMemory, hdf_file, dataset, i0, i1):
    with shm.txn() as memory:
        with h5py.File(hdf_file, "r") as fd:
            memory[i0:i1] = fd[dataset][i0:i1]


def read_patches(patches_file, model):
    fields = ("patches_xy", "patches_xz", "patches_yz", "x", "y", "z")
    shms = []
    futures = []
    with h5py.File(patches_file, "r") as fd:
        for field in fields:
            shms.append(SharedMemory(fd[field].shape, fd[field].dtype))
    increment = max(1, shms[0].shape[0] // 100)
    with multiprocessing.Pool(model.n_workers.get()) as pool:
        for field, shm in zip(fields, shms):
            for i0 in range(0, shm.shape[0], increment):
                i1 = min(i0 + increment, shm.shape[0])
                futures.append(pool.apply_async(
                    read_array, (shm, patches_file, field, i0, i1)))
        for future in tqdm.tqdm(futures):
            while True:
                try:
                    future.get(.25)
                    break
                except multiprocessing.TimeoutError:
                    QApplication.processEvents()
    results = []
    for shm in shms:
        with shm.txn() as memory:
            results.append(memory.copy())
    return results


def run_training(parent_widget,
                 model,
                 name,
                 patches_path,
                 model_path,
                 precomputed_url):
    with tqdm_progress() as result:
        with wsgi_server(model):
            viewer = create_neuroglancer_viewer(model)
            print("Neuroglancer URL: %s" % str(viewer))
            with viewer.txn() as txn:
                layer(txn, name, precomputed_url, cubehelix_shader, 40.0)
            webbrowser.open_new(viewer.get_viewer_url())
            set_status_bar_message("Reading patches (patience)")
            patches_xy, patches_xz, patches_yz, x, y, z = read_patches(
                patches_path, model)
            clear_status_bar_message()
            #
            # Put the training into a modal dialog
            #
            dialog = QDialog(parent_widget)
            dialog.setModal(True)
            dlayout = QVBoxLayout()
            dialog.setLayout(dlayout)
            window = TrainWindow(
                [patches_xy],
                [patches_xz],
                [patches_yz],
                x, y, z,
                n_components=64,
                use_position=True,
                whiten=False,
                max_samples=100000,
                n_jobs=model.n_workers.get(),
                input_model=None,
                output_file=model_path,
                viewer=viewer,
                image_names=[name],
                multipliers=[40.0],
                shaders=[cubehelix_shader]
            )
            dlayout.addWidget(window)
            button_box = QDialogButtonBox(
                QDialogButtonBox.Ok
            )
            dlayout.addWidget(button_box)

            def want_to_save(*args):
                buttons = QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel
                result = QMessageBox.question(
                    dialog,
                    "Save training",
                    "Do you want to save your training before exiting?",
                    buttons, QMessageBox.Save)
                if result == QMessageBox.Save:
                    window.fileSave()
                if result != QMessageBox.Cancel:
                    dialog.close()

            button_box.accepted.connect(want_to_save)
            button_box.rejected.connect(want_to_save)
            dialog.setModal(True)
            result = dialog.exec()
            return result
