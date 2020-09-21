# Multround alignment UI

This is a user interface to [Phathom's
multiround registration pipeline](https://github.com/chunglabmit/phathom/blob/master/phathom/pipeline/README.md).

## Installation

The easiest way to install this package is with 
[Anaconda](https://anaconda.com). The following will create a minimal
conda environment
```bash
git clone https://github.com/chunglabmit/multiround-alignment-ui
conda env create -f multiround-alignment-ui/environment.yml
conda activate multiround-alignment-ui
```

## Running

To run (assuming you have installed):

```bash
multiround-alignment-ui [session.maui]
```
where session.maui is the optional session file from a File->save
in a previous multiround-alignment-ui invocation.

## Using

The multiround pipeline is highly configurable, with different strategies
for many of the steps. The high-level pipeline consists of the following
steps, which correspond to the tabs in the application:

* Configuration - Setting up the location of the fixed and moving image stacks,
the output and other analysis-wide parameters.

* Preprocessing - converting the image stacks to Neuroglancer volumes, if
necessary

* Neuroglancer alignment - Manual alignment of the fixed and moving images

* Cell detection - detection of blobs which will be used as an input during
alignment

* Fine alignment - finding matches between the fixed and moving volumes,
filtering the matches and creating the warping function

* Apply alignment - warping the moving image to the fixed image volume

### Menu items

The multiround alignment UI has a menu bar with a single *File* menu. The
menu items are:

* Open - opens a **.maui** (Multiround Alignment UI) file. This file has the
settings that you enter into the UI - opening lets you pick up from where you
left off.

* Save - saves a **.maui** file.

* Quit - closes the application

### Configuration

The configuration screen lets you enter the locations of the fixed and
moving stacks as well as some other application-wide settings. These are:

* Fixed stack path - this is the filesystem path to the stack of .TIFF files
  for the fixed volume.
  These should be named so that they can be alphabetically sorted in increasing
  Z-order. For instance, they might be named, 
  "img_0000.tiff", "img_0001.tiff", etc. Note that files without zero-padded
  names might be loaded out-of-order (img_11.tiff follows img_1.tiff in
  alphabetical order, not img_2.tiff).
 
* Moving stack path - this is the filesystem path to the stack of .TIFF files
   for the moving volume.
 
* Voxel size - this is the size of a voxel in the X, Y and Z direction in 
   microns. The voxel sizes can be different if the voxels are anisotropic.
   Distances and distance-related parameters are in microns in the UI when
   they appear and this parameter supplies the conversion from voxels to microns.

* \# of workers - the number of worker processes / cpus used during multiprocessing
  operations. You may want to lower this number if you find your computer is running
  out of memory.

* \# of workers for I/O - the number of worker processes devoted to file read / write
  operations. You may want to lower this number if the UI floods the network while
  reading or writing image data.

* Use GPU - the GPU will be used for calculating the final warping if this is checked.
  Currently, computers with more than 20-30 cores will perform the calculations faster
  if this box is *not* checked even if a GPU is installed.

* Static content source - this is the URL used by Neuroglancer to fetch Neuroglancer's
  static web assets. See https://github.com/google/neuroglancer#building for
  details on building the resources yourself.

* Bind address - the Neuroglancer webserver listens for HTTP requests at this address.
  If you're running this on your local machine, leave as "localhost" to keep the
  webserver from listening to requests outside of your machine. If you're running
  remotely (e.g. `ssh -X server.mit.edu multiround-alignment-ui`), this should be
  the DNS name or IP address of the remote machine so that the webserver will listen
  to requests from your machine.

* Port number - the port number that the Neuroglancer webserver listens to. Leave
  as-is ("0") to select any open port, set to a number to specify a particular
  port to bind to. A strategy for remote operation might be to port-forward this
  port and use a bind address of "localhost". For instance:
  
  ```bash
  ssh -X -L 10000:localhost:10000 multiround-alignment-ui
  ```

### Preprocessing

Currently, the only preprocessing task is to convert a stack of .tiff file to
a Neuroglancer / Chunglab / blockfs volume. If you have a volume that is already
in the blockfs format, you can use it directly by filling in the precomputed path.

There are similar blocks of controls for the moving and fixed volumes.

* Precomputed path - this is the path to the existing or to-be-created Neuroglancer
  volume. The button to the right ("...") can be used to browse the filesystem.

* **Make Neuroglancer volume ** button - press this button to make / remake the
  Neuroglancer volume from the TIFF stack.

The ** Run all ** button at the bottom of the page will make both the fixed and
moving Neuroglancer volumes.

### Neuroglancer alignment

This tab controls launching the Neuroglancer website to manually align the
moving volume to the fixed volume. Multiround-alignment-ui uses nuggt-align to
control Neuroglancer. The details of how to use nuggt-align are here:
https://github.com/chunglabmit/nuggt#nuggt-align

The tab has the following fields:

* Decimation level - this controls what level of the Neuroglancer pyramid is
  used for display. At decimation level 1, the volume will be shown at its original
  resolution, at decimation 2, the volume will be show at 1/2 resolution, at
  decimation 3, the volume will be shown at 1/4 resolution and so on. For large
  volumes, a larger decimation level should be used to conserve memory and processing
  time, for small volumes, a smaller decimation level should be used to display
  the volume with higher fidelity.

* Launch Neuroglancer Alignment - this button starts the webserver and displays
  its URLs. You can open the URLs in your browser to see the fixed and
  moving volumes.

* Make rough alignment - this button becomes available after save your alignment
  in Neuroglancer (Shift + S). You should make the rough alignment after editing
  your alignment and before moving onto fine alignment.

### Cell detection

Cell detection must be done before fine alignment. There are two options for
fine alignment fixed/moving cell matching: "points" and "correlation". The "points"
method requires both fixed and moving cell detection and a higher-fidelity
cell detection than the "correlation" method.

There are two strategies for cell detection. The first uses a simple blob detector
to find cells. The second uses the blob detector, followed by patch collection
around each putative blob, followed by training a cell classifier using
**eflash-train** (https://github.com/chunglabmit/eflash_2018#eflash-train). The
first strategy is relatively fast, the second is time-consuming, but much more
accurate. The second strategy may be used when using "points" cell matching, but
is unnecessary for the "correlation" method.

The blob detector's pipeline is:

* Blur the image using a difference of Gaussians

* Find local maxima in the resulting image that are at least a minimum distance
  from any voxel of higher intensity.

* Take as cells any local maximum whose intensity in the difference of Gaussian
  image is higher than a threshold.

This tab has the following controls:

* Bypass training: check this box to use only the blob detector. Leave it unchecked
  to train and  use a classifier to filter the output of the blob detector.

For the fixed and moving volumes:

* Sigma - the standard deviation of the difference of Gaussians, in microns. The
  default of 2 microns is appropriate for a 10 micron nucleus.

* Threshold - the minimum intensity in the difference of Gaussians image for
  a local maximum voxel to be classified as a blob by the blob detector.

* Minimum distance - the minimum distance, in microns, that a local maximum must
  be from any higer-intensity voxel for that voxel to be classified as a blob.

* Run fixed / moving blob detection - this button will run the blob detector

* Run fixed / moving patch collection - this button will run patch collection
  for the classifier if appropriate.

* Run fixed / moving training - this option will start eflash_train to let
  you train a classifier for the blobs.

For all volumes:

* Run all blob detection and patch collection - runs blob detection for the
  fixed and moving volumes and patch collection for both if appropriate.

### Fine alignment

Fine alignment uses either correlations between the fixed and moving images
or positions of constellations of cells to find correspondences between
fixed and moving volumes. It then filters these to create a coherent deformation
field and it finally creates a warping function from the deformation. This
process is repeated iteratively, deforming the moving image or transforming blob
positions using the warping function from the previous iteration.

The controls for the number of iterations and current iteration are:

* Number of rounds - the number of iterations to be performed

* Current round - the iteration currently being worked on

There are two neighbor finding methods - **points** and **correlation**. The
**points** method needs the geometric features which are rotation invariant
features of the spatial relationship of the point of interest to its nearest
neighbors. The features in the fixed volume can be matched to the features in
the moving volume to find the same cell in both the fixed and moving volume.

#### Find neighbors - points

The **points** method warps the locations of the detected blobs in the fixed
volume to those in the moving volume. It then finds the closest N blobs in the
moving volume to each blob in the fixed volume, limited to moving blobs within a given
radius of the target fixed blob. The best match, from among those N blobs, must
have at most maximum distance between in feature space and the distance must be
at most a fraction of the next best match distance.

The parameters of the **points** method are:

* \# geometric neighbors - if this number is greater than 3, all possible combinations
  of 3, taken among the number of nearest neighbors are taken. This gives alternative
  geometric constellations for each point, in case there is a nearby false detection
  or missed blob. Increase this to 4 or more only if the detector is inaccurate - it
  greatly increases neighborhood finding calculation times and increases the number
  of false matches.

* Calculate fixed / moving / all geometric features - these buttons calculate
  teh geometric features for the **points** method.

* radius - the search radius after warping, in microns

* Max neighbors - the maximum number of neighbor candidates allowed. If more
  candidates are within the radius, the closest are used.

* Maximum feature distance - the euclidean distance in 6-dimensional space is
  calculated and the match is rejected if the distance is above this number. Set
  the maximum feature distance lower to reject false matches.

* Prominence threshold - the next best euclidean distance is multiplied by this
  value and the match is rejected if the match's feature distance is above
  the next best's fractional value. Set the prominence threshold lower to reject
  false matches.

* Find neighbors - this button performs the matching

* Show results - after running, this button shows a diagnostic PDF. The panel, 
  "Fixed and moving points after rigid transformation" shows the fixed points,
  warped into the moving space. If there is poor overlap, you should improve
  the manual alignment. The panel, "Matched points", shows the matches found.
  If there are few matched points (in the low hundreds or lower), then the
  prominence threshold or maximum feature distance should be raised. If the
  coverage is spotty or localized to just one area, the radius should be
  increased or the manual alighment should be improved. If this method still
  fails, "correlation" should be used.

#### Find neighbors - correlation

The **correlation** method works by assessing the correlation between patches
in the fixed and moving volumes. It calculates the cross correlation at the 
point of interest and all voxels one voxel away from that point. The point with
the highest correlation becomes the new point of interest and the algorithm
repeats, following the gradient until it reaches a local maximum. The method starts
by gridding the volume, then finding the nearest blob in the fixed volume to each
of the grid points. This lets the method discard areas with no cells and centers
the correlation over a local intensity maximum which helps with the gradient
descent. The correlation
method requires either a large blur or a somewhat-accurate alignment. It gives
more accurate results than the **points** method so it is a good choice for
the last alignment iteration.

The geometric transform does not need to be calculated and moving blobs do not
need to be found if only the correlation method is used.

The parameters for the correlation method:

* Sigma - the smoothing sigma for the fixed and moving images (in microns). A
  larger sigma allows for gradient descent if the previous alignment was poor
  whereas a smaller sigma gives more accurate results.

* Radius - a grid point will be discarded if there is no blob within this radius
  of the grid point.

* Minimum correlation - a grid point will not be used if the local correlation maximum
  is less than the minimum correlation. Correlations go from -1 to 1.

* Grid size - this is the number of grid points in the grid in the x, y  and z
  directions. Set these numbers lower to decrease the run time, set them higher
  to increase the accuracy. The x, y and z can be set independently, for instance
  specifying a low z if the tissue is a sheet with thin z thickness.

The **Show Results** button shows the layout of grid points, a histogram of
correlations and the alignment of the fixed and moving volume. You should see
a bimodal distribution of correlations with the minimum correlation separating
the inaccurate and accurate alignments - this can be used to adjust the minimum
correlation. If the alignment of the fixed and moving volume contains few points,
you can lower the minimum correlation, improve the manual alignment or try the
**points** method. If the alignment of the fixed and moving volume shows areas
of poor coverage, you may want to improve the manual alignment.

#### Filter matches

The **Filter matches** pipeline step models the alignment as an affine transform,
on top of the previous alignment, with local displacements. It calculates the
affine transform using RANSAC to exclude outliers from the output of
**Find neighbors**, then, for each point, it finds the two nearest neighbors and
checks to see if the displacement vector, from the affine transform of all three
agrees. Points are filtered out if their displacement is more than the maximum or if
the coherence of the three points is less than the allowed minimum.

**Filter matches** has the folowing parameters:

* Maximum distance - maximum allowed displacement in microns from the location
  of the moving point as predicted  by the affine transform.

* Minimum coherence - the minimum allowed coherence of each point with its
  nearest neighbors.

The *Show results* button shows plots of the filtering process. The 
"Starting residuals" panel shows the distance between the moving point as
predicted by the previous transform applied to the fixed point and the
moving point's actual position. There should be a relatively coherent pattern
of color gradation, if not, then there are too many false matches from
the **Find neighbors** step. The "Matches after applying affine transform"
step should show most of the fixed points having approximately the same displacement
as their neighbors.

"Distribution of displacement coherences" can be used to set the minimum coherence.
There should be a clear peak to the right of the histogram and the minimum
coherence line should be adjusted so that the peak is to the right. If the
peak is broad or non-existent or is below 75%, then you may want to consider
changing the parameters of **Find neighbors** or consider using the correlation
method. The "Coherent affine-transformed points" graph should be checked as well.
If there are clear gaps or if the extents of the graph do not cover the entire volume,
you will need to lower the minimum coherence or add more rounds in order to refine and
extend the alignment to uncovered areas.

#### Fit nonrigid transform

The last step on the fine alignment tab is **Fit nonrigid transform**. This step
creates the warping function, either to be used as the starting point for the
next round or as the final transformation for the actual warping. 