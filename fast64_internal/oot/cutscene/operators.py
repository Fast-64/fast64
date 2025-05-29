import os
import re
import bpy

from bpy.path import abspath
from bpy.ops import object
from bpy.props import StringProperty, EnumProperty, IntProperty
from bpy.types import Scene, Operator, Context
from bpy.utils import register_class, unregister_class
from ...utility import CData, PluginError, writeCData, raisePluginError
from ...game_data import game_data
from ..collection_utility import getCollection
from .constants import ootEnumCSTextboxType, ootEnumCSListType
from .importer import importCutsceneData
from .exporter import getNewCutsceneExport
from ..exporter.cutscene import Cutscene


def checkGetFilePaths(context: Context):
    cpath = abspath(context.scene.ootCutsceneExportPath)

    if not cpath.endswith(".c"):
        raise PluginError("Output file must end with .c")

    hpath = cpath[:-1] + "h"
    headerfilename = os.path.basename(hpath)

    return cpath, hpath, headerfilename


def ootCutsceneIncludes(headerfilename):
    ret = CData()

    ret.header = (
        f"#ifndef {headerfilename.removesuffix('.h').upper()}_H\n"
        + f"#define {headerfilename.removesuffix('.h').upper()}_H\n\n"
    )

    if bpy.context.scene.fast64.oot.is_globalh_present():
        ret.header += (
            '#include "ultra64.h"\n'
            + '#include "z64.h"\n'
            + '#include "macros.h"\n'
            + '#include "command_macros_base.h"\n'
            + '#include "z64cutscene_commands.h"\n\n'
        )
    else:
        ret.header += (
            '#include "ultra64.h"\n'
            + '#include "sequence.h"\n'
            + '#include "z64math.h"\n'
            + '#include "z64cutscene.h"\n'
            + '#include "z64cutscene_commands.h"\n'
            + '#include "z64ocarina.h"\n'
            + '#include "z64player.h"\n\n'
        )

    if len(headerfilename) > 0:
        ret.source = f'#include "{headerfilename}"\n\n'
    return ret


def insertCutsceneData(filePath: str, csName: str):
    """Inserts the motion data in the cutscene and returns the new data"""
    fileLines = []

    # if the file is not found then it's likely a new file that needs to be created
    try:
        with open(filePath, "r") as inputFile:
            fileLines = inputFile.readlines()
    except FileNotFoundError:
        fileLines = []

    foundCutscene = False
    motionExporter = getNewCutsceneExport(csName)
    beginIndex = 0

    for i, line in enumerate(fileLines):
        # skip commented lines and preprocessor directives
        if not line.startswith("//") and not line.startswith("/*") and not line.startswith("#"):
            if f"CutsceneData {csName}" in line:
                foundCutscene = True

            if foundCutscene:
                if "CS_HEADER" in line:
                    # save the index of the line that contains the entry total and the framecount for later use
                    beginIndex = i

                # looking at next line to see if we reached the end of the cs script
                index = i + 1
                if index < len(fileLines) and "CS_END_OF_SCRIPT" in fileLines[index]:
                    # exporting first to get the new framecount and the total of entries values
                    fileLines.insert(index, motionExporter.getExportData())

                    # update framecount and entry total values
                    beginLine = fileLines[beginIndex]
                    reMatch = re.search(r"\b\(([0-9a-fA-F, ]*)\b", beginLine)
                    if reMatch is not None:
                        params = reMatch[1].split(", ")
                        entryTotal = int(params[0], base=0)
                        frameCount = int(params[1], base=0)
                        entries = re.sub(
                            r"\b\(([0-9a-fA-F]*)\b", f"({entryTotal + motionExporter.entryTotal}", beginLine
                        )
                        frames = re.sub(r"\b([0-9a-fA-F]*)\)", f"{frameCount + motionExporter.frameCount})", beginLine)
                        fileLines[beginIndex] = f"{entries.split(', ')[0]}, {frames.split(', ')[1]}"
                    else:
                        raise PluginError("ERROR: Can't find `CS_HEADER()` parameters!")
                    break

    fileData = CData()

    if not foundCutscene:
        print(f"WARNING: Can't find Cutscene ``{csName}``, inserting data at the end of the file.")
        motionExporter.addBeginEndCmds = True
        csArrayName = f"CutsceneData {csName}[]"
        fileLines.append("\n" + csArrayName + " = {\n" + motionExporter.getExportData() + "};\n")
        fileData.header = f"{csArrayName};\n"

    fileData.source = "".join(line for line in fileLines)
    return fileData


class OOTCSTextAdd(Operator):
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


class OOT_ImportCutscene(Operator):
    bl_idname = "object.oot_import_cutscenes"
    bl_label = "Import Cutscenes"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        try:
            if context.mode != "OBJECT":
                object.mode_set(mode="OBJECT")

            path = abspath(context.scene.ootCutsceneImportPath)
            csName = context.scene.ootCSImportName if len(context.scene.ootCSImportName) > 0 else None
            context.scene.ootCSNumber = importCutsceneData(path, None, csName)

            self.report({"INFO"}, "Successfully imported cutscenes")
            return {"FINISHED"}
        except Exception as e:
            raisePluginError(self, e)
            return {"CANCELLED"}


class OOT_ExportCutscene(Operator):
    bl_idname = "object.oot_export_cutscene"
    bl_label = "Export Cutscene"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    def execute(self, context):
        try:
            if context.mode != "OBJECT":
                object.mode_set(mode="OBJECT")

            activeObj = context.view_layer.objects.active

            if activeObj is None or activeObj.type != "EMPTY" or activeObj.ootEmptyType != "Cutscene":
                raise PluginError("You must select a cutscene object")

            if activeObj.parent is not None:
                raise PluginError("Cutscene object must not be parented to anything")

            cpath, hpath, headerfilename = checkGetFilePaths(context)
            csdata = ootCutsceneIncludes(headerfilename)
            cs_name = activeObj.name.removeprefix("Cutscene.")

            if context.scene.fast64.oot.exportMotionOnly:
                # TODO: improve this
                csdata.append(insertCutsceneData(cpath, cs_name))
            else:
                cutscene = Cutscene.new(
                    cs_name,
                    activeObj,
                    context.scene.fast64.oot.useDecompFeatures,
                    context.scene.fast64.oot.exportMotionOnly,
                )

                if cutscene is not None:
                    csdata.append(cutscene.getC())
                else:
                    raise PluginError(f"ERROR: can't process cutscene '{cs_name}'.")

            csdata.header += "\n#endif\n"
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
                if obj.type == "EMPTY" and obj.ootEmptyType == "Cutscene":
                    if obj.parent is not None:
                        print(f"Parent: {obj.parent.name}, Object: {obj.name}")
                        raise PluginError("Cutscene object must not be parented to anything")

                    if context.scene.fast64.oot.exportMotionOnly:
                        raise PluginError("ERROR: Not implemented yet.")
                    else:
                        cs_name = obj.name.removeprefix("Cutscene.")
                        cutscene = Cutscene.new(
                            cs_name,
                            obj,
                            context.scene.fast64.oot.useDecompFeatures,
                            context.scene.fast64.oot.exportMotionOnly,
                        )

                        if cutscene is not None:
                            csdata.append(cutscene.getC())
                        else:
                            raise PluginError(f"ERROR: can't process cutscene '{cs_name}'.")

                    count += 1

            if count == 0:
                raise PluginError("Could not find any cutscenes to export")

            csdata.header += "\n#endif\n"
            writeCData(csdata, hpath, cpath)
            self.report({"INFO"}, "Successfully exported " + str(count) + " cutscenes")
            return {"FINISHED"}
        except Exception as e:
            raisePluginError(self, e)
            return {"CANCELLED"}


class OOT_SearchCSDestinationEnumOperator(Operator):
    bl_idname = "object.oot_search_cs_dest_enum_operator"
    bl_label = "Choose Destination"
    bl_property = "csDestination"
    bl_options = {"REGISTER", "UNDO"}

    csDestination: EnumProperty(items=game_data.z64.enums.enum_cs_destination, default="cutscene_map_ganon_horse")
    objName: StringProperty()

    def execute(self, context):
        obj = bpy.data.objects[self.objName]
        obj.ootCutsceneProperty.csDestination = self.csDestination

        context.region.tag_redraw()
        self.report({"INFO"}, "Selected: " + self.csDestination)
        return {"FINISHED"}

    def invoke(self, context, event):
        context.window_manager.invoke_search_popup(self)
        return {"RUNNING_MODAL"}


class OOT_SearchCSSeqOperator(Operator):
    bl_idname = "object.oot_search_cs_seq_enum_operator"
    bl_label = "Search Music Sequence"
    bl_property = "seqId"
    bl_options = {"REGISTER", "UNDO"}

    seqId: EnumProperty(items=game_data.z64.enums.enum_seq_id, default="general_sfx")
    itemIndex: IntProperty()
    listType: StringProperty()

    def execute(self, context):
        csProp = context.view_layer.objects.active.ootCutsceneProperty
        for elem in csProp.csLists:
            if elem.listType == self.listType:
                elem.seqList[self.itemIndex].csSeqID = self.seqId
                break
        context.region.tag_redraw()
        self.report({"INFO"}, "Selected: " + self.seqId)
        return {"FINISHED"}

    def invoke(self, context, event):
        context.window_manager.invoke_search_popup(self)
        return {"RUNNING_MODAL"}


oot_cutscene_classes = (
    OOTCSTextAdd,
    OOTCSListAdd,
    OOT_ImportCutscene,
    OOT_ExportCutscene,
    OOT_ExportAllCutscenes,
    OOT_SearchCSDestinationEnumOperator,
    OOT_SearchCSSeqOperator,
)


def cutscene_ops_register():
    for cls in oot_cutscene_classes:
        register_class(cls)

    Scene.ootCutsceneExportPath = StringProperty(name="File", subtype="FILE_PATH")
    Scene.ootCutsceneImportPath = StringProperty(name="File", subtype="FILE_PATH")
    Scene.ootCSNumber = IntProperty(default=1, min=0)
    Scene.ootCSImportName = StringProperty(
        name="CS Name", description="Used to import a single cutscene, can be ``None``"
    )


def cutscene_ops_unregister():
    for cls in reversed(oot_cutscene_classes):
        unregister_class(cls)

    del Scene.ootCSImportName
    del Scene.ootCSNumber
    del Scene.ootCutsceneImportPath
    del Scene.ootCutsceneExportPath
