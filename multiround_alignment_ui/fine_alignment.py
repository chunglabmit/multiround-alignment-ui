import os

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QGroupBox, QHBoxLayout, \
    QPushButton, QLabel, QSpinBox, QDoubleSpinBox, QComboBox
from PyQt5.QtGui import QDesktopServices
from PyQt5.QtCore import QUrl
from phathom.pipeline.geometric_features_cmd import main as geometric_features
from phathom.pipeline.find_neighbors_cmd import main as find_neighbors
from phathom.pipeline.find_corr_neighbors_cmd import main as find_corr_neighbors
from phathom.pipeline.filter_matches_cmd import main as filter_matches
from phathom.pipeline.fit_nonrigid_transform_cmd \
    import main as fit_nonrigid_transform
from .model import Model, Variable, FindNeighborsMethod
import pathlib

from .utils import OnActivateMixin, tqdm_progress, fixed_neuroglancer_url, \
    moving_neuroglancer_url


def voxel_size(model:Model) -> str:
    """
    Create a comma-separated string representation of the voxel_size

    :param model: Get the voxel size from the model's voxel_size variables
    :return: string representation of voxel size
    """
    return ",".join(["%.02f" % _ for _ in (
        model.x_voxel_size.get(),
        model.y_voxel_size.get(),
        model.z_voxel_size.get()
    )])


class FineAlignmentWidget(QWidget, OnActivateMixin):
    def __init__(self, model:Model):
        QWidget.__init__(self)
        self.model = model
        self.variables_have_been_hooked_to_widgets = False
        self.last_round_idx = None
        self.model.output_path.register_callback("fine-alignment",
                                                 self.on_output_path_changed)
        layout = QVBoxLayout()
        self.setLayout(layout)
        ##################################
        #
        # Geometric features buttons
        #
        group_box = QGroupBox("Geometric features")
        gglayout = QVBoxLayout()
        layout.addWidget(group_box)
        group_box.setLayout(gglayout)
        glayout = QHBoxLayout()
        gglayout.addLayout(glayout)
        glayout.addWidget(QLabel("# geometric neighbors"))
        self.n_geometric_neighbors_widget = QSpinBox()
        glayout.addWidget(self.n_geometric_neighbors_widget)
        self.n_geometric_neighbors_widget.setMinimum(3)
        self.n_geometric_neighbors_widget.setMaximum(6)
        self.model.n_geometric_neighbors.bind_spin_box(
            self.n_geometric_neighbors_widget)
        glayout.addStretch(1)

        glayout = QHBoxLayout()
        gglayout.addLayout(glayout)
        self.fixed_geometric_features_button = QPushButton(
            "Calculate fixed geometric features")
        glayout.addWidget(self.fixed_geometric_features_button)
        self.fixed_geometric_features_button.clicked.connect(
            self.on_fixed_geometric_features)
        self.moving_geometric_features_button = QPushButton(
            "Calculate moving geometric features")
        glayout.addWidget(self.moving_geometric_features_button)
        self.moving_geometric_features_button.clicked.connect(
            self.on_moving_geometric_features)
        self.all_geometric_features_button = QPushButton(
            "Calculate all geometric features")
        glayout.addWidget(self.all_geometric_features_button)
        self.all_geometric_features_button.clicked.connect(
            self.on_all_geometric_features)
        #
        ###################################
        #
        # # of refinement rounds
        #
        group_box = QGroupBox("Refinement rounds")
        layout.addWidget(group_box)
        glayout = QVBoxLayout()
        group_box.setLayout(glayout)
        hlayout = QHBoxLayout()
        glayout.addLayout(hlayout)
        hlayout.addWidget(QLabel("Number of rounds:"))
        self.n_refinement_rounds_widget = QSpinBox()
        self.n_refinement_rounds_widget.setMinimum(1)
        self.n_refinement_rounds_widget.setMaximum(10)
        hlayout.addWidget(self.n_refinement_rounds_widget)
        self.model.n_refinement_rounds.bind_spin_box(
            self.n_refinement_rounds_widget)
        self.model.n_refinement_rounds.register_callback(
            "fine-alignment", self.on_refinement_rounds_changed)
        hlayout.addStretch(1)
        hlayout = QHBoxLayout()
        glayout.addLayout(hlayout)
        hlayout.addWidget(QLabel("Current round:"))
        self.current_refinement_round_widget = QSpinBox()
        self.current_refinement_round_widget.setValue(1)
        self.current_refinement_round_widget.setMinimum(1)
        self.current_refinement_round_widget.setMaximum(
            self.model.n_refinement_rounds.get())
        hlayout.addWidget(self.current_refinement_round_widget)
        self.current_refinement_round_widget.valueChanged.connect(
            self.on_current_round_changed)
        hlayout.addStretch(1)
        #
        ###################################
        #
        # Find neighbors
        #
        group_box = QGroupBox("Find neighbors")
        layout.addWidget(group_box)
        glayout = QVBoxLayout()
        group_box.setLayout(glayout)
        # Method
        hlayout = QHBoxLayout()
        glayout.addLayout(hlayout)
        hlayout.addWidget(QLabel("Method:"))
        self.find_neighbors_method_widget = QComboBox()
        self.find_neighbors_method_widget.addItems(
            [FindNeighborsMethod.POINTS.value,
             FindNeighborsMethod.CORRELATION.value]
        )
        hlayout.addWidget(self.find_neighbors_method_widget)

        self.find_neighbors_method_widget.currentIndexChanged.connect(
            self.on_find_neighbors_method_change
        )
        hlayout.addStretch(1)
        self.find_neighbors_points_panel = QWidget()
        glayout.addWidget(self.find_neighbors_points_panel)
        playout = QVBoxLayout()
        self.find_neighbors_points_panel.setLayout(playout)
        # radius
        hlayout = QHBoxLayout()
        playout.addLayout(hlayout)
        hlayout.addWidget(QLabel("Radius:"))
        self.radius_widget = QDoubleSpinBox()
        self.radius_widget.setMinimum(1.0)
        self.radius_widget.setMaximum(1000.0)
        hlayout.addWidget(self.radius_widget)

        def on_radius_change(value):
            self.model.find_neighbors_radius[self.current_round_idx].set(value)
        self.radius_widget.valueChanged.connect(on_radius_change)
        hlayout.addStretch(1)
        # max neighbors
        hlayout = QHBoxLayout()
        playout.addLayout(hlayout)
        hlayout.addWidget(QLabel("Max neighbors:"))
        self.max_neighbors_widget = QSpinBox()
        self.max_neighbors_widget.setMinimum(2)
        self.max_neighbors_widget.setMaximum(10000)
        hlayout.addWidget(self.max_neighbors_widget)
        def on_max_neighbors_change(value):
            self.model.max_neighbors[self.current_round_idx].set(value)
        self.max_neighbors_widget.valueChanged.connect(on_max_neighbors_change)
        hlayout.addStretch(1)

        # feature distance
        hlayout = QHBoxLayout()
        playout.addLayout(hlayout)
        hlayout.addWidget(QLabel("Maximum feature distance:"))
        self.feature_distance_widget = QDoubleSpinBox()
        self.feature_distance_widget.setMinimum(.5)
        self.feature_distance_widget.setMaximum(10.0)
        hlayout.addWidget(self.feature_distance_widget)

        def on_feature_distance_change(value):
            self.model.find_neighbors_feature_distance[self.current_round_idx]\
                .set(value)
        self.feature_distance_widget.valueChanged.connect(
            on_feature_distance_change)
        hlayout.addStretch(1)
        # prominence threshold
        hlayout = QHBoxLayout()
        playout.addLayout(hlayout)
        hlayout.addWidget(QLabel("Prominence threshold:"))
        self.prominence_threshold_widget = QDoubleSpinBox()
        self.prominence_threshold_widget.setMinimum(.01)
        self.prominence_threshold_widget.setMaximum(1.0)
        hlayout.addWidget(self.prominence_threshold_widget)

        def on_prominence_threshold_change(value):
            self.model.find_neighbors_prominence_threshold[
                self.current_round_idx].set(value)
        self.prominence_threshold_widget.valueChanged.connect(
            on_prominence_threshold_change)
        hlayout.addStretch(1)
        self.find_neighbors_correlation_panel = QWidget()
        glayout.addWidget(self.find_neighbors_correlation_panel)
        playout = QVBoxLayout()
        self.find_neighbors_correlation_panel.setLayout(playout)
        # find-corr-neighbors sigma
        hlayout = QHBoxLayout()
        playout.addLayout(hlayout)
        hlayout.addWidget(QLabel("Sigma (um):"))
        self.find_corr_neighbors_sigma_widget = QDoubleSpinBox()
        self.find_corr_neighbors_sigma_widget.setMinimum(0)
        self.find_corr_neighbors_sigma_widget.setMaximum(20)
        hlayout.addWidget(self.find_corr_neighbors_sigma_widget)

        def on_corr_neighbors_sigma_change(value):
            self.model.find_corr_neighbors_sigma[
                self.current_round_idx].set(value)
        self.find_corr_neighbors_sigma_widget.valueChanged.connect(
            on_corr_neighbors_sigma_change
        )
        hlayout.addStretch(1)
        # find-corr-neighbors radius
        hlayout = QHBoxLayout()
        playout.addLayout(hlayout)
        hlayout.addWidget(QLabel("Radius (um):"))
        self.find_corr_neighbors_radius_widget = QDoubleSpinBox()
        self.find_corr_neighbors_radius_widget.setMinimum(1)
        self.find_corr_neighbors_radius_widget.setMaximum(200)
        hlayout.addWidget(self.find_corr_neighbors_radius_widget)

        def on_corr_neighbors_radius_change(value):
            self.model.find_corr_neighbors_radius[
                self.current_round_idx].set(value)
        self.find_corr_neighbors_radius_widget.valueChanged.connect(
            on_corr_neighbors_radius_change
        )
        hlayout.addStretch(1)
        # find-corr-neighbors min correlation
        hlayout = QHBoxLayout()
        playout.addLayout(hlayout)
        hlayout.addWidget(QLabel("Minimum correlation:"))
        self.find_corr_neighbors_min_correlation_widget = QDoubleSpinBox()
        self.find_corr_neighbors_min_correlation_widget.setMinimum(0)
        self.find_corr_neighbors_min_correlation_widget.setMaximum(1)
        hlayout.addWidget(self.find_corr_neighbors_min_correlation_widget)

        def on_corr_neighbors_min_correlation_change(value):
            self.model.find_corr_neighbors_min_correlation[
                self.current_round_idx].set(value)
        self.find_corr_neighbors_min_correlation_widget.valueChanged.connect(
            on_corr_neighbors_min_correlation_change
        )
        hlayout.addStretch(1)

        # find-neighbors button
        self.find_neighbors_button = QPushButton("Run find-neighbors")
        self.find_neighbors_button.clicked.connect(
            self.on_find_neighbors)
        hlayout = QHBoxLayout()
        glayout.addLayout(hlayout)
        hlayout.addWidget(self.find_neighbors_button)
        self.show_find_neighbors_pdf_button = QPushButton("Show results")
        hlayout.addWidget(self.show_find_neighbors_pdf_button)
        self.show_find_neighbors_pdf_button.clicked.connect(
            self.on_show_find_neighbors_results)
        #
        ############################
        #
        # filter matches
        #
        group_box = QGroupBox("Filter matches")
        layout.addWidget(group_box)
        glayout = QVBoxLayout()
        group_box.setLayout(glayout)
        hlayout = QHBoxLayout()
        glayout.addLayout(hlayout)
        hlayout.addWidget(QLabel("Maximum distance (μm):"))
        self.maximum_distance_widget = QDoubleSpinBox()
        self.maximum_distance_widget.setMinimum(10.0)
        self.maximum_distance_widget.setMaximum(1000.0)
        hlayout.addWidget(self.maximum_distance_widget)
        glayout.addLayout(hlayout)

        def on_maximum_distance_changed(value):
            self.model.filter_matches_max_distance[self.current_round_idx]\
                .set(value)

        self.maximum_distance_widget.valueChanged.connect(
            on_maximum_distance_changed)
        hlayout.addStretch(1)

        hlayout = QHBoxLayout()
        glayout.addLayout(hlayout)
        hlayout.addWidget(QLabel("Minimum coherence:"))
        self.minimum_coherence_widget = QDoubleSpinBox()
        self.minimum_coherence_widget.setMinimum(.01)
        self.minimum_coherence_widget.setMaximum(1.0)
        hlayout.addWidget(self.minimum_coherence_widget)

        def on_minimum_coherence_changed(value):
            self.model.filter_matches_min_coherence[self.current_round_idx]\
                .set(value)

        self.minimum_coherence_widget.valueChanged.connect(
            on_minimum_coherence_changed)
        hlayout.addStretch(1)
        hlayout = QHBoxLayout()
        glayout.addLayout(hlayout)
        self.filter_matches_button = QPushButton("Filter matches")
        hlayout.addWidget(self.filter_matches_button)
        self.filter_matches_button.clicked.connect(self.on_filter_matches)
        self.show_filter_matches_pdf_button = QPushButton("Show results")
        hlayout.addWidget(self.show_filter_matches_pdf_button)
        self.show_filter_matches_pdf_button.clicked.connect(
            self.on_show_filter_matches_results)
        #
        ##############################################
        #
        # fit nonrigid transform
        #
        group_box = QGroupBox("Fit nonrigid transform")
        layout.addWidget(group_box)
        glayout = QVBoxLayout()
        group_box.setLayout(glayout)
        self.fit_nonrigid_transform_button = QPushButton()
        hlayout = QHBoxLayout()
        glayout.addLayout(hlayout)
        hlayout.addWidget(self.fit_nonrigid_transform_button)
        self.fit_nonrigid_transform_button.clicked.connect(
            self.on_fit_nonrigid_transform)
        self.show_fit_nonrigid_transform_pdf_button = QPushButton(
            "Show results")
        hlayout.addWidget(self.show_fit_nonrigid_transform_pdf_button)
        self.show_fit_nonrigid_transform_pdf_button.clicked.connect(
            self.on_show_fit_nonrigid_transform_results)

        layout.addStretch(1)
        self.on_current_round_changed()

    def on_activated(self):
        self.update_controls()

    def on_find_neighbors_method_change(self, value):
        self.model.find_neighbors_method[self.current_round_idx].set(
            self.find_neighbors_method_widget.currentText()
        )
        self.enable_find_neighbors_panels()

    def enable_find_neighbors_panels(self):
        enable_points = (
            self.model.find_neighbors_method[self.current_round_idx].get() ==
            FindNeighborsMethod.POINTS.value)
        self.find_neighbors_points_panel.setVisible(enable_points)
        self.find_neighbors_correlation_panel.setVisible(not enable_points)

    def fixed_coords_path(self) -> str:
        if self.model.bypass_training.get():
            return self.model.fixed_blob_path.get()
        else:
            return self.model.fixed_coords_path.get()

    def moving_coords_path(self) -> str:
        if self.model.bypass_training.get():
            return self.model.moving_blob_path.get()
        else:
            return self.model.moving_coords_path.get()

    def update_controls(self):
        self.enable_find_neighbors_panels()
        idx = self.current_round_idx
        transform_path = self.model.rough_interpolator.get() if idx == 0 \
            else self.model.fit_nonrigid_transform_inverse_path[idx-1].get()
        self.find_neighbors_method_widget.setCurrentText(
            self.model.find_neighbors_method[idx].get())
        for src_paths, dest_paths, widget, name, re_name in (
                (
                    [self.fixed_coords_path()],
                    [self.model.fixed_geometric_features_path.get()],
                    self.fixed_geometric_features_button,
                    "Calculate fixed geometric features",
                    "Recalculate fixed geometric features"
                ),
                (
                    [self.moving_coords_path()],
                    [self.model.moving_geometric_features_path.get()],
                    self.moving_geometric_features_button,
                    "Calculate moving geometric features",
                    "Recalculate moving geometric features"
                ),
                (
                    [
                        self.fixed_coords_path(),
                        self.moving_coords_path()
                    ],
                    [
                        self.model.fixed_geometric_features_path.get(),
                        self.model.moving_geometric_features_path.get()
                    ],
                    self.all_geometric_features_button,
                    "Calculate all geometric features",
                    "Recalculate all geometric features"
                ),
                (
                    [
                        self.fixed_coords_path(),
                        self.moving_coords_path(),
                        self.model.fixed_geometric_features_path.get(),
                        self.model.moving_geometric_features_path.get(),
                        transform_path
                    ],
                    [
                        self.model.find_neighbors_path[idx].get(),
                        self.model.find_neighbors_pdf_path[idx].get()
                    ],
                    self.find_neighbors_button,
                    "Find neighbors (round %d)" % (idx + 1),
                    "Rerun find neighbors (round %d)" % (idx + 1)
                ),
                (
                    [
                        self.model.find_neighbors_path[idx].get()
                    ],
                    [
                        self.model.filter_matches_path[idx].get(),
                        self.model.filter_matches_pdf_path[idx].get()
                    ],
                    self.filter_matches_button,
                    "Run filter matches (round %d)" % (idx+1),
                    "Rerun filter matches (round %d)" % (idx+1)
                ),
                (
                    [
                        self.model.filter_matches_path[idx].get()
                    ],
                    [
                        self.model.fit_nonrigid_transform_pdf_path[idx].get(),
                        self.model.fit_nonrigid_transform_inverse_path[idx].get(),
                        self.model.fit_nonrigid_transform_path[idx].get()
                    ],
                    self.fit_nonrigid_transform_button,
                    "Fit nonrigid transform (round %d)" % (idx+1),
                    "Rerun phathom-fit-nonrigid-transform (round %d)" % (idx+1)
                )
        ):
            if not all([os.path.exists(_) for _ in src_paths]):
                widget.setDisabled(True)
                widget.setText(name)
            else:
                widget.setDisabled(False)
                if all([os.path.exists(_) for _ in dest_paths]):
                    widget.setText(re_name)
                else:
                    widget.setText(name)
        for button, path in (
                ( self.show_find_neighbors_pdf_button,
                  self.model.find_neighbors_pdf_path[idx].get()),
                ( self.show_filter_matches_pdf_button,
                  self.model.filter_matches_pdf_path[idx].get()),
                ( self.show_fit_nonrigid_transform_pdf_button,
                  self.model.fit_nonrigid_transform_pdf_path[idx].get())
        ):
            if os.path.exists(path):
                button.setDisabled(False)
            else:
                button.setDisabled(True)

    def on_fixed_geometric_features(self, *args):
        with tqdm_progress() as result:
            geometric_features(
                [
                    "--input", self.fixed_coords_path(),
                    "--output", self.model.fixed_geometric_features_path.get(),
                    "--voxel-size", voxel_size(self.model),
                    "--n-workers", str(self.model.n_workers.get()),
                    "--n-neighbors", str(self.model.n_geometric_neighbors.get())
                ]
            )
        self.update_controls()
        return result.result()

    def on_moving_geometric_features(self, *args):
        with tqdm_progress() as result:
            geometric_features(
                [
                    "--input", self.moving_coords_path(),
                    "--output", self.model.moving_geometric_features_path.get(),
                    "--voxel-size", voxel_size(self.model),
                    "--n-workers", str(self.model.n_workers.get()),
                    "--n-neighbors", str(self.model.n_geometric_neighbors.get())
                ]
            )
        self.update_controls()
        return result.result()

    def on_all_geometric_features(self, *args):
        if self.on_fixed_geometric_features():
            self.on_moving_geometric_features()

    def on_find_neighbors(self, *args):
        idx = self.current_round_idx
        if self.model.find_neighbors_method[idx].get() ==\
                FindNeighborsMethod.POINTS.value:
            self.on_find_neighbors_points()
        else:
            self.on_find_neighbors_correlation()

    def on_find_neighbors_correlation(self):
        idx = self.current_round_idx
        interpolator_variable = \
            self.model.rough_interpolator if idx == 0 \
            else self.model.fit_nonrigid_transform_path[idx-1]
        sigma_x, sigma_y, sigma_z = [
            self.model.find_corr_neighbors_sigma[idx].get() / _.get()
            for _ in (self.model.x_voxel_size, self.model.y_voxel_size,
                      self.model.z_voxel_size)]
        with tqdm_progress():
            find_corr_neighbors([
                str(_) for _ in (
                    "--fixed-coords", self.model.fixed_blob_path.get(),
                    "--fixed-url", fixed_neuroglancer_url(self.model),
                    "--moving-url", moving_neuroglancer_url(self.model),
                    "--transform", interpolator_variable.get(),
                    "--output", self.model.find_neighbors_path[idx].get(),
                    "--visualization-file", self.model.find_neighbors_pdf_path[idx].get(),
                    "--sigma-x", sigma_x,
                    "--sigma-y", sigma_y,
                    "--sigma-z", sigma_z,
                    "--radius", self.model.find_corr_neighbors_radius[idx].get(),
                    "--n-cores", self.model.n_workers.get(),
                    "--min-correlation",
                    self.model.find_corr_neighbors_min_correlation[idx].get()
                )
            ])
        self.update_controls()

    def on_find_neighbors_points(self):
        idx = self.current_round_idx
        interpolator_variable = self.model.rough_inverse_interpolator\
            if idx == 0 \
            else self.model.fit_nonrigid_transform_inverse_path[idx-1]
        with tqdm_progress():
            find_neighbors([str(_) for _ in (
                "--fixed-coords", self.fixed_coords_path(),
                "--moving-coords", self.moving_coords_path(),
                "--fixed-features",
                self.model.fixed_geometric_features_path.get(),
                "--moving-features",
                self.model.moving_geometric_features_path.get(),
                "--non-rigid-transformation",
                interpolator_variable.get(),
                "--output", self.model.find_neighbors_path[idx].get(),
                "--visualization-file",
                self.model.find_neighbors_pdf_path[idx].get(),
                "--voxel-size", voxel_size(self.model),
                "--radius", self.model.find_neighbors_radius[idx].get(),
                "--max-fdist",
                self.model.find_neighbors_feature_distance[idx].get(),
                "--prom-thresh",
                self.model.find_neighbors_prominence_threshold[idx].get(),
                "--max-neighbors",
                self.model.max_neighbors[idx].get(),
                "--n-workers", self.model.n_workers.get())
            ])
        self.update_controls()

    def on_show_find_neighbors_results(self):
        idx = self.current_round_idx
        path = self.model.find_neighbors_pdf_path[idx].get()
        url = pathlib.Path(path).as_uri()
        QDesktopServices.openUrl(QUrl(url))

    def on_filter_matches(self):
        idx = self.current_round_idx
        with tqdm_progress():
            filter_matches([
                "--input", self.model.find_neighbors_path[idx].get(),
                "--output", self.model.filter_matches_path[idx].get(),
                "--max-distance",
                str(self.model.filter_matches_max_distance[idx].get()),
                "--min-coherence",
                str(self.model.filter_matches_min_coherence[idx].get()),
                "--visualization-file",
                self.model.filter_matches_pdf_path[idx].get()
            ])
        self.update_controls()

    def on_show_filter_matches_results(self):
        idx = self.current_round_idx
        path = self.model.filter_matches_pdf_path[idx].get()
        url = pathlib.Path(path).as_uri()
        QDesktopServices.openUrl(QUrl(url))

    def on_fit_nonrigid_transform(self):
        idx = self.current_round_idx
        with tqdm_progress():
            fit_nonrigid_transform([
                "--input", self.model.filter_matches_path[idx].get(),
                "--output", self.model.fit_nonrigid_transform_path[idx].get(),
                "--fixed-url", fixed_neuroglancer_url(self.model),
                "--moving-url", moving_neuroglancer_url(self.model),
                "--inverse",
                self.model.fit_nonrigid_transform_inverse_path[idx].get(),
                "--visualization-file",
                self.model.fit_nonrigid_transform_pdf_path[idx].get()
            ])
        self.update_controls()

    def on_show_fit_nonrigid_transform_results(self):
        idx = self.current_round_idx
        path = self.model.fit_nonrigid_transform_pdf_path[idx].get()
        url = pathlib.Path(path).as_uri()
        QDesktopServices.openUrl(QUrl(url))
        
    def on_refinement_rounds_changed(self, n_rounds):
        #
        # Extend the numeric variables
        #
        for variables in (
            self.model.max_neighbors,
            self.model.find_neighbors_method,
            self.model.find_neighbors_radius,
            self.model.find_neighbors_feature_distance,
            self.model.find_neighbors_prominence_threshold,
            self.model.find_corr_neighbors_sigma,
            self.model.find_corr_neighbors_radius,
            self.model.find_corr_neighbors_min_correlation,
            self.model.filter_matches_min_coherence,
            self.model.filter_matches_max_distance
        ):
            while len(variables) < n_rounds:
                variables.append(Variable(variables[-1].get()))
        #
        # Append "" to the path variables
        #
        some_append = False
        for variables in (
            self.model.find_neighbors_path,
            self.model.find_neighbors_pdf_path,
            self.model.filter_matches_path,
            self.model.filter_matches_pdf_path,
            self.model.fit_nonrigid_transform_path,
            self.model.fit_nonrigid_transform_inverse_path,
            self.model.fit_nonrigid_transform_pdf_path
        ):
            while len(variables) < n_rounds:
                variables.append(Variable(""))
                some_append = True
        if some_append:
            # Need to set the paths for the appended - this is the
            # easiest way.
            self.on_output_path_changed()
        if self.current_refinement_round_widget.value() >= n_rounds:
            self.current_refinement_round_widget.setValue(n_rounds)
        self.current_refinement_round_widget.setMaximum(n_rounds)

    @property
    def current_round_idx(self):
        return self.current_refinement_round_widget.value() - 1

    def on_current_round_changed(self, *args):
        variables_and_widgets = (
            (self.model.max_neighbors,
             self.max_neighbors_widget),
            (self.model.find_neighbors_radius,
             self.radius_widget),
            (self.model.find_neighbors_feature_distance,
             self.feature_distance_widget),
            (self.model.find_neighbors_prominence_threshold,
             self.prominence_threshold_widget),
            (self.model.find_corr_neighbors_sigma,
             self.find_corr_neighbors_sigma_widget),
            (self.model.find_corr_neighbors_radius,
             self.find_corr_neighbors_radius_widget),
            (self.model.find_corr_neighbors_min_correlation,
             self.find_corr_neighbors_min_correlation_widget),
            (self.model.filter_matches_max_distance,
             self.maximum_distance_widget),
            (self.model.filter_matches_min_coherence,
             self.minimum_coherence_widget)
        )
        if self.variables_have_been_hooked_to_widgets:
            for variables, widget in variables_and_widgets:
                variable = variables[self.last_round_idx]
                variable.unregister_callback("fine-alignment")
        for variables, widget in variables_and_widgets:
            variable = variables[self.current_round_idx]
            widget.setValue(variable.get())
            on_change = lambda value, widget=widget: widget.setValue(value)
            variable.register_callback("fine-alignment", on_change)
        on_change = lambda value: \
            self.find_neighbors_method_widget.setCurrentText(value)
        self.model.find_neighbors_method[self.current_round_idx]\
            .register_callback("fine-alignment", on_change)
        self.last_round_idx = self.current_round_idx
        self.variables_have_been_hooked_to_widgets = True
        self.update_controls()

    def on_output_path_changed(self, *args):
        self.model.fixed_geometric_features_path.set(
            os.path.join(self.model.output_path.get(),
                         "fixed-geometric-features.npy"))
        self.model.moving_geometric_features_path.set(
            os.path.join(self.model.output_path.get(),
                         "moving-geometric-features.npy"))
        for idx in range(self.model.n_refinement_rounds.get()):
            self.model.find_neighbors_path[idx].set(os.path.join(
                self.model.output_path.get(),
                "find-neighbors_round_%d.json" % (idx+1)))
            self.model.find_neighbors_pdf_path[idx].set(os.path.join(
                self.model.output_path.get(),
                "find-neighbors_round_%d.pdf" % (idx+1)
            ))
            self.model.filter_matches_path[idx].set(os.path.join(
                self.model.output_path.get(),
                "filter-matches_round_%d.json" % (idx+1)
            ))
            self.model.filter_matches_pdf_path[idx].set(os.path.join(
                self.model.output_path.get(),
                "filter-matches_round_%d.pdf" % (idx+1)
            ))
            self.model.fit_nonrigid_transform_path[idx].set(
                os.path.join(
                    self.model.output_path.get(),
                    "fit-nonrigid-transform_round_%d.pkl" % (idx+1)))
            self.model.fit_nonrigid_transform_inverse_path[idx].set(
                os.path.join(
                    self.model.output_path.get(),
                    "fit-nonrigid-transform-inverse_round_%d.pkl" % (idx+1)))
            self.model.fit_nonrigid_transform_pdf_path[idx].set(
                os.path.join(
                    self.model.output_path.get(),
                    "fit-nonrigid-transform_round_%d.pdf" % (idx+1)))



