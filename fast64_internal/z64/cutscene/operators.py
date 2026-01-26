import bpy

from bpy.path import abspath
from bpy.ops import object
from bpy.props import StringProperty, EnumProperty, IntProperty
from bpy.types import Scene, Operator, Object
from bpy.utils import register_class, unregister_class
from ...utility import PluginError, ExportUtils, raisePluginError
from ...game_data import game_data
from ..collection_utility import getCollection
from .constants import ootEnumCSTextboxType
from .importer import importCutsceneData
from ..exporter.cutscene import Cutscene


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
    listType: EnumProperty(items=lambda self, context: game_data.z64.get_enum("cs_list_type"))
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
        with ExportUtils() as export_utils:
            try:
                if context.mode != "OBJECT":
                    object.mode_set(mode="OBJECT")

                if context.scene.fast64.oot.export_cutscene_obj is not None:
                    cs_obj = context.scene.fast64.oot.export_cutscene_obj
                else:
                    cs_obj = context.view_layer.objects.active

                if cs_obj is None or cs_obj.type != "EMPTY" or cs_obj.ootEmptyType != "Cutscene":
                    raise PluginError("You must select a cutscene object")

                if cs_obj.parent is not None:
                    raise PluginError("Cutscene object must not be parented to anything")

                Cutscene.export(cs_obj)

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
        with ExportUtils() as export_utils:
            try:
                if context.mode != "OBJECT":
                    object.mode_set(mode="OBJECT")

                cs_obj_list: list[Object] = []

                for obj in context.view_layer.objects:
                    if obj.type == "EMPTY" and obj.ootEmptyType == "Cutscene":
                        if obj.parent is not None:
                            print(f"Parent: {obj.parent.name}, Object: {obj.name}")
                            raise PluginError("Cutscene object must not be parented to anything")

                        cs_obj_list.append(obj)

                for count, cs_obj in enumerate(cs_obj_list, 1):
                    # skip the includes if this isn't the first cutscene
                    # skip the #endif directive if this isn't the last cutscene
                    Cutscene.export(cs_obj, count > 1, count < len(cs_obj_list))

                if count == 0:
                    raise PluginError("Could not find any cutscenes to export")

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
