import bpy
from bpy.utils import register_class, unregister_class
from ..utility import prop_split, gammaInverse
from .oot_collision import OOTWaterBoxProperty, drawWaterBoxProperty
from .oot_constants import ootEnumEmptyType, ootEnumSceneID
from .oot_utility import getSceneObj, getRoomObj

from .oot_actor import (
    OOTActorProperty,
    OOTTransitionActorProperty,
    OOTEntranceProperty,
    OOT_SearchActorIDEnumOperator,
    OOTActorHeaderItemProperty,
    OOTActorHeaderProperty,
    drawActorProperty,
    drawTransitionActorProperty,
    drawEntranceProperty,
)

from .oot_scene_room import (
    OOTRoomHeaderProperty,
    OOTSceneHeaderProperty,
    OOTAlternateSceneHeaderProperty,
    OOTAlternateRoomHeaderProperty,
    OOTSceneProperties,
    OOT_SearchMusicSeqEnumOperator,
    OOT_SearchObjectEnumOperator,
    OOT_SearchSceneEnumOperator,
    OOTLightProperty,
    OOTLightGroupProperty,
    OOTObjectProperty,
    OOTExitProperty,
    OOTSceneTableEntryProperty,
    OOTExtraCutsceneProperty,
    OOTBGProperty,
    drawSceneHeaderProperty,
    drawAlternateSceneHeaderProperty,
    drawRoomHeaderProperty,
    drawAlternateRoomHeaderProperty,
)

from .oot_cutscene import (
    OOTCutsceneProperty,
    OOTCSTextboxProperty,
    OOTCSTextboxAdd,
    OOTCSLightingProperty,
    OOTCSTimeProperty,
    OOTCSBGMProperty,
    OOTCSMiscProperty,
    OOTCS0x09Property,
    OOTCSUnkProperty,
    OOTCSListProperty,
    OOTCSListAdd,
    drawCutsceneProperty,
)


def headerSettingsToIndices(headerSettings):
    headers = set()
    if headerSettings.childDayHeader:
        headers.add(0)
    if headerSettings.childNightHeader:
        headers.add(1)
    if headerSettings.adultDayHeader:
        headers.add(2)
    if headerSettings.adultNightHeader:
        headers.add(3)
    for cutsceneHeader in headerSettings.cutsceneHeaders:
        headers.add(cutsceneHeader.headerIndex)

    return headers


class OOTObjectPanel(bpy.types.Panel):
    bl_label = "Object Inspector"
    bl_idname = "OBJECT_PT_OOT_Object_Inspector"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "object"
    bl_options = {"HIDE_HEADER"}

    @classmethod
    def poll(cls, context):
        return context.scene.gameEditorMode == "OOT" and (context.object is not None and context.object.data is None)

    def draw(self, context):
        prop_split(self.layout, context.scene, "gameEditorMode", "Game")
        box = self.layout.box()
        box.box().label(text="OOT Object Inspector")
        obj = context.object
        objName = obj.name
        prop_split(box, obj, "ootEmptyType", "Object Type")

        sceneObj = getSceneObj(obj)
        roomObj = getRoomObj(obj)

        altSceneProp = sceneObj.ootAlternateSceneHeaders if sceneObj is not None else None
        altRoomProp = roomObj.ootAlternateRoomHeaders if roomObj is not None else None

        if obj.ootEmptyType == "Actor":
            drawActorProperty(box, obj.ootActorProperty, altRoomProp, objName)

        elif obj.ootEmptyType == "Transition Actor":
            drawTransitionActorProperty(box, obj.ootTransitionActorProperty, altSceneProp, roomObj, objName)

        elif obj.ootEmptyType == "Water Box":
            drawWaterBoxProperty(box, obj.ootWaterBoxProperty)

        elif obj.ootEmptyType == "Scene":
            drawSceneHeader(box, obj)

        elif obj.ootEmptyType == "Room":
            drawRoomHeaderProperty(box, obj.ootRoomHeader, None, None, objName)
            if obj.ootRoomHeader.menuTab == "Alternate":
                drawAlternateRoomHeaderProperty(box, obj.ootAlternateRoomHeaders, objName)

        elif obj.ootEmptyType == "Entrance":
            drawEntranceProperty(box, obj, altSceneProp, objName)

        elif obj.ootEmptyType == "Cull Group":
            obj.ootCullGroupProperty.draw(box)

        elif obj.ootEmptyType == "LOD":
            drawLODProperty(box, obj)

        elif obj.ootEmptyType == "Cutscene":
            drawCutsceneProperty(box, obj)

        elif obj.ootEmptyType == "None":
            box.label(text="Geometry can be parented to this.")


def drawSceneHeader(box: bpy.types.UILayout, obj: bpy.types.Object):
    objName = obj.name
    drawSceneHeaderProperty(box, obj.ootSceneHeader, None, None, objName)
    if obj.ootSceneHeader.menuTab == "Alternate":
        drawAlternateSceneHeaderProperty(box, obj.ootAlternateSceneHeaders, objName)
    box.prop(obj.fast64.oot.scene, "write_dummy_room_list")


def drawLODProperty(box, obj):
    col = box.column()
    col.box().label(text="LOD Settings (Blender Units)")
    for otherObj in obj.children:
        if bpy.context.scene.exportHiddenGeometry or not otherObj.hide_get():
            prop_split(col, otherObj, "f3d_lod_z", otherObj.name)
    col.prop(obj, "f3d_lod_always_render_farthest")


def setLightPropertyValues(lightProp, ambient, diffuse0, diffuse1, fogColor, fogNear):
    lightProp.ambient = gammaInverse([value / 255 for value in ambient]) + [1]
    lightProp.diffuse0 = gammaInverse([value / 255 for value in diffuse0]) + [1]
    lightProp.diffuse1 = gammaInverse([value / 255 for value in diffuse1]) + [1]
    lightProp.fogColor = gammaInverse([value / 255 for value in fogColor]) + [1]
    lightProp.fogNear = fogNear


def onUpdateOOTEmptyType(self, context):
    isNoneEmpty = self.ootEmptyType == "None"
    isBoxEmpty = self.ootEmptyType == "Water Box"
    isSphereEmpty = self.ootEmptyType == "Cull Group"
    self.show_name = not (isBoxEmpty or isNoneEmpty or isSphereEmpty)
    self.show_axis = not (isBoxEmpty or isNoneEmpty or isSphereEmpty)

    if isBoxEmpty:
        self.empty_display_type = "CUBE"

    if isSphereEmpty:
        self.empty_display_type = "SPHERE"

    if self.ootEmptyType == "Scene":
        if len(self.ootSceneHeader.lightList) == 0:
            light = self.ootSceneHeader.lightList.add()
        if not self.ootSceneHeader.timeOfDayLights.defaultsSet:
            self.ootSceneHeader.timeOfDayLights.defaultsSet = True
            timeOfDayLights = self.ootSceneHeader.timeOfDayLights
            setLightPropertyValues(
                timeOfDayLights.dawn, [70, 45, 57], [180, 154, 138], [20, 20, 60], [140, 120, 100], 0x3E1
            )
            setLightPropertyValues(
                timeOfDayLights.day, [105, 90, 90], [255, 255, 240], [50, 50, 90], [100, 100, 120], 0x3E4
            )
            setLightPropertyValues(
                timeOfDayLights.dusk, [120, 90, 0], [250, 135, 50], [30, 30, 60], [120, 70, 50], 0x3E3
            )
            setLightPropertyValues(timeOfDayLights.night, [40, 70, 100], [20, 20, 35], [50, 50, 100], [0, 0, 30], 0x3E0)


class OOT_ManualUpgrade(bpy.types.Operator):
    bl_idname = "object.oot_manual_upgrade"
    bl_label = "Upgrade Fast64 OoT Object Data"
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    def execute(self, context):
        OOT_ObjectProperties.upgrade_changed_props()
        return {"FINISHED"}


class OOT_ObjectProperties(bpy.types.PropertyGroup):
    scene: bpy.props.PointerProperty(type=OOTSceneProperties)

    @staticmethod
    def upgrade_changed_props():
        for obj in bpy.data.objects:
            if obj.data is None:
                if obj.ootEmptyType == "Room":
                    OOTObjectProperty.upgrade_object(obj)


class OOTRemoveSceneSettingsProperty(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(name="Name", default="spot03")
    subFolder: bpy.props.StringProperty(name="Subfolder", default="overworld")
    customExport: bpy.props.BoolProperty(name="Custom Export Path")
    option: bpy.props.EnumProperty(items=ootEnumSceneID, default="SCENE_YDAN")


class OOTExportSceneSettingsProperty(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(name="Name", default="spot03")
    subFolder: bpy.props.StringProperty(name="Subfolder", default="overworld")
    exportPath: bpy.props.StringProperty(name="Directory", subtype="FILE_PATH")
    customExport: bpy.props.BoolProperty(name="Custom Export Path")
    singleFile: bpy.props.BoolProperty(
        name="Export as Single File",
        default=False,
        description="Does not split the scene and rooms into multiple files.",
    )
    option: bpy.props.EnumProperty(items=ootEnumSceneID, default="SCENE_YDAN")


class OOTImportSceneSettingsProperty(bpy.types.PropertyGroup):
    name: bpy.props.StringProperty(name="Name", default="spot03")
    subFolder: bpy.props.StringProperty(name="Subfolder", default="overworld")
    destPath: bpy.props.StringProperty(name="Directory", subtype="FILE_PATH")
    isCustomDest: bpy.props.BoolProperty(name="Custom Path")
    includeMesh: bpy.props.BoolProperty(name="Mesh", default=True)
    includeCollision: bpy.props.BoolProperty(name="Collision", default=True)
    includeActors: bpy.props.BoolProperty(name="Actors", default=True)
    includeCullGroups: bpy.props.BoolProperty(name="Cull Groups", default=True)
    includeLights: bpy.props.BoolProperty(name="Lights", default=True)
    includeCameras: bpy.props.BoolProperty(name="Cameras", default=True)
    includePaths: bpy.props.BoolProperty(name="Paths", default=True)
    includeWaterBoxes: bpy.props.BoolProperty(name="Water Boxes", default=True)
    option: bpy.props.EnumProperty(items=ootEnumSceneID, default="SCENE_YDAN")

    def draw(self, layout: bpy.types.UILayout, sceneOption: str):
        col = layout.column()
        includeButtons1 = col.row(align=True)
        includeButtons1.prop(self, "includeMesh", toggle=1)
        includeButtons1.prop(self, "includeCollision", toggle=1)

        includeButtons2 = col.row(align=True)
        includeButtons2.prop(self, "includeActors", toggle=1)
        includeButtons2.prop(self, "includeCullGroups", toggle=1)
        includeButtons2.prop(self, "includeLights", toggle=1)

        includeButtons3 = col.row(align=True)
        includeButtons3.prop(self, "includeCameras", toggle=1)
        includeButtons3.prop(self, "includePaths", toggle=1)
        includeButtons3.prop(self, "includeWaterBoxes", toggle=1)
        col.prop(self, "isCustomDest")
        if self.isCustomDest:
            prop_split(col, self, "destPath", "Directory")
            prop_split(col, self, "name", "Name")
        else:
            if self.option == "Custom":
                prop_split(col, self, "subFolder", "Subfolder")
                prop_split(col, self, "name", "Name")

        col.label(text="Cutscenes won't be imported.")

        if "SCENE_BDAN" in sceneOption:
            col.label(text="Pulsing wall effect won't be imported.", icon="ERROR")


class OOTCullGroupProperty(bpy.types.PropertyGroup):
    sizeControlsCull: bpy.props.BoolProperty(default=True, name="Empty Size Controls Cull Depth")
    manualRadius: bpy.props.IntProperty(min=0)

    def draw(self, layout: bpy.types.UILayout):
        col = layout.column()
        col.prop(self, "sizeControlsCull")
        if not self.sizeControlsCull:
            prop_split(col, self, "manualRadius", "Radius (OOT Units)")
        col.label(text="Meshes generate cull groups automatically.", icon="INFO")
        col.label(text="This is only for custom cull group shapes.")
        col.label(text="Use Options -> Transform -> Affect Only -> Parent ", icon="INFO")
        col.label(text="to move object without affecting children.")


oot_obj_classes = (
    OOTSceneProperties,
    OOT_ObjectProperties,
    OOT_SearchActorIDEnumOperator,
    OOT_SearchMusicSeqEnumOperator,
    OOT_SearchObjectEnumOperator,
    OOT_SearchSceneEnumOperator,
    OOTLightProperty,
    OOTLightGroupProperty,
    OOTObjectProperty,
    OOTExitProperty,
    OOTSceneTableEntryProperty,
    OOTCSTextboxProperty,
    OOTCSTextboxAdd,
    OOTCSLightingProperty,
    OOTCSTimeProperty,
    OOTCSBGMProperty,
    OOTCSMiscProperty,
    OOTCS0x09Property,
    OOTCSUnkProperty,
    OOTCSListProperty,
    OOTCSListAdd,
    OOTCutsceneProperty,
    OOTExtraCutsceneProperty,
    OOTActorHeaderItemProperty,
    OOTActorHeaderProperty,
    OOTActorProperty,
    OOTTransitionActorProperty,
    OOTEntranceProperty,
    OOTSceneHeaderProperty,
    OOTAlternateSceneHeaderProperty,
    OOTBGProperty,
    OOTRoomHeaderProperty,
    OOTAlternateRoomHeaderProperty,
    OOT_ManualUpgrade,
    OOTImportSceneSettingsProperty,
    OOTExportSceneSettingsProperty,
    OOTRemoveSceneSettingsProperty,
    OOTCullGroupProperty,
)

oot_obj_panel_classes = (OOTObjectPanel,)


def oot_obj_panel_register():
    for cls in oot_obj_panel_classes:
        register_class(cls)


def oot_obj_panel_unregister():
    for cls in oot_obj_panel_classes:
        unregister_class(cls)


def isSceneObj(self, obj):
    return obj.data is None and obj.ootEmptyType == "Scene"


def oot_obj_register():
    for cls in oot_obj_classes:
        register_class(cls)

    bpy.types.Object.ootEmptyType = bpy.props.EnumProperty(
        name="OOT Object Type", items=ootEnumEmptyType, default="None", update=onUpdateOOTEmptyType
    )

    bpy.types.Scene.ootSceneExportSettings = bpy.props.PointerProperty(type=OOTExportSceneSettingsProperty)
    bpy.types.Scene.ootSceneImportSettings = bpy.props.PointerProperty(type=OOTImportSceneSettingsProperty)
    bpy.types.Scene.ootSceneRemoveSettings = bpy.props.PointerProperty(type=OOTRemoveSceneSettingsProperty)
    bpy.types.Scene.ootSceneExportObj = bpy.props.PointerProperty(type=bpy.types.Object, poll=isSceneObj)
    bpy.types.Scene.ootActiveHeaderLock = bpy.props.BoolProperty(default=False)

    bpy.types.Object.ootActorProperty = bpy.props.PointerProperty(type=OOTActorProperty)
    bpy.types.Object.ootTransitionActorProperty = bpy.props.PointerProperty(type=OOTTransitionActorProperty)
    bpy.types.Object.ootWaterBoxProperty = bpy.props.PointerProperty(type=OOTWaterBoxProperty)
    bpy.types.Object.ootRoomHeader = bpy.props.PointerProperty(type=OOTRoomHeaderProperty)
    bpy.types.Object.ootSceneHeader = bpy.props.PointerProperty(type=OOTSceneHeaderProperty)
    bpy.types.Object.ootAlternateSceneHeaders = bpy.props.PointerProperty(type=OOTAlternateSceneHeaderProperty)
    bpy.types.Object.ootAlternateRoomHeaders = bpy.props.PointerProperty(type=OOTAlternateRoomHeaderProperty)
    bpy.types.Object.ootEntranceProperty = bpy.props.PointerProperty(type=OOTEntranceProperty)
    bpy.types.Object.ootCutsceneProperty = bpy.props.PointerProperty(type=OOTCutsceneProperty)
    bpy.types.Object.ootCullGroupProperty = bpy.props.PointerProperty(type=OOTCullGroupProperty)


def oot_obj_unregister():

    del bpy.types.Scene.ootSceneExportSettings
    del bpy.types.Scene.ootSceneImportSettings
    del bpy.types.Scene.ootSceneRemoveSettings
    del bpy.types.Scene.ootSceneExportObj
    del bpy.types.Scene.ootActiveHeaderLock

    del bpy.types.Object.ootEmptyType

    del bpy.types.Object.ootActorProperty
    del bpy.types.Object.ootTransitionActorProperty
    del bpy.types.Object.ootWaterBoxProperty
    del bpy.types.Object.ootRoomHeader
    del bpy.types.Object.ootSceneHeader
    del bpy.types.Object.ootAlternateSceneHeaders
    del bpy.types.Object.ootAlternateRoomHeaders
    del bpy.types.Object.ootEntranceProperty
    del bpy.types.Object.ootCutsceneProperty

    for cls in reversed(oot_obj_classes):
        unregister_class(cls)
