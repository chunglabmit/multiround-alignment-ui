import traceback

import json
import neuroglancer

import os
from PyQt5.QtCore import Qt, QUrl
from PyQt5.QtGui import QDesktopServices, QGuiApplication, QCursor

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QGroupBox, QHBoxLayout, \
    QPushButton, QLabel, QSpinBox, QMessageBox

from nuggt.align import ViewerPair
from phathom.pipeline.pickle_alignment_cmd import main as pickle_alignment
from precomputed_tif.client import ArrayReader

from .model import Model
from .utils import OnActivateMixin, fixed_neuroglancer_url, \
    moving_neuroglancer_url, set_status_bar_message, clear_status_bar_message


class NeuroglancerAlignmentWidget(QWidget, OnActivateMixin):
    def __init__(self, model:Model):
        QWidget.__init__(self)
        self.model = model
        layout = QVBoxLayout()
        self.setLayout(layout)
        self.model.output_path.register_callback("neuroglancer-alignment",
                                                 self.on_output_path_changed)
        #
        # Decimation level
        #
        hlayout = QHBoxLayout()
        layout.addLayout(hlayout)
        hlayout.addWidget(QLabel("Decimation level"))
        self.decimation_widget = QSpinBox()
        hlayout.addWidget(self.decimation_widget)
        self.decimation_widget.setMinimum(1)
        self.decimation_widget.setMaximum(6)
        self.model.nuggt_decimation_level.bind_spin_box(self.decimation_widget)
        hlayout.addStretch(1)
        #
        # Nuggt-align launch button
        #
        hlayout = QHBoxLayout()
        layout.addLayout(hlayout)
        self.launch_button = QPushButton("Launch Neuroglancer Alignment")
        self.launch_button.clicked.connect(self.on_launch)
        hlayout.addWidget(self.launch_button)
        hlayout.addStretch(1)
        #
        # Reference URL
        #
        hlayout = QHBoxLayout()
        layout.addLayout(hlayout)
        self.reference_url_widget = QLabel()
        hlayout.addWidget(self.reference_url_widget)
        self.reference_url_widget.linkActivated.connect(
            self.on_reference_url_clicked)
        def on_reference_url_changed(*args):
            url = self.model.nuggt_reference_url.get()
            text = '<a href="%s">Reference url (%s)</a>' % (url, url)
            self.reference_url_widget.setText(text)
        self.model.nuggt_reference_url.register_callback(
            "reference-url-link", on_reference_url_changed)
        hlayout.addStretch(1)
        #
        # Moving URL
        #
        hlayout = QHBoxLayout()
        layout.addLayout(hlayout)
        self.moving_url_widget = QLabel()
        hlayout.addWidget(self.moving_url_widget)
        self.moving_url_widget.linkActivated.connect(
            self.on_moving_url_clicked)
        def on_moving_url_changed(*args):
            url = self.model.nuggt_moving_url.get()
            text = '<a href="%s">Moving url (%s)</a>' % (url, url)
            self.moving_url_widget.setText(text)
        self.model.nuggt_moving_url.register_callback(
            "moving-url-link", on_moving_url_changed)
        hlayout.addStretch(1)
        #
        # Make rough alignment
        #
        hlayout = QHBoxLayout()
        layout.addLayout(hlayout)
        self.make_rough_alignment_button_widget = QPushButton(
            "Make rough alignment")
        self.make_rough_alignment_button_widget.clicked.connect(
            self.on_make_rough_alignment
        )
        hlayout.addWidget(self.make_rough_alignment_button_widget)
        hlayout.addStretch(1)
        layout.addStretch(1)

    def on_activated(self):
        self.update_controls()

    def update_controls(self):
        if os.path.exists(self.model.nuggt_rescaled_points_path.get()):
            self.make_rough_alignment_button_widget.setEnabled(True)
        else:
            self.make_rough_alignment_button_widget.setEnabled(False)

    def on_output_path_changed(self, *args):
        if not self.model.nuggt_points_path.get():
            self.model.nuggt_points_path.set(
                os.path.join(self.model.output_path.get(),
                             "nuggt-alignment.json")
            )
        if not self.model.nuggt_rescaled_points_path.get():
            self.model.nuggt_rescaled_points_path.set(
                os.path.join(self.model.output_path.get(),
                             "nuggt-rescaled-alignment.json")
            )

    def on_launch(self, *args):
        neuroglancer.set_server_bind_address(
            bind_address=self.model.bind_address.get())
        neuroglancer.set_static_content_source(
            url=self.model.static_content_source.get())
        QGuiApplication.setOverrideCursor(QCursor(Qt.WaitCursor))
        try:
            level = 2 ** (self.model.nuggt_decimation_level.get() - 1)
            fixed_ar = ArrayReader(fixed_neuroglancer_url(self.model),
                                   format="blockfs",
                                   level=level)
            set_status_bar_message("Loading fixed volume...")
            fixed_volume = fixed_ar[:, :, :]
            moving_ar = ArrayReader(moving_neuroglancer_url(self.model),
                                    format="blockfs",
                                    level=level)
            set_status_bar_message("Loading moving volume...")
            moving_volume = moving_ar[:, :, :]
            voxel_size = (self.model.x_voxel_size.get() * 1000 * level,
                          self.model.y_voxel_size.get() * 1000 * level,
                          self.model.z_voxel_size.get() * 1000 * level)
            set_status_bar_message("Starting Neuroglancer")
            self.viewer_pair = ViewerPair(
                fixed_volume, moving_volume,
                None,
                self.model.nuggt_points_path.get(),
                voxel_size, voxel_size)
            real_save = self.viewer_pair.save_points
            #
            # Do some housekeeping associated with saving files
            # * make the rescaled points file
            # * enable the rough alignment button
            #
            def on_save(*args):
                real_save()
                with open(self.model.nuggt_points_path.get()) as fd:
                    coords = json.load(fd)
                coords["reference"], coords["moving"] = [
                    [[_ * level for _ in __] for __ in coords[k] ]
                    for k in ("reference", "moving")]
                with open(self.model.nuggt_rescaled_points_path.get(), "w") as fd:
                    json.dump(coords, fd)
                self.update_controls()
            self.viewer_pair.save_points = on_save
            reference_url = self.viewer_pair.reference_viewer.get_viewer_url()
            moving_url = self.viewer_pair.moving_viewer.get_viewer_url()
            self.model.nuggt_reference_url.set(reference_url)
            self.model.nuggt_moving_url.set(moving_url)
        except:
            why = traceback.format_exc()
            QMessageBox.critical(None, "Error during execution", why)
        finally:
            clear_status_bar_message()
            QGuiApplication.restoreOverrideCursor()

    def on_reference_url_clicked(self, *args):
        url = QUrl(self.model.nuggt_reference_url.get())
        QDesktopServices.openUrl(url)

    def on_moving_url_clicked(self, *args):
        url = QUrl(self.modelnuggt_moving_url.get())
        QDesktopServices.openUrl(url)

    def on_make_rough_alignment(self, *args):
        fixed_ar = ArrayReader(fixed_neuroglancer_url(self.model),
                               format="blockfs")
        zs, ys, xs = fixed_ar.shape
        input = self.model.nuggt_rescaled_points_path.get()
        pickle_alignment([
            "--input",
            input,
            "--output",
            self.model.rough_interpolator.get(),
            "--invert",
            "--image-size",
            "%d,%d,%d" % (xs, ys, zs)
        ])
        set_status_bar_message("Interpolator written to %s" % input)