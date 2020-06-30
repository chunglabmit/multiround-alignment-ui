#
# The model is a blackboard holding the parameters for running the multiround
# alignment.
#
import json
import os
import tempfile

import typing
from PyQt5.QtWidgets import QLineEdit, QSpinBox, QDoubleSpinBox, QLabel, QCheckBox
import uuid


class Variable:
    """
    A variable in the model, supplying standardized getters and setters
    and a callback mechanism on variable change.

    """
    def __init__(self, value=None):
        self.__value = value
        self.__callbacks = {}

    def get(self):
        return self.__value

    def set(self, new_value):
        if self.__value == new_value:
            return
        self.__value = new_value
        for callback in self.__callbacks.values():
            callback(self.__value)

    def register_callback(self, name, function):
        self.__callbacks[name] = function

    def unregister_callback(self, name):
        del self.__callbacks[name]

    def bind_line_edit(self, widget:QLineEdit, name=None):
        if name is None:
            name = uuid.uuid4()
        def on_change(*args):
            self.set(widget.text())

        def on_callback(*args):
            widget.setText(self.get())
        on_callback()
        widget.editingFinished.connect(on_change)
        self.register_callback(name, on_callback)

    def bind_spin_box(self, widget:QSpinBox, name=None):
        if name is None:
            name  = uuid.uuid4()
        def on_change(*args):
            self.set(widget.value())

        def on_callback(*args):
            value = self.get()
            # Probably temporary until widget is set up properly
            if value < widget.minimum():
                widget.setMinimum(value)
            if value > widget.maximum():
                widget.setMaximum(value)
            widget.setValue(value)
        on_callback()
        widget.editingFinished.connect(on_change)
        self.register_callback(name, on_callback)

    def bind_double_spin_box(self, widget: QDoubleSpinBox, name=None):
        def on_change(*args):
            self.set(widget.value())

        def on_callback(*args):
            value = self.get()
            if value < widget.minimum():
                widget.setMinimum(value)
            if value > widget.maximum():
                widget.setMaximum(value)
            widget.setValue(value)
        on_callback()
        widget.editingFinished.connect(on_change)
        if name is None:
            name = uuid.uuid4()
        self.register_callback(name, on_callback)

    def bind_label(self, widget: QLabel):
        def on_change(*args):
            widget.setText(str(self.get()))
        on_change()
        self.register_callback(uuid.uuid4(), on_change)

    def bind_checkbox(self, widget: QCheckBox):
        def on_callback(*args):
            widget.setChecked(self.get())
        def on_change(*args):
            self.set(widget.isChecked())
        on_callback()
        self.register_callback(uuid.uuid4(), on_callback)
        widget.clicked.connect(on_change)


class Model:
    def __init__(self):
        self.__n_workers = Variable(os.cpu_count())
        self.__n_io_workers = Variable(min(os.cpu_count(), 12))
        #
        # Neuroglancer
        #
        self.__static_content_source = Variable(
            "https://leviathan-chunglab.mit.edu/neuroglancer")
        self.__bind_address = Variable("localhost")
        self.__port_number = Variable(0)
        self.__neuroglancer_initialized = Variable(False)
        self.__config_file = Variable(tempfile.mktemp(".json"))
        self.__img_server_port_number = Variable(8999)
        #
        # Volume geometry
        #
        self.__x_voxel_size = Variable(1.8)
        self.__y_voxel_size = Variable(1.8)
        self.__z_voxel_size = Variable(2.0)
        #
        # Preprocessing
        #
        self.__fixed_stack_path = Variable("")
        self.__moving_stack_path = Variable("")
        self.__output_path = Variable("")
        self.__fixed_preprocessed_path = Variable("")
        self.__moving_preprocessed_path = Variable("")
        self.__fixed_precomputed_path = Variable("")
        self.__moving_precomputed_path = Variable("")
        #
        # Rigid alignment
        #
        self.__center_x = Variable(0)
        self.__center_y = Variable(0)
        self.__center_z = Variable(0)
        self.__offset_x = Variable(0)
        self.__offset_y = Variable(0)
        self.__offset_z = Variable(0)
        self.__angle_x = Variable(0.0)
        self.__angle_y = Variable(0.0)
        self.__angle_z = Variable(0.0)
        self.__fixed_display_threshold = Variable(0.5)
        self.__moving_display_threshold = Variable(0.5)
        #
        # Rough alignment
        #
        self.__rough_interpolator = Variable("")
        #
        # Cell finding
        #
        self.__bypass_training = Variable(False)
        self.__fixed_blob_path = Variable("")
        self.__moving_blob_path = Variable("")
        self.__fixed_blob_threshold = Variable(100.)
        self.__moving_blob_threshold = Variable(100.)
        self.__fixed_low_sigma = Variable(1.0)
        self.__moving_low_sigma = Variable(1.0)
        self.__fixed_min_distance = Variable(3.0)
        self.__moving_min_distance = Variable(3.0)
        self.__fixed_patches_path = Variable("")
        self.__moving_patches_path = Variable("")
        self.__fixed_model_path = Variable("")
        self.__moving_model_path = Variable("")
        self.__fixed_coords_path = Variable("")
        self.__moving_coords_path = Variable("")
        #
        # Fine alignment
        #
        self.__fixed_geometric_features_path = Variable("")
        self.__moving_geometric_features_path = Variable("")
        self.__n_refinement_rounds = Variable(5)
        self.__find_neighbors_radius = [
            Variable(150), Variable(125), Variable(100), Variable(75),
            Variable(50)]
        self.__find_neighbors_feature_distance = [
            Variable(2.0), Variable(2.25), Variable(2.5), Variable(2.75),
            Variable(3.0)
        ]
        self.__find_neighbors_prominence_threshold = [
            Variable(0.3), Variable(0.4), Variable(0.5), Variable(0.6),
            Variable(0.7)
        ]
        self.__find_neighbors_path = [
            Variable("") for _ in range(5)
        ]
        self.__find_neighbors_pdf_path = [
            Variable("") for _ in range(5)
        ]
        #
        # Filter matches
        #
        self.__filter_matches_path = [Variable("") for _ in range(5)]
        self.__filter_matches_pdf_path = [Variable("") for _ in range(5)]
        self.__filter_matches_max_distance = [Variable(200.) for _ in range(5)]
        self.__filter_matches_min_coherence = [Variable(.9) for _ in range(5)]
        #
        # Fit nonrigid transform
        #
        self.__fit_nonrigid_transform_path = [Variable("") for _ in range(5)]
        self.__fit_nonrigid_transform_inverse_path = [
            Variable("") for _ in range(5)]
        self.__fit_nonrigid_transform_pdf_path = [
            Variable("") for _ in range(5)]
        #
        # Apply alignment
        #
        self.__n_alignment_channels = Variable(1)
        self.__n_levels = Variable(7)
        self.__alignment_input_paths = [Variable("")]
        self.__alignment_output_paths = [Variable("")]
        self.__alignment_tiff_directories = [Variable("")]
        self.__alignment_input_coords = Variable("")
        self.__alignment_output_coords = Variable("")
        #
        # The dictionary
        #
        self.__serialization_dictionary = dict(
            n_workers=self.n_workers,
            n_io_workers=self.n_io_workers,
            static_content_source=self.static_content_source,
            bind_address=self.bind_address,
            port_number=self.port_number,
            x_voxel_size=self.x_voxel_size,
            y_voxel_size=self.y_voxel_size,
            z_voxel_size=self.z_voxel_size,
            fixed_stack_path=self.fixed_stack_path,
            fixed_precomputed_path=self.fixed_precomputed_path,
            fixed_preprocessed_path=self.fixed_preprocessed_path,
            moving_stack_path=self.moving_stack_path,
            moving_precomputed_path=self.moving_precomputed_path,
            moving_preprocessed_path=self.moving_preprocessed_path,
            output_path=self.output_path,
            center_x=self.center_x,
            center_y=self.center_y,
            center_z=self.center_z,
            offset_x=self.offset_x,
            offset_y=self.offset_y,
            offset_z=self.offset_z,
            angle_x=self.angle_x,
            angle_y=self.angle_y,
            angle_z=self.angle_z,
            fixed_display_threshold=self.fixed_display_threshold,
            moving_display_threshold=self.moving_display_threshold,
            rough_interpolator=self.rough_interpolator,
            bypass_training=self.bypass_training,
            fixed_blob_path=self.fixed_blob_path,
            moving_blob_path=self.moving_blob_path,
            fixed_blob_threshold=self.fixed_blob_threshold,
            moving_blob_threshold=self.moving_blob_threshold,
            fixed_low_sigma=self.fixed_low_sigma,
            moving_low_sigma=self.moving_low_sigma,
            fixed_min_distance=self.fixed_min_distance,
            moving_min_distance=self.moving_min_distance,
            fixed_patches_path=self.fixed_patches_path,
            moving_patches_path=self.moving_patches_path,
            fixed_model_path=self.fixed_model_path,
            moving_model_path=self.moving_model_path,
            fixed_coords_path=self.fixed_coords_path,
            moving_coords_path=self.moving_coords_path,
            fixed_geometric_features_path=self.fixed_geometric_features_path,
            moving_geometric_features_path=self.moving_geometric_features_path,
            n_refinement_rounds=self.n_refinement_rounds,
            find_neighbors_radius=self.find_neighbors_radius,
            find_neighbors_feature_distance=
            self.find_neighbors_feature_distance,
            find_neighbors_promience_threshold=
            self.find_neighbors_prominence_threshold,
            find_neighbors_path=self.find_neighbors_path,
            find_neighbors_pdf_path=self.find_neighbors_pdf_path,
            filter_matches_path=self.filter_matches_path,
            filter_matches_pdf_path=self.filter_matches_pdf_path,
            filter_matches_max_distance=self.filter_matches_max_distance,
            filter_matches_min_coherence=self.filter_matches_min_coherence,
            fit_nonrigid_transform_path=self.fit_nonrigid_transform_path,
            fit_nonrigid_transform_inverse_path=
            self.fit_nonrigid_transform_inverse_path,
            fit_nonrigid_transform_pdf_path=
            self.fit_nonrigid_transform_pdf_path,
            n_alignment_channels=self.n_alignment_channels,
            n_levels=self.n_levels,
            alignment_input_paths=self.alignment_input_paths,
            alignment_output_paths=self.alignment_output_paths,
            alignment_tiff_directories=self.alignment_tiff_directories,
            alignment_input_coords=self.alignment_input_coords,
            alignment_output_coords=self.alignment_output_coords
        )

    def read(self, path):
        with open(path, "r") as fd:
            d = json.load(fd)
        for key in self.__serialization_dictionary:
            if key in d:
                target = self.__serialization_dictionary[key]
                if isinstance(target, Variable):
                    target.set(d[key])
                elif isinstance(target, list):
                    for i, value in enumerate(d[key]):
                        if len(target) > i:
                            target[i].set(value)
                        else:
                            target.append(Variable(value))
                else:
                    raise ValueError("Unsupported type: %s" % type(target))
            else:
                print("Warning: %s was missing from configuration" % key)
                print("The file, %s, may be from an older version" % path)

    def write(self, path):
        d = dict([
            (key,
             vorlist.get()
             if isinstance(vorlist, Variable)
             else [_.get() for _ in vorlist]
             ) for key, vorlist in self.__serialization_dictionary.items()])
        with open(path, "w") as fd:
            json.dump(d, fd, indent=2)

    @property
    def n_workers(self) -> Variable:
        return self.__n_workers

    @property
    def n_io_workers(self) -> Variable:
        return self.__n_io_workers

    @property
    def static_content_source(self) -> Variable:
        return self.__static_content_source

    @property
    def bind_address(self) -> Variable:
        return self.__bind_address

    @property
    def port_number(self) -> Variable:
        return self.__port_number

    @property
    def img_server_port_number(self) -> Variable:
        return self.__img_server_port_number

    @property
    def neuroglancer_initialized(self) -> Variable:
        return self.__neuroglancer_initialized

    @property
    def config_file(self) -> Variable:
        return self.__config_file

    @property
    def x_voxel_size(self) -> Variable:
        return self.__x_voxel_size

    @property
    def y_voxel_size(self) -> Variable:
        return self.__y_voxel_size

    @property
    def z_voxel_size(self) -> Variable:
        return self.__z_voxel_size

    @property
    def fixed_stack_path(self) -> Variable:
        """Location of the stack of .tif files for the fixed frame of reference
        """
        return self.__fixed_stack_path

    @property
    def moving_stack_path(self) -> Variable:
        """
        Location of the stack of .tif files for the moving frame of reference
        :return: the string path
        :rtype: str
        """
        return self.__moving_stack_path

    @property
    def output_path(self) -> Variable:
        return self.__output_path

    @property
    def fixed_preprocessed_path(self) -> Variable:
        return self.__fixed_preprocessed_path

    @property
    def moving_preprocessed_path(self) -> Variable:
        return self.__moving_preprocessed_path

    @property
    def fixed_precomputed_path(self) -> Variable:
        return self.__fixed_precomputed_path

    @property
    def moving_precomputed_path(self) -> Variable:
        return self.__moving_precomputed_path

    @property
    def center_x(self) -> Variable:
        return self.__center_x

    @property
    def center_y(self) -> Variable:
        return self.__center_y

    @property
    def center_z(self) -> Variable:
        return self.__center_z

    @property
    def offset_x(self) -> Variable:
        return self.__offset_x

    @property
    def offset_y(self) -> Variable:
        return self.__offset_y

    @property
    def offset_z(self) -> Variable:
        return self.__offset_z

    @property
    def angle_x(self) -> Variable:
        return self.__angle_x

    @property
    def angle_y(self) -> Variable:
        return self.__angle_y

    @property
    def angle_z(self) -> Variable:
        return self.__angle_z

    @property
    def fixed_display_threshold(self) -> Variable:
        return self.__fixed_display_threshold

    @property
    def moving_display_threshold(self) -> Variable:
        return self.__moving_display_threshold

    @property
    def rough_interpolator(self) -> Variable:
        return self.__rough_interpolator

    @property
    def  bypass_training(self) -> Variable:
        return self.__bypass_training

    @property
    def fixed_blob_path(self) -> Variable:
        return self.__fixed_blob_path

    @property
    def moving_blob_path(self) -> Variable:
        return self.__moving_blob_path

    @property
    def fixed_blob_threshold(self) -> Variable:
        return self.__fixed_blob_threshold

    @property
    def moving_blob_threshold(self) -> Variable:
        return self.__moving_blob_threshold

    @property
    def fixed_low_sigma(self) -> Variable:
        return self.__fixed_low_sigma

    @property
    def moving_low_sigma(self) -> Variable:
        return self.__moving_low_sigma

    @property
    def fixed_min_distance(self) -> Variable:
        return self.__fixed_min_distance

    @property
    def moving_min_distance(self) -> Variable:
        return self.__moving_min_distance

    @property
    def fixed_patches_path(self) -> Variable:
        return self.__fixed_patches_path

    @property
    def moving_patches_path(self) -> Variable:
        return self.__moving_patches_path

    @property
    def fixed_model_path(self) -> Variable:
        return self.__fixed_model_path

    @property
    def moving_model_path(self) -> Variable:
        return self.__moving_model_path

    @property
    def fixed_coords_path(self) -> Variable:
        return self.__fixed_coords_path

    @property
    def moving_coords_path(self) -> Variable:
        return self.__moving_coords_path

    @property
    def fixed_geometric_features_path(self) -> Variable:
        return self.__fixed_geometric_features_path

    @property
    def moving_geometric_features_path(self) -> Variable:
        return self.__moving_geometric_features_path

    @property
    def n_refinement_rounds(self) -> Variable:
        return self.__n_refinement_rounds

    @property
    def find_neighbors_radius(self) -> typing.List[Variable]:
        return self.__find_neighbors_radius

    @property
    def find_neighbors_feature_distance(self) -> typing.List[Variable]:
        return self.__find_neighbors_feature_distance

    @property
    def find_neighbors_prominence_threshold(self) -> typing.List[Variable]:
        return self.__find_neighbors_prominence_threshold

    @property
    def find_neighbors_path(self) -> typing.List[Variable]:
        return self.__find_neighbors_path

    @property
    def find_neighbors_pdf_path(self) -> typing.List[Variable]:
        return self.__find_neighbors_pdf_path

    @property
    def filter_matches_path(self) -> typing.List[Variable]:
        return self.__filter_matches_path

    @property
    def filter_matches_pdf_path(self) -> typing.List[Variable]:
        return self.__filter_matches_pdf_path

    @property
    def filter_matches_max_distance(self) -> typing.List[Variable]:
        return self.__filter_matches_max_distance

    @property
    def filter_matches_min_coherence(self) -> typing.List[Variable]:
        return self.__filter_matches_min_coherence

    @property
    def fit_nonrigid_transform_path(self) -> typing.List[Variable]:
        return self.__fit_nonrigid_transform_path

    @property
    def fit_nonrigid_transform_inverse_path(self) -> typing.List[Variable]:
        return self.__fit_nonrigid_transform_inverse_path

    @property
    def fit_nonrigid_transform_pdf_path(self) -> typing.List[Variable]:
        return self.__fit_nonrigid_transform_pdf_path

    @property
    def n_alignment_channels(self) ->Variable:
        return self.__n_alignment_channels

    @property
    def n_levels(self) -> Variable:
        return self.__n_levels

    @property
    def alignment_input_paths(self) -> typing.List[Variable]:
        return self.__alignment_input_paths

    @property
    def alignment_output_paths(self) -> typing.List[Variable]:
        return self.__alignment_output_paths

    @property
    def alignment_tiff_directories(self) -> typing.List[Variable]:
        return self.__alignment_tiff_directories

    @property
    def alignment_input_coords(self) -> Variable:
        return self.__alignment_input_coords

    @property
    def alignment_output_coords(self) -> Variable:
        return self.__alignment_output_coords