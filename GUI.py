import vtk
import numpy as np
import laspy
import vtk.util.numpy_support as vtk_np
import argparse
import sys
from math import floor

from PyQt6.QtWidgets import QApplication, QWidget, QMainWindow, QComboBox, QGridLayout, QLabel, QPushButton
from PyQt6.QtCore import Qt
from vtk.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor

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
        attributes = ['None', 'Type of Wall/Structure', 'Height of Existing Wall', 'Height of Original Wall', 'Completeness', 'Width']
        self.attributeDropdown.addItems(attributes)

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

        # for use later
        self.currAttribute = 'None'

        self.pc = laspy.read(args.input)
        self.pc_array = np.vstack([self.pc.x, self.pc.y, self.pc.z]).transpose()
        # self.pc_array = self.pc_array[::100] # Randomly reducing the points by a factor of 100
        # print(self.pc_array.shape)
        # print(self.pc_array[0])

        self.nCoords = self.pc_array.shape[0]
        self.nElem = self.pc_array.shape[1]

        self.verts = vtk.vtkPoints()
        self.cells = vtk.vtkCellArray()
        self.scalars = None

        self.pd = vtk.vtkPolyData()

        self.verts.SetData(vtk_np.numpy_to_vtk(self.pc_array))

        self.cells_npy = np.vstack([np.ones(self.nCoords,dtype=np.int64),
                        np.arange(self.nCoords,dtype=np.int64)]).T.flatten()
        # print(self.cells_npy.shape)

        self.cells.SetCells(self.nCoords,vtk_np.numpy_to_vtkIdTypeArray(self.cells_npy))

        self.pd.SetPoints(self.verts)
        self.pd.SetVerts(self.cells)

        self.mapper = vtk.vtkPolyDataMapper()
        self.mapper.SetInputDataObject(self.pd)

        self.actor = vtk.vtkActor()
        self.actor.SetMapper(self.mapper)
        self.actor.GetProperty().SetRepresentationToPoints()
        self.actor.GetProperty().SetColor(0.0,1.0,0.0)

        self.ren = vtk.vtkRenderer()
        self.ren.AddActor(self.actor)

        self.ui.vtkWidget.GetRenderWindow().AddRenderer(self.ren)
        self.iren = self.ui.vtkWidget.GetRenderWindow().GetInteractor()

    def screenshotCallback(self):
        save_frame(self.ui.vtkWidget.GetRenderWindow())
        
    def quitCallback(self):
        sys.exit()
    
    def attributeCallback(self, val):
        self.currAttribute = val
        self.ui.vtkWidget.GetRenderWindow().Render()

# used to update current location of camera
def locationCallback(caller, ev):
    locationCallback.label.setText('Current (X,Y,Z) position:\n' + str(tuple(map(floor, locationCallback.cam.GetPosition()))))


if __name__ == '__main__':
    global args

    parser = argparse.ArgumentParser(description='CS53000 Final Project')
    parser.add_argument('-i', '--input', required=True, type=str, help='Path of the LiDAR point cloud dataset')

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

    locationCallback.cam = window.ren.GetActiveCamera()
    locationCallback.label = window.ui.positionLabel
    window.iren.AddObserver('EndInteractionEvent', locationCallback)
    window.ui.positionLabel.setText('Current (X,Y,Z) position:\n' + str(tuple(map(floor, window.ren.GetActiveCamera().GetPosition()))))
    
    sys.exit(app.exec())