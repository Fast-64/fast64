import math
import bpy
from os.path import dirname, abspath
import sys

sys.path.append(dirname(dirname(dirname(abspath(__file__)))))
from fast64 import register

sys.path.append(dirname(dirname(abspath(__file__))))
from fast64_internal.f3d.f3d_gbi import get_F3D_GBI
from fast64_internal.f3d.f3d_material import createF3DMat
from fast64_internal.f3d.f3d_parser import F3DContext, getImportData, importMeshC

register()


def purge_orphans():
    if bpy.app.version >= (3, 0, 0):
        bpy.ops.outliner.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)
    else:
        # call purge_orphans() recursively until there are no more orphan data blocks to purge
        result = bpy.ops.outliner.orphans_purge()
        if result.pop() != "CANCELLED":
            purge_orphans()


def clean_scene():
    """
    Removing all of the objects, collection, materials, particles,
    textures, images, curves, meshes, actions, nodes, and worlds from the scene
    """
    if bpy.context.active_object and bpy.context.active_object.mode == "EDIT":
        bpy.ops.object.editmode_toggle()

    for obj in bpy.data.objects:
        obj.hide_set(False)
        obj.hide_select = False
        obj.hide_viewport = False

    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete()

    collection_names = [col.name for col in bpy.data.collections]
    for name in collection_names:
        bpy.data.collections.remove(bpy.data.collections[name])

    # in the case when you modify the world shader
    world_names = [world.name for world in bpy.data.worlds]
    for name in world_names:
        bpy.data.worlds.remove(bpy.data.worlds[name])
    # create a new world data block
    bpy.ops.world.new()
    bpy.context.scene.world = bpy.data.worlds["World"]

    purge_orphans()


clean_scene()

obj = None
if bpy.context.mode != "OBJECT":
    bpy.ops.object.mode_set(mode="OBJECT")

name = "cube_Cube_mesh"
importPath = "./cube/model.inc.c"
basePath = bpy.path.abspath(bpy.context.scene.DLImportBasePath)
scaleValue = bpy.context.scene.blenderF3DScale

removeDoubles = bpy.context.scene.DLRemoveDoubles
importNormals = bpy.context.scene.DLImportNormals
drawLayer = bpy.context.scene.DLImportDrawLayer

data = getImportData([importPath])

importMeshC(
    data,
    name,
    scaleValue,
    removeDoubles,
    importNormals,
    drawLayer,
    F3DContext(get_F3D_GBI(), basePath, createF3DMat(None)),
)
