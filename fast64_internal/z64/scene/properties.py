import bpy
from bpy.types import PropertyGroup, Object, Light, UILayout, Scene, Context
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
from ...utility import prop_split, customExportWarning
from ..cutscene.constants import ootEnumCSWriteType

from ..utility import (
    onMenuTabChange,
    onHeaderMenuTabChange,
    drawCollectionOps,
    drawEnumWithCustom,
    drawAddButton,
    is_oot_features,
    is_game_oot,
    get_cs_index_start,
    get_game_prop_name,
)

from ..constants import (
    oot_data,
    ootEnumSceneID,
    ootEnumGlobalObject,
    ootEnumNaviHints,
    ootEnumSkybox,
    ootEnumCloudiness,
    ootEnumSkyboxLighting,
    ootEnumMapLocation,
    ootEnumCameraMode,
    ootEnumAudioSessionPreset,
    ootEnumHeaderMenu,
    ootEnumDrawConfig,
    ootEnumHeaderMenuComplete,
    mm_data,
    mm_enum_scene_id,
    mm_enum_global_object,
    mm_enum_skybox,
    mm_enum_skybox_config,
    mm_enum_draw_config,
)

ootEnumSceneMenuAlternate = [
    ("General", "General", "General"),
    ("Lighting", "Lighting", "Lighting"),
    ("Cutscene", "Cutscene", "Cutscene"),
    ("Exits", "Exits", "Exits"),
]
ootEnumSceneMenu = ootEnumSceneMenuAlternate + [
    ("Alternate", "Alternate", "Alternate"),
]

ootEnumLightGroupMenu = [
    ("Dawn", "Dawn", "Dawn"),
    ("Day", "Day", "Day"),
    ("Dusk", "Dusk", "Dusk"),
    ("Night", "Night", "Night"),
]

ootEnumTransitionAnims = [
    ("Custom", "Custom", "Custom"),
    ("0x00", "Spiky", "Spiky"),
    ("0x01", "Triforce", "Triforce"),
    ("0x02", "Slow Black Fade", "Slow Black Fade"),
    ("0x03", "Slow Day/White, Slow Night/Black Fade", "Slow Day/White, Slow Night/Black Fade"),
    ("0x04", "Fast Day/Black, Slow Night/Black Fade", "Fast Day/Black, Slow Night/Black Fade"),
    ("0x05", "Fast Day/White, Slow Night/Black Fade", "Fast Day/White, Slow Night/Black Fade"),
    ("0x06", "Very Slow Day/White, Slow Night/Black Fade", "Very Slow Day/White, Slow Night/Black Fade"),
    ("0x07", "Very Slow Day/White, Slow Night/Black Fade", "Very Slow Day/White, Slow Night/Black Fade"),
    ("0x0E", "Slow Sandstorm Fade", "Slow Sandstorm Fade"),
    ("0x0F", "Fast Sandstorm Fade", "Fast Sandstorm Fade"),
    ("0x20", "Iris Fade", "Iris Fade"),
    ("0x2C", "Shortcut Transition", "Shortcut Transition"),
]

ootEnumExitIndex = [
    ("Custom", "Custom", "Custom"),
    ("Default", "Default", "Default"),
]


class OOTSceneCommon:
    ootEnumBootMode = [
        ("Play", "Play", "Play"),
        ("Map Select", "Map Select", "Map Select"),
        ("File Select", "File Select", "File Select"),
    ]

    def isSceneObj(self, obj):
        return obj.type == "EMPTY" and obj.ootEmptyType == "Scene"


class OOTSceneProperties(PropertyGroup):
    write_dummy_room_list: BoolProperty(
        name="Dummy Room List",
        default=False,
        description=(
            "When exporting the scene to C, use NULL for the pointers to room "
            "start/end offsets, instead of the appropriate symbols"
        ),
    )


class Z64_ExitProperty(PropertyGroup):
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

    def draw_props(self, layout: UILayout, index: int, headerIndex: int, objName: str):
        box = layout.box()
        box.prop(self, "expandTab", text="Exit " + str(index + 1), icon="TRIA_DOWN" if self.expandTab else "TRIA_RIGHT")

        if self.expandTab:
            drawCollectionOps(box, index, "Exit", headerIndex, objName)

            if is_game_oot():
                drawEnumWithCustom(box, self, "exitIndex", "Exit Index", "")

                if self.exitIndex != "Custom":
                    box.label(text='This is unfinished, use "Custom".')
                    exitGroup = box.column()
                    exitGroup.enabled = False
                    drawEnumWithCustom(exitGroup, self, "scene", "Scene", "")
                    exitGroup.prop(self, "continueBGM", text="Continue BGM")
                    exitGroup.prop(self, "displayTitleCard", text="Display Title Card")
                    drawEnumWithCustom(exitGroup, self, "fadeInAnim", "Fade In Animation", "")
                    drawEnumWithCustom(exitGroup, self, "fadeOutAnim", "Fade Out Animation", "")
            else:
                prop_split(box, self, "exitIndexCustom", "Exit Index")


class Z64_LightProperty(PropertyGroup):
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
    z_far: IntProperty(name="", default=0x3200, min=0, max=2**15 - 1, update=on_update_oot_render_settings)
    expandTab: BoolProperty(name="Expand Tab")

    def draw_props(
        self, layout: UILayout, name: str, showExpandTab: bool, index: int, sceneHeaderIndex: int, objName: str
    ):
        if showExpandTab:
            box = layout.box().column()
            box.prop(self, "expandTab", text=name, icon="TRIA_DOWN" if self.expandTab else "TRIA_RIGHT")
            expandTab = self.expandTab
        else:
            box = layout
            expandTab = True

        if expandTab:
            if index is not None:
                drawCollectionOps(box, index, "Light", sceneHeaderIndex, objName)
            prop_split(box, self, "ambient", "Ambient Color")

            if self.useCustomDiffuse0:
                prop_split(box, self, "diffuse0Custom", "Diffuse 0")
                box.label(text="Make sure light is not part of scene hierarchy.", icon="FILE_PARENT")
            else:
                prop_split(box, self, "diffuse0", "Diffuse 0")
            box.prop(self, "useCustomDiffuse0")

            if self.useCustomDiffuse1:
                prop_split(box, self, "diffuse1Custom", "Diffuse 1")
                box.label(text="Make sure light is not part of scene hierarchy.", icon="FILE_PARENT")
            else:
                prop_split(box, self, "diffuse1", "Diffuse 1")
            box.prop(self, "useCustomDiffuse1")

            prop_split(box, self, "fogColor", "Fog Color")
            prop_split(box, self, "fogNear", "Fog Near (Fog Far=1000)")
            prop_split(box, self, "z_far", "Z Far (Draw Distance)")
            prop_split(box, self, "transitionSpeed", "Transition Speed")


class Z64_LightGroupProperty(PropertyGroup):
    expandTab: BoolProperty()
    menuTab: EnumProperty(items=ootEnumLightGroupMenu)
    dawn: PointerProperty(type=Z64_LightProperty)
    day: PointerProperty(type=Z64_LightProperty)
    dusk: PointerProperty(type=Z64_LightProperty)
    night: PointerProperty(type=Z64_LightProperty)
    defaultsSet: BoolProperty()

    def draw_props(self, layout: UILayout):
        box = layout.column()
        box.row().prop(self, "menuTab", expand=True)
        if self.menuTab == "Dawn":
            self.dawn.draw_props(box, "Dawn", False, None, None, None)
        if self.menuTab == "Day":
            self.day.draw_props(box, "Day", False, None, None, None)
        if self.menuTab == "Dusk":
            self.dusk.draw_props(box, "Dusk", False, None, None, None)
        if self.menuTab == "Night":
            self.night.draw_props(box, "Night", False, None, None, None)


class Z64_SceneTableEntryProperty(PropertyGroup):
    drawConfig: EnumProperty(items=ootEnumDrawConfig, name="Scene Draw Config", default="SDC_DEFAULT")
    mm_draw_config: EnumProperty(items=mm_enum_draw_config, name="Scene Draw Config", default="SCENE_DRAW_CFG_DEFAULT")
    drawConfigCustom: StringProperty(name="Scene Draw Config Custom")

    def draw_props(self, layout: UILayout):
        drawEnumWithCustom(layout, self, get_game_prop_name("draw_config"), "Draw Config", "", "drawConfigCustom")


class Z64_ExtraCutsceneProperty(PropertyGroup):
    csObject: PointerProperty(
        name="Cutscene Object",
        type=Object,
        poll=lambda self, object: object.type == "EMPTY" and object.ootEmptyType == "Cutscene",
    )


def minimap_chest_poll(self: "Z64_MapDataChestProperty", object: Object):
    return (
        object.type == "EMPTY" and object.ootEmptyType == "Actor" and object.ootActorProperty.actorID == "ACTOR_EN_BOX"
    )


class Z64_MapDataChestProperty(PropertyGroup):
    expand_tab: BoolProperty(name="Expand Tab")

    # used to get the room index, the coordinates and the chest flag
    chest_obj: PointerProperty(type=Object, poll=minimap_chest_poll, name="Chest Empty Object")

    def draw_props(self, layout: UILayout, index: int, header_index: int, obj_name: str):
        box = layout.box()
        box.prop(
            self,
            "expand_tab",
            text=f"Chest Actor No.{index + 1}",
            icon="TRIA_DOWN" if self.expand_tab else "TRIA_RIGHT",
        )

        if self.expand_tab:
            drawCollectionOps(box, index, "Minimap Chest", header_index, obj_name)
            box.prop(self, "chest_obj")


class Z64_MapDataRoomProperty(PropertyGroup):
    expand_tab: BoolProperty(name="Expand Tab")

    map_id: StringProperty(name="Minimap ID", default="MAP_DATA_NO_MAP")
    center_x: IntProperty(name="Center X", default=0)
    floor_y: IntProperty(name="Floor Y", default=0)
    center_z: IntProperty(name="Center Z", default=0)
    flags: StringProperty(name="Flags", default="0x0000")

    def draw_props(self, layout: UILayout, index: int, header_index: int, obj_name: str):
        box = layout.box()
        box.prop(
            self,
            "expand_tab",
            text=f"Minimap Room Index {index}",
            icon="TRIA_DOWN" if self.expand_tab else "TRIA_RIGHT",
        )

        if self.expand_tab:
            drawCollectionOps(box, index, "Minimap Room", header_index, obj_name)
            prop_split(box, self, "map_id", "Minimap ID")
            prop_split(box, self, "center_x", "Center X")
            prop_split(box, self, "floor_y", "Floor Y")
            prop_split(box, self, "center_z", "Center Z")
            prop_split(box, self, "flags", "Flags")


class Z64_SceneHeaderProperty(PropertyGroup):
    expandTab: BoolProperty(name="Expand Tab")
    usePreviousHeader: BoolProperty(name="Use Previous Header", default=True)

    # SCENE_CMD_SPECIAL_FILES
    globalObject: EnumProperty(name="Global Object", default="OBJECT_GAMEPLAY_DANGEON_KEEP", items=ootEnumGlobalObject)
    mm_global_obj: EnumProperty(name="Global Object", default="GAMEPLAY_DANGEON_KEEP", items=mm_enum_global_object)
    globalObjectCustom: StringProperty(name="Global Object Custom", default="0x00")

    # OoT exclusive
    naviCup: EnumProperty(name="Navi Hints", default="NAVI_QUEST_HINTS_NONE", items=ootEnumNaviHints)
    naviCupCustom: StringProperty(name="Navi Hints Custom", default="0x00")

    # SCENE_CMD_SKYBOX_SETTINGS
    skyboxID: EnumProperty(name="Skybox", items=ootEnumSkybox, default="0x01")
    mm_skybox_id: EnumProperty(name="Skybox", items=mm_enum_skybox, default="SKYBOX_NORMAL_SKY")
    skyboxIDCustom: StringProperty(name="Skybox ID", default="0")
    skyboxCloudiness: EnumProperty(name="Cloudiness", items=ootEnumCloudiness, default="0x00")
    mm_skybox_config: EnumProperty(name="Skybox Config", items=mm_enum_skybox_config, default="SKYBOX_CONFIG_0")
    skyboxCloudinessCustom: StringProperty(name="Cloudiness ID", default="0x00")
    skyboxLighting: EnumProperty(
        name="Skybox Lighting",
        items=ootEnumSkyboxLighting,
        default="LIGHT_MODE_TIME",
        update=on_update_oot_render_settings,
    )
    skyboxLightingCustom: StringProperty(
        name="Skybox Lighting Custom", default="0x00", update=on_update_oot_render_settings
    )

    # MM exclusive
    skybox_texture_id: StringProperty(name="Skybox Texture ID", default="0x00")

    # SCENE_CMD_SOUND_SETTINGS
    musicSeq: EnumProperty(name="Music Sequence", items=oot_data.ootEnumMusicSeq, default="NA_BGM_FIELD_LOGIC")
    mm_seq_id: EnumProperty(name="Music Sequence", items=mm_data.enum_seq_id, default="NA_BGM_TERMINA_FIELD")
    musicSeqCustom: StringProperty(name="Music Sequence ID", default="0x00")
    nightSeq: EnumProperty(name="Nighttime SFX", items=oot_data.ootEnumNightSeq, default="0x00")
    mm_ambience_id: EnumProperty(name="Nighttime SFX", items=mm_data.enum_ambiance_id, default="0x00")
    nightSeqCustom: StringProperty(name="Nighttime SFX ID", default="0x00")
    audioSessionPreset: EnumProperty(name="Audio Session Preset", items=ootEnumAudioSessionPreset, default="0x00")
    audioSessionPresetCustom: StringProperty(name="Audio Session Preset", default="0x00")

    # SCENE_CMD_ENV_LIGHT_SETTINGS
    timeOfDayLights: PointerProperty(type=Z64_LightGroupProperty, name="Time Of Day Lighting")
    lightList: CollectionProperty(type=Z64_LightProperty, name="Lighting List")

    # SCENE_CMD_EXIT_LIST
    exitList: CollectionProperty(type=Z64_ExitProperty, name="Exit List")

    writeCutscene: BoolProperty(name="Write Cutscene")
    csWriteType: EnumProperty(name="Cutscene Data Type", items=ootEnumCSWriteType, default="Object")
    csWriteCustom: StringProperty(name="CS hdr var:", default="")
    csWriteObject: PointerProperty(
        name="Cutscene Object",
        type=Object,
        poll=lambda self, object: object.type == "EMPTY" and object.ootEmptyType == "Cutscene",
    )

    extraCutscenes: CollectionProperty(type=Z64_ExtraCutsceneProperty, name="Extra Cutscenes")
    sceneTableEntry: PointerProperty(type=Z64_SceneTableEntryProperty)
    menuTab: EnumProperty(name="Menu", items=ootEnumSceneMenu, update=onMenuTabChange)
    altMenuTab: EnumProperty(name="Menu", items=ootEnumSceneMenuAlternate)

    appendNullEntrance: BoolProperty(
        name="Append Null Entrance",
        description="Add an additional {0, 0} to the end of the EntranceEntry list.",
        default=False,
    )

    ## OoT exclusive

    # SCENE_CMD_MISC_SETTINGS
    mapLocation: EnumProperty(name="Map Location", items=ootEnumMapLocation, default="0x00")
    mapLocationCustom: StringProperty(name="Skybox Lighting Custom", default="0x00")
    cameraMode: EnumProperty(name="Camera Mode", items=ootEnumCameraMode, default="0x00")
    cameraModeCustom: StringProperty(name="Camera Mode Custom", default="0x00")

    ## MM exclusive

    # SCENE_CMD_SET_REGION_VISITED
    set_region_visited: BoolProperty(
        name="Set Region Visited Flag",
        default=False,
        description="Sets a flag that indicates the region has been visited. Scene indices are mapped to their region in `gSceneIdsPerRegion` from `z_inventory.c`",
    )

    # SCENE_CMD_MINIMAP_INFO (note: room informations are defined in `Z64_RoomHeaderProperty`)
    minimap_room_expand: BoolProperty(name="Expand Tab")
    minimap_room_list: CollectionProperty(type=Z64_MapDataRoomProperty, name="Minimap Room List")
    minimap_scale: IntProperty(name="Minimap Scale", default=0)

    # SCENE_CMD_MINIMAP_COMPASS_ICON_INFO
    minimap_chest_expand: BoolProperty(name="Expand Tab")
    minimap_chest_list: CollectionProperty(type=Z64_MapDataChestProperty, name="Minimap Chest List")

    def draw_props(self, layout: UILayout, dropdownLabel: str, headerIndex: int, objName: str):
        from .operators import OOT_SearchMusicSeqEnumOperator, MM_SearchMusicSeqEnumOperator  # temp circular import fix

        cs_index_start = get_cs_index_start()

        if dropdownLabel is not None:
            layout.prop(self, "expandTab", text=dropdownLabel, icon="TRIA_DOWN" if self.expandTab else "TRIA_RIGHT")
            if not self.expandTab:
                return
        if headerIndex is not None and headerIndex > (cs_index_start - 1):
            drawCollectionOps(layout, headerIndex - cs_index_start, "Scene", None, objName)

        if is_game_oot() and headerIndex is not None and headerIndex > 0 and headerIndex < cs_index_start:
            layout.prop(self, "usePreviousHeader", text="Use Previous Header")
            if self.usePreviousHeader:
                return

        if headerIndex is None or headerIndex == 0:
            layout.row().prop(self, "menuTab", expand=True)
            menuTab = self.menuTab
        else:
            layout.row().prop(self, "altMenuTab", expand=True)
            menuTab = self.altMenuTab

        if menuTab == "General":
            general = layout.column()
            general.box().label(text="General")

            # General
            drawEnumWithCustom(
                general, self, get_game_prop_name("global_obj"), "Global Object", "", "globalObjectCustom"
            )
            if is_game_oot():
                drawEnumWithCustom(general, self, "naviCup", "Navi Hints", "")
            if headerIndex is None or headerIndex == 0:
                self.sceneTableEntry.draw_props(general)

            if not is_oot_features():
                general.prop(self, "set_region_visited")

            general.prop(self, "appendNullEntrance")

            # Skybox And Sound
            skyboxAndSound = layout.column()
            skyboxAndSound.box().label(text="Skybox And Sound")

            prop_split(skyboxAndSound, self, "skybox_texture_id", "Skybox Texture ID")
            drawEnumWithCustom(skyboxAndSound, self, get_game_prop_name("skybox_id"), "Skybox", "", "skyboxIDCustom")
            drawEnumWithCustom(
                skyboxAndSound, self, get_game_prop_name("skybox_config"), "Skybox Config", "", "skyboxCloudinessCustom"
            )
            drawEnumWithCustom(
                skyboxAndSound, self, get_game_prop_name("seq_id"), "Music Sequence", "", "musicSeqCustom"
            )

            if is_game_oot():
                op_name = OOT_SearchMusicSeqEnumOperator.bl_idname
            else:
                op_name = MM_SearchMusicSeqEnumOperator.bl_idname

            musicSearch = skyboxAndSound.operator(op_name, icon="VIEWZOOM")
            musicSearch.objName = objName
            musicSearch.headerIndex = headerIndex if headerIndex is not None else 0
            drawEnumWithCustom(
                skyboxAndSound, self, get_game_prop_name("ambience_id"), "Nighttime SFX", "", "nightSeqCustom"
            )
            drawEnumWithCustom(skyboxAndSound, self, "audioSessionPreset", "Audio Session Preset", "")

            # Camera And World Map | Minimap Settings
            if is_oot_features():
                cameraAndWorldMap = layout.column()
                cameraAndWorldMap.box().label(text="Camera And World Map")
                drawEnumWithCustom(cameraAndWorldMap, self, "mapLocation", "Map Location", "")
                drawEnumWithCustom(cameraAndWorldMap, self, "cameraMode", "Camera Mode", "")
            else:
                minimap = layout.column()
                minimap.box().label(text="Minimap Settings")
                prop_split(minimap, self, "minimap_scale", "Minimap Scale")

                map_room_box = minimap.column().box()
                list_length = len(self.minimap_room_list)
                item_count = "Empty" if list_length == 0 else f"{list_length} item{'s' if list_length > 1 else ''}"
                map_room_box.prop(
                    self,
                    "minimap_room_expand",
                    text=f"Minimap Room List ({item_count})",
                    icon="TRIA_DOWN" if self.minimap_room_expand else "TRIA_RIGHT",
                )
                if self.minimap_room_expand:
                    for i in range(list_length):
                        self.minimap_room_list[i].draw_props(map_room_box, i, headerIndex, objName)
                    drawAddButton(map_room_box, list_length, "Minimap Room", headerIndex, objName)

                chest_box = minimap.column().box()
                list_length = len(self.minimap_chest_list)
                item_count = "Empty" if list_length == 0 else f"{list_length} item{'s' if list_length > 1 else ''}"
                chest_box.prop(
                    self,
                    "minimap_chest_expand",
                    text=f"Minimap Chest List ({item_count})",
                    icon="TRIA_DOWN" if self.minimap_chest_expand else "TRIA_RIGHT",
                )
                if self.minimap_chest_expand:
                    for i in range(list_length):
                        self.minimap_chest_list[i].draw_props(chest_box, i, headerIndex, objName)
                    drawAddButton(chest_box, list_length, "Minimap Chest", headerIndex, objName)

        elif menuTab == "Lighting":
            lighting = layout.column()
            lighting.box().label(text="Lighting List")
            drawEnumWithCustom(lighting, self, "skyboxLighting", "Lighting Mode", "")
            if self.skyboxLighting == "LIGHT_MODE_TIME":  # Time of Day
                self.timeOfDayLights.draw_props(lighting)
            else:
                for i in range(len(self.lightList)):
                    self.lightList[i].draw_props(lighting, "Lighting " + str(i), True, i, headerIndex, objName)
                drawAddButton(lighting, len(self.lightList), "Light", headerIndex, objName)

        elif menuTab == "Cutscene":
            cutscene = layout.column()

            cutscene.enabled = is_oot_features()

            r = cutscene.row()
            r.prop(self, "writeCutscene", text="Write Cutscene")
            if self.writeCutscene:
                r.prop(self, "csWriteType", text="Data")
                if self.csWriteType == "Custom":
                    cutscene.prop(self, "csWriteCustom")
                else:
                    cutscene.prop(self, "csWriteObject")

            if headerIndex is None or headerIndex == 0:
                cutscene.label(text="Extra cutscenes (not in any header):")
                for i in range(len(self.extraCutscenes)):
                    box = cutscene.box().column()
                    drawCollectionOps(box, i, "extraCutscenes", None, objName, True)
                    box.prop(self.extraCutscenes[i], "csObject", text="CS obj")
                if len(self.extraCutscenes) == 0:
                    drawAddButton(cutscene, 0, "extraCutscenes", 0, objName)

        elif menuTab == "Exits":
            exitBox = layout.column()
            exitBox.box().label(text="Exit List")
            for i in range(len(self.exitList)):
                self.exitList[i].draw_props(exitBox, i, headerIndex, objName)

            drawAddButton(exitBox, len(self.exitList), "Exit", headerIndex, objName)


def update_cutscene_index(self: "Z64_AlternateSceneHeaderProperty", context: Context):
    cs_index_start = get_cs_index_start()

    if self.currentCutsceneIndex < cs_index_start:
        self.currentCutsceneIndex = cs_index_start

    onHeaderMenuTabChange(self, context)


class Z64_AlternateSceneHeaderProperty(PropertyGroup):
    cutsceneHeaders: CollectionProperty(type=Z64_SceneHeaderProperty)
    currentCutsceneIndex: IntProperty(default=1, update=update_cutscene_index)

    # OoT exclusive
    childNightHeader: PointerProperty(name="Child Night Header", type=Z64_SceneHeaderProperty)
    adultDayHeader: PointerProperty(name="Adult Day Header", type=Z64_SceneHeaderProperty)
    adultNightHeader: PointerProperty(name="Adult Night Header", type=Z64_SceneHeaderProperty)
    headerMenuTab: EnumProperty(name="Header Menu", items=ootEnumHeaderMenu, update=onHeaderMenuTabChange)

    def draw_props(self, layout: UILayout, objName: str):
        headerSetup = layout.column()
        cs_index_start = get_cs_index_start()
        can_draw_cs_header = not is_game_oot()

        if not can_draw_cs_header:
            headerSetupBox = headerSetup.column()
            headerSetupBox.row().prop(self, "headerMenuTab", expand=True)

            if self.headerMenuTab == "Child Night":
                self.childNightHeader.draw_props(headerSetupBox, None, 1, objName)
            elif self.headerMenuTab == "Adult Day":
                self.adultDayHeader.draw_props(headerSetupBox, None, 2, objName)
            elif self.headerMenuTab == "Adult Night":
                self.adultNightHeader.draw_props(headerSetupBox, None, 3, objName)
            elif self.headerMenuTab == "Cutscene":
                can_draw_cs_header = True

        if can_draw_cs_header:
            prop_split(headerSetup, self, "currentCutsceneIndex", "Cutscene Index")
            drawAddButton(headerSetup, len(self.cutsceneHeaders), "Scene", None, objName)
            index = self.currentCutsceneIndex
            if index - cs_index_start < len(self.cutsceneHeaders):
                self.cutsceneHeaders[index - cs_index_start].draw_props(headerSetup, None, index, objName)
            else:
                headerSetup.label(text="No cutscene header for this index.", icon="QUESTION")


class OOT_BootupSceneOptions(PropertyGroup):
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
    bootMode: EnumProperty(default="Play", name="Boot Mode", items=OOTSceneCommon.ootEnumBootMode)

    # see src/code/z_play.c:Play_Init() - can't access more than 16 cutscenes?
    cutsceneIndex: IntProperty(min=4, max=19, default=4, name="Cutscene Index")

    def draw_props(self, layout: UILayout):
        layout.prop(self, "bootToScene", text="Boot To Scene (HackerOOT)")
        if self.bootToScene:
            layout.prop(self, "newGameOnly")
            prop_split(layout, self, "bootMode", "Boot Mode")
            if self.bootMode == "Play":
                prop_split(layout, self, "newGameName", "New Game Name")
            if self.bootMode != "Map Select":
                prop_split(layout, self, "spawnIndex", "Spawn")
                layout.prop(self, "overrideHeader")
                if self.overrideHeader:
                    prop_split(layout, self, "headerOption", "Header Option")
                    if self.headerOption == "Cutscene":
                        prop_split(layout, self, "cutsceneIndex", "Cutscene Index")


class Z64_RemoveSceneSettingsProperty(PropertyGroup):
    name: StringProperty(name="Name", default="spot03")
    subFolder: StringProperty(name="Subfolder", default="overworld")
    customExport: BoolProperty(name="Custom Export Path")
    option: EnumProperty(items=ootEnumSceneID, default="SCENE_DEKU_TREE")
    mm_option: EnumProperty(items=mm_enum_scene_id, default="SCENE_20SICHITAI2")

    def draw_props(self, layout: UILayout):
        if is_game_oot() and self.option == "Custom" or self.mm_option == "Custom":
            prop_split(layout, self, "subFolder", "Subfolder")
            prop_split(layout, self, "name", "Name")


class Z64_ExportSceneSettingsProperty(PropertyGroup):
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
    mm_option: EnumProperty(items=mm_enum_scene_id, default="SCENE_20SICHITAI2")

    def draw_props(self, layout: UILayout):
        if self.customExport:
            prop_split(layout, self, "exportPath", "Directory")
            prop_split(layout, self, "name", "Name")
            customExportWarning(layout)
        else:
            if is_game_oot() and self.option == "Custom" or self.mm_option == "Custom":
                prop_split(layout, self, "subFolder", "Subfolder")
                prop_split(layout, self, "name", "Name")

        prop_split(layout, bpy.context.scene, "ootSceneExportObj", "Scene Object")

        layout.prop(self, "singleFile")
        layout.prop(self, "customExport")


class Z64_ImportSceneSettingsProperty(PropertyGroup):
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
    includeCutscenes: BoolProperty(name="Cutscenes", default=False)
    includeAnimatedMats: BoolProperty(name="Animated Materials", default=False)
    includeActorCs: BoolProperty(name="Actor Cutscenes", default=False)
    option: EnumProperty(items=ootEnumSceneID, default="SCENE_DEKU_TREE")
    mm_option: EnumProperty(items=mm_enum_scene_id, default="SCENE_20SICHITAI2")

    def draw_props(self, layout: UILayout, sceneOption: str):
        col = layout.column()
        includeButtons1 = col.row(align=True)
        includeButtons1.prop(self, "includeMesh", toggle=1)
        includeButtons1.prop(self, "includeCollision", toggle=1)
        includeButtons1.prop(self, "includeActors", toggle=1)

        includeButtons2 = col.row(align=True)
        includeButtons2.prop(self, "includeCullGroups", toggle=1)
        includeButtons2.prop(self, "includeLights", toggle=1)
        includeButtons2.prop(self, "includeCameras", toggle=1)

        includeButtons3 = col.row(align=True)
        includeButtons3.prop(self, "includePaths", toggle=1)
        includeButtons3.prop(self, "includeWaterBoxes", toggle=1)
        includeButtons3.prop(self, "includeCutscenes", toggle=1)

        includeButtons4 = col.row(align=True)
        if not is_oot_features():
            includeButtons4.prop(self, "includeAnimatedMats", toggle=1)
            includeButtons4.prop(self, "includeActorCs", toggle=1)

        col.prop(self, "isCustomDest")

        if self.isCustomDest:
            prop_split(col, self, "destPath", "Directory")
            prop_split(col, self, "name", "Name")
        else:
            if is_game_oot() and self.option == "Custom" or self.mm_option == "Custom":
                prop_split(col, self, "subFolder", "Subfolder")
                prop_split(col, self, "name", "Name")

        if is_game_oot():
            if "SCENE_JABU_JABU" in sceneOption:
                col.label(text="Pulsing wall effect won't be imported.", icon="ERROR")

        if not is_oot_features():
            if not self.includeActors:
                col.label(text="MapDataChest won't be imported.", icon="ERROR")


classes = (
    # OoT exclusive
    OOT_BootupSceneOptions,
    # MM exclusive
    Z64_MapDataChestProperty,
    Z64_MapDataRoomProperty,
    # Common
    Z64_ExitProperty,
    Z64_LightProperty,
    Z64_LightGroupProperty,
    Z64_SceneTableEntryProperty,
    Z64_ExtraCutsceneProperty,
    Z64_SceneHeaderProperty,
    Z64_AlternateSceneHeaderProperty,
    Z64_RemoveSceneSettingsProperty,
    Z64_ExportSceneSettingsProperty,
    Z64_ImportSceneSettingsProperty,
)


def scene_props_register():
    for cls in classes:
        register_class(cls)

    Object.ootSceneHeader = PointerProperty(type=Z64_SceneHeaderProperty)
    Object.ootAlternateSceneHeaders = PointerProperty(type=Z64_AlternateSceneHeaderProperty)
    Scene.ootSceneExportObj = PointerProperty(type=Object, poll=OOTSceneCommon.isSceneObj)
    Scene.ootSceneExportSettings = PointerProperty(type=Z64_ExportSceneSettingsProperty)
    Scene.ootSceneImportSettings = PointerProperty(type=Z64_ImportSceneSettingsProperty)
    Scene.ootSceneRemoveSettings = PointerProperty(type=Z64_RemoveSceneSettingsProperty)


def scene_props_unregister():
    del Object.ootSceneHeader
    del Object.ootAlternateSceneHeaders
    del Scene.ootSceneExportObj
    del Scene.ootSceneExportSettings
    del Scene.ootSceneImportSettings
    del Scene.ootSceneRemoveSettings

    for cls in reversed(classes):
        unregister_class(cls)
