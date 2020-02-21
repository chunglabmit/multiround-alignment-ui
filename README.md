# Multround alignment UI

This is a user interface to [Phathom's
multiround registration pipeline](https://github.com/chunglabmit/phathom/blob/master/phathom/pipeline/README.md).

## Installation

PyQt5 must be installed in your virtual environment as a prerequisite to
installing using PIP. A typical install:
```bash
conda create -n multround-alignment-ui
conda install pyqt numpy scipy scikit-image matplotlib
pip install tornado==4.5.3
pip install git@github.comchunglabmit/phathom.git#egg=phathom
pip install https://github.com/chunglabmit/precomputed-tif.git#egg=precomputed-tif
pip install https://github.com/chunglabmit/multiround-alignment-ui.git#egg=multiround-alignment-ui
```
