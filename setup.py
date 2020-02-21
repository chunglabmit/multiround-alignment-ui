from setuptools import setup, find_packages, Extension
import numpy as np
import os

version = "0.1.0"

with open("./README.md") as fd:
    long_description = fd.read()

setup(
    name="multiround-alignment-ui",
    version=version,
    description=
    "User interface for Phathom's registration pipeline",
    long_description=long_description,
    install_requires=[
        "eflash-2018",
        "gunicorn",
        "neuroglancer",
        "nuggt",
        "phathom",
        "precomputed-tif",
        "vispy"
    ],
    author="Kwanghun Chung Lab",
    packages=["multiround_alignment_ui"],
    entry_points={ 'console_scripts': [
        "multiround-alignment-ui=multiround_alignment_ui.main:main"
    ]},
    url="https://github.com/chunglabmit/multiround-alignment-ui",
    license="MIT",
    classifiers=[
        "Development Status :: 3 - Alpha",
        'Programming Language :: Python :: 3.5',
    ]
)