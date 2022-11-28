import bpy
from bpy.utils import register_class, unregister_class
from ..utility import prop_split, gammaInverse
from .oot_collision import drawWaterBoxProperty
from .oot_constants import ootEnumEmptyType
from .oot_utility import getSceneObj, getRoomObj
from .oot_cutscene import drawCutsceneProperty
from .scene.panel.properties import OOTSceneProperties
from .room.panel.properties import OOTObjectProperty

from .oot_actor import (
    drawActorProperty,
    drawTransitionActorProperty,
    drawEntranceProperty,
)

from .oot_scene_room import (
    drawSceneHeaderProperty,
    drawAlternateSceneHeaderProperty,
    drawRoomHeaderProperty,
    drawAlternateRoomHeaderProperty,
)


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


class OOT_ObjectProperties(bpy.types.PropertyGroup):
    scene: bpy.props.PointerProperty(type=OOTSceneProperties)

    @staticmethod
    def upgrade_changed_props():
        for obj in bpy.data.objects:
            if obj.data is None:
                if obj.ootEmptyType == "Room":
                    OOTObjectProperty.upgrade_object(obj)


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
    OOTCullGroupProperty,
    OOT_ManualUpgrade,
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

    bpy.types.Scene.ootActiveHeaderLock = bpy.props.BoolProperty(default=False)
    bpy.types.Object.ootCullGroupProperty = bpy.props.PointerProperty(type=OOTCullGroupProperty)


def oot_obj_unregister():
    del bpy.types.Scene.ootActiveHeaderLock
    del bpy.types.Object.ootEmptyType
    del bpy.types.Object.ootCullGroupProperty

    for cls in reversed(oot_obj_classes):
        unregister_class(cls)
