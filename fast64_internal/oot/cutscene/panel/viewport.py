import os
from bpy.path import abspath
from bpy.ops import object
from bpy.props import StringProperty
from bpy.types import Scene, Operator, Context
from bpy.utils import register_class, unregister_class
from ....utility import PluginError, writeCData, raisePluginError, prop_split
from ....panels import OOT_Panel
from ...oot_cutscene import ootCutsceneIncludes, ootCutsceneDataToC, convertCutsceneObject


#############
# Operators #
#############
def checkGetFilePaths(context: Context):
    cpath = abspath(context.scene.ootCutsceneExportPath)

    if not cpath.endswith(".c"):
        raise PluginError("Output file must end with .c")

    hpath = cpath[:-1] + "h"
    headerfilename = os.path.basename(hpath)

    return cpath, hpath, headerfilename


class OOT_ExportCutscene(Operator):
    bl_idname = "object.oot_export_cutscene"
    bl_label = "Export Cutscene"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    def execute(self, context):
        try:
            if context.mode != "OBJECT":
                object.mode_set(mode="OBJECT")

            activeObj = context.view_layer.objects.active

            if activeObj is None or activeObj.data is not None or activeObj.ootEmptyType != "Cutscene":
                raise PluginError("You must select a cutscene object")

            if activeObj.parent is not None:
                raise PluginError("Cutscene object must not be parented to anything")

            cpath, hpath, headerfilename = checkGetFilePaths(context)
            csdata = ootCutsceneIncludes(headerfilename)
            converted = convertCutsceneObject(activeObj)
            csdata.append(ootCutsceneDataToC(converted, converted.name))
            writeCData(csdata, hpath, cpath)

            self.report({"INFO"}, "Successfully exported cutscene")
            return {"FINISHED"}
        except Exception as e:
            raisePluginError(self, e)
            return {"CANCELLED"}


class OOT_ExportAllCutscenes(Operator):
    bl_idname = "object.oot_export_all_cutscenes"
    bl_label = "Export All Cutscenes"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    def execute(self, context):
        try:
            if context.mode != "OBJECT":
                object.mode_set(mode="OBJECT")
            cpath, hpath, headerfilename = checkGetFilePaths(context)
            csdata = ootCutsceneIncludes(headerfilename)
            count = 0
            for obj in context.view_layer.objects:
                if obj.data is not None or obj.ootEmptyType != "Cutscene":
                    continue
                if obj.parent is not None:
                    raise PluginError("Cutscene object must not be parented to anything")
                converted = convertCutsceneObject(obj)
                csdata.append(ootCutsceneDataToC(converted, converted.name))
                count += 1
            if count == 0:
                raise PluginError("Could not find any cutscenes to export")
            writeCData(csdata, hpath, cpath)
            self.report({"INFO"}, "Successfully exported " + str(count) + " cutscenes")
            return {"FINISHED"}
        except Exception as e:
            raisePluginError(self, e)
            return {"CANCELLED"}


#############
#   Panel   #
#############
class OOT_CutscenePanel(OOT_Panel):
    bl_idname = "OOT_PT_export_cutscene"
    bl_label = "OOT Cutscene Exporter"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "OOT"

    def draw(self, context):
        col = self.layout.column()
        col.operator(OOT_ExportCutscene.bl_idname)
        col.operator(OOT_ExportAllCutscenes.bl_idname)
        prop_split(col, context.scene, "ootCutsceneExportPath", "File")


oot_cutscene_panel_classes = [
    OOT_CutscenePanel,
]

oot_cutscene_classes = [
    OOT_ExportCutscene,
    OOT_ExportAllCutscenes,
]


def oot_cutscene_panel_register():
    for cls in oot_cutscene_panel_classes:
        register_class(cls)


def oot_cutscene_panel_unregister():
    for cls in oot_cutscene_panel_classes:
        unregister_class(cls)


def oot_cutscene_register():
    for cls in oot_cutscene_classes:
        register_class(cls)

    Scene.ootCutsceneExportPath = StringProperty(name="File", subtype="FILE_PATH")


def oot_cutscene_unregister():
    for cls in reversed(oot_cutscene_classes):
        unregister_class(cls)

    del Scene.ootCutsceneExportPath
