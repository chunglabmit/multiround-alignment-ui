# Multround alignment UI

This is a user interface to [Phathom's
multiround registration pipeline](https://github.com/chunglabmit/phathom/blob/master/phathom/pipeline/README.md).

## Installation

PyQt5 must be installed in your virtual environment as a prerequisite to
installing using PIP. A typical install:
```bash
conda create -n multiround-alignment-ui
conda activate multiround-alignment-ui
conda install pyqt numpy scipy scikit-image matplotlib tornado=4.5.3 gunicorn pytorch
git clone https://github.com/chunglabmit/multiround-alignment-ui
cd multiround-alignment-ui
pip install -r requirements.txt
pip install .
```
