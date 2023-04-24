import vtk
import numpy as np
import laspy
import vtk.util.numpy_support as vtk_np
import geopandas as gpd

class VTKActorWrapper(object):
    def __init__(self, nparray):
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

        self.mapper = vtk.vtkPolyDataMapper()
        self.mapper.SetInputDataObject(self.pd)

        self.actor = vtk.vtkActor()
        self.actor.SetMapper(self.mapper)
        self.actor.GetProperty().SetRepresentationToPoints()
        # self.actor.GetProperty().SetColor(0.0,1.0,0.0)


shapefile = gpd.read_file(r'.\Latest_versions_2023_03_28\Mawchu_Llacta_walls_2023_03_28_UTM.shp')

pc = laspy.read('Mawchu_LLacta_UTM.las')


pc_array = np.vstack([pc.x, pc.y, pc.z]).transpose()
pc_array = pc_array[::100] # Randomly reducing the points 
                        #  by a factor of 100

def filtered_array(shapefile, pc_array, wall_class = 'Delimitacion de manzana'):
    num = 0
    polygons = []
    for idx, rows in shapefile.iterrows():     
        if rows['clase_rev']== wall_class:
            num = num+1
            polygons.append(rows['geometry'].bounds[:]) # Bounds = (minx, miny, maxx, maxy)
    
    print('Number of walls: ',num)
    polygons = np.asarray(polygons)
    points = []
    for i in range(polygons.shape[0]):
        mask = (pc_array[:,0]>polygons[i,0])*(pc_array[:,0]<polygons[i,2])*(pc_array[:,1]>polygons[i,1])*(pc_array[:,1]<polygons[i,3])
        points.append(pc_array[mask])

    points_arr = np.concatenate(points, axis=0)
    # print(points_arr.shape)
    return points_arr


'''

# num_block = 0
# num_patio = 0
# num_internal = 0
# num_stairs = 0
# num_platform = 0
# num_nd = 0
# num_other =0

# block = []
# patio = []
# internal = []
# stairs = []
# platform = []
# nd = []
# other = []

# for idx, rows in shapefile.iterrows():
#     # print(idx, rows['geometry'].bounds[:]) # Bounds = (minx, miny, maxx, maxy)
#     if rows['clase_rev']=='Delimitacion de manzana':
#         num_block = num_block+1
#         block.append(rows['geometry'].bounds[:])

#     if rows['clase_rev']=='Division de grupo patio':
#         num_patio = num_patio+1
#         patio.append(rows['geometry'].bounds[:])
    
#     if rows['clase_rev']=='Division interna de manzana':
#         num_internal = num_internal+1
#         internal.append(rows['geometry'].bounds[:])

#     if rows['clase_rev']=='Escalera':
#         num_stairs = num_stairs+1
#         stairs.append(rows['geometry'].bounds[:])

#     if rows['clase_rev']=='Muro de plataforma':
#         num_platform = num_platform+1
#         platform.append(rows['geometry'].bounds[:])
    
#     if rows['clase_rev']=='No definido':
#         num_nd = num_nd+1
#         nd.append(rows['geometry'].bounds[:])
    
#     if rows['clase_rev']=='Otro':
#         num_other = num_other+1
#         other.append(rows['geometry'].bounds[:])

# print('Delimitacion de manzana walls: ',num_block)
# print('Division de grupo patio walls: ',num_patio)
# print('Division interna de manzana walls: ',num_internal)
# print('Escalera walls: ',num_stairs)
# print('Muro de plataforma walls: ',num_platform)
# print('No definido walls: ',num_nd)
# print('Otro walls: ',num_other)


# block = np.asarray(block)
# patio = np.asarray(patio)
# internal = np.asarray(internal)
# stairs = np.asarray(stairs)
# platform = np.asarray(platform)
# nd = np.asarray(nd)
# other = np.asarray(other)

# list_array = []
# for i in range(block.shape[0]):
#     mask = (pc_array[:,0]>block[i,0])*(pc_array[:,0]<block[i,2])*(pc_array[:,1]>block[i,1])*(pc_array[:,1]<block[i,3])

#     list_array.append(pc_array[mask])


# array = np.concatenate(list_array, axis=0)
# print(array.shape)
# new_array = array
'''
points_array = filtered_array(shapefile=shapefile, pc_array=pc_array, wall_class='Division de grupo patio')
new_actor = VTKActorWrapper(points_array)
new_actor = new_actor.actor
new_actor.GetProperty().SetColor(1.0,0.0,0.0)

actor1 = VTKActorWrapper(pc_array)
actor1 = actor1.actor

ren = vtk.vtkRenderer()
ren.AddActor(actor1)
ren.AddActor(new_actor)

window = vtk.vtkRenderWindow()
window.AddRenderer(ren)
window.SetSize(1000,1000)

interactor =vtk.vtkRenderWindowInteractor()
interactor.SetRenderWindow(window)
interactor.Initialize()

window.Render()
interactor.Start()

