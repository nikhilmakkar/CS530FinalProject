import vtk
import numpy as np
import laspy
import vtk.util.numpy_support as vtk_np
# import open3d as o3d


pc = laspy.read('C:/Users/tanne/Desktop/VisualizationFinalProjectData/Mawchu_LLacta_UTM.las')
# pc = laspy.read('2.las')

pc_array = np.vstack([pc.x, pc.y, pc.z]).transpose()
# pc_array = pc_array[::100] # Randomly reducing the points 
                        #  by a factor of 100
print(pc_array.shape)
print(pc_array[0])

colors = np.vstack([pc.red/2**16, pc.green/2**16, pc.blue/2**16]).transpose()

nCoords = pc_array.shape[0]
nElem = pc_array.shape[1]

verts = vtk.vtkPoints()
cells = vtk.vtkCellArray()
scalars = None

pd = vtk.vtkPolyData()

verts.SetData(vtk_np.numpy_to_vtk(pc_array))

cells_npy = np.vstack([np.ones(nCoords,dtype=np.int64),
                np.arange(nCoords,dtype=np.int64)]).T.flatten()
print(cells_npy.shape)

cells.SetCells(nCoords,vtk_np.numpy_to_vtkIdTypeArray(cells_npy))

pd.SetPoints(verts)
pd.SetVerts(cells)
pd.GetPointData().SetScalars(vtk_np.numpy_to_vtk(colors))

mapper = vtk.vtkPolyDataMapper()
mapper.SetInputDataObject(pd)
mapper.SetColorModeToDirectScalars()

actor = vtk.vtkActor()
actor.SetMapper(mapper)
actor.GetProperty().SetRepresentationToPoints()

ren = vtk.vtkRenderer()
ren.AddActor(actor)

window = vtk.vtkRenderWindow()
window.AddRenderer(ren)
# window.SetSize(1000,1000)

interactor =vtk.vtkRenderWindowInteractor()
interactor.SetRenderWindow(window)
interactor.Initialize()

window.Render()
interactor.Start()