import os

from PyQt5.QtWidgets import QWidget, QGridLayout, QLabel, QLineEdit, QPushButton, QHBoxLayout, QGroupBox, QSizePolicy, \
    QDoubleSpinBox, QCheckBox
from PyQt5.QtWidgets import QFileDialog, QSpinBox, QVBoxLayout
from .model import Model, Variable
from .utils import connect_input_and_button

class ConfigurationWidget(QWidget):
    def __init__(self, model:Model):
        QWidget.__init__(self)
        self.model = model
        top_layout = QVBoxLayout()
        self.setLayout(top_layout)
        layout = QGridLayout()
        top_layout.addLayout(layout)
        layout.setColumnStretch(1, 1)
        paths = (
                ("Fixed stack path", model.fixed_stack_path),
                ("Moving stack path", model.moving_stack_path),
                ("Output path", model.output_path)
        )
        for row_idx, (name, variable) in enumerate(paths):
            label = QLabel(name)
            layout.addWidget(label, row_idx, 0)
            input = QLineEdit()
            layout.addWidget(input, row_idx, 1)
            button = QPushButton("...")
            layout.addWidget(button, row_idx, 2)
            self.connect_input_and_button(name, input, button, variable)
        row_idx = len(paths)
        #
        # Voxel size
        #
        hlayout = QHBoxLayout()
        top_layout.addLayout(hlayout)
        hlayout.addWidget(QLabel("voxel size (μm):"))
        for label, variable in (
                ("X", self.model.x_voxel_size),
                ("Y", self.model.y_voxel_size),
                ("Z", self.model.z_voxel_size)):
            voxel_size_widget = QDoubleSpinBox()
            voxel_size_widget.setMinimum(0.01)
            voxel_size_widget.setMaximum(10.0)
            hlayout.addWidget(QLabel(label))
            hlayout.addWidget(voxel_size_widget)
            variable.bind_double_spin_box(voxel_size_widget)
        hlayout.addStretch(1)

        hlayout = QHBoxLayout()
        top_layout.addLayout(hlayout)
        label = QLabel("# of workers")
        hlayout.addWidget(label)
        n_workers_widget = QSpinBox()
        n_workers_widget.setMinimum(1)
        n_workers_widget.setMaximum(os.cpu_count())
        n_workers_widget.setValue(model.n_workers.get())
        hlayout.addWidget(n_workers_widget)
        self.model.n_workers.bind_spin_box(n_workers_widget)
        hlayout.addStretch(1)

        hlayout = QHBoxLayout()
        top_layout.addLayout(hlayout)
        label = QLabel("# of workers for I/O")
        hlayout.addWidget(label)
        n_io_workers_widget = QSpinBox()
        n_io_workers_widget.setMinimum(1)
        n_io_workers_widget.setMaximum(os.cpu_count())
        n_io_workers_widget.setValue(model.n_io_workers.get())
        hlayout.addWidget(n_io_workers_widget)
        self.model.n_io_workers.bind_spin_box(n_io_workers_widget)
        hlayout.addStretch(1)

        hlayout = QHBoxLayout()
        top_layout.addLayout(hlayout)
        self.use_gpu_widget = QCheckBox("Use GPU")
        hlayout.addWidget(self.use_gpu_widget)
        self.model.use_gpu.bind_checkbox(self.use_gpu_widget)
        hlayout.addStretch(1)

        group_box = QGroupBox("Neuroglancer parameters")
        group_box.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Minimum)
        top_layout.addWidget(group_box)
        layout = QVBoxLayout()
        group_box.setLayout(layout)
        hlayout = QHBoxLayout()
        layout.addLayout(hlayout)
        hlayout.addWidget(QLabel("Static content source"))
        static_content_source_widget = QLineEdit()
        static_content_source_widget.setText(
            model.static_content_source.get())
        self.model.static_content_source.bind_line_edit(
            static_content_source_widget)
        hlayout.addWidget(static_content_source_widget)
        hlayout = QHBoxLayout()
        layout.addLayout(hlayout)
        hlayout.addWidget(QLabel("Bind address"))
        bind_address_widget = QLineEdit()
        bind_address_widget.setText(model.bind_address.get())
        self.model.bind_address.bind_line_edit(bind_address_widget)
        hlayout.addWidget(bind_address_widget)
        hlayout = QHBoxLayout()
        layout.addLayout(hlayout)
        hlayout.addWidget(QLabel("Port number"))
        port_number_widget = QSpinBox()
        port_number_widget.setValue(model.port_number.get())
        port_number_widget.setMinimum(0)
        port_number_widget.setMaximum(65535)
        self.model.port_number.bind_spin_box(port_number_widget)
        hlayout.addWidget(port_number_widget)
        hlayout.addStretch(1)

        top_layout.addStretch(1)

    def connect_input_and_button(self,
                          name:str,
                          input:QLineEdit,
                          button:QPushButton,
                          variable:Variable):
        connect_input_and_button(self, name, input, button, variable)
