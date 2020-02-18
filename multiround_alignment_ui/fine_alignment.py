import os

from PyQt5.QtWidgets import QWidget, QVBoxLayout, QGroupBox, QHBoxLayout, \
    QPushButton, QLabel, QSpinBox, QDoubleSpinBox

from phathom.pipeline.geometric_features_cmd import main as geometric_features
from phathom.pipeline.find_neighbors_cmd import main as find_neighbors
from phathom.pipeline.filter_matches_cmd import main as filter_matches
from phathom.pipeline.fit_nonrigid_transform_cmd \
    import main as fit_nonrigid_transform
from .model import Model, Variable

from .utils import OnActivateMixin, tqdm_progress


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
        glayout = QHBoxLayout()
        layout.addWidget(group_box)
        group_box.setLayout(glayout)
        self.fixed_geometric_features_button = QPushButton(
            "Calculate fixed geometric features")
        glayout.addWidget(self.fixed_geometric_features_button)
        self.fixed_geometric_features_button.clicked.connect(
            self.on_fixed_geometric_features)
        self.moving_geometric_features_button = QPushButton(
            "Calculate moving geometric features")
        glayout.addWidget(self.moving_geometric_features_button)
        self.fixed_geometric_features_button.clicked.connect(
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
        # radius
        hlayout = QHBoxLayout()
        glayout.addLayout(hlayout)
        hlayout.addWidget(QLabel("Radius:"))
        self.radius_widget = QDoubleSpinBox()
        self.radius_widget.setMinimum(1.0)
        self.radius_widget.setMaximum(1000.0)
        hlayout.addWidget(self.radius_widget)

        def on_radius_change(value):
            self.model.find_neighbors_radius[self.current_round_idx].set(value)
        self.radius_widget.valueChanged.connect(on_radius_change)
        hlayout.addStretch(1)
        # feature distance
        hlayout = QHBoxLayout()
        glayout.addLayout(hlayout)
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
        glayout.addLayout(hlayout)
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

        self.find_neighbors_button = QPushButton("Run find-neighbors")
        self.find_neighbors_button.clicked.connect(
            self.on_find_neighbors)
        glayout.addWidget(self.find_neighbors_button)
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
        hlayout.addWidget(QLabel("Maximum distance (μm):"))
        self.maximum_distance_widget = QDoubleSpinBox()
        self.maximum_distance_widget.setMinimum(10.0)
        self.maximum_distance_widget.setMaximum(1000.0)
        hlayout.addWidget(self.maximum_distance_widget)

        def on_maximum_distance_changed(value):
            self.model.filter_matches_max_distance[self.current_round_idx]\
                .set(value)

        self.maximum_distance_widget.valueChanged.connect(
            on_maximum_distance_changed)
        hlayout.addStretch(1)

        hlayout = QHBoxLayout()
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
        self.filter_matches_button = QPushButton("Filter matches")
        glayout.addWidget(self.filter_matches_button)
        self.filter_matches_button.clicked.connect(self.on_filter_matches)
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
        glayout.addWidget(self.fit_nonrigid_transform_button)
        self.fit_nonrigid_transform_button.clicked.connect(
            self.on_fit_nonrigid_transform)

        layout.addStretch(1)
        self.on_current_round_changed()

    def on_activated(self):
        self.update_controls()

    def update_controls(self):
        idx = self.current_round_idx
        transform_path = self.model.rough_interpolator.get() if idx == 0 \
            else self.model.fit_nonrigid_transform_inverse_path[idx-1]
        for src_paths, dest_paths, widget, name, re_name in (
                (
                    [self.model.fixed_coords_path.get()],
                    [self.model.fixed_geometric_features_path.get()],
                    self.fixed_geometric_features_button,
                    "Calculate fixed geometric features",
                    "Recalculate fixed geometric features"
                ),
                (
                    [self.model.moving_coords_path.get()],
                    [self.model.moving_geometric_features_path.get()],
                    self.moving_geometric_features_button,
                    "Calculate moving geometric features",
                    "Recalculate moving geometric features"
                ),
                (
                    [
                        self.model.fixed_coords_path.get(),
                        self.model.moving_coords_path.get()
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
                        self.model.fixed_coords_path.get(),
                        self.model.moving_coords_path.get(),
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
                    "Filter matches (round %d)" % (idx+1),
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
                if any([os.path.exists(_) for _ in dest_paths]):
                    widget.setText(re_name)
                else:
                    widget.setText(name)

    def on_fixed_geometric_features(self, *args):
        with tqdm_progress() as result:
            geometric_features(
                [
                    "--input", self.model.fixed_coords_path.get(),
                    "--output", self.model.fixed_geometric_features_path.get(),
                    "--voxel-size", voxel_size(self.model),
                    "--n-workers", str(self.model.n_workers.get())
                ]
            )
        self.update_controls()
        return result.result()

    def on_moving_geometric_features(self, *args):
        with tqdm_progress() as result:
            geometric_features(
                [
                    "--input", self.model.moving_coords_path.get(),
                    "--output", self.model.moving_geometric_features_path.get(),
                    "--voxel-size", voxel_size(self.model),
                    "--n-workers", str(self.model.n_workers.get())
                ]
            )
        self.update_controls()
        return result.result()

    def on_all_geometric_features(self, *args):
        if self.on_fixed_geometric_features():
            self.on_moving_geometric_features()

    def on_find_neighbors(self, *args):
        idx = self.current_round_idx
        interpolator_variable = self.rough_interpolator if idx == 0 \
            else self.model.fit_nonrigid_transform_inverse_path
        with tqdm_progress():
            find_neighbors([str(_) for _ in (
                "--fixed-coords", self.model.fixed_coords_path.get(),
                "--moving-coords", self.model.moving_coords_path.get(),
                "--fixed-features",
                self.model.fixed_geometric_features_path.get(),
                "--moving-features",
                self.model.moving_geometric_features_path.get(),
                "--non-rigid-transformation",
                self.model.interpolator_variable.get(),
                "--output", self.model.find_neighbors_path[idx].get(),
                "--visualization-file",
                self.model.find_neighbors_pdf_path.get(),
                "--voxel-size", voxel_size(self.model),
                "--radius", self.model.find_neighbors_radius[idx].get(),
                "--max-fdist",
                self.model.find_neighbors_feature_distance[idx].get(),
                "--prom-thresh",
                self.model.find_neighbors_prominence_threshold[idx].get(),
                "--n-workers", self.model.n_workers.get())
            ])
        self.update_controls()

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

    def on_fit_nonrigid_transform(self):
        idx = self.current_round_idx
        with tqdm_progress():
            fit_nonrigid_transform([
                "--input", self.model.filter_matches_path[idx].get(),
                "--output", self.model.fit_nonrigid_transform_path.get(),
                "--inverse",
                self.model.fit_nonrigid_transform_inverse_path.get(),
                "--visualization-file", self.model.filter_matches_pdf_path.get()
            ])

    def on_refinement_rounds_changed(self, n_rounds):
        #
        # Extend the numeric variables
        #
        for variables in (
            self.model.find_neighbors_radius,
            self.model.find_neighbors_feature_distance,
            self.model.find_neighbors_prominence_threshold,
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

    @property
    def current_round_idx(self):
        return self.current_refinement_round_widget.value() - 1

    def on_current_round_changed(self, *args):
        variables_and_widgets = (
            (self.model.find_neighbors_radius,
             self.radius_widget),
            (self.model.find_neighbors_feature_distance,
             self.feature_distance_widget),
            (self.model.find_neighbors_prominence_threshold,
             self.prominence_threshold_widget),
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
        self.last_round_idx = self.current_round_idx
        self.variables_have_been_hooked_to_widgets = True

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

