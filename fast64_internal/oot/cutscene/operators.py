import os
from bpy.path import abspath
from bpy.ops import object
from bpy.props import StringProperty, EnumProperty, IntProperty
from bpy.types import Scene, Operator, Context, UILayout
from bpy.utils import register_class, unregister_class
from ...utility import CData, PluginError, writeCData, raisePluginError
from ..oot_constants import ootEnumCSTextboxType, ootEnumCSListType, ootEnumCSListTypeIcons
from ..oot_utility import getCollection
from ..scene.exporter.to_c import ootCutsceneDataToC
from .exporter import convertCutsceneObject


def checkGetFilePaths(context: Context):
    cpath = abspath(context.scene.ootCutsceneExportPath)

    if not cpath.endswith(".c"):
        raise PluginError("Output file must end with .c")

    hpath = cpath[:-1] + "h"
    headerfilename = os.path.basename(hpath)

    return cpath, hpath, headerfilename


def ootCutsceneIncludes(headerfilename):
    ret = CData()
    ret.source = (
        '#include "ultra64.h"\n'
        + '#include "z64.h"\n'
        + '#include "macros.h"\n'
        + '#include "command_macros_base.h"\n'
        + '#include "z64cutscene_commands.h"\n\n'
        + '#include "'
        + headerfilename
        + '"\n\n'
    )
    return ret


def drawCSListAddOp(layout: UILayout, objName: str, collectionType):
    def addButton(row):
        nonlocal l
        op = row.operator(OOTCSListAdd.bl_idname, text=ootEnumCSListType[l][1], icon=ootEnumCSListTypeIcons[l])
        op.collectionType = collectionType
        op.listType = ootEnumCSListType[l][0]
        op.objName = objName
        l += 1

    box = layout.column(align=True)
    l = 0
    row = box.row(align=True)
    row.label(text="Add:")
    addButton(row)
    for _ in range(3):
        row = box.row(align=True)
        for _ in range(3):
            addButton(row)
    box.label(text="Install zcamedit for camera/actor motion.")


class OOTCSTextboxAdd(Operator):
    bl_idname = "object.oot_cstextbox_add"
    bl_label = "Add CS Textbox"
    bl_options = {"REGISTER", "UNDO"}

    collectionType: StringProperty()
    textboxType: EnumProperty(items=ootEnumCSTextboxType)
    listIndex: IntProperty()
    objName: StringProperty()

    def execute(self, context):
        collection = getCollection(self.objName, self.collectionType, self.listIndex)
        newTextboxElement = collection.add()
        newTextboxElement.textboxType = self.textboxType
        return {"FINISHED"}


class OOTCSListAdd(Operator):
    bl_idname = "object.oot_cslist_add"
    bl_label = "Add CS List"
    bl_options = {"REGISTER", "UNDO"}

    collectionType: StringProperty()
    listType: EnumProperty(items=ootEnumCSListType)
    objName: StringProperty()

    def execute(self, context):
        collection = getCollection(self.objName, self.collectionType, None)
        newList = collection.add()
        newList.listType = self.listType
        return {"FINISHED"}


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


oot_cutscene_classes = (
    OOTCSTextboxAdd,
    OOTCSListAdd,
    OOT_ExportCutscene,
    OOT_ExportAllCutscenes,
)


def cutscene_ops_register():
    for cls in oot_cutscene_classes:
        register_class(cls)

    Scene.ootCutsceneExportPath = StringProperty(name="File", subtype="FILE_PATH")


def cutscene_ops_unregister():
    for cls in reversed(oot_cutscene_classes):
        unregister_class(cls)

    del Scene.ootCutsceneExportPath
