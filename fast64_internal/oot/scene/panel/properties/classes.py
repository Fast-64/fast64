from bpy.types import PropertyGroup, Object, Light
from bpy.props import EnumProperty, IntProperty, StringProperty, CollectionProperty, PointerProperty, BoolProperty, FloatVectorProperty
from .....render_settings import on_update_oot_render_settings
from ....cutscene.panel.properties import OOTCSListProperty
from ....oot_utility import onMenuTabChange, onHeaderMenuTabChange

from ....oot_constants import (
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
)


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
    scene: EnumProperty(items=ootEnumSceneID, default="SCENE_YDAN")
    sceneCustom: StringProperty(default="SCENE_YDAN")

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

    globalObject: EnumProperty(
        name="Global Object", default="OBJECT_GAMEPLAY_DANGEON_KEEP", items=ootEnumGlobalObject
    )
    globalObjectCustom: StringProperty(name="Global Object Custom", default="0x00")
    naviCup: EnumProperty(name="Navi Hints", default="0x00", items=ootEnumNaviHints)
    naviCupCustom: StringProperty(name="Navi Hints Custom", default="0x00")

    skyboxID: EnumProperty(name="Skybox", items=ootEnumSkybox, default="0x01")
    skyboxIDCustom: StringProperty(name="Skybox ID", default="0")
    skyboxCloudiness: EnumProperty(name="Cloudiness", items=ootEnumCloudiness, default="0x00")
    skyboxCloudinessCustom: StringProperty(name="Cloudiness ID", default="0x00")
    skyboxLighting: EnumProperty(
        name="Skybox Lighting", items=ootEnumSkyboxLighting, default="false", update=on_update_oot_render_settings
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
    audioSessionPreset: EnumProperty(
        name="Audio Session Preset", items=ootEnumAudioSessionPreset, default="0x00"
    )
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
