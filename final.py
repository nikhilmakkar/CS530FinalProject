import vtk
import numpy as np
import laspy
import vtk.util.numpy_support as vtk_np
import argparse
import sys
from math import floor
import geopandas as gpd
import concurrent.futures
import matplotlib.path as mpltPath
from vtk_colorbar import colorbar, colorbar_param
import pickle
import pandas as pd


from PyQt6.QtWidgets import QApplication, QWidget, QMainWindow, QComboBox, QGridLayout, QLabel, QPushButton
from PyQt6.QtCore import Qt
from vtk.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor

# wrapper class for pointcloud actor
class VTKActorWrapper(object):
    def __init__(self, nparray, colors=None, values=None):
        super(VTKActorWrapper, self).__init__()

        self.nparray = nparray

        nCoords = nparray.shape[0]

        self.verts = vtk.vtkPoints()
        self.cells = vtk.vtkCellArray()

        self.pd = vtk.vtkPolyData()
        self.verts.SetData(vtk_np.numpy_to_vtk(nparray))
        self.cells_npy = np.vstack([np.ones(nCoords,dtype=np.int64),
                               np.arange(nCoords,dtype=np.int64)]).T.flatten()
        self.cells.SetCells(nCoords,vtk_np.numpy_to_vtkIdTypeArray(self.cells_npy))
        self.pd.SetPoints(self.verts)
        self.pd.SetVerts(self.cells)
        if colors is not None: # sets specific colors to points if passed in
            self.pd.GetPointData().SetScalars(vtk_np.numpy_to_vtk(colors))
        elif values is not None: # sets sepcific values to points if passed in
            self.pd.GetPointData().SetScalars(vtk_np.numpy_to_vtk(values))

        self.mapper = vtk.vtkPolyDataMapper()
        self.mapper.SetInputDataObject(self.pd)
        if colors is not None:
            self.mapper.SetColorModeToDirectScalars()

        self.actor = vtk.vtkActor()
        self.actor.SetMapper(self.mapper)
        self.actor.GetProperty().SetRepresentationToPoints()

frame_counter = 0

# screenshot function
def save_frame(window):
    global frame_counter
    # ---------------------------------------------------------------
    # Save current contents of render window to PNG file
    # ---------------------------------------------------------------
    file_name = "finalProject" + str(frame_counter).zfill(5) + ".png"
    image = vtk.vtkWindowToImageFilter()
    image.SetInput(window)
    png_writer = vtk.vtkPNGWriter()
    png_writer.SetInputConnection(image.GetOutputPort())
    png_writer.SetFileName(file_name)
    window.Render()
    png_writer.Write()
    frame_counter += 1
    print(file_name + " has been successfully exported")

# returns dictionary of (category string: list of points) key-value pairs, creating a apir for each category in shapefile['header']
def categorical_arrays(shapefile, header):
    return shapefile.groupby(header)['pts'].agg(lambda x: np.concatenate(x.values, axis=0)).to_dict()

# used by realBoundary function to find points within actual polygons in parallel
def parallelFunction(args):
    pg, pc_array = args
    if pg.geom_type == 'Polygon':
        coords = pg.exterior.coords
        # print(coords)
    elif pg.geom_type == 'MultiPolygon':
        coords = np.concatenate([poly.exterior.coords for poly in pg.geoms])

    path = mpltPath.Path(coords)
    mask = path.contains_points(pc_array[:,0:2])
    x = pc_array[mask]
    return x

# finds the points within each polygon, runs in parallel
def realBoundary(shapefile, pc_array):
    with concurrent.futures.ProcessPoolExecutor() as executor:
        pts = [i for i in executor.map(parallelFunction, [[pg, pc_array] for pg in shapefile['geometry']])]
    return pts

# finds the points within the bounding box of each polygon; faster than realBoundary, but not as accurate
def boundingBox(shapefile, pc_array):
    pts = []
    for pg in shapefile['geometry'].apply(lambda x: x.bounds[:]):
        mask = (pc_array[:,0]>pg[0]) * (pc_array[:,0]<pg[2]) * (pc_array[:,1]>pg[1]) * (pc_array[:,1]<pg[3])
        pts.append(pc_array[mask])
    return pts

class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        MainWindow.setObjectName('The Main Window')
        MainWindow.setWindowTitle('Machu Llacta Visualization')
        # in Qt, windows are made of widgets.
        # centralWidget will contains all the other widgets
        self.centralWidget = QWidget(MainWindow)
        # we will organize the contents of our centralWidget
        # in a grid / table layout
        self.gridlayout = QGridLayout(self.centralWidget)
        # vtkWidget is a widget that encapsulates a vtkRenderWindow
        # and the associated vtkRenderWindowInteractor. We add
        # it to centralWidget.
        self.vtkWidget = QVTKRenderWindowInteractor(self.centralWidget)

        self.screenshotButton = QPushButton()
        self.screenshotButton.setText('Save Screenshot')
        self.quitButton = QPushButton()
        self.quitButton.setText('Quit')

        self.attributeLabel = QLabel('Attribute that is Visualized:')
        self.attributeDropdown = QComboBox()
        self.attributes = ['None', 'Type of Wall/Structure', 'Completeness', 'Wall Thickness', 'Maximum Original Height', 'Maximum Conserved Height', 'Time of Construction']
        self.attributeDropdown.addItems(self.attributes)

        self.positionLabel = QLabel('Current (X,Y,Z) position: (0,0,0)')
        self.positionLabel.setAlignment(Qt.AlignmentFlag.AlignHCenter)

        # We are now going to position our widgets inside our
        # grid layout. The top left corner is (0,0)
        # x adjusts the relative width of the sidebar compared to the interactive window
        # y adjusts the number of "rows" in a column; used to separate parts of the sidebar
        x = 10
        y = 50
        self.gridlayout.addWidget(self.vtkWidget, 0, 0, y, x)

        self.gridlayout.addWidget(self.screenshotButton, 0, x, 1, 1)
        self.gridlayout.addWidget(self.attributeLabel, 4, x, 1, 1)
        self.gridlayout.addWidget(self.attributeDropdown, 5, x, 1, 1)
        self.gridlayout.addWidget(self.positionLabel, y-4, x, 1, 1)
        self.gridlayout.addWidget(self.quitButton, y-1, x, 1, 1)
        MainWindow.setCentralWidget(self.centralWidget)


class FinalProject(QMainWindow):
    def __init__(self, parent = None):
        QMainWindow.__init__(self, parent)
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        self.attributes = self.ui.attributes

        # defining variables
        self.currAttribute = 'None' # current attribute being visualized

        # creates dictionaries for numerical and categorical datatypes with (category name string: [column name in walls shapefile string, column name in structures shapefile string]) key value pairs
        self.numericalDict = {'Wall Thickness': ['grosor', 'grosor_1'], 'Maximum Original Height': ['alt_max', None], 'Maximum Conserved Height': ['alt_cons', 'alt']}
        self.categoryDict = {'None': 'None', 'Type of Wall/Structure': ['clase_rev', 'design_co1'] , 'Completeness': ['preserva_1', 'preserva_1'], 'Time of Construction': [None, 'temp_con_2']}

        # defines colors used to visualize categorical attributes
        self.categoryColors = [(235, 172, 35), (184, 0, 88), (0, 140, 249), (0, 110, 0), (0, 187, 173), (209, 99, 230), (89, 84, 214), (178, 69, 2), (255, 146, 135), (0, 198, 248), (135, 133, 0), (0, 167, 108), (189, 189, 189), (251, 73, 176)]
        self.categoryColors = [tuple(j/255 for j in i) for i in self.categoryColors]

        # defines colors used to visualize numerical attributes
        viridis = [[0.267004, 0.004874, 0.329415], [0.282656, 0.100196, 0.42216], [0.277134, 0.185228, 0.489898], [0.253935, 0.265254, 0.529983], [0.221989, 0.339161, 0.548752], [0.190631, 0.407061, 0.556089], [0.163625, 0.471133, 0.558148], [0.139147, 0.533812, 0.555298], [0.120565, 0.596422, 0.543611], [0.134692, 0.658636, 0.517649], [0.20803, 0.718701, 0.472873], [0.327796, 0.77398, 0.40664], [0.477504, 0.821444, 0.318195], [0.647257, 0.8584, 0.209861], [0.82494, 0.88472, 0.106217], [0.993248, 0.906157, 0.143936]]

        # read in the shapefiles
        self.shapefileWalls = gpd.read_file(args.walls)
        self.shapefileStructures = gpd.read_file(args.structures)

        # read in pointcloud data, build pointcloud array
        self.pc = laspy.read(args.input)
        self.pc_array = np.vstack([self.pc.x, self.pc.y, self.pc.z]).transpose()
        if not args.all:
            self.pc_array = self.pc_array[::100] # Randomly reducing the points by a factor of 100

        # get colors for each point
        self.colors = np.vstack([self.pc.red/2**16, self.pc.green/2**16, self.pc.blue/2**16]).transpose()

        self.nCoords = self.pc_array.shape[0]
        self.nElem = self.pc_array.shape[1]

        # presort points into each wall component, so we do not have to do it everytime we change category
        if args.wallsfile: # read in preprocessed points
            with open(args.wallsfile, 'rb') as fp:
                ptsWalls = pickle.load(fp)
        elif args.boundaries: # process the points, based on either polygons or bounding boxes
            ptsWalls = realBoundary(self.shapefileWalls, self.pc_array)
        else:
            ptsWalls = boundingBox(self.shapefileWalls, self.pc_array)

        if args.structuresfile: # read in preprocessed points
            with open(args.structuresfile, 'rb') as fp:
                ptsStructures = pickle.load(fp)
        elif args.boundaries: # process the points, based on either polygons or bounding boxes
            ptsStructures = realBoundary(self.shapefileStructures, self.pc_array)
        else:
            ptsStructures = boundingBox(self.shapefileStructures, self.pc_array)

        # remove wall entries that have no points in them
        mask = sorted((i for i, pt in enumerate(ptsWalls) if len(pt) == 0), reverse=True)
        for i in mask:
            del ptsWalls[i]
            self.shapefileWalls.drop(i, inplace=True)

        # remove structure entries that have no points in them
        mask = sorted((i for i, pt in enumerate(ptsStructures) if len(pt) == 0), reverse=True)
        for i in mask:
            del ptsStructures[i]
            self.shapefileStructures.drop(i, inplace=True)

        # add pts columns to walls shapefile and structures shapefile
        self.shapefileWalls['pts'] = ptsWalls
        self.shapefileStructures['pts'] = ptsStructures
        del ptsWalls
        del ptsStructures

        # building the max height structure column
        self.shapefileStructures['alt_muro'] = pd.to_numeric(self.shapefileStructures['alt_muro_1'], 'coerce')
        self.shapefileStructures['alt'] = self.shapefileStructures[['alt_muro', 'altura_has', 'altura_h_1']].max(axis=1)

        # change thickness from strings to numbers, and removing outliers / entry errors in column
        self.shapefileStructures['grosor_1'] = pd.to_numeric(self.shapefileStructures['grosor_1'], 'coerce')
        self.shapefileStructures.at[self.shapefileStructures[self.shapefileStructures['grosor_1'] == self.shapefileStructures['grosor_1'].max()]['grosor_1'].index[0], 'grosor_1'] /= 10 # fixing incorrectly labeled thickness
        self.shapefileStructures.at[self.shapefileStructures[self.shapefileStructures['grosor_1'] == self.shapefileStructures['grosor_1'].max()]['grosor_1'].index[0], 'grosor_1'] /= 10 # fixing incorrectly labeled thickness
        self.shapefileStructures.at[self.shapefileStructures[self.shapefileStructures['grosor_1'] == self.shapefileStructures['grosor_1'].max()]['grosor_1'].index[0], 'grosor_1'] /= 10 # fixing incorrectly labeled thickness


        self.ren = vtk.vtkRenderer()

        # create actor will all points, with natural color
        self.allPoints = VTKActorWrapper(self.pc_array, colors=self.colors)
        self.ren.AddActor(self.allPoints.actor)

        # dict of lists containing the actors needed for each attribute
        self.attributeActorDict = dict()

        # create the actors for each attribute; we can then turn their visbility on and off
        for attribute in self.attributes:
            if attribute != 'None':
                # is a categorical attribute; will need a legend
                if attribute in self.categoryDict.keys():
                    if attribute == 'Type of Wall/Structure':
                        self.masterListWalls = categorical_arrays(self.shapefileWalls, self.categoryDict[attribute][0])
                        self.masterListStructures = categorical_arrays(self.shapefileStructures, self.categoryDict[attribute][1])
                        self.masterList = self.masterListWalls | self.masterListStructures # merge the two together
                    elif attribute == 'Completeness':
                        self.masterListWalls = categorical_arrays(self.shapefileWalls, self.categoryDict[attribute][0])
                        self.masterListStructures = categorical_arrays(self.shapefileStructures, self.categoryDict[attribute][1])
                        self.masterList = dict()
                        for c in self.masterListStructures.keys():
                            self.masterList[c] = np.concatenate([self.masterListWalls[c], self.masterListStructures[c]], axis=0)
                    elif attribute == 'Time of Construction':
                        self.masterList = categorical_arrays(self.shapefileStructures, self.categoryDict[attribute][1])
                    
                    self.attributeActorDict[attribute] = []

                    self.legendSquare = vtk.vtkCubeSource()
                    self.legendSquare.Update()
                    self.legend = vtk.vtkLegendBoxActor()
                    self.legend.SetNumberOfEntries(len(self.masterList))
                    i = 0
                    for c, arr in self.masterList.items():
                        actorTemp = VTKActorWrapper(arr)
                        actorTemp.actor.GetProperty().SetColor(self.categoryColors[i])
                        
                        self.ren.AddActor(actorTemp.actor)
                        self.attributeActorDict[attribute].append(actorTemp.actor)

                        self.legend.SetEntry(i, self.legendSquare.GetOutput(), c, self.categoryColors[i])
                        i += 1

                    self.legend.GetPositionCoordinate().SetCoordinateSystemToView()
                    self.legend.GetPositionCoordinate().SetValue(0.5, -0.9)
                    self.legend.GetPosition2Coordinate().SetCoordinateSystemToView()
                    self.legend.GetPosition2Coordinate().SetValue(1, -0.5)
                    self.legend.UseBackgroundOn()
                    self.legend.SetBackgroundColor(1, 1, 1)

                    self.ren.AddActor(self.legend)

                    self.attributeActorDict[attribute].append(self.legend)

                    for actor in self.attributeActorDict[attribute]:
                        actor.VisibilityOff()

                # is a numerical attribute; will need a colorbar
                elif attribute in self.numericalDict.keys():
                    if attribute == 'Wall Thickness' or attribute == 'Maximum Conserved Height':
                        minValWalls, maxValWalls = self.shapefileWalls[self.numericalDict[attribute][0]].agg(['min', 'max'])
                        minValStructures, maxValStructures = self.shapefileStructures[self.numericalDict[attribute][1]].agg(['min', 'max'])
                        minVal = min(minValWalls, minValStructures)
                        maxVal = max(maxValWalls, maxValStructures)
                    
                        values = []
                        points = []

                        for i in self.shapefileWalls.index:
                            for pt in self.shapefileWalls['pts'][i]:
                                values.append(self.shapefileWalls[self.numericalDict[attribute][0]][i])
                                points.append(pt)
                        for i in self.shapefileStructures.index:
                            for pt in self.shapefileStructures['pts'][i]:
                                values.append(self.shapefileStructures[self.numericalDict[attribute][1]][i])
                                points.append(pt)

                    elif attribute == 'Maximum Original Height':
                        minVal, maxVal = self.shapefileWalls[self.numericalDict[attribute][0]].agg(['min', 'max'])

                        values = []
                        points = []

                        for i in self.shapefileWalls.index:
                            for pt in self.shapefileWalls['pts'][i]:
                                values.append(self.shapefileWalls[self.numericalDict[attribute][0]][i])
                                points.append(pt)

                    self.attributeActorDict[attribute] = []

                    actorTemp = VTKActorWrapper(np.asarray(points), colors=None, values=np.asarray(values))
                    ctf = vtk.vtkColorTransferFunction()
                    for value, color in zip(np.linspace(minVal, maxVal, len(viridis)), viridis):
                        ctf.AddRGBPoint(value, *color)
                    actorTemp.mapper.SetLookupTable(ctf)

                    self.ren.AddActor(actorTemp.actor)
                    self.attributeActorDict[attribute].append(actorTemp.actor)

                    Colorbar_param = colorbar_param(title=attribute, pos=[0.9, 0.1], height=1000, width=150, nlabels=11)
                    Colorbar = colorbar(ctf, Colorbar_param)
                    self.ren.AddActor2D(Colorbar.get())
                    self.attributeActorDict[attribute].append(Colorbar.get())

                    for actor in self.attributeActorDict[attribute]:
                        actor.VisibilityOff()


        self.ui.vtkWidget.GetRenderWindow().AddRenderer(self.ren)
        self.iren = self.ui.vtkWidget.GetRenderWindow().GetInteractor()

    def screenshotCallback(self):
        save_frame(self.ui.vtkWidget.GetRenderWindow())
        
    def quitCallback(self):
        sys.exit()
    
    def attributeCallback(self, val):
        if self.currAttribute != 'None': # turn off old actors if needed
            for actor in self.attributeActorDict[self.currAttribute]:
                actor.VisibilityOff()
        if val != 'None': # turn on new actors if needed
             for actor in self.attributeActorDict[val]:
                actor.VisibilityOn()

        self.currAttribute = val
        self.ui.vtkWidget.GetRenderWindow().Render()

# used to update current location of camera on GUI
def locationCallback(caller, ev):
    locationCallback.label.setText('Current (X,Y,Z) position:\n' + str(tuple(map(floor, locationCallback.cam.GetPosition()))))


if __name__ == '__main__':
    global args

    parser = argparse.ArgumentParser(description='CS53000 Final Project')
    parser.add_argument('-i', '--input', required=True, type=str, help='Path of the point cloud dataset')
    parser.add_argument('-w', '--walls', required=True, type=str, help='Path of the Walls Shapefile')
    parser.add_argument('-s', '--structures', required=True, type=str, help='Path of the Structures Shapefile')
    parser.add_argument('--wallsfile', required=False, type=str, help='Path of the preprocessed points pkl file for walls')
    parser.add_argument('--structuresfile', required=False, type=str, help='Path of the preprocessed points pkl file for structures')
    parser.add_argument('-a', '--all', action='store_true', help='Use all points instead of reducing')
    parser.add_argument('-b', '--boundaries', action='store_true', help='Calculate and use actual wall boundaries instead of bounding boxes')

    args = parser.parse_args()

    app = QApplication([])
    window = FinalProject()
    window.ui.vtkWidget.GetRenderWindow().SetSize(2048, 2048)
    window.show()
    window.setWindowState(Qt.WindowState.WindowMaximized)  # Maximize the window
    window.iren.Initialize() # Need this line to actually show the render inside Qt

    window.ui.screenshotButton.clicked.connect(window.screenshotCallback)
    window.ui.quitButton.clicked.connect(window.quitCallback)
    window.ui.attributeDropdown.currentTextChanged.connect(window.attributeCallback)

    # make camera location GUI widget change whenever camera finishes changing
    locationCallback.cam = window.ren.GetActiveCamera()
    locationCallback.label = window.ui.positionLabel
    window.iren.AddObserver('EndInteractionEvent', locationCallback)
    window.ui.positionLabel.setText('Current (X,Y,Z) position:\n' + str(tuple(map(floor, window.ren.GetActiveCamera().GetPosition()))))
    
    sys.exit(app.exec())