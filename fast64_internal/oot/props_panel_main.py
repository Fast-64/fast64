import bpy
from bpy.utils import register_class, unregister_class
from ..utility import prop_split, gammaInverse
from .oot_utility import getSceneObj, getRoomObj
from .scene.properties import OOTSceneProperties
from .room.properties import OOTObjectProperty, OOTRoomHeaderProperty, OOTAlternateRoomHeaderProperty
from .collision.properties import OOTWaterBoxProperty
from .cutscene.properties import OOTCutsceneProperty
from .cutscene.motion.properties import (
    OOTCutsceneMotionProperty,
    CutsceneCmdActorCueListProperty,
    CutsceneCmdActorCueProperty,
)

from .actor.properties import (
    OOTActorProperty,
    OOTTransitionActorProperty,
    OOTEntranceProperty,
)

# Make sure to add exceptions in utility.py - selectMeshChildrenOnly
ootEnumEmptyType = [
    ("None", "None", "None"),
    ("Scene", "Scene", "Scene"),
    ("Room", "Room", "Room"),
    ("Actor", "Actor", "Actor"),
    ("Transition Actor", "Transition Actor", "Transition Actor"),
    ("Entrance", "Entrance", "Entrance"),
    ("Water Box", "Water Box", "Water Box"),
    ("Cull Group", "Custom Cull Group", "Cull Group"),
    ("LOD", "LOD Group", "LOD Group"),
    ("Cutscene", "Cutscene Main", "Cutscene"),
    ("CS Actor Cue List", "CS Actor Cue List", "CS Actor Cue List"),
    ("CS Actor Cue", "CS Actor Cue", "CS Actor Cue"),
    ("CS Player Cue List", "CS Player Cue List", "CS Player Cue List"),
    ("CS Player Cue", "CS Player Cue", "CS Player Cue"),
    ("CS Actor Cue Preview", "CS Actor Cue Preview", "CS Actor Cue Preview"),
    ("CS Player Cue Preview", "CS Player Cue Preview", "CS Player Cue Preview"),
    ("CS Dummy Cue", "CS Dummy Cue", "CS Dummy Cue"),
    # ('Camera Volume', 'Camera Volume', 'Camera Volume'),
]


def drawSceneHeader(box: bpy.types.UILayout, obj: bpy.types.Object):
    objName = obj.name
    obj.ootSceneHeader.draw_props(box, None, None, objName)
    if obj.ootSceneHeader.menuTab == "Alternate":
        obj.ootAlternateSceneHeaders.draw_props(box, objName)
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
        return context.scene.gameEditorMode == "OOT" and (context.object is not None and context.object.type == "EMPTY")

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
            actorProp: OOTActorProperty = obj.ootActorProperty
            actorProp.draw_props(box, altRoomProp, objName)

        elif obj.ootEmptyType == "Transition Actor":
            transActorProp: OOTTransitionActorProperty = obj.ootTransitionActorProperty
            transActorProp.draw_props(box, altSceneProp, roomObj, objName)

        elif obj.ootEmptyType == "Water Box":
            waterBoxProps: OOTWaterBoxProperty = obj.ootWaterBoxProperty
            waterBoxProps.draw_props(box)

        elif obj.ootEmptyType == "Scene":
            drawSceneHeader(box, obj)

        elif obj.ootEmptyType == "Room":
            roomProp: OOTRoomHeaderProperty = obj.ootRoomHeader
            roomProp.draw_props(box, None, None, objName)
            if obj.ootRoomHeader.menuTab == "Alternate":
                roomAltProp: OOTAlternateRoomHeaderProperty = obj.ootAlternateRoomHeaders
                roomAltProp.draw_props(box, objName)

        elif obj.ootEmptyType == "Entrance":
            entranceProp: OOTEntranceProperty = obj.ootEntranceProperty
            entranceProp.draw_props(box, obj, altSceneProp, objName)

        elif obj.ootEmptyType == "Cull Group":
            cullGroupProp: OOTCullGroupProperty = obj.ootCullGroupProperty
            cullGroupProp.draw_props(box)

        elif obj.ootEmptyType == "LOD":
            drawLODProperty(box, obj)

        elif obj.ootEmptyType == "Cutscene":
            csProp: OOTCutsceneProperty = obj.ootCutsceneProperty
            csProp.draw_props(box, obj)

        elif obj.ootEmptyType in [
            "CS Actor Cue List",
            "CS Player Cue List",
            "CS Actor Cue Preview",
            "CS Player Cue Preview",
        ]:
            labelPrefix = "Player" if "Player" in obj.ootEmptyType else "Actor"
            actorCueListProp: CutsceneCmdActorCueListProperty = obj.ootCSMotionProperty.actorCueListProp
            actorCueListProp.draw_props(box, obj.ootEmptyType == f"CS {labelPrefix} Cue Preview", labelPrefix, obj.name)

        elif obj.ootEmptyType in ["CS Actor Cue", "CS Player Cue", "CS Dummy Cue"]:
            labelPrefix = "Player" if obj.parent.ootEmptyType == "CS Player Cue List" else "Actor"
            actorCueProp: CutsceneCmdActorCueProperty = obj.ootCSMotionProperty.actorCueProp
            actorCueProp.draw_props(box, labelPrefix, obj.ootEmptyType == "CS Dummy Cue", obj.name)

        elif obj.ootEmptyType == "None":
            box.label(text="Geometry can be parented to this.")


class OOT_ObjectProperties(bpy.types.PropertyGroup):
    scene: bpy.props.PointerProperty(type=OOTSceneProperties)

    @staticmethod
    def upgrade_changed_props():
        for obj in bpy.data.objects:
            if obj.type == "EMPTY":
                if obj.ootEmptyType == "Room":
                    OOTObjectProperty.upgrade_object(obj)
                if obj.ootEmptyType in {"Entrance", "Transition Actor"}:
                    OOTActorProperty.upgrade_object(obj)
                if obj.ootEmptyType == "Cutscene":
                    OOTCutsceneProperty.upgrade_object(obj)
                if any(obj.name.startswith(elem) for elem in ["ActionList.", "Point.", "Preview."]):
                    OOTCutsceneMotionProperty.upgrade_object(obj)

                    if "Point." in obj.name:
                        parentObj = obj.parent
                        if parentObj is not None:
                            if parentObj.children[-1] == obj:
                                obj.ootEmptyType = "CS Dummy Cue"
                        else:
                            print("WARNING: An Actor Cue has been detected outside an Actor Cue List: " + obj.name)
            elif obj.type == "ARMATURE":
                parentObj = obj.parent
                if parentObj is not None and (
                    parentObj.name.startswith("Cutscene.") or parentObj.ootEmptyType == "Cutscene"
                ):
                    OOTCutsceneMotionProperty.upgrade_object(obj)


class OOTCullGroupProperty(bpy.types.PropertyGroup):
    sizeControlsCull: bpy.props.BoolProperty(default=True, name="Empty Size Controls Cull Depth")
    manualRadius: bpy.props.IntProperty(min=0)

    def draw_props(self, layout: bpy.types.UILayout):
        col = layout.column()
        col.prop(self, "sizeControlsCull")
        if not self.sizeControlsCull:
            prop_split(col, self, "manualRadius", "Radius (OOT Units)")
        col.label(text="RSP culling is automatic. The 'Custom Cull Group' empty type is for CPU culling.", icon="INFO")
        col.label(text="This will create custom cull group shape entries to be used in Cullable rooms.")
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
