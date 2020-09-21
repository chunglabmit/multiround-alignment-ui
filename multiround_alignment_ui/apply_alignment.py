import os
import pathlib
from functools import partial
from phathom.pipeline.warp_image import main as warp_image
from phathom.pipeline.warp_points_cmd import main as warp_points
from blockfs.blockfs2tif import main as blockfs2tif
import typing
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QGroupBox, QHBoxLayout, QLabel, QSpinBox, QPushButton, QLineEdit, \
    QFileDialog, QWidgetItem

from multiround_alignment_ui.model import Model, Variable
from multiround_alignment_ui.utils import tqdm_progress, set_status_bar_message


class ApplyAlignmentWidget(QWidget):
    def __init__(self, model:Model):
        super(ApplyAlignmentWidget, self).__init__()
        self.model = model

        self.model.moving_precomputed_path.register_callback(
            "apply-alignment", self.on_moving_precomputed_path_changed)
        self.hookup_input_paths()

        layout = QVBoxLayout()
        self.setLayout(layout)

        group_box = QGroupBox("Apply alignment to image volume")
        layout.addWidget(group_box)
        glayout = QVBoxLayout()
        group_box.setLayout(glayout)
        hlayout = QHBoxLayout()
        glayout.addLayout(hlayout)
        hlayout.addWidget(QLabel("# of channels:"))
        self.n_channels_widget = QSpinBox()
        hlayout.addWidget(self.n_channels_widget)
        self.n_channels_widget.setMinimum(1)
        self.n_channels_widget.setMaximum(10)
        self.model.n_alignment_channels.bind_spin_box(self.n_channels_widget)
        self.model.n_alignment_channels.register_callback(
            "apply-alignment", self.on_n_channels_changed)
        hlayout.addStretch(1)
        hlayout=QHBoxLayout()
        glayout.addLayout(hlayout)
        hlayout.addWidget(QLabel("# of decimation levels / channel:"))
        self.n_levels_widget = QSpinBox()
        hlayout.addWidget(self.n_levels_widget)
        self.n_levels_widget.setMinimum(1)
        self.n_levels_widget.setMaximum(12)
        self.model.n_levels.bind_spin_box(self.n_levels_widget)
        hlayout.addStretch(1)
        self.inputs_groupbox = QGroupBox("Inputs")
        glayout.addWidget(self.inputs_groupbox)
        self.inputs_layout = QVBoxLayout()
        self.inputs_groupbox.setLayout(self.inputs_layout)
        self.input_hlayouts = []
        self.input_widgets = []
        self.layout_inputs()
        self.outputs_groupbox = QGroupBox("Outputs")
        glayout.addWidget(self.outputs_groupbox)
        self.outputs_layout = QVBoxLayout()
        self.outputs_groupbox.setLayout(self.outputs_layout)
        self.output_hlayouts = []
        self.output_widgets = []
        self.layout_outputs()
        self.tiff_groupbox = QGroupBox("Precomputed⇨TIFF")
        glayout.addWidget(self.tiff_groupbox)
        self.tiff_layout = QVBoxLayout()
        self.tiff_groupbox.setLayout(self.tiff_layout)
        self.tiff_hlayouts = []
        self.tiff_widgets = []
        self.layout_tiffs()
        hlayout=QHBoxLayout()
        glayout.addLayout(hlayout)
        self.run_image_alignment_button=QPushButton("Run image warping")
        hlayout.addWidget(self.run_image_alignment_button)
        self.run_image_alignment_button.clicked.connect(
            self.on_run_image_alignment)
        self.make_tiff_files_button=QPushButton("Make TIFF files")
        hlayout.addWidget(self.make_tiff_files_button)
        self.make_tiff_files_button.clicked.connect(
            self.on_make_tiff_files)
        glayout.addStretch(1)
        #
        # The coordinates files box.
        #
        group_box = QGroupBox("Coordinate warping")
        layout.addWidget(group_box)
        glayout = QVBoxLayout()
        group_box.setLayout(glayout)
        hlayout = QHBoxLayout()
        glayout.addLayout(hlayout)
        hlayout.addWidget(QLabel("Input coordinates file:"))
        self.input_coords_widget = QLineEdit()
        hlayout.addWidget(self.input_coords_widget)
        self.model.alignment_input_coords.bind_line_edit(
            self.input_coords_widget)
        button = QPushButton("...")
        hlayout.addWidget(button)
        button.clicked.connect(self.on_input_coords_dlg_button)
        hlayout = QHBoxLayout()
        glayout.addLayout(hlayout)
        hlayout.addWidget(QLabel("Output coordinates file:"))
        self.output_coords_widget = QLineEdit()
        hlayout.addWidget(self.output_coords_widget)
        self.model.alignment_output_coords.bind_line_edit(
            self.output_coords_widget)
        button = QPushButton("...")
        hlayout.addWidget(button)
        button.clicked.connect(self.on_output_coords_dlg_button)
        self.warp_coords_button = QPushButton("Warp coordinates")
        glayout.addWidget(self.warp_coords_button)
        self.warp_coords_button.clicked.connect(
            self.on_run_coordinates_alignment)
        glayout.addStretch(1)

        layout.addStretch(1)

    def on_moving_precomputed_path_changed(self, value):
        self.model.alignment_input_paths[0].set(value)

    def hookup_input_paths(self):
        for idx, input_variable in enumerate(self.model.alignment_input_paths):
            input_variable.register_callback(
                "alignment-output-path",
                    partial(self.on_input_path_changed, idx=idx))

    def on_input_path_changed(self, value, idx):
        self.model.alignment_output_paths[idx].set(value+"_warped")
        self.model.alignment_tiff_directories[idx].set(value+"_tiff")

    def on_n_channels_changed(self, *args):
        for variables in (self.model.alignment_input_paths,
                         self.model.alignment_output_paths,
                         self.model.alignment_tiff_directories):
            while len(variables) < self.model.n_alignment_channels.get():
                variables.append(Variable(""))
        self.hookup_input_paths()
        self.layout_inputs()
        self.layout_outputs()
        self.layout_tiffs()

    def on_run_image_alignment(self, *args):
        interpolator = self.model.fit_nonrigid_transform_path[
        self.model.n_refinement_rounds.get() - 1].get()
        xs = self.model.x_voxel_size.get()
        ys = self.model.y_voxel_size.get()
        zs = self.model.z_voxel_size.get()
        args = ["--interpolator", interpolator,
                "--n-workers", self.model.n_workers.get(),
                "--n-writers", self.model.n_io_workers.get(),
                "--n-levels", self.model.n_levels.get(),
                "--voxel-size", "%.3f,%.3f,%.3f"  % (xs, ys, zs)]
        if self.model.use_gpu.get():
            args.append("--use-gpu")
        for idx in range(self.model.n_alignment_channels.get()):
            src_path = self.model.alignment_input_paths[idx].get()
            dest_path = self.model.alignment_output_paths[idx].get()
            if any([len(_) == 0 for _ in (src_path, dest_path)]):
                continue
            src_url = pathlib.Path(src_path).as_uri()
            args += ["--url", src_url]
            args += ["--output", dest_path]
        with tqdm_progress():
            warp_image([str(_) for _ in args])

    def on_make_tiff_files(self, *args):
        with tqdm_progress():
            for idx in range(self.model.n_alignment_channels.get()):
                tiff_dir = self.model.alignment_tiff_directories[idx].get()
                if len(tiff_dir) == 0:
                    continue
                output_pattern = os.path.join(tiff_dir, "img_%05d.tiff")
                precomputed_dir = self.model.alignment_output_paths[idx].get()
                if not os.path.exists(precomputed_dir):
                    set_status_bar_message(
                        "Skipping %s" % os.path.split(precomputed_dir)[-1])
                    continue
                precomputed_path = os.path.join(precomputed_dir,
                                                "1_1_1",
                                                "precomputed.blockfs")
                blockfs2tif([
                    "--input", precomputed_path,
                    "--output-pattern", output_pattern,
                    "--n-workers", str(self.model.n_io_workers.get())])

    def on_run_coordinates_alignment(self, *args):
        interpolator = self.model.fit_nonrigid_transform_inverse_path[
            self.model.n_refinement_rounds.get() - 1].get()
        with tqdm_progress():
            input_coords = self.model.alignment_input_coords.get()
            output_coords = self.model.alignment_output_coords.get()
            warp_points([
                "--interpolator", interpolator,
                "--input", input_coords,
                "--output", output_coords,
                "--n-workers", str(self.model.n_workers.get())
            ])

    def layout_inputs(self):
        hlayouts = self.input_hlayouts
        path_variables = self.model.alignment_input_paths
        widgets = self.input_widgets
        vlayout = self.inputs_layout
        self.layout_group(
            "Precomputed volume", vlayout, hlayouts, path_variables, widgets,
            self.on_input_dlg_button)

    def layout_outputs(self):
        self.layout_group(
            "Warped volume",
            self.outputs_layout, self.output_hlayouts,
            self.model.alignment_output_paths, self.output_widgets,
            self.on_output_dlg_button)

    def layout_tiffs(self):
        self.layout_group(
            "Tiff directory",
            self.tiff_layout, self.tiff_hlayouts,
            self.model.alignment_tiff_directories, self.tiff_widgets,
            self.on_tiff_dlg_button)

    def layout_group(self,
                     name:str,
                     vlayout:QVBoxLayout,
                     hlayouts:typing.List[QHBoxLayout],
                     path_variables:typing.List[Variable],
                     widgets:typing.List[QLineEdit],
                     button_fn:typing.Callable[[Variable, str], type(None)]):
        """
        Layout the controls in one of the groups: input precomputed,
        output precomputed or tiffs

        :param name: A display name for the label to the left of the line edit
        :param vlayout: The top-level QT layout
        :param hlayouts: A list of the subsidiary horizontal layouts per channel
        :param path_variables: path variables per channel
        :param widgets: the QLineEdit widgets per channel
        :param button_fn: The function to run when someone presses the widget's
                          path-finding button.
        """
        n_channels = self.model.n_alignment_channels.get()
        while len(hlayouts) > n_channels:
            idx = len(hlayouts) - 1
            path_variables[idx].unregister_callback(
                "apply-alignment")
            hlayout = hlayouts[idx]
            while hlayout.count() > 0:
                item = hlayout.itemAt(0)
                hlayout.removeItem(item)
                if isinstance(item, QWidgetItem):
                    item.widget().close()
            del widgets[idx]
            vlayout.removeItem(hlayouts[idx])
            del hlayouts[idx]
        while n_channels > len(hlayouts):
            idx = len(hlayouts)
            hlayout = QHBoxLayout()
            hlayouts.append(hlayout)
            vlayout.addLayout(hlayout)
            hlayout.addWidget(
                QLabel("%s #%d: " % (name.capitalize(), idx + 1)))
            widget = QLineEdit()
            hlayout.addWidget(widget)
            widgets.append(widget)
            variable = path_variables[idx]
            variable.bind_line_edit(widget, "apply-alignment")
            button = QPushButton("...")
            hlayout.addWidget(button)
            button.clicked.connect(partial(button_fn, variable=variable))

    def on_input_dlg_button(self, variable, *args):
        new_value = QFileDialog.getExistingDirectory(
            self, "Choose precomputed volume", variable.get())
        if new_value:
            variable.set(new_value)

    def on_output_dlg_button(self, variable, *args):
        new_value = QFileDialog.getExistingDirectory(
            self, "Choose destination", variable.get())
        if new_value:
            variable.set(new_value)

    def on_tiff_dlg_button(self, variable, *args):
        new_value = QFileDialog.getExistingDirectory(
            self, "Choose TIFF file directory", variable.get())
        if new_value:
            variable.set(new_value)

    def on_input_coords_dlg_button(self, *args):
        old_value = self.model.alignment_input_coords.get()
        if len(old_value) == 0:
            old_value = self.model.output_path.get()
        new_value, kind = QFileDialog.getOpenFileName(
            self, "Choose input coordinates file",
            old_value, "Coordinates file (*.json)")
        if new_value:
            self.model.alignment_input_coords.set(new_value)

    def on_output_coords_dlg_button(self, *args):
        old_value = self.model.alignment_output_coords.get()
        if len(old_value) == 0:
            old_value = self.model.output_path.get()
        new_value, kind = QFileDialog.getSaveFileName(
            self, "Choose output coordinates file",
            old_value, "Coordinates file (*.json)")
        if new_value:
            self.model.alignment_output_coords.set(new_value)
