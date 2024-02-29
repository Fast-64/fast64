import math
import bpy
from bpy_types import PropertyGroup
import mathutils
from ..f3d.f3d_gbi import get_F3D_GBI
from ..f3d.f3d_material import createF3DMat
from ..f3d.f3d_parser import F3DContext, getImportData, parseF3D
from ..panels import MK64_Panel
from ..utility import applyRotation, prop_split
from bpy.utils import register_class, unregister_class
from ..utility import raisePluginError

class MK64_Properties(PropertyGroup):
    """Global MK64 Scene Properties found under scene.fast64.mk64"""

    version: bpy.props.IntProperty(name="MK64_Properties Version", default=0)

def importMeshC(
    data: str,
    name: str,
    scale: float,
    removeDoubles: bool,
    importNormals: bool,
    drawLayer: str,
    f3dContext: F3DContext,
    callClearMaterial: bool = True,
) -> bpy.types.Object:
    mesh = bpy.data.meshes.new(name + "_mesh")
    obj = bpy.data.objects.new(name + "_mesh", mesh)
    bpy.context.collection.objects.link(obj)

    f3dContext.mat().draw_layer.oot = drawLayer
    transformMatrix = mathutils.Matrix.Scale(1 / scale, 4)

    parseF3D(data, name, transformMatrix, name, name, "oot", drawLayer, f3dContext, True)
    f3dContext.createMesh(obj, removeDoubles, importNormals, callClearMaterial)

    applyRotation([obj], math.radians(-90), "X")
    return obj

class MK64_ImportCourseDL(bpy.types.Operator):
    # set bl_ properties
    bl_idname = "object.f3d_import_dl"
    bl_label = "Import DL"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    # Called on demand (i.e. button press, menu item)
    # Can also be called from operator search menu (Spacebar)
    def execute(self, context):
        obj = None
        if context.mode != "OBJECT":
            bpy.ops.object.mode_set(mode="OBJECT")

        try:
            name = context.scene.DLImportName
            importPath = bpy.path.abspath(context.scene.DLImportPath)
            basePath = bpy.path.abspath(context.scene.DLImportBasePath)
            scaleValue = context.scene.blenderF3DScale

            removeDoubles = context.scene.DLRemoveDoubles
            importNormals = context.scene.DLImportNormals
            drawLayer = context.scene.DLImportDrawLayer

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

            self.report({"INFO"}, "Success!")
            return {"FINISHED"}

        except Exception as e:
            if context.mode != "OBJECT":
                bpy.ops.object.mode_set(mode="OBJECT")
            raisePluginError(self, e)
            return {"CANCELLED"}  # must return a set


class MK64_ImportCourseDLPanel(MK64_Panel):
    bl_idname = "MK64_import_course_DL_panel_settings"
    bl_label = "MK64 Import Course DL Panel Settings"
    bl_options = set()  # default to open
    bl_order = 0  # force to front

    @classmethod
    def poll(cls, context):
        return True

    # called every frame
    def draw(self, context):
        col = self.layout.column()
        col.scale_y = 1.1  # extra padding

        col.operator(MK64_ImportCourseDL.bl_idname)
        prop_split(col, context.scene, "DLImportName", "Name")
        prop_split(col, context.scene, "DLImportPath", "File")
        prop_split(col, context.scene, "DLImportBasePath", "Base Path")
        prop_split(col, context.scene, "blenderF3DScale", "Scale")
        prop_split(col, context.scene, "DLImportDrawLayer", "Draw Layer")
        col.prop(context.scene, "DLRemoveDoubles")
        col.prop(context.scene, "DLImportNormals")

        box = col.box().column()
        box.label(text="All data must be contained within file.")
        box.label(text="The only exception are pngs converted to inc.c.")

        # col.template_list('F3D_UL_ImportDLPathList', '', context.scene,
        # 	'DLImportOtherFiles', context.scene, 'DLImportOtherFilesIndex')




mk64_classes = (MK64_Properties,)

mk64_panel_classes = (
    MK64_ImportCourseDL,
    MK64_ImportCourseDLPanel,
)

def mk64_panel_register():
    for cls in mk64_panel_classes:
        register_class(cls)

def mk64_panel_unregister():
    for cls in mk64_panel_classes:
        unregister_class(cls)

def mk64_register(registerPanels):
    for cls in mk64_classes:
        register_class(cls)
    if registerPanels:
        mk64_panel_register()

def mk64_unregister(registerPanel):
    for cls in reversed(mk64_classes):
        unregister_class(cls)
    if registerPanel:
        mk64_panel_unregister()