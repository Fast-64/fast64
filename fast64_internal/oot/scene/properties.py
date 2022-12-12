from bpy.types import PropertyGroup, Object, Light, UILayout, Scene
from bpy.props import (
    EnumProperty,
    IntProperty,
    StringProperty,
    CollectionProperty,
    PointerProperty,
    BoolProperty,
    FloatVectorProperty,
)
from bpy.utils import register_class, unregister_class
from ...render_settings import on_update_oot_render_settings
from ...utility import prop_split
from ..cutscene.properties import OOTCSListProperty
from ..oot_utility import onMenuTabChange, onHeaderMenuTabChange

from ..oot_constants import (
    ootEnumMusicSeq,
    ootEnumSceneID,
    ootEnumExitIndex,
    ootEnumTransitionAnims,
    ootEnumLightGroupMenu,
    ootEnumGlobalObject,
    ootEnumNaviHints,
    ootEnumSkybox,
    ootEnumCloudiness,
    ootEnumSkyboxLighting,
    ootEnumMapLocation,
    ootEnumCameraMode,
    ootEnumNightSeq,
    ootEnumAudioSessionPreset,
    ootEnumCSWriteType,
    ootEnumSceneMenu,
    ootEnumSceneMenuAlternate,
    ootEnumHeaderMenu,
    ootEnumDrawConfig,
    ootEnumHeaderMenuComplete,
)


ootEnumBootMode = [
    ("Play", "Play", "Play"),
    ("Map Select", "Map Select", "Map Select"),
    ("File Select", "File Select", "File Select"),
]

def isSceneObj(self, obj):
    return obj.data is None and obj.ootEmptyType == "Scene"


class OOTSceneProperties(PropertyGroup):
    write_dummy_room_list: BoolProperty(
        name="Dummy Room List",
        default=False,
        description=(
            "When exporting the scene to C, use NULL for the pointers to room "
            "start/end offsets, instead of the appropriate symbols"
        ),
    )


class OOTExitProperty(PropertyGroup):
    expandTab: BoolProperty(name="Expand Tab")

    exitIndex: EnumProperty(items=ootEnumExitIndex, default="Default")
    exitIndexCustom: StringProperty(default="0x0000")

    # These are used when adding an entry to gEntranceTable
    scene: EnumProperty(items=ootEnumSceneID, default="SCENE_DEKU_TREE")
    sceneCustom: StringProperty(default="SCENE_DEKU_TREE")

    # These are used when adding an entry to gEntranceTable
    continueBGM: BoolProperty(default=False)
    displayTitleCard: BoolProperty(default=True)
    fadeInAnim: EnumProperty(items=ootEnumTransitionAnims, default="0x02")
    fadeInAnimCustom: StringProperty(default="0x02")
    fadeOutAnim: EnumProperty(items=ootEnumTransitionAnims, default="0x02")
    fadeOutAnimCustom: StringProperty(default="0x02")


class OOTLightProperty(PropertyGroup):
    ambient: FloatVectorProperty(
        name="Ambient Color",
        size=4,
        min=0,
        max=1,
        default=(70 / 255, 40 / 255, 57 / 255, 1),
        subtype="COLOR",
        update=on_update_oot_render_settings,
    )
    useCustomDiffuse0: BoolProperty(name="Use Custom Diffuse 0 Light Object", update=on_update_oot_render_settings)
    useCustomDiffuse1: BoolProperty(name="Use Custom Diffuse 1 Light Object", update=on_update_oot_render_settings)
    diffuse0: FloatVectorProperty(
        name="",
        size=4,
        min=0,
        max=1,
        default=(180 / 255, 154 / 255, 138 / 255, 1),
        subtype="COLOR",
        update=on_update_oot_render_settings,
    )
    diffuse1: FloatVectorProperty(
        name="",
        size=4,
        min=0,
        max=1,
        default=(20 / 255, 20 / 255, 60 / 255, 1),
        subtype="COLOR",
        update=on_update_oot_render_settings,
    )
    diffuse0Custom: PointerProperty(name="Diffuse 0", type=Light, update=on_update_oot_render_settings)
    diffuse1Custom: PointerProperty(name="Diffuse 1", type=Light, update=on_update_oot_render_settings)
    fogColor: FloatVectorProperty(
        name="",
        size=4,
        min=0,
        max=1,
        default=(140 / 255, 120 / 255, 110 / 255, 1),
        subtype="COLOR",
        update=on_update_oot_render_settings,
    )
    fogNear: IntProperty(name="", default=993, min=0, max=2**10 - 1, update=on_update_oot_render_settings)
    transitionSpeed: IntProperty(name="", default=1, min=0, max=63, update=on_update_oot_render_settings)
    fogFar: IntProperty(name="", default=0x3200, min=0, max=2**16 - 1, update=on_update_oot_render_settings)
    expandTab: BoolProperty(name="Expand Tab")


class OOTLightGroupProperty(PropertyGroup):
    expandTab: BoolProperty()
    menuTab: EnumProperty(items=ootEnumLightGroupMenu)
    dawn: PointerProperty(type=OOTLightProperty)
    day: PointerProperty(type=OOTLightProperty)
    dusk: PointerProperty(type=OOTLightProperty)
    night: PointerProperty(type=OOTLightProperty)
    defaultsSet: BoolProperty()


class OOTSceneTableEntryProperty(PropertyGroup):
    drawConfig: EnumProperty(items=ootEnumDrawConfig, name="Scene Draw Config", default="SDC_DEFAULT")
    drawConfigCustom: StringProperty(name="Scene Draw Config Custom")
    hasTitle: BoolProperty(default=True)


class OOTExtraCutsceneProperty(PropertyGroup):
    csObject: PointerProperty(name="Cutscene Object", type=Object)


class OOTSceneHeaderProperty(PropertyGroup):
    expandTab: BoolProperty(name="Expand Tab")
    usePreviousHeader: BoolProperty(name="Use Previous Header", default=True)

    globalObject: EnumProperty(name="Global Object", default="OBJECT_GAMEPLAY_DANGEON_KEEP", items=ootEnumGlobalObject)
    globalObjectCustom: StringProperty(name="Global Object Custom", default="0x00")
    naviCup: EnumProperty(name="Navi Hints", default="0x00", items=ootEnumNaviHints)
    naviCupCustom: StringProperty(name="Navi Hints Custom", default="0x00")

    skyboxID: EnumProperty(name="Skybox", items=ootEnumSkybox, default="0x01")
    skyboxIDCustom: StringProperty(name="Skybox ID", default="0")
    skyboxCloudiness: EnumProperty(name="Cloudiness", items=ootEnumCloudiness, default="0x00")
    skyboxCloudinessCustom: StringProperty(name="Cloudiness ID", default="0x00")
    skyboxLighting: EnumProperty(
        name="Skybox Lighting", items=ootEnumSkyboxLighting, default="LIGHT_MODE_TIME", update=on_update_oot_render_settings
    )
    skyboxLightingCustom: StringProperty(
        name="Skybox Lighting Custom", default="0x00", update=on_update_oot_render_settings
    )

    mapLocation: EnumProperty(name="Map Location", items=ootEnumMapLocation, default="0x00")
    mapLocationCustom: StringProperty(name="Skybox Lighting Custom", default="0x00")
    cameraMode: EnumProperty(name="Camera Mode", items=ootEnumCameraMode, default="0x00")
    cameraModeCustom: StringProperty(name="Camera Mode Custom", default="0x00")

    musicSeq: EnumProperty(name="Music Sequence", items=ootEnumMusicSeq, default="0x02")
    musicSeqCustom: StringProperty(name="Music Sequence ID", default="0x00")
    nightSeq: EnumProperty(name="Nighttime SFX", items=ootEnumNightSeq, default="0x00")
    nightSeqCustom: StringProperty(name="Nighttime SFX ID", default="0x00")
    audioSessionPreset: EnumProperty(name="Audio Session Preset", items=ootEnumAudioSessionPreset, default="0x00")
    audioSessionPresetCustom: StringProperty(name="Audio Session Preset", default="0x00")

    timeOfDayLights: PointerProperty(type=OOTLightGroupProperty, name="Time Of Day Lighting")
    lightList: CollectionProperty(type=OOTLightProperty, name="Lighting List")
    exitList: CollectionProperty(type=OOTExitProperty, name="Exit List")

    writeCutscene: BoolProperty(name="Write Cutscene")
    csWriteType: EnumProperty(name="Cutscene Data Type", items=ootEnumCSWriteType, default="Embedded")
    csWriteCustom: StringProperty(name="CS hdr var:", default="")
    csWriteObject: PointerProperty(name="Cutscene Object", type=Object)

    # These properties are for the deprecated "Embedded" cutscene type. They have
    # not been removed as doing so would break any existing scenes made with this
    # type of cutscene data.
    csEndFrame: IntProperty(name="End Frame", min=0, default=100)
    csWriteTerminator: BoolProperty(name="Write Terminator (Code Execution)")
    csTermIdx: IntProperty(name="Index", min=0)
    csTermStart: IntProperty(name="Start Frm", min=0, default=99)
    csTermEnd: IntProperty(name="End Frm", min=0, default=100)
    csLists: CollectionProperty(type=OOTCSListProperty, name="Cutscene Lists")

    extraCutscenes: CollectionProperty(type=OOTExtraCutsceneProperty, name="Extra Cutscenes")

    sceneTableEntry: PointerProperty(type=OOTSceneTableEntryProperty)

    menuTab: EnumProperty(name="Menu", items=ootEnumSceneMenu, update=onMenuTabChange)
    altMenuTab: EnumProperty(name="Menu", items=ootEnumSceneMenuAlternate)

    appendNullEntrance: BoolProperty(
        name="Append Null Entrance",
        description="Add an additional {0, 0} to the end of the EntranceEntry list.",
        default=False,
    )


class OOTAlternateSceneHeaderProperty(PropertyGroup):
    childNightHeader: PointerProperty(name="Child Night Header", type=OOTSceneHeaderProperty)
    adultDayHeader: PointerProperty(name="Adult Day Header", type=OOTSceneHeaderProperty)
    adultNightHeader: PointerProperty(name="Adult Night Header", type=OOTSceneHeaderProperty)
    cutsceneHeaders: CollectionProperty(type=OOTSceneHeaderProperty)

    headerMenuTab: EnumProperty(name="Header Menu", items=ootEnumHeaderMenu, update=onHeaderMenuTabChange)
    currentCutsceneIndex: IntProperty(min=4, default=4, update=onHeaderMenuTabChange)


class OOTBootupSceneOptions(PropertyGroup):
    bootToScene: BoolProperty(default=False, name="Boot To Scene")
    overrideHeader: BoolProperty(default=False, name="Override Header")
    headerOption: EnumProperty(items=ootEnumHeaderMenuComplete, name="Header", default="Child Day")
    spawnIndex: IntProperty(name="Spawn", min=0)
    newGameOnly: BoolProperty(
        default=False,
        name="Override Scene On New Game Only",
        description="Only use this starting scene after loading a new save file",
    )
    newGameName: StringProperty(default="Link", name="New Game Name")
    bootMode: EnumProperty(default="Play", name="Boot Mode", items=ootEnumBootMode)

    # see src/code/z_play.c:Play_Init() - can't access more than 16 cutscenes?
    cutsceneIndex: IntProperty(min=4, max=19, default=4, name="Cutscene Index")


class OOTRemoveSceneSettingsProperty(PropertyGroup):
    name: StringProperty(name="Name", default="spot03")
    subFolder: StringProperty(name="Subfolder", default="overworld")
    customExport: BoolProperty(name="Custom Export Path")
    option: EnumProperty(items=ootEnumSceneID, default="SCENE_DEKU_TREE")


class OOTExportSceneSettingsProperty(PropertyGroup):
    name: StringProperty(name="Name", default="spot03")
    subFolder: StringProperty(name="Subfolder", default="overworld")
    exportPath: StringProperty(name="Directory", subtype="FILE_PATH")
    customExport: BoolProperty(name="Custom Export Path")
    singleFile: BoolProperty(
        name="Export as Single File",
        default=False,
        description="Does not split the scene and rooms into multiple files.",
    )
    option: EnumProperty(items=ootEnumSceneID, default="SCENE_DEKU_TREE")


class OOTImportSceneSettingsProperty(PropertyGroup):
    name: StringProperty(name="Name", default="spot03")
    subFolder: StringProperty(name="Subfolder", default="overworld")
    destPath: StringProperty(name="Directory", subtype="FILE_PATH")
    isCustomDest: BoolProperty(name="Custom Path")
    includeMesh: BoolProperty(name="Mesh", default=True)
    includeCollision: BoolProperty(name="Collision", default=True)
    includeActors: BoolProperty(name="Actors", default=True)
    includeCullGroups: BoolProperty(name="Cull Groups", default=True)
    includeLights: BoolProperty(name="Lights", default=True)
    includeCameras: BoolProperty(name="Cameras", default=True)
    includePaths: BoolProperty(name="Paths", default=True)
    includeWaterBoxes: BoolProperty(name="Water Boxes", default=True)
    option: EnumProperty(items=ootEnumSceneID, default="SCENE_DEKU_TREE")

    def draw(self, layout: UILayout, sceneOption: str):
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

        if "SCENE_JABU_JABU" in sceneOption:
            col.label(text="Pulsing wall effect won't be imported.", icon="ERROR")


classes = (
    OOTExitProperty,
    OOTLightProperty,
    OOTLightGroupProperty,
    OOTSceneTableEntryProperty,
    OOTExtraCutsceneProperty,
    OOTSceneHeaderProperty,
    OOTAlternateSceneHeaderProperty,
    OOTBootupSceneOptions,
    OOTRemoveSceneSettingsProperty,
    OOTExportSceneSettingsProperty,
    OOTImportSceneSettingsProperty,
)


def scene_props_register():
    for cls in classes:
        register_class(cls)

    Object.ootSceneHeader = PointerProperty(type=OOTSceneHeaderProperty)
    Object.ootAlternateSceneHeaders = PointerProperty(type=OOTAlternateSceneHeaderProperty)
    Scene.ootSceneExportObj = PointerProperty(type=Object, poll=isSceneObj)
    Scene.ootSceneExportSettings = PointerProperty(type=OOTExportSceneSettingsProperty)
    Scene.ootSceneImportSettings = PointerProperty(type=OOTImportSceneSettingsProperty)
    Scene.ootSceneRemoveSettings = PointerProperty(type=OOTRemoveSceneSettingsProperty)


def scene_props_unregister():
    del Object.ootSceneHeader
    del Object.ootAlternateSceneHeaders
    del Scene.ootSceneExportObj
    del Scene.ootSceneExportSettings
    del Scene.ootSceneImportSettings
    del Scene.ootSceneRemoveSettings

    for cls in reversed(classes):
        unregister_class(cls)
