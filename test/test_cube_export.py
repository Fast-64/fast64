import math
import bpy
from os.path import dirname, abspath
import sys
import mathutils

sys.path.append(dirname(dirname(dirname(abspath(__file__)))))
from fast64 import register

sys.path.append(dirname(dirname(abspath(__file__))))
from fast64_internal.utility import PluginError, applyRotation
from fast64_internal.f3d.f3d_gbi import DLFormat
from fast64_internal.f3d.f3d_material import createF3DMat, getDefaultMaterialPreset
from fast64_internal.f3d.f3d_writer import exportF3DtoC, getWriteMethodFromEnum

register()

def purge_orphans():
    if bpy.app.version >= (3, 0, 0):
        bpy.ops.outliner.orphans_purge(
            do_local_ids=True, do_linked_ids=True, do_recursive=True
        )
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

bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 0))

bpy.ops.object.select_all(action="SELECT")

if bpy.context.mode != "OBJECT":
    bpy.ops.object.mode_set(mode="OBJECT")

allObjs = bpy.context.selected_objects
if len(allObjs) == 0:
    raise PluginError("No objects selected.")
obj = bpy.context.selected_objects[0]
if obj.type != "MESH":
    raise PluginError("Object is not a mesh.")

preset = getDefaultMaterialPreset("Shaded Solid")
createF3DMat(obj, preset)

scaleValue = bpy.context.scene.blenderF3DScale
finalTransform = mathutils.Matrix.Diagonal(mathutils.Vector((scaleValue, scaleValue, scaleValue))).to_4x4()
applyRotation([obj], math.radians(90), "X")

exportPath = bpy.path.abspath(bpy.context.scene.DLExportPath)
dlFormat = DLFormat.Static if bpy.context.scene.DLExportisStatic else DLFormat.Dynamic
texDir = bpy.context.scene.DLTexDir
savePNG = bpy.context.scene.saveTextures
separateTexDef = bpy.context.scene.DLSeparateTextureDef
DLName = "cube"
matWriteMethod = getWriteMethodFromEnum(bpy.context.scene.matWriteMethod)

exportF3DtoC(
    exportPath,
    obj,
    dlFormat,
    finalTransform,
    texDir,
    savePNG,
    separateTexDef,
    DLName,
    matWriteMethod,
)

applyRotation([obj], math.radians(-90), "X")