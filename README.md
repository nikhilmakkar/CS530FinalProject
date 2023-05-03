# CS 530 Final Project: Machu Llacta
An interactive visualization of the ruins of Machu Llacta using VTK and PyQt6.

Final project for CS 530: Introduction to Scientific Visualization - Spring 2023

Tanner Waltz and Nikhil Makkar

## Video Demonstration
This is the video used uring the in-class presentation. [Click here.](https://youtu.be/jjk2Bt0sGAc)

## How to Download Data
### Point Cloud Data
1. Go to **Link 1** on the README.pdf included in the submission.
2. Download `Mawchu_Llacta_UTM.las`. This is the point cloud dataset, used with the `-i` option.

### Walls and Structures Shapefiles
1. Go to **Link 2** on the README.pdf included in the submission.
2. Download the entire folder. This is done by clicking the name of the folder at the top of the page, then clicking 'Download'.
3. Extract the entire folder.
4. `Mawchu_Llacta_walls_2023_03_28_UTM.shp` is the walls shapefile, used with the `-w` option.
5. `Mawchu_Llacta_structures_2023_03_28_UTM.shp` is the structures shapefile, used with the `-s` option.

### Preprocessed Points Pickle Files for Walls and Structures
1. These will be downloaded automatically when you clone the repository, in the `data` folder.
2. `data/fullBoundaryWalls.pkl` is the full preprocessed points pickle file for walls, used with the `--wallsfile` option.
3. `data/fullBoundaryStructures.pkl` is the full preprocessed points pickle file for structures, used with the `--structuresfile` option.

We also provide two reduced preprocessed points pickle files, `data/reducedBoundaryWalls.pkl` and `data/reducedBoundaryStructures.pkl`, which can be used instead.

## How to Prepare Environment
1. Clone and enter the repository ([https://github.com/nikhilmakkar/CS530FinalProject](https://github.com/nikhilmakkar/CS530FinalProject))
2. Run `pip install -r requirements.txt` to download necessary packages to the environment

## How to Run
1. Run `python final.py OPTIONS`

### Recommendations for Running the Visualization
Because the point cloud dataset is massive, it takes a LONG time for a computer to process the points and calculate what points exist in each wall/structure polygon. Thus, we have provided the option to use preprocessed pickle files to avoid this task. However, we also still provide the option to perform the computations locally if desired.

It also takes a large amount of computing resources to visualize all 93 million points. Thus, we have also provided the option to reduce the number of points shown in the visualization if desired. We have also provided two preprocessed pickle files that are also reduced.

Here are our two recommended methods of running the program:
1. All points, using full preprocessed data:
	- `python final.py -i [PATH] -w [PATH] -s [PATH] --wallsfile data/fullBoundaryWalls.pkl --structuresfile data/fullBoundaryStructures.pkl -a`
2. Reduced points, using reduced preprocessed data:
	- `python final.py -i [PATH] -w [PATH] -s [PATH] --wallsfile data/reducedBoundaryWalls.pkl --structuresfile data/reducedBoundaryStructures.pkl` 

## Options
- `-h`: Show help message
- `-i`, `--input`: Required, Path of point cloud dataset
- `-w`, `--walls`: Required, Path of the walls shapefile
- `-s`, `--structures`: Required, Path of the structures shapefile
- `--wallsfile`: Path of the processed points pickle file for walls
- `--structuresfile`: Path of the processed points pickle file for structures
- `-a`, `--all`: Flag to use all points in point cloud, rather than reducing
- `-b`, `--boundaries`: Calculate and use actual wall boundaries instead of bounding boxes
