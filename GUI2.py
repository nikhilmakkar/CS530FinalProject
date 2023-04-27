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


from PyQt6.QtWidgets import QApplication, QWidget, QMainWindow, QComboBox, QGridLayout, QLabel, QPushButton
from PyQt6.QtCore import Qt
from vtk.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor

class VTKActorWrapper(object):
    def __init__(self, nparray, colors=None, values=None):
        super(VTKActorWrapper, self).__init__()

        self.nparray = nparray

        nCoords = nparray.shape[0]
        nElem = nparray.shape[1]

        self.verts = vtk.vtkPoints()
        self.cells = vtk.vtkCellArray()
        self.scalars = None

        self.pd = vtk.vtkPolyData()
        self.verts.SetData(vtk_np.numpy_to_vtk(nparray))
        self.cells_npy = np.vstack([np.ones(nCoords,dtype=np.int64),
                               np.arange(nCoords,dtype=np.int64)]).T.flatten()
        self.cells.SetCells(nCoords,vtk_np.numpy_to_vtkIdTypeArray(self.cells_npy))
        self.pd.SetPoints(self.verts)
        self.pd.SetVerts(self.cells)
        if colors is not None:
            self.pd.GetPointData().SetScalars(vtk_np.numpy_to_vtk(colors))
        elif values is not None:
            self.pd.GetPointData().SetScalars(vtk_np.numpy_to_vtk(values))

        self.mapper = vtk.vtkPolyDataMapper()
        self.mapper.SetInputDataObject(self.pd)
        if colors is not None:
            self.mapper.SetColorModeToDirectScalars()

        self.actor = vtk.vtkActor()
        self.actor.SetMapper(self.mapper)
        self.actor.GetProperty().SetRepresentationToPoints()

frame_counter = 0

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

def categorical_arrays(shapefile, header):
    return shapefile.groupby(header)['pts'].agg(lambda x: np.concatenate(x.values, axis=0)).to_dict()

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

def realBoundary(shapefile, pc_array):
    with concurrent.futures.ProcessPoolExecutor() as executor:
        pts = [i for i in executor.map(parallelFunction, [[pg, pc_array] for pg in shapefile['geometry']])]
    return pts

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
        self.attributes = ['None', 'Type of Wall', 'Completeness', 'Wall Thickness', 'Maximum Original Height', 'Maximum Conserved Height']
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

class MouseInteractorStyle(vtk.vtkInteractorStyleTrackballCamera):
    def __init__(self, data):
        self.AddObserver('LeftButtonPressEvent', self.left_button_press_event)
        self.data = data
        self.selected_mapper = vtk.vtkDataSetMapper()
        self.selected_actor = vtk.vtkActor()

        self.selected_mapper2 = vtk.vtkDataSetMapper()
        self.selected_actor2 = vtk.vtkActor()
        
        self.vtk_list = vtk.vtkIdList()
        # self.locator = vtk.vtkPointLocator()
        self.locator = vtk.vtkStaticPointLocator()
        self.locator.SetDataSet(self.data)
        self.locator.BuildLocator()
        # self.radius=0.02
        self.radius=10
        self.pointsize=2

    def left_button_press_event(self, obj, event):
                
        pos = self.GetInteractor().GetEventPosition()

        self.picker = vtk.vtkCellPicker()
        self.picker.SetTolerance(0.001)

        # Pick from this location.
        self.picker.Pick(pos[0], pos[1], 0, self.GetDefaultRenderer())

        self.world_position = self.picker.GetPickPosition()
        # print(f'Cell id is: {self.picker.GetCellId()}')
        
        self.locator.FindPointsWithinRadius(self.radius, self.world_position, self.vtk_list)
        # print(self.vtk_list)

        if self.picker.GetCellId() != -1:
            # print(f'Pick position is: ({self.world_position[0]:.6g}, {self.world_position[1]:.6g}, {self.world_position[2]:.6g})')

            ids = vtk.vtkIdTypeArray()
            ids.SetNumberOfComponents(1)
            ids.InsertNextValue(self.picker.GetCellId())
            # print(ids,'\n')

            selection_node = vtk.vtkSelectionNode()
            selection_node.SetFieldType(vtk.vtkSelectionNode.CELL)
            selection_node.SetContentType(vtk.vtkSelectionNode.INDICES)
            selection_node.SetSelectionList(ids)

            selection = vtk.vtkSelection()
            selection.AddNode(selection_node)

            extract_selection = vtk.vtkExtractSelection()
            extract_selection.SetInputData(0, self.data)
            extract_selection.SetInputData(1, selection)
            extract_selection.Update()

            # In selection
            selected = vtk.vtkUnstructuredGrid()
            selected.ShallowCopy(extract_selection.GetOutput())

            # print(f'Number of points in the selection: {selected.GetNumberOfPoints()}')
            # print(f'Number of cells in the selection : {selected.GetNumberOfCells()}\n')

            # print('########################\n') 

            self.selected_mapper.SetInputData(selected)
            self.selected_actor.SetMapper(self.selected_mapper)

            # self.selected_actor.GetProperty().SetColor(self.colors.GetColor3d('Black'))
            self.selected_actor.GetProperty().SetPointSize(self.pointsize)

            self.GetInteractor().GetRenderWindow().GetRenderers().GetFirstRenderer().AddActor(self.selected_actor)
            
            
            ids2 = vtk.vtkIdTypeArray()
            ids2.SetNumberOfComponents(1)

            for i in range(self.vtk_list.GetNumberOfIds()):
                ids2.InsertNextValue(self.vtk_list.GetId(i))

            selection_node2 = vtk.vtkSelectionNode()
            selection_node2.SetFieldType(vtk.vtkSelectionNode.CELL)
            selection_node2.SetContentType(vtk.vtkSelectionNode.INDICES)
            selection_node2.SetSelectionList(ids2)

            selection2 = vtk.vtkSelection()
            selection2.AddNode(selection_node2)

            extract_selection2 = vtk.vtkExtractSelection()
            extract_selection2.SetInputData(0, self.data)
            extract_selection2.SetInputData(1, selection2)
            extract_selection2.Update()
            
    #         # In selection
            selected2 = vtk.vtkUnstructuredGrid()
            selected2.ShallowCopy(extract_selection2.GetOutput())

            # print(f'Number of neighboring points: {selected2.GetNumberOfPoints()}')
    #         # print(f'Number of neighboring cells: {selected2.GetNumberOfCells()}\n')
            # print('########################\n') 

            self.selected_mapper2.SetInputData(selected2)
            self.selected_actor2.SetMapper(self.selected_mapper2)     
            self.selected_actor2.GetProperty().SetPointSize(self.pointsize)
            self.GetInteractor().GetRenderWindow().GetRenderers().GetFirstRenderer().AddActor(self.selected_actor2)
        # Forward events
        self.OnLeftButtonDown()

class FinalProject(QMainWindow):
    def __init__(self, parent = None):
        QMainWindow.__init__(self, parent)
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)

        self.attributes = self.ui.attributes

        # for use later
        self.currAttribute = 'None'
        self.numericalDict = {'Wall Thickness': 'grosor', 'Maximum Original Height': 'alt_max', 'Maximum Conserved Height': 'alt_cons'}
        self.categoryDict = {'None': 'None', 'Type of Wall': 'clase_rev', 'Completeness': 'preserva_1'}
        self.categoryColors = [(235, 172, 35), (184, 0, 88), (0, 140, 249), (0, 110, 0), (0, 187, 173), (209, 99, 230), (89, 84, 214), (178, 69, 2), (255, 146, 135), (0, 198, 248), (135, 133, 0), (0, 167, 108), (189, 189, 189)]
        self.categoryColors = [tuple(j/255 for j in i) for i in self.categoryColors]

        viridis = [[0.267004, 0.004874, 0.329415], [0.282656, 0.100196, 0.42216], [0.277134, 0.185228, 0.489898], [0.253935, 0.265254, 0.529983], [0.221989, 0.339161, 0.548752], [0.190631, 0.407061, 0.556089], [0.163625, 0.471133, 0.558148], [0.139147, 0.533812, 0.555298], [0.120565, 0.596422, 0.543611], [0.134692, 0.658636, 0.517649], [0.20803, 0.718701, 0.472873], [0.327796, 0.77398, 0.40664], [0.477504, 0.821444, 0.318195], [0.647257, 0.8584, 0.209861], [0.82494, 0.88472, 0.106217], [0.993248, 0.906157, 0.143936]]

        self.shapefile = gpd.read_file(args.shapefile)

        self.pc = laspy.read(args.input)
        self.pc_array = np.vstack([self.pc.x, self.pc.y, self.pc.z]).transpose()
        if not args.full:
            self.pc_array = self.pc_array[::100] # Randomly reducing the points by a factor of 100

        self.colors = np.vstack([self.pc.red/2**16, self.pc.green/2**16, self.pc.blue/2**16]).transpose()

        self.nCoords = self.pc_array.shape[0]
        self.nElem = self.pc_array.shape[1]

        # presort points into each wall component, so we do not have to do it everytime we change category
        if args.boundaries:
            pts = realBoundary(self.shapefile, self.pc_array)
        else:
            pts = boundingBox(self.shapefile, self.pc_array)

        mask = sorted((i for i, pt in enumerate(pts) if len(pt) == 0), reverse=True)
        for i in mask:
            del pts[i]
            self.shapefile.drop(i, inplace=True)

        self.shapefile['pts'] = pts

        self.ren = vtk.vtkRenderer()

        self.allPoints = VTKActorWrapper(self.pc_array, colors=self.colors)
        self.ren.AddActor(self.allPoints.actor)


        self.style = MouseInteractorStyle(self.allPoints.pd)
        self.style.SetDefaultRenderer(self.ren)

        # dict of lists containing the actors needed for each attribute
        self.attributeActorDict = dict()

        # create the actors for each attribute; we can then turn their visbility on and off
        for attribute in self.attributes:
            if attribute != 'None':
                if attribute in self.categoryDict.keys(): # is a categorical attribute
                    self.masterList = categorical_arrays(self.shapefile, self.categoryDict[attribute])
                    
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
                elif attribute in self.numericalDict.keys(): # is a numerical attribute
                    self.attributeActorDict[attribute] = []

                    minVal, maxVal = self.shapefile[self.numericalDict[attribute]].agg(['min', 'max'])

                    values = []
                    points = []

                    for i in self.shapefile.index:
                        for pt in self.shapefile['pts'][i]:
                            values.append(self.shapefile['grosor'][i])
                            points.append(pt)

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

# used to update current location of camera
def locationCallback(caller, ev):
    locationCallback.label.setText('Current (X,Y,Z) position:\n' + str(tuple(map(floor, locationCallback.cam.GetPosition()))))


if __name__ == '__main__':
    global args

    parser = argparse.ArgumentParser(description='CS53000 Final Project')
    parser.add_argument('-i', '--input', required=True, type=str, help='Path of the LiDAR point cloud dataset')
    parser.add_argument('-s', '--shapefile', required=True, type=str, help='Path of the Walls Shapefile')
    parser.add_argument('-f', '--full', action='store_true', help='Use all points instead of reducing')
    parser.add_argument('-b', '--boundaries', action='store_true', help='Use actual wall boundaries instead of bounding boxes')

    args = parser.parse_args()

    app = QApplication([])
    window = FinalProject()
    window.ui.vtkWidget.GetRenderWindow().SetSize(2048, 2048)
    
    window.show()
    window.setWindowState(Qt.WindowState.WindowMaximized)  # Maximize the window
    window.iren.Initialize() # Need this line to actually show the render inside Qt
    window.iren.SetInteractorStyle(window.style)

    window.ui.screenshotButton.clicked.connect(window.screenshotCallback)
    window.ui.quitButton.clicked.connect(window.quitCallback)
    window.ui.attributeDropdown.currentTextChanged.connect(window.attributeCallback)

    locationCallback.cam = window.ren.GetActiveCamera()
    locationCallback.label = window.ui.positionLabel
    window.iren.AddObserver('EndInteractionEvent', locationCallback)
    window.ui.positionLabel.setText('Current (X,Y,Z) position:\n' + str(tuple(map(floor, window.ren.GetActiveCamera().GetPosition()))))
    
    sys.exit(app.exec())