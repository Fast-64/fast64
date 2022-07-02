import math, os, bpy, bmesh, mathutils
from bpy.utils import register_class, unregister_class
from io import BytesIO

from ..f3d.f3d_gbi import *
from .oot_constants import *
from .oot_utility import *
from .oot_scene_room import *
from .oot_actor import *
from .oot_collision import *
from .oot_spline import *
from ..utility import *


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
            drawSceneHeaderProperty(box, obj.ootSceneHeader, None, None, objName)
            if obj.ootSceneHeader.menuTab == "Alternate":
                drawAlternateSceneHeaderProperty(box, obj.ootAlternateSceneHeaders, objName)
            box.prop(obj.fast64.oot.scene, "write_dummy_room_list")

        elif obj.ootEmptyType == "Room":
            drawRoomHeaderProperty(box, obj.ootRoomHeader, None, None, objName)
            if obj.ootRoomHeader.menuTab == "Alternate":
                drawAlternateRoomHeaderProperty(box, obj.ootAlternateRoomHeaders, objName)

        elif obj.ootEmptyType == "Entrance":
            drawEntranceProperty(box, obj, altSceneProp, objName)

        elif obj.ootEmptyType == "Cull Group":
            drawCullGroupProperty(box, obj)

        elif obj.ootEmptyType == "LOD":
            drawLODProperty(box, obj)

        elif obj.ootEmptyType == "Cutscene":
            drawCutsceneProperty(box, obj)

        elif obj.ootEmptyType == "None":
            box.label(text="Geometry can be parented to this.")

        # if obj.ootEmptyType != "Scene" and obj.ootEmptyType != "Room":
        # 	drawParentSceneRoom(box, context.object)


def drawLODProperty(box, obj):
    col = box.column()
    col.box().label(text="LOD Settings (Blender Units)")
    for otherObj in obj.children:
        if bpy.context.scene.exportHiddenGeometry or not otherObj.hide_get():
            prop_split(col, otherObj, "f3d_lod_z", otherObj.name)
    col.prop(obj, "f3d_lod_always_render_farthest")


def drawCullGroupProperty(box, obj):
    col = box.column()
    col.label(text="Use Options -> Transform -> Affect Only -> Parent ")
    col.label(text="to move object without affecting children.")


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


class OOT_ObjectProperties(bpy.types.PropertyGroup):
    version: bpy.props.IntProperty(name="OOT_ObjectProperties Version", default=0)
    cur_version = 0  # version after property migration

    scene: bpy.props.PointerProperty(type=OOTSceneProperties)


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
    OOTRoomHeaderProperty,
    OOTAlternateRoomHeaderProperty,
)

oot_obj_panel_classes = (OOTObjectPanel,)


def oot_obj_panel_register():
    for cls in oot_obj_panel_classes:
        register_class(cls)


def oot_obj_panel_unregister():
    for cls in oot_obj_panel_classes:
        unregister_class(cls)


def oot_obj_register():
    for cls in oot_obj_classes:
        register_class(cls)

    bpy.types.Object.ootEmptyType = bpy.props.EnumProperty(
        name="OOT Object Type", items=ootEnumEmptyType, default="None", update=onUpdateOOTEmptyType
    )

    bpy.types.Object.ootActorProperty = bpy.props.PointerProperty(type=OOTActorProperty)
    bpy.types.Object.ootTransitionActorProperty = bpy.props.PointerProperty(type=OOTTransitionActorProperty)
    bpy.types.Object.ootWaterBoxProperty = bpy.props.PointerProperty(type=OOTWaterBoxProperty)
    bpy.types.Object.ootRoomHeader = bpy.props.PointerProperty(type=OOTRoomHeaderProperty)
    bpy.types.Object.ootSceneHeader = bpy.props.PointerProperty(type=OOTSceneHeaderProperty)
    bpy.types.Object.ootAlternateSceneHeaders = bpy.props.PointerProperty(type=OOTAlternateSceneHeaderProperty)
    bpy.types.Object.ootAlternateRoomHeaders = bpy.props.PointerProperty(type=OOTAlternateRoomHeaderProperty)
    bpy.types.Object.ootEntranceProperty = bpy.props.PointerProperty(type=OOTEntranceProperty)
    bpy.types.Object.ootCutsceneProperty = bpy.props.PointerProperty(type=OOTCutsceneProperty)


def oot_obj_unregister():

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
