import math, bpy, mathutils
import os
from bpy.utils import register_class, unregister_class
from re import findall, sub
from pathlib import Path
from ..panels import SM64_Panel
from ..operators import ObjectDataExporter

from ..utility import (
    PluginError,
    CData,
    Vector,
    directory_ui_warnings,
    filepath_ui_warnings,
    toAlnum,
    convertRadiansToS16,
    checkIdentityRotation,
    obj_scale_is_unified,
    all_values_equal_x,
    checkIsSM64PreInlineGeoLayout,
    prop_split,
    multilineLabel,
    raisePluginError,
    enumExportHeaderType,
)

from ..f3d.f3d_gbi import (
    DLFormat,
    upgrade_old_prop,
)

from .sm64_constants import (
    levelIDNames,
    enumLevelNames,
    enumModelIDs,
    enumMacrosNames,
    enumSpecialsNames,
    enumBehaviourPresets,
    enumBehaviorMacros,
    enumPresetBehaviors,
    behaviorMacroArguments,
    behaviorPresetContents,
    obj_field_enums,
    obj_group_enums,
    groupsSeg5,
    groupsSeg6,
    groups_obj_export,
)
from .sm64_utility import convert_addr_to_func

from .sm64_spline import (
    assertCurveValid,
    convertSplineObject,
)

from .sm64_geolayout_classes import (
    DisplayListNode,
    JumpNode,
    TranslateNode,
    RotateNode,
    TranslateRotateNode,
    FunctionNode,
    CustomNode,
    BillboardNode,
    ScaleNode,
)


enumTerrain = [
    ("Custom", "Custom", "Custom"),
    ("TERRAIN_GRASS", "Grass", "Grass"),
    ("TERRAIN_STONE", "Stone", "Stone"),
    ("TERRAIN_SNOW", "Snow", "Snow"),
    ("TERRAIN_SAND", "Sand", "Sand"),
    ("TERRAIN_SPOOKY", "Spooky", "Spooky"),
    ("TERRAIN_WATER", "Water", "Water"),
    ("TERRAIN_SLIDE", "Slide", "Slide"),
]

enumMusicSeq = [
    ("Custom", "Custom", "Custom"),
    ("SEQ_LEVEL_BOSS_KOOPA", "Boss Koopa", "Boss Koopa"),
    ("SEQ_LEVEL_BOSS_KOOPA_FINAL", "Boss Koopa Final", "Boss Koopa Final"),
    ("SEQ_LEVEL_GRASS", "Grass Level", "Grass Level"),
    ("SEQ_LEVEL_HOT", "Hot Level", "Hot Level"),
    ("SEQ_LEVEL_INSIDE_CASTLE", "Inside Castle", "Inside Castle"),
    ("SEQ_LEVEL_KOOPA_ROAD", "Koopa Road", "Koopa Road"),
    ("SEQ_LEVEL_SLIDE", "Slide Level", "Slide Level"),
    ("SEQ_LEVEL_SNOW", "Snow Level", "Snow Level"),
    ("SEQ_LEVEL_SPOOKY", "Spooky Level", "Spooky Level"),
    ("SEQ_LEVEL_UNDERGROUND", "Underground Level", "Underground Level"),
    ("SEQ_LEVEL_WATER", "Water Level", "Water Level"),
    ("SEQ_MENU_FILE_SELECT", "File Select", "File Select"),
    ("SEQ_MENU_STAR_SELECT", "Star Select Menu", "Star Select Menu"),
    ("SEQ_MENU_TITLE_SCREEN", "Title Screen", "Title Screen"),
    ("SEQ_EVENT_BOSS", "Boss", "Boss"),
    ("SEQ_EVENT_CUTSCENE_COLLECT_KEY", "Collect Key", "Collect Key"),
    ("SEQ_EVENT_CUTSCENE_COLLECT_STAR", "Collect Star", "Collect Star"),
    ("SEQ_EVENT_CUTSCENE_CREDITS", "Credits", "Credits"),
    ("SEQ_EVENT_CUTSCENE_ENDING", "Ending Cutscene", "Ending Cutscene"),
    ("SEQ_EVENT_CUTSCENE_INTRO", "Intro Cutscene", "Intro Cutscene"),
    ("SEQ_EVENT_CUTSCENE_LAKITU", "Lakitu Cutscene", "Lakitu Cutscene"),
    ("SEQ_EVENT_CUTSCENE_STAR_SPAWN", "Star Spawn", "Star Spawn"),
    ("SEQ_EVENT_CUTSCENE_VICTORY", "Victory Cutscene", "Victory Cutscene"),
    ("SEQ_EVENT_ENDLESS_STAIRS", "Endless Stairs", "Endless Stairs"),
    ("SEQ_EVENT_HIGH_SCORE", "High Score", "High Score"),
    ("SEQ_EVENT_KOOPA_MESSAGE", "Koopa Message", "Koopa Message"),
    ("SEQ_EVENT_MERRY_GO_ROUND", "Merry Go Round", "Merry Go Round"),
    ("SEQ_EVENT_METAL_CAP", "Metal Cap", "Metal Cap"),
    ("SEQ_EVENT_PEACH_MESSAGE", "Peach Message", "Peach Message"),
    ("SEQ_EVENT_PIRANHA_PLANT", "Piranha Lullaby", "Piranha Lullaby"),
    ("SEQ_EVENT_POWERUP", "Powerup", "Powerup"),
    ("SEQ_EVENT_RACE", "Race", "Race"),
    ("SEQ_EVENT_SOLVE_PUZZLE", "Solve Puzzle", "Solve Puzzle"),
    ("SEQ_SOUND_PLAYER", "Sound Player", "Sound Player"),
    ("SEQ_EVENT_TOAD_MESSAGE", "Toad Message", "Toad Message"),
]

enumWarpType = [
    ("Warp", "Warp", "Warp"),
    ("Painting", "Painting", "Painting"),
    ("Instant", "Instant", "Instant"),
]

enumWarpFlag = [
    ("Custom", "Custom", "Custom"),
    ("WARP_NO_CHECKPOINT", "No Checkpoint", "No Checkpoint"),
    ("WARP_CHECKPOINT", "Checkpoint", "Checkpoint"),
]

enumEnvFX = [
    ("Custom", "Custom", "Custom"),
    ("ENVFX_MODE_NONE", "None", "None"),
    ("ENVFX_SNOW_NORMAL", "Snow", "Used in CCM, SL"),
    ("ENVFX_SNOW_WATER", "Water Bubbles", "Used in Secret Aquarium, Sunken Ships"),
    ("ENVFX_SNOW_BLIZZARD", "Blizzard", "Unused"),
    ("ENVFX_FLOWERS", "Flowers", "Unused"),
    ("ENVFX_LAVA_BUBBLES", "Lava Bubbles", "Used in LLL, BitFS, Bowser 2"),
    ("ENVFX_WHIRLPOOL_BUBBLES", "Whirpool Bubbles", "Used in DDD where whirpool is"),
    ("ENVFX_JETSTREAM_BUBBLES", "Jetstream Bubbles", "Used in JRB, DDD where jetstream is"),
]

enumCameraMode = [
    ("Custom", "Custom", "Custom"),
    ("CAMERA_MODE_NONE", "None", "None"),
    ("CAMERA_MODE_RADIAL", "Radial", "Radial"),
    ("CAMERA_MODE_OUTWARD_RADIAL", "Outward Radial", "Outward Radial"),
    ("CAMERA_MODE_BEHIND_MARIO", "Behind Mario", "Behind Mario"),
    ("CAMERA_MODE_CLOSE", "Close", "Close"),
    ("CAMERA_MODE_C_UP", "C Up", "C Up"),
    ("CAMERA_MODE_WATER_SURFACE", "Water Surface", "Water Surface"),
    ("CAMERA_MODE_SLIDE_HOOT", "Slide/Hoot", "Slide/Hoot"),
    ("CAMERA_MODE_INSIDE_CANNON", "Inside Cannon", "Inside Cannon"),
    ("CAMERA_MODE_BOSS_FIGHT", "Boss Fight", "Boss Fight"),
    ("CAMERA_MODE_PARALLEL_TRACKING", "Parallel Tracking", "Parallel Tracking"),
    ("CAMERA_MODE_FIXED", "Fixed", "Fixed"),
    ("CAMERA_MODE_8_DIRECTIONS", "8 Directions", "8 Directions"),
    ("CAMERA_MODE_FREE_ROAM", "Free Roam", "Free Roam"),
    ("CAMERA_MODE_SPIRAL_STAIRS", "Spiral Stairs", "Spiral Stairs"),
]

enumBackground = [
    ("OCEAN_SKY", "Ocean Sky", "Ocean Sky"),
    ("FLAMING_SKY", "Flaming Sky", "Flaming Sky"),
    ("UNDERWATER_CITY", "Underwater City", "Underwater City"),
    ("BELOW_CLOUDS", "Below Clouds", "Below Clouds"),
    ("SNOW_MOUNTAINS", "Snow Mountains", "Snow Mountains"),
    ("DESERT", "Desert", "Desert"),
    ("HAUNTED", "Haunted", "Haunted"),
    ("GREEN_SKY", "Green Sky", "Green Sky"),
    ("ABOVE_CLOUDS", "Above Clouds", "Above Clouds"),
    ("PURPLE_SKY", "Purple Sky", "Purple Sky"),
    ("CUSTOM", "Custom", "Custom"),
]

backgroundSegments = {
    "OCEAN_SKY": "water",
    "FLAMING_SKY": "bitfs",
    "UNDERWATER_CITY": "wdw",
    "BELOW_CLOUDS": "cloud_floor",
    "SNOW_MOUNTAINS": "ccm",
    "DESERT": "ssl",
    "HAUNTED": "bbh",
    "GREEN_SKY": "bidw",
    "ABOVE_CLOUDS": "clouds",
    "PURPLE_SKY": "bits",
}

enumWaterBoxType = [("Water", "Water", "Water"), ("Toxic Haze", "Toxic Haze", "Toxic Haze")]


class InlineGeolayoutObjConfig:
    def __init__(
        self,
        name,
        geo_node,
        can_have_dl=False,
        must_have_dl=False,
        must_have_geo=False,
        uses_location=False,
        uses_rotation=False,
        uses_scale=False,
    ):
        self.name = name
        self.geo_node = geo_node
        self.can_have_dl = can_have_dl or must_have_dl
        self.must_have_dl = must_have_dl
        self.must_have_geo = must_have_geo
        self.uses_location = uses_location
        self.uses_rotation = uses_rotation
        self.uses_scale = uses_scale


inlineGeoLayoutObjects = {
    "Geo ASM": InlineGeolayoutObjConfig("Geo ASM", FunctionNode),
    "Geo Branch": InlineGeolayoutObjConfig("Geo Branch", JumpNode, must_have_geo=True),
    "Geo Translate/Rotate": InlineGeolayoutObjConfig(
        "Geo Translate/Rotate", TranslateRotateNode, can_have_dl=True, uses_location=True, uses_rotation=True
    ),
    "Geo Translate Node": InlineGeolayoutObjConfig(
        "Geo Translate Node", TranslateNode, can_have_dl=True, uses_location=True
    ),
    "Geo Rotation Node": InlineGeolayoutObjConfig(
        "Geo Rotation Node", RotateNode, can_have_dl=True, uses_rotation=True
    ),
    "Geo Billboard": InlineGeolayoutObjConfig("Geo Billboard", BillboardNode, can_have_dl=True, uses_location=True),
    "Geo Scale": InlineGeolayoutObjConfig("Geo Scale", ScaleNode, can_have_dl=True, uses_scale=True),
    "Geo Displaylist": InlineGeolayoutObjConfig("Geo Displaylist", DisplayListNode, must_have_dl=True),
    "Custom Geo Command": InlineGeolayoutObjConfig("Custom Geo Command", CustomNode),
}

# When adding new types related to geolayout,
# Make sure to add exceptions to enumSM64EmptyWithGeolayout
enumObjectType = [
    ("None", "None", "None"),
    ("Level Root", "Level Root", "Level Root"),
    ("Area Root", "Area Root", "Area Root"),
    ("Object", "Object", "Object"),
    ("Macro", "Macro", "Macro"),
    ("Special", "Special", "Special"),
    ("Mario Start", "Mario Start", "Mario Start"),
    ("Whirlpool", "Whirlpool", "Whirlpool"),
    ("Water Box", "Water Box", "Water Box"),
    ("Camera Volume", "Camera Volume", "Camera Volume"),
    ("Switch", "Switch Node", "Switch Node"),
    ("Puppycam Volume", "Puppycam Volume", "Puppycam Volume"),
    ("", "Inline Geolayout Commands", ""),  # This displays as a column header for the next set of options
    *[(key, key, key) for key in inlineGeoLayoutObjects.keys()],
]

enumPuppycamMode = [
    ("Custom", "Custom", "Custom"),
    ("NC_MODE_NORMAL", "Normal", "Normal"),
    ("NC_MODE_SLIDE", "Slide", "Slide"),
    ("NC_MODE_FIXED", "Fixed Position", "Fixed Position"),
    ("NC_MODE_2D", "Two Dimensional", "Two Dimensional"),
    ("NC_MODE_8D", "8 Directions", "8 Directions"),
    ("NC_MODE_FIXED_NOMOVE", "Fixed, No Move", "Fixed, No Move"),
    ("NC_MODE_NOTURN", "No Turning", "No Turning"),
    ("NC_MODE_NOROTATE", "No Rotation", "No Rotation"),
]

enumPuppycamFlags = [
    ("NC_FLAG_XTURN", "X Turn", "the camera's yaw can be moved by the player."),
    ("NC_FLAG_YTURN", "Y Turn", "the camera's pitch can be moved by the player."),
    ("NC_FLAG_ZOOM", "Zoom", "the camera's distance can be set by the player."),
    ("NC_FLAG_8D", "8 Directions", "the camera will snap to an 8 directional axis"),
    ("NC_FLAG_4D", "4 Directions", "the camera will snap to a 4 directional axis"),
    ("NC_FLAG_2D", "2D", "the camera will stick to 2D."),
    ("NC_FLAG_FOCUSX", "Use X Focus", "the camera will point towards its focus on the X axis."),
    ("NC_FLAG_FOCUSY", "Use Y Focus", "the camera will point towards its focus on the Y axis."),
    ("NC_FLAG_FOCUSZ", "Use Z Focus", "the camera will point towards its focus on the Z axis."),
    ("NC_FLAG_POSX", "Move on X axis", "the camera will move along the X axis."),
    ("NC_FLAG_POSY", "Move on Y axis", "the camera will move along the Y axis."),
    ("NC_FLAG_POSZ", "Move on Z axis", "the camera will move along the Z axis."),
    ("NC_FLAG_COLLISION", "Collision", "the camera will collide and correct itself with terrain."),
    (
        "NC_FLAG_SLIDECORRECT",
        "Slide Correction",
        "the camera will attempt to centre itself behind Mario whenever he's sliding.",
    ),
]


class SM64_Object:
    def __init__(self, model, position, rotation, behaviour, bparam, acts, name):
        self.model = model
        self.behaviour = behaviour
        self.bparam = bparam
        self.acts = acts
        self.position = position
        self.rotation = rotation
        self.name = name  # to sort by when exporting

    def to_c(self):
        if self.acts == 0x1F:
            return (
                "OBJECT("
                + str(self.model)
                + ", "
                + str(int(round(self.position[0])))
                + ", "
                + str(int(round(self.position[1])))
                + ", "
                + str(int(round(self.position[2])))
                + ", "
                + str(int(round(math.degrees(self.rotation[0]))))
                + ", "
                + str(int(round(math.degrees(self.rotation[1]))))
                + ", "
                + str(int(round(math.degrees(self.rotation[2]))))
                + ", "
                + str(self.bparam)
                + ", "
                + str(self.behaviour)
                + ")"
            )
        else:
            return (
                "OBJECT_WITH_ACTS("
                + str(self.model)
                + ", "
                + str(int(round(self.position[0])))
                + ", "
                + str(int(round(self.position[1])))
                + ", "
                + str(int(round(self.position[2])))
                + ", "
                + str(int(round(math.degrees(self.rotation[0]))))
                + ", "
                + str(int(round(math.degrees(self.rotation[1]))))
                + ", "
                + str(int(round(math.degrees(self.rotation[2]))))
                + ", "
                + str(self.bparam)
                + ", "
                + str(self.behaviour)
                + ", "
                + str(self.acts)
                + ")"
            )


class SM64_Whirpool:
    def __init__(self, index, condition, strength, position):
        self.index = index
        self.condition = condition
        self.strength = strength
        self.position = position
        self.name = "whirlpool"  # for sorting

    def to_c(self):
        return (
            "WHIRPOOL("
            + str(self.index)
            + ", "
            + str(self.condition)
            + ", "
            + str(int(round(self.position[0])))
            + ", "
            + str(int(round(self.position[1])))
            + ", "
            + str(int(round(self.position[2])))
            + ", "
            + str(self.strength)
            + ")"
        )


class SM64_Macro_Object:
    def __init__(self, preset, position, rotation, bparam):
        self.preset = preset
        self.bparam = bparam
        self.position = position
        self.rotation = rotation

    def to_c(self):
        if self.bparam is None:
            return (
                "MACRO_OBJECT("
                + str(self.preset)
                + ", "
                + str(int(round(math.degrees(self.rotation[1]))))
                + ", "
                + str(int(round(self.position[0])))
                + ", "
                + str(int(round(self.position[1])))
                + ", "
                + str(int(round(self.position[2])))
                + ")"
            )
        else:
            return (
                "MACRO_OBJECT_WITH_BEH_PARAM("
                + str(self.preset)
                + ", "
                + str(int(round(math.degrees(self.rotation[1]))))
                + ", "
                + str(int(round(self.position[0])))
                + ", "
                + str(int(round(self.position[1])))
                + ", "
                + str(int(round(self.position[2])))
                + ", "
                + str(self.bparam)
                + ")"
            )


class SM64_Special_Object:
    def __init__(self, preset, position, rotation, bparam):
        self.preset = preset
        self.bparam = bparam
        self.position = position
        self.rotation = rotation

    def to_binary(self):
        data = int(self.preset).to_bytes(2, "big")
        if len(self.position) > 3:
            raise PluginError("Object position should not be " + str(len(self.position) + " fields long."))
        for index in self.position:
            data.extend(int(round(index)).to_bytes(2, "big", signed=False))
        if self.rotation is not None:
            data.extend(int(round(math.degrees(self.rotation[1]))).to_bytes(2, "big"))
            if self.bparam is not None:
                data.extend(int(self.bparam).to_bytes(2, "big"))
        return data

    def to_c(self):
        if self.rotation is None:
            return (
                "SPECIAL_OBJECT("
                + str(self.preset)
                + ", "
                + str(int(round(self.position[0])))
                + ", "
                + str(int(round(self.position[1])))
                + ", "
                + str(int(round(self.position[2])))
                + "),\n"
            )
        elif self.bparam is None:
            return (
                "SPECIAL_OBJECT_WITH_YAW("
                + str(self.preset)
                + ", "
                + str(int(round(self.position[0])))
                + ", "
                + str(int(round(self.position[1])))
                + ", "
                + str(int(round(self.position[2])))
                + ", "
                + str(int(round(math.degrees(self.rotation[1]))))
                + "),\n"
            )
        else:
            return (
                "SPECIAL_OBJECT_WITH_YAW_AND_PARAM("
                + str(self.preset)
                + ", "
                + str(int(round(self.position[0])))
                + ", "
                + str(int(round(self.position[1])))
                + ", "
                + str(int(round(self.position[2])))
                + ", "
                + str(int(round(math.degrees(self.rotation[1]))))
                + ", "
                + str(self.bparam)
                + "),\n"
            )


class SM64_Mario_Start:
    def __init__(self, area, position, rotation):
        self.area = area
        self.position = position
        self.rotation = rotation
        self.name = "Mario"  # for sorting

    def to_c(self):
        return (
            "MARIO_POS("
            + str(self.area)
            + ", "
            + str(int(round(math.degrees(self.rotation[1]))))
            + ", "
            + str(int(round(self.position[0])))
            + ", "
            + str(int(round(self.position[1])))
            + ", "
            + str(int(round(self.position[2])))
            + ")"
        )


class SM64_Area:
    def __init__(
        self, index, music_seq, music_preset, terrain_type, geolayout, collision, warpNodes, name, startDialog
    ):
        self.cameraVolumes = []
        self.puppycamVolumes = []
        self.name = toAlnum(name)
        self.geolayout = geolayout
        self.collision = collision
        self.index = index
        self.objects = []
        self.macros = []
        self.specials = []
        self.water_boxes = []
        self.music_preset = music_preset
        self.music_seq = music_seq
        self.terrain_type = terrain_type
        self.warpNodes = warpNodes
        self.mario_start = None
        self.splines = []
        self.startDialog = startDialog

    def macros_name(self):
        return self.name + "_macro_objs"

    def to_c_script(self, includeRooms, persistentBlockString: str = ""):
        data = ""
        data += "\tAREA(" + str(self.index) + ", " + self.geolayout.name + "),\n"
        for warpNode in self.warpNodes:
            data += "\t\t" + warpNode + ",\n"
        # export objects in name order
        for obj in sorted(self.objects, key=(lambda obj: obj.name)):
            data += "\t\t" + obj.to_c() + ",\n"
        data += "\t\tTERRAIN(" + self.collision.name + "),\n"
        if includeRooms:
            data += "\t\tROOMS(" + self.collision.rooms_name() + "),\n"
        data += "\t\tMACRO_OBJECTS(" + self.macros_name() + "),\n"
        if self.music_seq is None:
            data += "\t\tSTOP_MUSIC(0),\n"
        else:
            data += "\t\tSET_BACKGROUND_MUSIC(" + self.music_preset + ", " + self.music_seq + "),\n"
        if self.startDialog is not None:
            data += "\t\tSHOW_DIALOG(0x00, " + self.startDialog + "),\n"
        data += "\t\tTERRAIN_TYPE(" + self.terrain_type + "),\n"
        data += f"{persistentBlockString}\n"
        data += "\tEND_AREA(),\n"
        return data

    def to_c_macros(self):
        data = CData()
        data.header = "extern const MacroObject " + self.macros_name() + "[];\n"
        data.source += "const MacroObject " + self.macros_name() + "[] = {\n"
        for macro in self.macros:
            data.source += "\t" + macro.to_c() + ",\n"
        data.source += "\tMACRO_OBJECT_END(),\n};\n\n"

        return data

    def to_c_camera_volumes(self):
        data = ""
        for camVolume in self.cameraVolumes:
            data += "\t" + camVolume.to_c() + "\n"
        return data

    def to_c_puppycam_volumes(self):
        data = ""
        for puppycamVolume in self.puppycamVolumes:
            data += "\t" + puppycamVolume.to_c() + "\n"
        return data

    def hasCutsceneSpline(self):
        for spline in self.splines:
            if spline.splineType == "Cutscene":
                return True
        return False

    def to_c_splines(self):
        data = CData()
        for spline in self.splines:
            data.append(spline.to_c())
        if self.hasCutsceneSpline():
            data.source = '#include "src/game/camera.h"\n\n' + data.source
            data.header = '#include "src/game/camera.h"\n\n' + data.header
        return data


class CollisionWaterBox:
    def __init__(self, waterBoxType, position, scale, emptyScale):
        # The scale ordering is due to the fact that scaling happens AFTER rotation.
        # Thus the translation uses Y-up, while the scale uses Z-up.
        self.waterBoxType = waterBoxType
        self.low = (position[0] - scale[0] * emptyScale, position[2] - scale[1] * emptyScale)
        self.high = (position[0] + scale[0] * emptyScale, position[2] + scale[1] * emptyScale)
        self.height = position[1] + scale[2] * emptyScale

    def to_binary(self):
        data = bytearray([0x00, 0x00 if self.waterBoxType == "Water" else 0x32])
        data.extend(int(round(self.low[0])).to_bytes(2, "big", signed=True))
        data.extend(int(round(self.low[1])).to_bytes(2, "big", signed=True))
        data.extend(int(round(self.high[0])).to_bytes(2, "big", signed=True))
        data.extend(int(round(self.high[1])).to_bytes(2, "big", signed=True))
        data.extend(int(round(self.height)).to_bytes(2, "big", signed=True))
        return data

    def to_c(self):
        data = (
            "COL_WATER_BOX("
            + ("0x00" if self.waterBoxType == "Water" else "0x32")
            + ", "
            + str(int(round(self.low[0])))
            + ", "
            + str(int(round(self.low[1])))
            + ", "
            + str(int(round(self.high[0])))
            + ", "
            + str(int(round(self.high[1])))
            + ", "
            + str(int(round(self.height)))
            + "),\n"
        )
        return data


class CameraVolume:
    def __init__(self, area, functionName, position, rotation, scale, emptyScale):
        # The scale ordering is due to the fact that scaling happens AFTER rotation.
        # Thus the translation uses Y-up, while the scale uses Z-up.
        self.area = area
        self.functionName = functionName
        self.position = position
        self.scale = mathutils.Vector((scale[0], scale[2], scale[1])) * emptyScale
        self.rotation = rotation

    def to_binary(self):
        raise PluginError("Binary exporting not implemented for camera volumens.")

    def to_c(self):
        data = (
            "{"
            + str(self.area)
            + ", "
            + str(self.functionName)
            + ", "
            + str(int(round(self.position[0])))
            + ", "
            + str(int(round(self.position[1])))
            + ", "
            + str(int(round(self.position[2])))
            + ", "
            + str(int(round(self.scale[0])))
            + ", "
            + str(int(round(self.scale[1])))
            + ", "
            + str(int(round(self.scale[2])))
            + ", "
            + str(convertRadiansToS16(self.rotation[1]))
            + "},"
        )
        return data


class PuppycamVolume:
    def __init__(self, area, level, permaswap, functionName, position, scale, emptyScale, camPos, camFocus, mode):
        self.level = level
        self.area = area
        self.functionName = functionName
        self.permaswap = permaswap
        self.mode = mode

        # camPos and camFocus are in blender scale, z-up
        # xyz, beginning and end
        self.begin = (position[0] - scale[0], position[1] - scale[2], position[2] - scale[1])
        self.end = (position[0] + scale[0], position[1] + scale[2], position[2] + scale[1])
        camScaleValue = bpy.context.scene.fast64.sm64.blender_to_sm64_scale

        # xyz for pos and focus obtained from chosen empties or from selected camera (32767 is ignore flag)
        if camPos != (32767, 32767, 32767):
            self.camPos = (camPos[0] * camScaleValue, camPos[2] * camScaleValue, camPos[1] * camScaleValue * -1)
        else:
            self.camPos = camPos

        if camFocus != (32767, 32767, 32767):
            self.camFocus = (camFocus[0] * camScaleValue, camFocus[2] * camScaleValue, camFocus[1] * camScaleValue * -1)
        else:
            self.camFocus = camFocus

    def to_binary(self):
        raise PluginError("Binary exporting not implemented for puppycam volumes.")

    def to_c(self):
        data = (
            "{"
            + str(self.level)
            + ", "
            + str(self.area)
            + ", "
            + ("1" if self.permaswap else "0")
            + ", "
            + str(self.mode)
            + (", &" if str(self.functionName) != "0" else ", ")
            + str(self.functionName)
            + ", "
            + str(int(round(self.begin[0])))
            + ", "
            + str(int(round(self.begin[1])))
            + ", "
            + str(int(round(self.begin[2])))
            + ", "
            + str(int(round(self.end[0])))
            + ", "
            + str(int(round(self.end[1])))
            + ", "
            + str(int(round(self.end[2])))
            + ", "
            + str(int(round(self.camPos[0])))
            + ", "
            + str(int(round(self.camPos[1])))
            + ", "
            + str(int(round(self.camPos[2])))
            + ", "
            + str(int(round(self.camFocus[0])))
            + ", "
            + str(int(round(self.camFocus[1])))
            + ", "
            + str(int(round(self.camFocus[2])))
            + "},"
        )
        return data


def exportAreaCommon(areaObj, transformMatrix, geolayout, collision, name):
    bpy.ops.object.select_all(action="DESELECT")
    areaObj.select_set(True)

    if not areaObj.noMusic:
        if areaObj.musicSeqEnum != "Custom":
            musicSeq = areaObj.musicSeqEnum
        else:
            musicSeq = areaObj.music_seq
    else:
        musicSeq = None

    if areaObj.terrainEnum != "Custom":
        terrainType = areaObj.terrainEnum
    else:
        terrainType = areaObj.terrain_type

    area = SM64_Area(
        areaObj.areaIndex,
        musicSeq,
        areaObj.music_preset,
        terrainType,
        geolayout,
        collision,
        [areaObj.warpNodes[i].to_c() for i in range(len(areaObj.warpNodes))],
        name,
        areaObj.startDialog if areaObj.showStartDialog else None,
    )

    start_process_sm64_objects(areaObj, area, transformMatrix, False)

    return area


# These are all done in reference to refresh 8
def handleRefreshDiffModelIDs(modelID):
    refresh_version = bpy.context.scene.fast64.sm64.refresh_version
    if refresh_version == "Refresh 6":
        if modelID == "MODEL_TWEESTER":
            modelID = "MODEL_TORNADO"
    elif refresh_version == {"Refresh 3", "Refresh 4", "Refresh 5"}:
        if modelID == "MODEL_TWEESTER":
            modelID = "MODEL_TORNADO"
        elif modelID == "MODEL_WAVE_TRAIL":
            modelID = "MODEL_WATER_WAVES"
        elif modelID == "MODEL_IDLE_WATER_WAVE":
            modelID = "MODEL_WATER_WAVES_SURF"
        elif modelID == "MODEL_SMALL_WATER_SPLASH":
            modelID = "MODEL_SPOT_ON_GROUND"

    return modelID


def start_process_sm64_objects(obj, area, transformMatrix, specialsOnly):
    # spaceRotation = mathutils.Quaternion((1, 0, 0), math.radians(90.0)).to_matrix().to_4x4()

    # We want translations to be relative to area obj, but rotation/scale to be world space
    translation, rotation, scale = obj.matrix_world.decompose()
    process_sm64_objects(obj, area, mathutils.Matrix.Translation(translation), transformMatrix, specialsOnly)


def process_sm64_objects(obj, area, rootMatrix, transformMatrix, specialsOnly):
    translation, originalRotation, scale = (transformMatrix @ rootMatrix.inverted() @ obj.matrix_world).decompose()

    final_transform = (
        mathutils.Matrix.Translation(translation)
        @ originalRotation.to_matrix().to_4x4()
        @ mathutils.Matrix.Diagonal(scale).to_4x4()
    )

    # Hacky solution to handle Z-up to Y-up conversion
    rotation = (originalRotation @ mathutils.Quaternion((1, 0, 0), math.radians(90.0))).to_euler("ZXY")

    if obj.type == "EMPTY":
        if obj.sm64_obj_type == "Area Root" and obj.areaIndex != area.index:
            return
        if specialsOnly:
            if obj.sm64_obj_type == "Special":
                preset = obj.sm64_special_enum if obj.sm64_special_enum != "Custom" else obj.sm64_obj_preset
                area.specials.append(
                    SM64_Special_Object(
                        preset,
                        translation,
                        rotation if obj.sm64_obj_set_yaw else None,
                        obj.fast64.sm64.game_object.get_behavior_params()
                        if (obj.sm64_obj_set_yaw and obj.sm64_obj_set_bparam)
                        else None,
                    )
                )
            elif obj.sm64_obj_type == "Water Box":
                checkIdentityRotation(obj, rotation.to_quaternion(), False)
                area.water_boxes.append(CollisionWaterBox(obj.waterBoxType, translation, scale, obj.empty_display_size))
        else:
            if obj.sm64_obj_type == "Object":
                modelID = obj.sm64_model_enum if obj.sm64_model_enum != "Custom" else obj.sm64_obj_model
                modelID = handleRefreshDiffModelIDs(modelID)
                behaviour = (
                    convert_addr_to_func(obj.sm64_behaviour_enum)
                    if obj.sm64_behaviour_enum != "Custom"
                    else obj.sm64_obj_behaviour
                )
                area.objects.append(
                    SM64_Object(
                        modelID,
                        translation,
                        rotation,
                        behaviour,
                        obj.fast64.sm64.game_object.get_behavior_params(),
                        get_act_string(obj),
                        obj.name,
                    )
                )
            elif obj.sm64_obj_type == "Macro":
                macro = obj.sm64_macro_enum if obj.sm64_macro_enum != "Custom" else obj.sm64_obj_preset
                area.macros.append(
                    SM64_Macro_Object(
                        macro,
                        translation,
                        rotation,
                        obj.fast64.sm64.game_object.get_behavior_params() if obj.sm64_obj_set_bparam else None,
                    )
                )
            elif obj.sm64_obj_type == "Mario Start":
                mario_start = SM64_Mario_Start(obj.sm64_obj_mario_start_area, translation, rotation)
                area.objects.append(mario_start)
                area.mario_start = mario_start
            elif obj.sm64_obj_type == "Trajectory":
                pass
            elif obj.sm64_obj_type == "Whirpool":
                area.objects.append(
                    SM64_Whirpool(obj.whirlpool_index, obj.whirpool_condition, obj.whirpool_strength, translation)
                )
            elif obj.sm64_obj_type == "Camera Volume":
                checkIdentityRotation(obj, rotation.to_quaternion(), True)
                if obj.cameraVolumeGlobal:
                    triggerIndex = -1
                else:
                    triggerIndex = area.index
                area.cameraVolumes.append(
                    CameraVolume(
                        triggerIndex,
                        obj.cameraVolumeFunction,
                        translation,
                        rotation,
                        scale,
                        obj.empty_display_size,
                    )
                )

            elif obj.sm64_obj_type == "Puppycam Volume":
                checkIdentityRotation(obj, rotation.to_quaternion(), False)

                triggerIndex = area.index
                puppycamProp = obj.puppycamProp
                if puppycamProp.puppycamUseFlags:
                    puppycamModeString = "0"
                    if puppycamProp.NC_FLAG_XTURN:
                        puppycamModeString += " | NC_FLAG_XTURN"
                    if puppycamProp.NC_FLAG_YTURN:
                        puppycamModeString += " | NC_FLAG_YTURN"
                    if puppycamProp.NC_FLAG_ZOOM:
                        puppycamModeString += " | NC_FLAG_ZOOM"
                    if puppycamProp.NC_FLAG_8D:
                        puppycamModeString += " | NC_FLAG_8D"
                    if puppycamProp.NC_FLAG_4D:
                        puppycamModeString += " | NC_FLAG_4D"
                    if puppycamProp.NC_FLAG_2D:
                        puppycamModeString += " | NC_FLAG_2D"
                    if puppycamProp.NC_FLAG_FOCUSX:
                        puppycamModeString += " | NC_FLAG_FOCUSX"
                    if puppycamProp.NC_FLAG_FOCUSY:
                        puppycamModeString += " | NC_FLAG_FOCUSY"
                    if puppycamProp.NC_FLAG_FOCUSZ:
                        puppycamModeString += " | NC_FLAG_FOCUSZ"
                    if puppycamProp.NC_FLAG_POSX:
                        puppycamModeString += " | NC_FLAG_POSX"
                    if puppycamProp.NC_FLAG_POSY:
                        puppycamModeString += " | NC_FLAG_POSY"
                    if puppycamProp.NC_FLAG_POSZ:
                        puppycamModeString += " | NC_FLAG_POSZ"
                    if puppycamProp.NC_FLAG_COLLISION:
                        puppycamModeString += " | NC_FLAG_COLLISION"
                    if puppycamProp.NC_FLAG_SLIDECORRECT:
                        puppycamModeString += " | NC_FLAG_SLIDECORRECT"
                else:
                    puppycamModeString = (
                        puppycamProp.puppycamMode
                        if puppycamProp.puppycamMode != "Custom"
                        else puppycamProp.puppycamType
                    )

                if (not puppycamProp.puppycamUseEmptiesForPos) and puppycamProp.puppycamCamera is not None:
                    puppycamCamPosCoords = puppycamProp.puppycamCamera.location
                elif puppycamProp.puppycamUseEmptiesForPos and puppycamProp.puppycamCamPos != "":
                    puppycamPosObject = bpy.context.scene.objects[puppycamProp.puppycamCamPos]
                    puppycamCamPosCoords = puppycamPosObject.location
                else:
                    puppycamCamPosCoords = (32767, 32767, 32767)

                if (not puppycamProp.puppycamUseEmptiesForPos) and puppycamProp.puppycamCamera is not None:
                    puppycamCamFocusCoords = (puppycamProp.puppycamCamera.matrix_local @ mathutils.Vector((0, 0, -1)))[
                        :
                    ]
                elif puppycamProp.puppycamUseEmptiesForPos and puppycamProp.puppycamCamFocus != "":
                    puppycamFocObject = bpy.context.scene.objects[puppycamProp.puppycamCamFocus]
                    puppycamCamFocusCoords = puppycamFocObject.location
                else:
                    puppycamCamFocusCoords = (32767, 32767, 32767)

                area.puppycamVolumes.append(
                    PuppycamVolume(
                        triggerIndex,
                        levelIDNames[bpy.context.scene.fast64.sm64.export_level_name],
                        puppycamProp.puppycamVolumePermaswap,
                        puppycamProp.puppycamVolumeFunction,
                        translation,
                        scale,
                        obj.empty_display_size,
                        puppycamCamPosCoords,
                        puppycamCamFocusCoords,
                        puppycamModeString,
                    )
                )

    elif not specialsOnly and assertCurveValid(obj):
        area.splines.append(convertSplineObject(area.name + "_spline_" + obj.name, obj, final_transform))

    for child in obj.children:
        process_sm64_objects(child, area, rootMatrix, transformMatrix, specialsOnly)


def get_act_string(obj):
    if (
        obj.sm64_obj_use_act1
        and obj.sm64_obj_use_act2
        and obj.sm64_obj_use_act3
        and obj.sm64_obj_use_act4
        and obj.sm64_obj_use_act5
        and obj.sm64_obj_use_act6
    ):
        return 0x1F
    elif (
        not obj.sm64_obj_use_act1
        and not obj.sm64_obj_use_act2
        and not obj.sm64_obj_use_act3
        and not obj.sm64_obj_use_act4
        and not obj.sm64_obj_use_act5
        and not obj.sm64_obj_use_act6
    ):
        return 0
    else:
        data = ""
        if obj.sm64_obj_use_act1:
            data += (" | " if len(data) > 0 else "") + "ACT_1"
        if obj.sm64_obj_use_act2:
            data += (" | " if len(data) > 0 else "") + "ACT_2"
        if obj.sm64_obj_use_act3:
            data += (" | " if len(data) > 0 else "") + "ACT_3"
        if obj.sm64_obj_use_act4:
            data += (" | " if len(data) > 0 else "") + "ACT_4"
        if obj.sm64_obj_use_act5:
            data += (" | " if len(data) > 0 else "") + "ACT_5"
        if obj.sm64_obj_use_act6:
            data += (" | " if len(data) > 0 else "") + "ACT_6"
        return data


class SearchModelIDEnumOperator(bpy.types.Operator):
    bl_idname = "object.search_model_id_enum_operator"
    bl_label = "Search Model IDs"
    bl_property = "sm64_model_enum"
    bl_options = {"REGISTER", "UNDO"}

    sm64_model_enum: bpy.props.EnumProperty(items=enumModelIDs)

    def execute(self, context):
        context.object.sm64_model_enum = self.sm64_model_enum
        bpy.context.region.tag_redraw()
        self.report({"INFO"}, "Selected: " + self.sm64_model_enum)
        return {"FINISHED"}

    def invoke(self, context, event):
        context.window_manager.invoke_search_popup(self)
        return {"RUNNING_MODAL"}


class SearchBehaviourEnumOperator(bpy.types.Operator):
    bl_idname = "object.search_behaviour_enum_operator"
    bl_label = "Search Behaviours"
    bl_property = "sm64_behaviour_enum"
    bl_options = {"REGISTER", "UNDO"}

    sm64_behaviour_enum: bpy.props.EnumProperty(items=enumBehaviourPresets)

    def execute(self, context):
        context.object.sm64_behaviour_enum = self.sm64_behaviour_enum
        bpy.context.region.tag_redraw()
        name = convert_addr_to_func(self.sm64_behaviour_enum) if self.sm64_behaviour_enum != "Custom" else "Custom"
        self.report({"INFO"}, "Selected: " + name)
        return {"FINISHED"}

    def invoke(self, context, event):
        context.window_manager.invoke_search_popup(self)
        return {"RUNNING_MODAL"}


class SearchMacroEnumOperator(bpy.types.Operator):
    bl_idname = "object.search_macro_enum_operator"
    bl_label = "Search Macros"
    bl_property = "sm64_macro_enum"
    bl_options = {"REGISTER", "UNDO"}

    sm64_macro_enum: bpy.props.EnumProperty(items=enumMacrosNames)

    def execute(self, context):
        context.object.sm64_macro_enum = self.sm64_macro_enum
        bpy.context.region.tag_redraw()
        self.report({"INFO"}, "Selected: " + self.sm64_macro_enum)
        return {"FINISHED"}

    def invoke(self, context, event):
        context.window_manager.invoke_search_popup(self)
        return {"RUNNING_MODAL"}


class SearchSpecialEnumOperator(bpy.types.Operator):
    bl_idname = "object.search_special_enum_operator"
    bl_label = "Search Specials"
    bl_property = "sm64_special_enum"
    bl_options = {"REGISTER", "UNDO"}

    sm64_special_enum: bpy.props.EnumProperty(items=enumSpecialsNames)

    def execute(self, context):
        context.object.sm64_special_enum = self.sm64_special_enum
        bpy.context.region.tag_redraw()
        self.report({"INFO"}, "Selected: " + self.sm64_special_enum)
        return {"FINISHED"}

    def invoke(self, context, event):
        context.window_manager.invoke_search_popup(self)
        return {"RUNNING_MODAL"}


class SM64ObjectPanel(bpy.types.Panel):
    bl_label = "Object Inspector"
    bl_idname = "OBJECT_PT_SM64_Object_Inspector"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "object"
    bl_options = {"HIDE_HEADER"}

    @classmethod
    def poll(cls, context):
        return context.scene.gameEditorMode == "SM64" and (
            context.object is not None and context.object.type == "EMPTY"
        )

    def draw_inline_obj(self, box: bpy.types.UILayout, obj: bpy.types.Object):
        obj_details: InlineGeolayoutObjConfig = inlineGeoLayoutObjects.get(obj.sm64_obj_type)

        # display transformation warnings
        warnings = set()
        if obj_details.uses_scale and not obj_scale_is_unified(obj):
            warnings.add("Object's scale must all be the same exact value (e.g. 2, 2, 2)")

        if not obj_details.uses_scale and not all_values_equal_x(obj.scale, 1):
            warnings.add("Object's scale values must all be set to 1")

        loc = obj.matrix_local.decompose()[0]
        if not obj_details.uses_location and not all_values_equal_x(loc, 0):
            warnings.add("Object's relative location must be set to 0")

        if not obj_details.uses_rotation and not all_values_equal_x(obj.rotation_euler, 0):
            warnings.add("Object's rotations must be set to 0")

        if len(warnings):
            warning_box = box.box()
            warning_box.alert = True
            warning_box.label(text="Warning: Unexpected export results from these issues:", icon="ERROR")
            for warning in warnings:
                warning_box.label(text=warning, icon="ERROR")
            warning_box.label(text=f'Relative location: {", ".join([str(l) for l in loc])}')

        if obj.sm64_obj_type == "Geo ASM":
            prop_split(box, obj.fast64.sm64.geo_asm, "func", "Function")
            prop_split(box, obj.fast64.sm64.geo_asm, "param", "Parameter")
            return

        elif obj.sm64_obj_type == "Custom Geo Command":
            prop_split(box, obj, "customGeoCommand", "Geo Macro")
            prop_split(box, obj, "customGeoCommandArgs", "Parameters")
            return

        if obj_details.can_have_dl:
            prop_split(box, obj, "draw_layer_static", "Draw Layer")

            if not obj_details.must_have_dl:
                prop_split(box, obj, "useDLReference", "Use DL Reference")

            if obj_details.must_have_dl or obj.useDLReference:
                # option to specify a mesh instead of string reference
                prop_split(box, obj, "dlReference", "Displaylist variable or hex address")

        if obj_details.must_have_geo:
            prop_split(box, obj, "geoReference", "Geolayout variable or hex address")

        if obj_details.uses_rotation or obj_details.uses_location or obj_details.uses_scale:
            info_box = box.box()
            info_box.label(text="Note: uses empty object's:")
            if obj_details.uses_location:
                info_box.label(text="Location", icon="DOT")
            if obj_details.uses_rotation:
                info_box.label(text="Rotation", icon="DOT")
            if obj_details.uses_scale:
                info_box.label(text="Scale", icon="DOT")

        if len(obj.children):
            if checkIsSM64PreInlineGeoLayout(obj.sm64_obj_type):
                box.box().label(text="Children of this object will just be the following geo commands.")
            else:
                box.box().label(text="Children of this object will be wrapped in GEO_OPEN_NODE and GEO_CLOSE_NODE.")

    def draw_behavior_params(self, obj: bpy.types.Object, parent_box: bpy.types.UILayout):
        game_object = obj.fast64.sm64.game_object  # .bparams
        parent_box.separator()
        box = parent_box.box()
        box.label(text="Behavior Parameters")

        box.prop(game_object, "use_individual_params", text="Use Individual Behavior Params")

        if game_object.use_individual_params:
            individuals = box.box()
            individuals.label(text="Individual Behavior Parameters")
            column = individuals.column()
            for i in range(1, 5):
                row = column.row()
                row.prop(game_object, f"bparam{i}", text=f"Param {i}")
            individuals.separator(factor=0.25)
            individuals.label(text=f"Result: {game_object.get_combined_bparams()}")
        else:
            box.separator(factor=0.5)
            box.label(text="All Behavior Parameters")
            box.prop(game_object, "bparams", text="")
            parent_box.separator()

    def draw(self, context):
        prop_split(self.layout, context.scene, "gameEditorMode", "Game")
        box = self.layout.box().column()
        column = self.layout.box().column()  # added just for puppycam trigger importing
        box.box().label(text="SM64 Object Inspector")
        obj = context.object
        props = obj.fast64.sm64

        prop_split(box, obj, "sm64_obj_type", "Object Type")
        if obj.sm64_obj_type == "Object":
            prop_split(box, obj, "sm64_model_enum", "Model")
            if obj.sm64_model_enum == "Custom":
                prop_split(box, obj, "sm64_obj_model", "Model ID")
            box.operator(SearchModelIDEnumOperator.bl_idname, icon="VIEWZOOM")
            box.box().label(text="Model IDs defined in include/model_ids.h.")
            prop_split(box, obj, "sm64_behaviour_enum", "Behaviour")
            if obj.sm64_behaviour_enum == "Custom":
                prop_split(box, obj, "sm64_obj_behaviour", "Behaviour Name")
            box.operator(SearchBehaviourEnumOperator.bl_idname, icon="VIEWZOOM")
            behaviourLabel = box.box()
            behaviourLabel.label(text="Behaviours defined in include/behaviour_data.h.")
            behaviourLabel.label(text="Actual contents in data/behaviour_data.c.")
            self.draw_behavior_params(obj, box)
            self.draw_acts(obj, box)

        elif obj.sm64_obj_type == "Macro":
            prop_split(box, obj, "sm64_macro_enum", "Preset")
            if obj.sm64_macro_enum == "Custom":
                prop_split(box, obj, "sm64_obj_preset", "Preset Name")
            box.operator(SearchMacroEnumOperator.bl_idname, icon="VIEWZOOM")
            box.box().label(text="Macro presets defined in include/macro_preset_names.h.")
            box.prop(obj, "sm64_obj_set_bparam", text="Set Behaviour Parameter")
            if obj.sm64_obj_set_bparam:
                self.draw_behavior_params(obj, box)

        elif obj.sm64_obj_type == "Special":
            prop_split(box, obj, "sm64_special_enum", "Preset")
            if obj.sm64_special_enum == "Custom":
                prop_split(box, obj, "sm64_obj_preset", "Preset Name")
            box.operator(SearchSpecialEnumOperator.bl_idname, icon="VIEWZOOM")
            box.box().label(text="Special presets defined in include/special_preset_names.h.")
            box.prop(obj, "sm64_obj_set_yaw", text="Set Yaw")
            if obj.sm64_obj_set_yaw:
                box.prop(obj, "sm64_obj_set_bparam", text="Set Behaviour Parameter")
                if obj.sm64_obj_set_bparam:
                    self.draw_behavior_params(obj, box)

        elif obj.sm64_obj_type == "Mario Start":
            prop_split(box, obj, "sm64_obj_mario_start_area", "Area")

        elif obj.sm64_obj_type == "Trajectory":
            pass

        elif obj.sm64_obj_type == "Whirlpool":
            prop_split(box, obj, "whirpool_index", "Index")
            prop_split(box, obj, "whirpool_condition", "Condition")
            prop_split(box, obj, "whirpool_strength", "Strength")
            pass

        elif obj.sm64_obj_type == "Water Box":
            prop_split(box, obj, "waterBoxType", "Water Box Type")
            box.box().label(text="Water box area defined by top face of box shaped empty.")
            box.box().label(text="No rotation allowed.")

        elif obj.sm64_obj_type == "Level Root":
            levelObj = obj.fast64.sm64.level
            if obj.useBackgroundColor:
                prop_split(box, obj, "backgroundColor", "Background Color")
                box.prop(obj, "useBackgroundColor")
            else:
                # prop_split(box, obj, 'backgroundID', 'Background ID')
                prop_split(box, obj, "background", "Background")
                if obj.background == "CUSTOM":
                    prop_split(box, levelObj, "backgroundID", "Custom ID")
                    prop_split(box, levelObj, "backgroundSegment", "Custom Background Segment")
                    segmentExportBox = box.box()
                    segmentExportBox.label(
                        text=f"Exported Segment: _{levelObj.backgroundSegment}_{context.scene.fast64.sm64.compression_format}SegmentRomStart"
                    )
                box.prop(obj, "useBackgroundColor")
                # box.box().label(text = 'Background IDs defined in include/geo_commands.h.')
            box.prop(obj, "actSelectorIgnore")
            box.prop(obj, "setAsStartLevel")
            grid = box.grid_flow(columns=2)
            obj.fast64.sm64.segment_loads.draw(grid)
            prop_split(box, obj, "acousticReach", "Acoustic Reach")
            obj.starGetCutscenes.draw(box)

        elif obj.sm64_obj_type == "Area Root":
            area_props = props.area
            # Code that used to be in area inspector
            prop_split(box, obj, "areaIndex", "Area Index")
            box.prop(obj, "noMusic", text="Disable Music")
            if not obj.noMusic:
                prop_split(box, obj, "music_preset", "Music Preset")
                prop_split(box, obj, "musicSeqEnum", "Music Sequence")
                if obj.musicSeqEnum == "Custom":
                    prop_split(box, obj, "music_seq", "")

            prop_split(box, obj, "terrainEnum", "Terrain")
            if obj.terrainEnum == "Custom":
                prop_split(box, obj, "terrain_type", "")
            prop_split(box, obj, "envOption", "Environment Type")
            if obj.envOption == "Custom":
                prop_split(box, obj, "envType", "")
            prop_split(box, obj, "camOption", "Camera Type")
            if obj.camOption == "Custom":
                prop_split(box, obj, "camType", "")
            camBox = box.box()
            camBox.label(text="Warning: Camera modes can be overriden by area specific camera code.")
            camBox.label(text="Check the switch statment in camera_course_processing() in src/game/camera.c.")

            fog_box = box.box().column()
            fog_box.prop(area_props, "set_fog")
            fog_props = fog_box.column()
            fog_props.enabled = area_props.set_fog
            multilineLabel(
                fog_props,
                "All materials in the area with fog and\n"
                '"Use Area\'s Fog" enabled will use these fog\n'
                "settings.\n"
                "Each material will have its own fog\n"
                "applied as vanilla SM64 has no fog system.",
                icon="INFO",
            )
            prop_split(fog_props, obj, "area_fog_color", "Color")
            prop_split(fog_props, obj, "area_fog_position", "Position")

            if obj.areaIndex == 1 or obj.areaIndex == 2 or obj.areaIndex == 3:
                prop_split(box, obj, "echoLevel", "Echo Level")

            if obj.areaIndex == 1 or obj.areaIndex == 2 or obj.areaIndex == 3 or obj.areaIndex == 4:
                box.prop(obj, "zoomOutOnPause")

            box.prop(area_props, "disable_background")

            areaLayout = box.box()
            areaLayout.enabled = not obj.fast64.sm64.area.disable_background
            areaLayout.prop(obj, "areaOverrideBG")
            if obj.areaOverrideBG:
                prop_split(areaLayout, obj, "areaBGColor", "Background Color")

            box.prop(obj, "showStartDialog")
            if obj.showStartDialog:
                prop_split(box, obj, "startDialog", "Start Dialog")
                dialogBox = box.box()
                dialogBox.label(text="See text/us/dialogs.h for values.")
                dialogBox.label(text="See load_level_init_text() in src/game/level_update.c for conditions.")
            box.prop(obj, "enableRoomSwitch")
            if obj.enableRoomSwitch:
                infoBox = box.box()
                infoBox.label(
                    text="Every child hierarchy of the area root will be treated as its own room (except for the first one.)"
                )
                infoBox.label(
                    text='You can use empties with the "None" type as empty geolayout nodes to group related geometry under.'
                )
                infoBox.label(text="Children will ordered alphabetically, with the first child being always visible.")
            box.prop(obj, "useDefaultScreenRect")
            if not obj.useDefaultScreenRect:
                prop_split(box, obj, "screenPos", "Screen Position")
                prop_split(box, obj, "screenSize", "Screen Size")

            prop_split(box, obj, "clipPlanes", "Clip Planes")

            box.label(text="Warp Nodes")
            box.operator(AddWarpNode.bl_idname).option = len(obj.warpNodes)
            for i in range(len(obj.warpNodes)):
                drawWarpNodeProperty(box, obj.warpNodes[i], i)

        elif obj.sm64_obj_type == "Camera Volume":
            prop_split(box, obj, "cameraVolumeFunction", "Camera Function")
            box.prop(obj, "cameraVolumeGlobal")
            box.box().label(text="Only vertical axis rotation allowed.")

        elif obj.sm64_obj_type == "Puppycam Volume":
            puppycamProp = obj.puppycamProp
            prop_split(column, puppycamProp, "puppycamVolumeFunction", "Puppycam Function")
            column.prop(puppycamProp, "puppycamVolumePermaswap")
            column.prop(puppycamProp, "puppycamUseFlags")

            column.prop(puppycamProp, "puppycamUseEmptiesForPos")

            if puppycamProp.puppycamUseEmptiesForPos:
                column.label(text="Fixed Camera Position (Optional)")
                column.prop_search(puppycamProp, "puppycamCamPos", bpy.data, "objects", text="")

                column.label(text="Fixed Camera Focus (Optional)")
                column.prop_search(puppycamProp, "puppycamCamFocus", bpy.data, "objects", text="")
            else:
                column.label(text="Fixed Camera Position (Optional)")
                column.prop(puppycamProp, "puppycamCamera")
                if puppycamProp.puppycamCamera is not None:
                    column.box().label(text="FOV not exported, only for preview camera.")
                    prop_split(column, puppycamProp, "puppycamFOV", "Camera FOV")
                    column.operator("mesh.puppycam_setup_camera", text="Setup Camera", icon="VIEW_CAMERA")

            if puppycamProp.puppycamUseFlags:
                for i, flagSet in enumerate(enumPuppycamFlags):
                    column.prop(puppycamProp, flagSet[0])
            else:
                prop_split(column, puppycamProp, "puppycamMode", "Camera Mode")
                if puppycamProp.puppycamMode == "Custom":
                    prop_split(column, puppycamProp, "puppycamType", "")

            column.box().label(text="No rotation allowed.")

        elif obj.sm64_obj_type == "Switch":
            prop_split(box, obj, "switchFunc", "Function")
            prop_split(box, obj, "switchParam", "Parameter")
            box.box().label(text="Children will ordered alphabetically.")

        elif obj.sm64_obj_type in inlineGeoLayoutObjects:
            self.draw_inline_obj(box, obj)

        elif obj.sm64_obj_type == "None":
            box.box().label(text="This can be used as an empty transform node in a geolayout hierarchy.")

    def draw_acts(self, obj, layout):
        layout.label(text="Acts")
        acts = layout.row()
        self.draw_act(obj, acts, 1)
        self.draw_act(obj, acts, 2)
        self.draw_act(obj, acts, 3)
        self.draw_act(obj, acts, 4)
        self.draw_act(obj, acts, 5)
        self.draw_act(obj, acts, 6)

    def draw_act(self, obj, layout, value):
        layout = layout.column()
        layout.label(text=str(value))
        layout.prop(obj, "sm64_obj_use_act" + str(value), text="")


class AddBehavior(bpy.types.Operator):
    bl_idname = "scene.add_behavior_script"
    bl_label = "Add Behavior Script"
    option: bpy.props.IntProperty()

    def execute(self, context):
        prop = context.scene.fast64.sm64.combined_export
        prop.behavior_script.add()
        prop.behavior_script.move(len(prop.behavior_script) - 1, self.option)
        self.report({"INFO"}, "Success!")
        return {"FINISHED"}


class RemoveBehavior(bpy.types.Operator):
    bl_idname = "scene.remove_behavior_script"
    bl_label = "Remove Behavior Script"
    option: bpy.props.IntProperty()

    def execute(self, context):
        prop = context.scene.fast64.sm64.combined_export
        prop.behavior_script.remove(self.option)
        self.report({"INFO"}, "Success!")
        return {"FINISHED"}


class BehaviorScriptProperty(bpy.types.PropertyGroup):
    expand: bpy.props.BoolProperty(name="Expand", default=True)
    macro: bpy.props.EnumProperty(items=enumBehaviorMacros, name="Behavior Macro", default="BEGIN")
    object_fields: bpy.props.EnumProperty(items=obj_field_enums, name="Object Fields", default="oFlags")
    object_fields1: bpy.props.EnumProperty(items=obj_field_enums, name="Object Fields 1", default="oPosX")
    object_fields2: bpy.props.EnumProperty(items=obj_field_enums, name="Object Fields 2", default="oPosX")
    object_list: bpy.props.EnumProperty(items=obj_group_enums, name="Object List", default="OBJ_LIST_GENACTOR")
    # there are anywhere from 0 to 3 arguments for a bhv, rather than make a new prop
    # group and collection prop, I'll just have static props and choose to use
    # arguments as needed
    arg_1: bpy.props.StringProperty(name="Argument 1")
    arg_2: bpy.props.StringProperty(name="Argument 2")
    arg_3: bpy.props.StringProperty(name="Argument 3")
    # for gravity, 8 args are used, but everything else only uses a max of 3
    arg_4: bpy.props.StringProperty(name="Argument 4")
    arg_5: bpy.props.StringProperty(name="Argument 5")
    arg_6: bpy.props.StringProperty(name="Argument 6")
    arg_7: bpy.props.StringProperty(name="Argument 7")
    arg_8: bpy.props.StringProperty(name="Argument 8")
    # some objects have cmds that make sense to dynamically inherit it from export properties
    # load collision, or set model ID are easy examples
    inherit_from_export: bpy.props.BoolProperty(name="Inherit From Export")
    _inheritable_macros = {
        "LOAD_COLLISION_DATA",
        "SET_MODEL",
        # add support later maybe
        # "SET_HITBOX_WITH_OFFSET",
        # "SET_HITBOX",
        # "SET_HURTBOX",
    }

    # custom cmd variables
    num_args: bpy.props.IntProperty(name="Num Arguments", min=0, max=8)

    @property
    def bhv_args(self):
        return behaviorMacroArguments.get(self.macro)

    @property
    def arg_fields(self):
        return ("arg_1", "arg_2", "arg_3", "arg_4", "arg_5", "arg_6", "arg_7", "arg_8")

    @property
    def macro_args(self):
        if self.bhv_args:
            return [
                getattr(self, *self.field_or_enum(field, arg_name))
                for field, arg_name in zip(self.arg_fields, self.bhv_args)
            ]

    def field_or_enum(self, field, arg_name):
        if self.macro == "BEGIN":
            enum = "object_list"
            if self.object_list == "Custom":
                return field, enum
            else:
                return enum, None
        if "Field" in arg_name:
            digit = search[0][-1] if (search := findall("Field\s\d", arg_name)) else ""
            enum = f"object_fields{digit}"
            if getattr(self, enum) == "Custom":
                return field, enum
            else:
                return enum, None
        else:
            return field, None

    def get_inherit_args(self, context, props):
        assert self.macro in self._inheritable_macros

        if self.macro == "SET_MODEL":
            if not props.export_gfx:
                raise PluginError("Can't inherit model without exporting gfx data")
            return props.model_id_define
        if self.macro == "LOAD_COLLISION_DATA":
            if not props.export_col:
                raise PluginError("Can't inherit collision without exporting collision data")
            return props.collision_name
        return self.macro_args

    def get_args(self, context, props):
        if self.inherit_from_export and self.macro in self._inheritable_macros:
            return self.get_inherit_args(context, props)
        elif self.macro_args:
            return ", ".join(self.macro_args)
        else:
            return ""

    def draw(self, layout, index):
        box = layout.box().column()
        box.prop(
            self,
            "expand",
            text=f"Bhv Cmd:   {self.macro}",
            icon="TRIA_DOWN" if self.expand else "TRIA_RIGHT",
        )
        if self.expand:
            prop_split(box, self, "macro", "Behavior Macro")
            if self.macro in self._inheritable_macros:
                box.prop(self, "inherit_from_export")
            if self.macro == "Custom":
                prop_split(box, self, "num_args", "Num Arguments")
                for j in range(self.num_args):
                    prop_split(box, self, f"arg_{j + 1}", f"arg_{j + 1}")
            elif self.bhv_args and not (self.inherit_from_export and self.macro in self._inheritable_macros):
                for field, arg_name in zip(self.arg_fields, self.bhv_args):
                    draw_field, draw_enum = self.field_or_enum(field, arg_name)
                    if draw_enum:
                        split_1 = box.split(factor=0.45)
                        split_2 = split_1.split(factor=0.45)
                        split_2.label(text=arg_name)
                        split_2.prop(self, draw_enum, text="")
                        split_1.prop(self, draw_field, text="")
                    else:
                        prop_split(box, self, draw_field, arg_name)
            row = box.row()
            row.operator("scene.add_behavior_script", text="Add Bhv Cmd").option = index + 1
            row.operator("scene.remove_behavior_script", text="Remove Bhv Cmd").option = index


class SM64_ExportCombinedObject(ObjectDataExporter):
    bl_idname = "object.sm64_export_combined_object"
    bl_label = "SM64 Combined Object"

    def write_file_lines(self, path, file_lines):
        with open(path, "w") as file:
            [file.write(line) for line in file_lines]

    # exports the model ID load into the appropriate script.c location
    def export_script_load(self, context, props):
        decomp_path = Path(bpy.path.abspath(bpy.context.scene.fast64.sm64.decomp_path))
        if props.export_header_type == "Level":
            # for some reason full_level_path doesn't work here
            if props.non_decomp_level:
                levels_path = Path(props.full_level_path)
            else:
                levels_path = decomp_path / "levels" / props.export_level_name
            script_path = levels_path / "script.c"
            self.export_level_specific_load(script_path, props)
        elif props.export_header_type == "Actor":
            script_path = decomp_path / "levels" / "scripts.c"
            self.export_group_script_load(script_path, props)

    # delims to notify for when to start and end for sig/alt
    # if match line, then write out to that line
    # elif fast64_sig, insert after that line
    # else insert after alt_condition
    def find_export_lines(
        self, file_lines, match_str=None, fast64_signature=None, alt_condition=None, start_delim=None, end_delim=None
    ):
        search_sig = False if start_delim else True
        insert_line = 0
        alt_insert_line = 0
        match_line = 0
        for j, line in enumerate(file_lines):
            if start_delim and start_delim in line:
                search_sig = True
                insert_line = j
                continue
            if search_sig and match_str and match_str in line:
                match_line = j
                break
            if search_sig and fast64_signature and fast64_signature in line:
                insert_line = j
            if alt_condition is not None and alt_condition in line:
                alt_insert_line = j
            if end_delim and end_delim in line:
                search_sig = False
        return match_line, insert_line, alt_insert_line

    # export the model ID to /include/model_ids.h
    def export_model_id(self, context, props, offset):
        # won't find model_ids.h
        if props.non_decomp_level:
            return
        # check if model_ids.h exists
        decomp_path = Path(bpy.path.abspath(bpy.context.scene.fast64.sm64.decomp_path))
        model_ids = decomp_path / "include" / "model_ids.h"
        if not model_ids.exists():
            PluginError("Could not find model_ids.h")

        model_id_lines = open(model_ids, "r").readlines()
        export_model_id = f"#define {props.model_id_define: <34}{props.model_id + offset}\n"
        fast64_sig = "/* fast64 object exports get inserted here */"

        match_line, sig_insert_line, default_line = self.find_export_lines(
            model_id_lines,
            match_str=f"#define {props.model_id_define} ",
            fast64_signature=fast64_sig,
            alt_condition="#define MODEL_NONE",
        )

        if match_line:
            model_id_lines[match_line] = export_model_id
        elif sig_insert_line:
            model_id_lines.insert(sig_insert_line + 1, export_model_id)
        else:
            export_line = default_line + 1 if default_line else len(model_id_lines)
            model_id_lines.insert(export_line, f"\n{fast64_sig}\n")
            model_id_lines.insert(export_line + 1, export_model_id)

        self.write_file_lines(model_ids, model_id_lines)

    def export_group_script_load(self, script_path, props):
        if not script_path.exists():
            PluginError(f"Could not find {script_path.stem}")

        # do I somehow support this?
        if props.group_name == "Custom":
            return

        # add model load to existing global script func
        script_lines = open(script_path, "r").readlines()
        script_load = f"    LOAD_MODEL_FROM_GEO({props.model_id_define}, {props.geo_name}),\n"

        if props.group_num == 0:
            script = "level_main_scripts_entry"
        else:
            script = f"script_func_global_{props.group_num}"

        match_line, sig_insert_line, default_line = self.find_export_lines(
            script_lines,
            match_str=f"{props.model_id_define},",
            start_delim=f"const LevelScript {script}[]",
            end_delim="};",
        )

        if match_line:
            script_lines[match_line] = script_load
        elif sig_insert_line and props.group_num == 0:
            for i, line in enumerate(script_lines[sig_insert_line:]):
                if "ALLOC_LEVEL_POOL()" in line:
                    script_lines.insert(sig_insert_line + i + 1, script_load)
                    break
                elif "FREE_LEVEL_POOL()" in line:
                    script_lines.insert(sig_insert_line + i, script_load)
                    break
                elif "};" in line:
                    raise PluginError(f"Could not find FREE_LEVEL_POOL() or ALLOC_LEVEL_POOL() in {script}")
        elif sig_insert_line:
            script_lines.insert(sig_insert_line + 1, script_load)
        else:
            raise PluginError(f"Could not find {script} in {script_path}")

        self.write_file_lines(script_path, script_lines)

    def export_level_specific_load(self, script_path, props):
        if not script_path.exists():
            PluginError(f"Could not find {script_path.stem}")
        script_lines = open(script_path, "r").readlines()

        # place model load into custom level script array
        script_load = f"\tLOAD_MODEL_FROM_GEO({props.model_id_define}, {props.geo_name}),\n"
        fast64_level_script = f"fast64_{props.export_level_name}_loads"

        match_line, sig_insert_line, default_line = self.find_export_lines(
            script_lines,
            match_str=f"{props.model_id_define},",
            fast64_signature=f"const LevelScript {fast64_level_script}[]",
            alt_condition="#include ",
            start_delim=f"const LevelScript {fast64_level_script}[]",
            end_delim="RETURN()",
        )

        if match_line:
            script_lines[match_line] = script_load
        elif sig_insert_line:
            script_lines.insert(sig_insert_line + 1, script_load)
        else:
            export_line = default_line + 1 if default_line else len(script_lines)
            script_lines.insert(export_line, f"\nconst LevelScript {fast64_level_script}[] = {{\n")
            script_lines.insert(export_line + 1, script_load)
            script_lines.insert(export_line + 2, "\tRETURN(),\n")
            script_lines.insert(export_line + 3, "};\n")

        # jump to custom level script array
        match_line, sig_insert_line, default_line = self.find_export_lines(
            script_lines,
            match_str=f"JUMP_LINK({fast64_level_script})",
            fast64_signature="JUMP_LINK(",
            start_delim="ALLOC_LEVEL_POOL(",
            end_delim="AREA(",
        )

        if not match_line and sig_insert_line:
            script_lines.insert(sig_insert_line + 1, f"\tJUMP_LINK({fast64_level_script}),\n")
        elif not match_line and default_line:
            script_lines.insert(default_line, f"\tJUMP_LINK({fast64_level_script}),\n")

        self.write_file_lines(script_path, script_lines)

    def export_behavior_header(self, context, props):
        # check if behavior_header.h exists
        decomp_path = Path(bpy.path.abspath(bpy.context.scene.fast64.sm64.decomp_path))
        behavior_header = decomp_path / "include" / "behavior_data.h"
        if not behavior_header.exists():
            PluginError("Could not find behavior_data.h")

        bhv_header_lines = open(behavior_header, "r").readlines()
        export_bhv_include = f"extern const BehaviorScript {props.bhv_name}[];\n"
        fast64_sig = "/* fast64 object exports get inserted here */"

        match_line, sig_insert_line, default_line = self.find_export_lines(
            bhv_header_lines,
            match_str=export_bhv_include,
            fast64_signature=fast64_sig,
            alt_condition='#include "types.h"',
        )

        if match_line:
            bhv_header_lines[match_line] = export_bhv_include
        elif sig_insert_line:
            bhv_header_lines.insert(sig_insert_line + 1, export_bhv_include)
        else:
            export_line = default_line + 1 if default_line else len(bhv_header_lines)
            bhv_header_lines.insert(export_line, f"\n{fast64_sig}\n")
            bhv_header_lines.insert(export_line + 1, export_bhv_include)

        self.write_file_lines(behavior_header, bhv_header_lines)

    # export the behavior script, edits /data/behaviour_data.c and /include/behaviour_data.h
    def export_behavior_script(self, context, props):
        # make sure you have a bhv script
        if len(props.behavior_script) == 0:
            raise PluginError("Behavior must have more than 0 cmds to export")

        # export the behavior script itself
        decomp_path = Path(bpy.path.abspath(bpy.context.scene.fast64.sm64.decomp_path))
        behavior_data = decomp_path / "data" / "behavior_data.c"
        if not behavior_data.exists():
            PluginError("Could not find behavior_data.c")

        # add at top of bhvs, 3 lines after this is found
        bhv_data_lines = open(behavior_data, "r").readlines()

        if props.export_header_type == "Actor":
            include = f'#include "actors/{toAlnum(props.actor_group_name)}.h"\n'
        elif props.export_header_type == "Level" and not props.non_decomp_level:
            include = f'#include "levels/{toAlnum(props.export_level_name)}/header.h"\n'
        match_line, sig_insert_line, default_line = self.find_export_lines(
            bhv_data_lines,
            match_str=include,
            alt_condition='#include "',
        )
        if match_line:
            bhv_data_lines[match_line] = include
        elif sig_insert_line:
            bhv_data_lines.insert(sig_insert_line + 1, include)
        else:
            export_line = default_line + 1 if default_line else len(bhv_data_lines)
            bhv_data_lines.insert(export_line, include)

        export_bhv_name = f"const BehaviorScript {props.bhv_name}[] = {{\n"
        last_bhv_define = "#define SPAWN_WATER_DROPLET(dropletParams)"
        fast64_sig = "/* fast64 object exports get inserted here */"

        match_line, sig_insert_line, default_line = self.find_export_lines(
            bhv_data_lines, match_str=export_bhv_name, fast64_signature=fast64_sig, alt_condition=last_bhv_define
        )

        if match_line:
            for j, line in enumerate(bhv_data_lines[match_line + 1 :]):
                if "BehaviorScript" in line:
                    bhv_data_lines = bhv_data_lines[:match_line] + bhv_data_lines[j + match_line + 1 :]
                    break
            export_line = match_line - 1
        elif sig_insert_line:
            export_line = sig_insert_line
        else:
            export_line = default_line + 3 if default_line else len(bhv_data_lines)
            bhv_data_lines.insert(export_line, f"\n{fast64_sig}\n")
        bhv_data_lines.insert(export_line + 1, export_bhv_name)

        indent_level = 1
        tab_str = "\t"
        for j, bhv_cmd in enumerate(props.behavior_script):
            if bhv_cmd.macro in {"END_REPEAT", "END_REPEAT_CONTINUE", "END_LOOP"}:
                indent_level -= 1
            bhv_macro = f"{tab_str*indent_level}{bhv_cmd.macro}({bhv_cmd.get_args(context, props)}),\n"
            bhv_data_lines.insert(export_line + 2 + j, bhv_macro)
            if bhv_cmd.macro in {"BEGIN_REPEAT", "BEGIN_LOOP"}:
                indent_level += 1
        bhv_data_lines.insert(export_line + 3 + j, "};\n\n")

        self.write_file_lines(behavior_data, bhv_data_lines)
        # exporting bhv header
        self.export_behavior_header(context, props)

    # verify you can run this operator
    def verify_context(self, context, props):
        if context.mode != "OBJECT":
            raise PluginError("Operator can only be used in object mode.")
        if context.scene.fast64.sm64.export_type != "C":
            raise PluginError("Combined Object Export only supports C exporting")
        if not props.col_object and not props.gfx_object and not props.bhv_object:
            raise PluginError("No export object selected")
        if (
            context.active_object
            and context.active_object.type == "EMPTY"
            and context.active_object.sm64_obj_type == "Level Root"
        ):
            raise PluginError('Cannot export levels with "Export Object" Operator')

    def get_export_objects(self, context, props):
        if not props.export_all_selected:
            return {props.col_object, props.gfx_object, props.bhv_object}.difference({None})

        def obj_root(object, context):
            while object.parent and object.parent in context.selected_objects:
                if object.parent_type in {"ARMATURE", "OBJECT"}:
                    return obj_root(object.parent, context)
                else:
                    return object
            return object

        root_objects = {obj_root(obj, context) for obj in context.selected_objects}
        actor_objs = []
        for obj in root_objects:
            # eval this
            if "Geo" in obj.sm64_obj_type or obj.sm64_obj_type in {"None", "Switch"}:
                actor_objs.append(obj)

        return actor_objs

    # writes collision.inc.c file, collision_header.h
    # writes include into aggregate file in export location (leveldata.c/<group>.c)
    # writes name to header in aggregate file location (actor/level)
    # var name is: const Collision <props.col_obj>_collision[]
    def execute_col(self, props, obj):
        try:
            if props.export_col and props.obj_name_col and obj is props.col_object:
                bpy.ops.object.sm64_export_collision(export_obj=obj.name)
        except Exception as exc:
            # pass on multiple export, throw on singular
            if not props.export_all_selected:
                raise Exception(exc) from exc

    # writes model.inc.c, geo.inc.c file, geo_header.h
    # writes include into aggregate file (leveldata.c/<group>.c & geo.c)
    # writes name to header in aggregate file (header.h/<group>.h)
    # writes model ID to model_ids.h, ID starts at prop and increments from there
    # writes load to levels/scripts.c in appropriate group or in levels/lvl/script.c
    # var name is: const GeoLayout <props.gfx_obj>_geo[]
    def execute_gfx(self, props, context, obj, index):
        try:
            if props.export_gfx and props.obj_name_gfx and obj is props.gfx_object:
                if obj.type == "ARMATURE":
                    bpy.ops.object.sm64_export_geolayout_armature(export_obj=obj.name)
                else:
                    bpy.ops.object.sm64_export_geolayout_object(export_obj=obj.name)
                # write model ID, behavior, and level script load
                if props.export_script_loads and props.model_id != 0:
                    self.export_model_id(context, props, index)
                    self.export_script_load(context, props)
        except Exception as e:
            # pass on multiple export, throw on singular
            if not props.export_all_selected:
                raise Exception(e)

    def execute(self, context):
        props = context.scene.fast64.sm64.combined_export
        try:
            self.verify_context(context, props)
            actor_objs = self.get_export_objects(context, props)

            for index, obj in enumerate(actor_objs):
                props.context_obj = obj
                self.execute_col(props, obj)
                self.execute_gfx(props, context, obj, index)
                # do not export behaviors with multiple selection
                if props.export_bhv and props.obj_name_bhv and not props.export_all_selected:
                    self.export_behavior_script(context, props)
        except Exception as e:
            props.context_obj = None
            raisePluginError(self, e)
            return {"CANCELLED"}

        props.context_obj = None
        # you've done it!~
        self.report({"INFO"}, "Success!")
        return {"FINISHED"}


class SM64_CombinedObjectProperties(bpy.types.PropertyGroup):
    # callbacks must be defined before they are referenced in props
    def update_preset_behavior(self, context):
        def update_or_inherit(new_cmd, index, arg_val, bhv_arg):
            if arg_val == "inherit":
                new_cmd.inherit_from_export = True
            else:
                arg_field, _ = new_cmd.field_or_enum(f"arg_{index + 1}", bhv_arg)
                setattr(new_cmd, arg_field, arg_val)

        self.behavior_script.clear()
        bhv_preset = behaviorPresetContents.get(self.preset_behavior_script)
        if bhv_preset:
            for cmd in bhv_preset:
                new_cmd = self.behavior_script.add()
                new_cmd.expand = False
                new_cmd.macro = cmd[0]
                [
                    update_or_inherit(new_cmd, j, arg_val, bhv_arg)
                    for j, (arg_val, bhv_arg) in enumerate(zip(cmd[1], new_cmd.bhv_args))
                ]

    # internal object used to keep track during exports. Updated by export function
    context_obj: bpy.props.PointerProperty(type=bpy.types.Object)

    export_header_type: bpy.props.EnumProperty(
        name="Header Export",
        items=[*enumExportHeaderType, ("Custom", "Custom", "No headers are written")],
        default="Actor",
    )
    # level export header
    level_name: bpy.props.EnumProperty(items=enumLevelNames, name="Level", default="bob")
    custom_level_name: bpy.props.StringProperty(name="custom")
    non_decomp_level: bpy.props.BoolProperty(name="Custom Export Path")
    custom_level_path: bpy.props.StringProperty(name="Custom Path", subtype="FILE_PATH")

    # actor export header
    group_name: bpy.props.EnumProperty(name="Group Name", default="group0", items=groups_obj_export)
    # custom export path, no headers written
    custom_export_path: bpy.props.StringProperty(name="Custom Path", subtype="FILE_PATH")
    custom_include_directory: bpy.props.StringProperty(name="Include directory", subtype="FILE_PATH")

    # common export opts
    custom_group_name: bpy.props.StringProperty(name="custom")  # for custom group
    model_id: bpy.props.IntProperty(
        name="Model ID Num", default=0xE2, min=0, description="Export model ID number. A model ID of 0 exports nothing"
    )
    object_name: bpy.props.StringProperty(name="Actor Name", default="")

    # collision export options
    include_children: bpy.props.BoolProperty(
        name="Include Children",
        default=True,
        description="Collision export will include all child objects of linked/selected object",
    )
    export_rooms: bpy.props.BoolProperty(
        name="Export Rooms", description="Collision export will generate rooms.inc.c file"
    )

    # export options
    export_bhv: bpy.props.BoolProperty(
        name="Export Behavior", default=False, description="Export behavior with given object name"
    )
    export_col: bpy.props.BoolProperty(
        name="Export Collision", description="Export collision for linked or selected mesh that have collision data"
    )
    export_gfx: bpy.props.BoolProperty(
        name="Export Graphics", description="Export geo layouts for linked or selected mesh that have collision data"
    )
    export_script_loads: bpy.props.BoolProperty(
        name="Export Script Loads",
        description="Exports the Model ID and adds a level script load in the appropriate place",
    )
    export_all_selected: bpy.props.BoolProperty(
        name="Export All Selected",
        description="Export geo layouts and collision for all selected objects. Behavior will only export for the active object. Use with caution",
    )
    use_name_filtering: bpy.props.BoolProperty(
        name="Use Name Filtering",
        default=True,
        description="Filters common suffixes like _col or _geo from obj names so objs with same root but different suffixes export to the same folder",
    )

    # actual behavior
    behavior_script: bpy.props.CollectionProperty(type=BehaviorScriptProperty)
    preset_behavior_script: bpy.props.EnumProperty(
        items=enumPresetBehaviors, default="Custom", update=update_preset_behavior
    )

    collision_object: bpy.props.PointerProperty(type=bpy.types.Object)
    graphics_object: bpy.props.PointerProperty(type=bpy.types.Object)

    # is this abuse of properties?
    @property
    def col_object(self):
        if not self.export_col:
            return None
        if self.export_all_selected:
            return self.context_obj or bpy.context.active_object
        else:
            return self.collision_object or self.context_obj or bpy.context.active_object

    @property
    def gfx_object(self):
        if not self.export_gfx:
            return None
        if self.export_all_selected:
            return self.context_obj or bpy.context.active_object
        else:
            return self.graphics_object or self.context_obj or bpy.context.active_object

    @property
    def bhv_object(self):
        if not self.export_bhv or self.export_all_selected:
            return None
        else:
            return self.col_object or self.gfx_object or self.context_obj or bpy.context.active_object

    @property
    def group_num(self):
        """0 represents script_func_global"""
        assert self.group_name != "Custom", "Cannot know the group level script num if the group is custom"
        if self.group_name in {"common1", "group0"}:
            return 0
        elif self.group_name == "common0":
            return 1
        else:
            return int(self.group_name.removeprefix("group")) + 1

    @property
    def obj_name_col(self):
        if self.export_all_selected and self.col_object:
            return self.filter_name(self.col_object.name)
        if not self.object_name and not self.col_object:
            return ""
        else:
            return self.filter_name(self.object_name or self.col_object.name)

    @property
    def obj_name_gfx(self):
        if self.export_all_selected and self.gfx_object:
            return self.filter_name(self.gfx_object.name)
        if not self.object_name and not self.gfx_object:
            return ""
        else:
            return self.filter_name(self.object_name or self.gfx_object.name)

    @property
    def obj_name_bhv(self):
        if not self.bhv_object:
            return ""
        else:
            return self.filter_name(self.object_name or self.bhv_object.name)

    @property
    def bhv_name(self):
        return "bhv" + "".join([word.title() for word in toAlnum(self.obj_name_bhv).split("_")])

    @property
    def geo_name(self):
        return f"{toAlnum(self.obj_name_gfx)}_geo"

    @property
    def collision_name(self):
        return f"{toAlnum(self.obj_name_col)}_collision"

    @property
    def model_id_define(self):
        return f"MODEL_{toAlnum(self.obj_name_gfx)}".upper()

    @property
    def export_level_name(self):
        if self.level_name == "Custom" or self.non_decomp_level:
            return self.custom_level_name
        return self.level_name

    @property
    def actor_group_name(self):
        if self.group_name == "Custom":
            return self.custom_group_name
        else:
            return self.group_name

    @property
    def is_custom_level(self):
        return self.non_decomp_level or self.level_name == "Custom"

    @property
    def is_actor_custom_export(self):
        if self.non_decomp_level and self.export_header_type == "Level":
            return True
        elif self.export_header_type == "Custom":
            return True
        else:
            return False

    @property
    def actor_custom_path(self):
        if self.export_header_type == "Level":
            return self.full_level_path
        else:
            return self.custom_export_path

    @property
    def level_directory(self):
        if self.non_decomp_level:
            return self.custom_level_name
        level_name = self.custom_level_name if self.level_name == "Custom" else self.level_name
        return os.path.join("/levels/", level_name)

    @property
    def base_level_path(self):
        if self.non_decomp_level:
            return bpy.path.abspath(self.custom_level_path)
        return bpy.path.abspath(bpy.context.scene.fast64.sm64.decomp_path)

    @property
    def full_level_path(self):
        return os.path.join(self.base_level_path, self.level_directory)

    # remove user prefixes/naming that I will be adding, such as _col, _geo etc.
    def filter_name(self, name):
        if self.use_name_filtering:
            return sub("(_col)?(_geo)?(_bhv)?(lision)?", "", name)
        else:
            return name

    def draw_export_options(self, layout):
        split = layout.row(align=True)

        box = split.box()
        box.prop(self, "export_col", toggle=1)
        if self.export_col:
            box.prop(self, "include_children")
            box.prop(self, "export_rooms")
            if not self.export_all_selected:
                box.prop(self, "collision_object", icon_only=True)

        box = split.box()
        box.prop(self, "export_gfx", toggle=1)
        if self.export_gfx:
            if self.export_header_type != "Custom" and not (
                self.export_header_type == "Actor" and self.group_name == "Custom"
            ):
                box.prop(self, "export_script_loads")
            if not self.export_all_selected:
                box.prop(self, "graphics_object", icon_only=True)
            if self.export_script_loads:
                box.prop(self, "model_id", text="Model ID")
        col = layout.column()
        col.prop(self, "export_all_selected")
        col.prop(self, "use_name_filtering")
        if not self.export_all_selected:
            col.prop(self, "export_bhv")
            self.draw_obj_name(layout)

    @property
    def actor_names(self) -> list:
        return list(dict.fromkeys(filter(None, [self.obj_name_col, self.obj_name_gfx])).keys())

    def draw_level_path(self, layout):
        if not directory_ui_warnings(layout, bpy.path.abspath(self.base_level_path)):
            return
        if self.non_decomp_level:
            layout.label(text=f"Level export path: {self.full_level_path}")
        else:
            layout.label(text=f"Level export directory: {self.level_directory}")
        return True

    def draw_actor_path(self, layout):
        actor_path = Path(bpy.context.scene.fast64.sm64.decomp_path) / "actors"
        if not filepath_ui_warnings(layout, (actor_path / self.actor_group_name).with_suffix(".c")):
            return
        export_locations = ",".join({self.obj_name_col, self.obj_name_gfx})
        # can this be more clear?
        layout.label(text=f"Actor export path: actors/{export_locations}")
        return True

    def draw_col_names(self, layout):
        layout.label(text=f"Collision name: {self.collision_name}")
        if self.export_rooms:
            layout.label(text=f"Rooms name: {self.collision_name}_rooms")

    def draw_gfx_names(self, layout):
        layout.label(text=f"GeoLayout name: {self.geo_name}")
        if self.export_script_loads:
            layout.label(text=f"Model ID: {self.model_id_define}")

    def draw_obj_name(self, layout):
        split_1 = layout.split(factor=0.45)
        split_2 = split_1.split(factor=0.45)
        split_2.label(text="Name")
        split_2.prop(self, "object_name", text="")
        if bpy.context.active_object:
            tmp_obj_name = self.filter_name(bpy.context.active_object.name)
            split_1.label(text=f"or {repr(tmp_obj_name)} if no name")

    def draw_bhv_options(self, layout):
        if self.export_all_selected:
            return
        box = layout.box()
        prop_split(box, self, "preset_behavior_script", "Preset Behavior Script")
        box.operator("scene.add_behavior_script", text="Add Behavior Cmd").option = len(self.behavior_script)
        for index, bhv in enumerate(self.behavior_script):
            bhv.draw(box, index)

    def draw_props(self, layout):
        # level exports
        col = layout.column()
        box = col.box().column()
        box.operator("object.sm64_export_level", text="Export Level")

        box.prop(self, "non_decomp_level")
        if self.non_decomp_level:
            prop_split(box, self, "custom_level_path", "Custom Path")
        else:
            prop_split(box, self, "level_name", "Level")
        if self.is_custom_level:
            prop_split(box, self, "custom_level_name", "Name")
        self.draw_level_path(box.box())
        col.separator()
        # object exports
        box = col.box().column()
        if not self.export_col and not self.export_bhv and not self.export_gfx:
            col = box.column()
            col.operator("object.sm64_export_combined_object", text="Export Object")
            col.enabled = False
            self.draw_export_options(box)
            box.label(text="You must enable at least one export type", icon="ERROR")
            return
        else:
            box.operator("object.sm64_export_combined_object", text="Export Object")
            self.draw_export_options(box)

        # bhv export only, so enable bhv draw only
        if not self.export_col and not self.export_gfx:
            return self.draw_bhv_options(col)

        # pathing for gfx/col exports
        prop_split(box, self, "export_header_type", "Export Type")

        if self.export_header_type == "Custom":
            prop_split(box, self, "custom_export_path", "Custom Path")
            if bpy.context.scene.saveTextures:
                prop_split(box, self, "custom_include_directory", "Texture Include Directory")

        elif self.export_header_type == "Actor":
            prop_split(box, self, "group_name", "Group")
            if self.group_name == "Custom":
                prop_split(box, self, "custom_group_name", "Group Name")
        else:
            box.label(text="Destination level selection is shared with level export dropdown", icon="PINNED")
        # behavior options
        if self.export_bhv and not self.export_all_selected:
            self.draw_bhv_options(col)

        # info/warnings
        if self.export_header_type == "Custom":
            info_box = box.box()
            info_box.label(text="Export will not write headers, dependencies or script loads", icon="ERROR")

        if self.export_all_selected:
            info_box = box.box()
            multilineLabel(
                info_box,
                text="Object name used will be the name of respective selected objects.\n"
                "Objects will export based on root of parenting hierarchy.\n"
                "Model IDs will export in order starting from chosen Model ID Num.\n"
                "Behaviors will not export\n"
                "Duplicates objects will be exported! Use with Caution.",
                icon="ERROR",
            )

        info_box = box.box()
        info_box.scale_y = 0.5

        if self.export_header_type == "Level":
            if not self.draw_level_path(info_box):
                return

        elif self.export_header_type == "Actor":
            if not self.draw_actor_path(info_box):
                return
        elif self.export_header_type == "Custom" and bpy.context.scene.saveTextures:
            if self.custom_include_directory:
                info_box.label(text=f'Include directory "{self.custom_include_directory}"')
            else:
                actor_names = self.actor_names
                joined = ",".join(self.actor_names)
                if len(actor_names) > 1:
                    joined = "{" f"{joined}" "}"
                directory = f"{Path(bpy.path.abspath(self.custom_export_path)).name}/{joined}"
                info_box.label(text=f'Empty include directory, defaults to "{directory}"')

        if self.obj_name_gfx and self.export_gfx:
            self.draw_gfx_names(info_box)

        if self.obj_name_col and self.export_col:
            self.draw_col_names(info_box)

        if self.obj_name_bhv:
            info_box.label(text=f"Behavior name: {self.bhv_name}")


class SM64_CombinedObjectPanel(SM64_Panel):
    bl_idname = "SM64_PT_export_combined_object"
    bl_label = "SM64 Combined Exporter"
    decomp_only = True

    def draw(self, context):
        col = self.layout.column()
        context.scene.fast64.sm64.combined_export.draw_props(col)


enumStarGetCutscene = [
    ("Custom", "Custom", "Custom"),
    ("0", "Lakitu Flies Away", "Lakitu Flies Away"),
    ("1", "Rotate Around Mario", "Rotate Around Mario"),
    ("2", "Closeup Of Mario", "Closeup Of Mario"),
    ("3", "Bowser Keys", "Bowser Keys"),
    ("4", "100 Coin Star", "100 Coin Star"),
]


class WarpNodeProperty(bpy.types.PropertyGroup):
    warpType: bpy.props.EnumProperty(name="Warp Type", items=enumWarpType, default="Warp")
    warpID: bpy.props.StringProperty(name="Warp ID", default="0x0A")
    destLevelEnum: bpy.props.EnumProperty(name="Destination Level", default="bob", items=enumLevelNames)
    destLevel: bpy.props.StringProperty(name="Destination Level Value", default="LEVEL_BOB")
    destArea: bpy.props.StringProperty(name="Destination Area", default="0x01")
    destNode: bpy.props.StringProperty(name="Destination Node", default="0x0A")
    warpFlags: bpy.props.StringProperty(name="Warp Flags", default="WARP_NO_CHECKPOINT")
    warpFlagEnum: bpy.props.EnumProperty(name="Warp Flags Value", default="WARP_NO_CHECKPOINT", items=enumWarpFlag)
    instantOffset: bpy.props.IntVectorProperty(name="Offset", size=3, default=(0, 0, 0))
    instantWarpObject1: bpy.props.PointerProperty(name="Object 1", type=bpy.types.Object)
    instantWarpObject2: bpy.props.PointerProperty(name="Object 2", type=bpy.types.Object)
    useOffsetObjects: bpy.props.BoolProperty(name="Use Offset Objects", default=False)

    expand: bpy.props.BoolProperty()

    def uses_area_nodes(self):
        return (
            self.instantWarpObject1.sm64_obj_type == "Area Root"
            and self.instantWarpObject2.sm64_obj_type == "Area Root"
        )

    def calc_offsets_from_objects(self, reverse=False):
        if self.instantWarpObject1 is None or self.instantWarpObject2 is None:
            raise PluginError(f"Warp Start and Warp End in Warp Node {self.warpID} must have objects selected.")

        difference = self.instantWarpObject2.location - self.instantWarpObject1.location

        if reverse:
            difference *= -1

        # Convert from Blender space to SM64 space
        ret = Vector()
        ret.x = int(round(difference.x * bpy.context.scene.blenderF3DScale))
        ret.y = int(round(difference.z * bpy.context.scene.blenderF3DScale))
        ret.z = int(round(-difference.y * bpy.context.scene.blenderF3DScale))
        return ret

    def to_c(self):
        if self.warpType == "Instant":
            offset = Vector()

            if self.useOffsetObjects:
                offset = self.calc_offsets_from_objects(self.uses_area_nodes())
            else:
                offset.x = self.instantOffset[0]
                offset.y = self.instantOffset[1]
                offset.z = self.instantOffset[2]

            return (
                "INSTANT_WARP("
                + str(self.warpID)
                + ", "
                + str(self.destArea)
                + ", "
                + str(int(offset.x))
                + ", "
                + str(int(offset.y))
                + ", "
                + str(int(offset.z))
                + ")"
            )
        else:
            if self.warpType == "Warp":
                cmd = "WARP_NODE"
            elif self.warpType == "Painting":
                cmd = "PAINTING_WARP_NODE"

            if self.destLevelEnum == "Custom":
                destLevel = self.destLevel
            else:
                destLevel = levelIDNames[self.destLevelEnum]

            if self.warpFlagEnum == "Custom":
                warpFlags = self.warpFlags
            else:
                warpFlags = self.warpFlagEnum
            return (
                cmd
                + "("
                + str(self.warpID)
                + ", "
                + str(destLevel)
                + ", "
                + str(self.destArea)
                + ", "
                + str(self.destNode)
                + ", "
                + str(warpFlags)
                + ")"
            )


class AddWarpNode(bpy.types.Operator):
    bl_idname = "bone.add_warp_node"
    bl_label = "Add Warp Node"
    bl_options = {"REGISTER", "UNDO"}
    option: bpy.props.IntProperty()

    def execute(self, context):
        obj = context.object
        obj.warpNodes.add()
        obj.warpNodes.move(len(obj.warpNodes) - 1, self.option)
        self.report({"INFO"}, "Success!")
        return {"FINISHED"}


class RemoveWarpNode(bpy.types.Operator):
    bl_idname = "bone.remove_warp_node"
    bl_label = "Remove Warp Node"
    bl_options = {"REGISTER", "UNDO"}
    option: bpy.props.IntProperty()

    def execute(self, context):
        context.object.warpNodes.remove(self.option)
        self.report({"INFO"}, "Success!")
        return {"FINISHED"}


def drawWarpNodeProperty(layout, warpNode, index):
    box = layout.box().column()
    # box.box().label(text = 'Switch Option ' + str(index + 1))
    box.prop(
        warpNode,
        "expand",
        text="Warp Node " + str(warpNode.warpID),
        icon="TRIA_DOWN" if warpNode.expand else "TRIA_RIGHT",
    )
    if warpNode.expand:
        prop_split(box, warpNode, "warpType", "Warp Type")
        if warpNode.warpType == "Instant":
            prop_split(box, warpNode, "warpID", "Warp ID")
            prop_split(box, warpNode, "destArea", "Destination Area")
            prop_split(box, warpNode, "useOffsetObjects", "Use Offset Objects?")
            if warpNode.useOffsetObjects:
                prop_split(box, warpNode, "instantWarpObject1", "Warp Start")
                prop_split(box, warpNode, "instantWarpObject2", "Warp End")
                writeBox = box.box()
                if warpNode.instantWarpObject1 is None or warpNode.instantWarpObject2 is None:
                    writeBox.label(text="Both Objects must be selected for offset")
                else:
                    usesAreaNodes = warpNode.uses_area_nodes()
                    difference = warpNode.calc_offsets_from_objects(usesAreaNodes)
                    writeBox.label(text="Current Offset: ")

                    writeBox.label(text=f"X: {difference.x}")
                    writeBox.label(text=f"Y: {difference.y}")
                    writeBox.label(text=f"Z: {difference.z}")

                    if usesAreaNodes:
                        writeBox.label(text="(When using two area nodes, the calculation is reversed)")
            else:
                prop_split(box, warpNode, "instantOffset", "Offset")
        else:
            prop_split(box, warpNode, "warpID", "Warp ID")
            prop_split(box, warpNode, "destLevelEnum", "Destination Level")
            if warpNode.destLevelEnum == "Custom":
                prop_split(box, warpNode, "destLevel", "")
            prop_split(box, warpNode, "destArea", "Destination Area")
            prop_split(box, warpNode, "destNode", "Destination Node")
            prop_split(box, warpNode, "warpFlagEnum", "Warp Flags")
            if warpNode.warpFlagEnum == "Custom":
                prop_split(box, warpNode, "warpFlags", "Warp Flags Value")

        buttons = box.row(align=True)
        buttons.operator(RemoveWarpNode.bl_idname, text="Remove Option").option = index
        buttons.operator(AddWarpNode.bl_idname, text="Add Option").option = index + 1


class StarGetCutscenesProperty(bpy.types.PropertyGroup):
    star1_option: bpy.props.EnumProperty(items=enumStarGetCutscene, default="4", name="1")
    star2_option: bpy.props.EnumProperty(items=enumStarGetCutscene, default="4", name="2")
    star3_option: bpy.props.EnumProperty(items=enumStarGetCutscene, default="4", name="3")
    star4_option: bpy.props.EnumProperty(items=enumStarGetCutscene, default="4", name="4")
    star5_option: bpy.props.EnumProperty(items=enumStarGetCutscene, default="4", name="5")
    star6_option: bpy.props.EnumProperty(items=enumStarGetCutscene, default="4", name="6")
    star7_option: bpy.props.EnumProperty(items=enumStarGetCutscene, default="4", name="7")

    star1_value: bpy.props.IntProperty(default=0, min=0, max=15, name="Value")
    star2_value: bpy.props.IntProperty(default=0, min=0, max=15, name="Value")
    star3_value: bpy.props.IntProperty(default=0, min=0, max=15, name="Value")
    star4_value: bpy.props.IntProperty(default=0, min=0, max=15, name="Value")
    star5_value: bpy.props.IntProperty(default=0, min=0, max=15, name="Value")
    star6_value: bpy.props.IntProperty(default=0, min=0, max=15, name="Value")
    star7_value: bpy.props.IntProperty(default=0, min=0, max=15, name="Value")

    def value(self):
        value = "0x"
        value += self.star1_option if self.star1_option != "Custom" else format(self.star1_value, "X")
        value += self.star2_option if self.star2_option != "Custom" else format(self.star2_value, "X")
        value += self.star3_option if self.star3_option != "Custom" else format(self.star3_value, "X")
        value += self.star4_option if self.star4_option != "Custom" else format(self.star4_value, "X")
        value += self.star5_option if self.star5_option != "Custom" else format(self.star5_value, "X")
        value += self.star6_option if self.star6_option != "Custom" else format(self.star6_value, "X")
        value += self.star7_option if self.star7_option != "Custom" else format(self.star7_value, "X")
        value += "0"
        return value

    def draw(self, layout):
        layout.label(text="Star Get Cutscenes")
        layout.prop(self, "star1_option")
        if self.star1_option == "Custom":
            prop_split(layout, self, "star1_value", "")
        layout.prop(self, "star2_option")
        if self.star2_option == "Custom":
            prop_split(layout, self, "star2_value", "")
        layout.prop(self, "star3_option")
        if self.star3_option == "Custom":
            prop_split(layout, self, "star3_value", "")
        layout.prop(self, "star4_option")
        if self.star4_option == "Custom":
            prop_split(layout, self, "star4_value", "")
        layout.prop(self, "star5_option")
        if self.star5_option == "Custom":
            prop_split(layout, self, "star5_value", "")
        layout.prop(self, "star6_option")
        if self.star6_option == "Custom":
            prop_split(layout, self, "star6_value", "")
        layout.prop(self, "star7_option")
        if self.star7_option == "Custom":
            prop_split(layout, self, "star7_value", "")


def onUpdateObjectType(self, context):
    isNoneEmpty = self.sm64_obj_type == "None"
    isBoxEmpty = self.sm64_obj_type == "Water Box" or self.sm64_obj_type == "Camera Volume"
    self.show_name = not (isBoxEmpty or isNoneEmpty)
    self.show_axis = not (isBoxEmpty or isNoneEmpty)

    if isBoxEmpty:
        self.empty_display_type = "CUBE"


class PuppycamSetupCamera(bpy.types.Operator):
    """Setup Camera"""

    bl_idname = "mesh.puppycam_setup_camera"
    bl_label = "Set up Camera"
    bl_options = {"REGISTER"}

    def execute(self, context):
        scene = context.scene
        cameraObject = bpy.context.active_object.puppycamProp.puppycamCamera.data.name

        scene.camera = bpy.context.active_object.puppycamProp.puppycamCamera
        bpy.data.cameras[cameraObject].show_name = True
        bpy.data.cameras[cameraObject].show_safe_areas = True

        scene.safe_areas.title[0] = 0
        scene.safe_areas.title[1] = 8 / 240  # Use the safe areas to denote where default 8 pixel black bars will be
        scene.safe_areas.action = (0, 0)

        # If you could set resolution on a per-camera basis, I'd do that instead. Oh well.
        scene.render.resolution_x = 320
        scene.render.resolution_y = 240

        bpy.data.cameras[cameraObject].angle = math.radians(
            bpy.context.active_object.puppycamProp.puppycamFOV * (4 / 3)
        )

        return {"FINISHED"}


def sm64_is_camera_poll(self, object):
    return object.type == "CAMERA"


class PuppycamProperty(bpy.types.PropertyGroup):
    puppycamVolumeFunction: bpy.props.StringProperty(name="Puppycam Function", default="0")

    puppycamVolumePermaswap: bpy.props.BoolProperty(name="Permaswap")

    puppycamUseEmptiesForPos: bpy.props.BoolProperty(name="Use Empty Objects for positions")

    puppycamCamera: bpy.props.PointerProperty(type=bpy.types.Object, poll=sm64_is_camera_poll)

    puppycamFOV: bpy.props.FloatProperty(name="Field Of View", min=0, max=180, default=45)

    puppycamMode: bpy.props.EnumProperty(items=enumPuppycamMode, default="NC_MODE_NORMAL")

    puppycamType: bpy.props.StringProperty(name="Custom Mode", default="NC_MODE_NORMAL")

    puppycamCamPos: bpy.props.StringProperty(name="Fixed Camera Position")

    puppycamCamFocus: bpy.props.StringProperty(name="Fixed Camera Focus")

    puppycamUseFlags: bpy.props.BoolProperty(name="Use Flags")

    NC_FLAG_XTURN: bpy.props.BoolProperty(name="X Turn")

    NC_FLAG_YTURN: bpy.props.BoolProperty(name="Y Turn")

    NC_FLAG_ZOOM: bpy.props.BoolProperty(name="Y Turn")

    NC_FLAG_8D: bpy.props.BoolProperty(name="8 Directions")

    NC_FLAG_4D: bpy.props.BoolProperty(name="4 Directions")

    NC_FLAG_2D: bpy.props.BoolProperty(name="2D")

    NC_FLAG_FOCUSX: bpy.props.BoolProperty(name="Use X Focus")

    NC_FLAG_FOCUSY: bpy.props.BoolProperty(name="Use Y Focus")

    NC_FLAG_FOCUSZ: bpy.props.BoolProperty(name="Use Z Focus")

    NC_FLAG_POSX: bpy.props.BoolProperty(name="Move on X axis")

    NC_FLAG_POSY: bpy.props.BoolProperty(name="Move on Y axis")

    NC_FLAG_POSZ: bpy.props.BoolProperty(name="Move on Z axis")

    NC_FLAG_COLLISION: bpy.props.BoolProperty(name="Camera Collision")

    NC_FLAG_SLIDECORRECT: bpy.props.BoolProperty(name="Slide Correction")


class SM64_GeoASMProperties(bpy.types.PropertyGroup):
    name = "Geo ASM Properties"
    func: bpy.props.StringProperty(
        name="Geo ASM Func", default="", description="Name of function for C, hex address for binary."
    )
    param: bpy.props.StringProperty(
        name="Geo ASM Param", default="0", description="Function parameter. (Binary exporting will cast to int)"
    )

    @staticmethod
    def upgrade_object(obj: bpy.types.Object):
        geo_asm = obj.fast64.sm64.geo_asm
        upgrade_old_prop(geo_asm, "func", obj, {"geoASMFunc", "geo_func"})
        upgrade_old_prop(geo_asm, "param", obj, {"geoASMParam", "func_param"})


class SM64_AreaProperties(bpy.types.PropertyGroup):
    name = "Area Properties"
    disable_background: bpy.props.BoolProperty(
        name="Disable Background",
        default=False,
        description="Disable rendering background. Ideal for interiors or areas that should never see a background.",
    )
    set_fog: bpy.props.BoolProperty(
        name="Set Fog Settings",
        default=True,
        description='All materials in the area with fog and "Use Area\'s Fog" enabled will use these fog settings. Each material will have its own fog applied as vanilla SM64 has no fog system',
    )


class SM64_LevelProperties(bpy.types.PropertyGroup):
    name = "SM64 Level Properties"
    backgroundID: bpy.props.StringProperty(
        name="Background Define",
        default="BACKGROUND_CUSTOM",
        description="The background define that is passed into GEO_BACKGROUND\n"
        "(ex. BACKGROUND_OCEAN_SKY, BACKGROUND_GREEN_SKY)",
    )

    backgroundSegment: bpy.props.StringProperty(
        name="Background Segment",
        default="water_skybox",
        description="Segment that will be loaded.\n"
        "This will be suffixed with _yay0SegmentRomStart or _mio0SegmentRomStart\n"
        "(ex. water_skybox, bidw_skybox)",
    )


DEFAULT_BEHAVIOR_PARAMS = "0x00000000"


class SM64_GameObjectProperties(bpy.types.PropertyGroup):
    name = "Game Object Properties"
    bparams: bpy.props.StringProperty(
        name="Behavior Parameters", description="All Behavior Parameters", default=DEFAULT_BEHAVIOR_PARAMS
    )

    use_individual_params: bpy.props.BoolProperty(
        name="Use Individual Behavior Params", description="Use Individual Behavior Params", default=True
    )
    bparam1: bpy.props.StringProperty(name="Behavior Param 1", description="First Behavior Param", default="")
    bparam2: bpy.props.StringProperty(name="Behavior Param 2", description="Second Behavior Param", default="")
    bparam3: bpy.props.StringProperty(name="Behavior Param 3", description="Third Behavior Param", default="")
    bparam4: bpy.props.StringProperty(name="Behavior Param 4", description="Fourth Behavior Param", default="")

    @staticmethod
    def upgrade_object(obj):
        game_object: SM64_GameObjectProperties = obj.fast64.sm64.game_object

        upgrade_old_prop(game_object, "bparams", obj, "sm64_obj_bparam")

        # get combined bparams, if they arent the default value then return because they have been set
        combined_bparams = game_object.get_combined_bparams()
        if combined_bparams != DEFAULT_BEHAVIOR_PARAMS:
            return

        # If bparams arent the default bparams, disable `use_individual_params`
        if game_object.bparams != DEFAULT_BEHAVIOR_PARAMS:
            game_object.use_individual_params = False

    def get_combined_bparams(self):
        params = [self.bparam1, self.bparam2, self.bparam3, self.bparam4]
        fmt_params = []
        for i, p in enumerate(params):
            if len(p) == 0:
                continue
            shift = 8 * (3 - i)
            fmt_params.append(f"({p} << {shift})" if shift > 0 else f"({p})")

        if len(fmt_params) == 0:
            return DEFAULT_BEHAVIOR_PARAMS
        else:
            return " | ".join(fmt_params)

    def get_behavior_params(self):
        if self.use_individual_params:
            return self.get_combined_bparams()
        return self.bparams


class SM64_SegmentProperties(bpy.types.PropertyGroup):
    seg5_load_custom: bpy.props.StringProperty(name="Segment 5 Seg")
    seg5_group_custom: bpy.props.StringProperty(name="Segment 5 Group")
    seg6_load_custom: bpy.props.StringProperty(name="Segment 6 Seg")
    seg6_group_custom: bpy.props.StringProperty(name="Segment 6 Group")
    seg5_enum: bpy.props.EnumProperty(name="Segment 5 Group", default="Do Not Write", items=groupsSeg5)
    seg6_enum: bpy.props.EnumProperty(name="Segment 6 Group", default="Do Not Write", items=groupsSeg6)

    def draw(self, layout):
        col = layout.column()
        prop_split(col, self, "seg5_enum", "Segment 5 Select")
        if self.seg5_enum == "Custom":
            prop_split(col, self, "seg5_load_custom", "Segment 5 Seg")
            prop_split(col, self, "seg5_group_custom", "Segment 5 Group")
        col = layout.column()
        prop_split(col, self, "seg6_enum", "Segment 6 Select")
        if self.seg6_enum == "Custom":
            prop_split(col, self, "seg6_load_custom", "Segment 6 Seg")
            prop_split(col, self, "seg6_group_custom", "Segment 6 Group")

    def jump_link_from_enum(self, grp):
        if grp == "Do Not Write":
            return grp
        num = int(grp.removeprefix("group")) + 1
        return f"script_func_global_{num}"

    @property
    def seg5(self):
        if self.seg5_enum == "Custom":
            return self.seg5_load_custom
        else:
            return self.seg5_enum

    @property
    def seg6(self):
        if self.seg6_enum == "Custom":
            return self.seg6_load_custom
        else:
            return self.seg6_enum

    @property
    def group5(self):
        if self.seg5_enum == "Custom":
            return self.seg5_group_custom
        else:
            return self.jump_link_from_enum(self.seg5_enum)

    @property
    def group6(self):
        if self.seg6_enum == "Custom":
            return self.seg6_group_custom
        else:
            return self.jump_link_from_enum(self.seg6_enum)


class SM64_ObjectProperties(bpy.types.PropertyGroup):
    version: bpy.props.IntProperty(name="SM64_ObjectProperties Version", default=0)
    cur_version = 3  # version after property migration

    geo_asm: bpy.props.PointerProperty(type=SM64_GeoASMProperties)
    level: bpy.props.PointerProperty(type=SM64_LevelProperties)
    area: bpy.props.PointerProperty(type=SM64_AreaProperties)
    game_object: bpy.props.PointerProperty(type=SM64_GameObjectProperties)
    segment_loads: bpy.props.PointerProperty(type=SM64_SegmentProperties)

    @staticmethod
    def upgrade_changed_props():
        for obj in bpy.data.objects:
            if obj.fast64.sm64.version == 0:
                SM64_GeoASMProperties.upgrade_object(obj)
            if obj.fast64.sm64.version < 3:
                SM64_GameObjectProperties.upgrade_object(obj)
            obj.fast64.sm64.version = SM64_ObjectProperties.cur_version


sm64_obj_classes = (
    BehaviorScriptProperty,
    AddBehavior,
    RemoveBehavior,
    WarpNodeProperty,
    AddWarpNode,
    RemoveWarpNode,
    SearchModelIDEnumOperator,
    SearchBehaviourEnumOperator,
    SearchSpecialEnumOperator,
    SearchMacroEnumOperator,
    StarGetCutscenesProperty,
    PuppycamProperty,
    PuppycamSetupCamera,
    SM64_CombinedObjectProperties,
    SM64_ExportCombinedObject,
    SM64_GeoASMProperties,
    SM64_LevelProperties,
    SM64_AreaProperties,
    SM64_GameObjectProperties,
    SM64_SegmentProperties,
    SM64_ObjectProperties,
)


sm64_obj_panel_classes = (SM64ObjectPanel, SM64_CombinedObjectPanel)


def sm64_obj_panel_register():
    for cls in sm64_obj_panel_classes:
        register_class(cls)


def sm64_obj_panel_unregister():
    for cls in sm64_obj_panel_classes:
        unregister_class(cls)


def sm64_on_update_area_render_settings(self: bpy.types.Object, context: bpy.types.Context):
    renderSettings = context.scene.fast64.renderSettings
    if renderSettings.useObjectRenderPreview and renderSettings.sm64Area == self:
        area: bpy.types.Object = self
        renderSettings.fogPreviewColor = tuple(c for c in area.area_fog_color)
        renderSettings.fogPreviewPosition = tuple(round(p) for p in area.area_fog_position)

        renderSettings.clippingPlanes = tuple(float(p) for p in area.clipPlanes)


def sm64_obj_register():
    for cls in sm64_obj_classes:
        register_class(cls)

    bpy.types.Object.puppycamProp = bpy.props.PointerProperty(type=PuppycamProperty)

    bpy.types.Object.sm64_model_enum = bpy.props.EnumProperty(name="Model", items=enumModelIDs)

    bpy.types.Object.sm64_macro_enum = bpy.props.EnumProperty(name="Macro", items=enumMacrosNames)

    bpy.types.Object.sm64_special_enum = bpy.props.EnumProperty(name="Special", items=enumSpecialsNames)

    bpy.types.Object.sm64_behaviour_enum = bpy.props.EnumProperty(name="Behaviour", items=enumBehaviourPresets)

    # bpy.types.Object.sm64_model = bpy.props.StringProperty(
    # 	name = 'Model Name')
    # bpy.types.Object.sm64_macro = bpy.props.StringProperty(
    # 	name = 'Macro Name')
    # bpy.types.Object.sm64_special = bpy.props.StringProperty(
    # 	name = 'Special Name')
    # bpy.types.Object.sm64_behaviour = bpy.props.StringProperty(
    # 	name = 'Behaviour Name')

    bpy.types.Object.sm64_obj_type = bpy.props.EnumProperty(
        name="SM64 Object Type", items=enumObjectType, default="None", update=onUpdateObjectType
    )

    bpy.types.Object.sm64_obj_model = bpy.props.StringProperty(name="Model", default="MODEL_NONE")

    bpy.types.Object.sm64_obj_preset = bpy.props.StringProperty(name="Preset")

    bpy.types.Object.sm64_obj_behaviour = bpy.props.StringProperty(name="Behaviour")

    bpy.types.Object.sm64_obj_mario_start_area = bpy.props.StringProperty(name="Area", default="0x01")

    bpy.types.Object.whirpool_index = bpy.props.StringProperty(name="Index", default="0")
    bpy.types.Object.whirpool_condition = bpy.props.StringProperty(name="Condition", default="3")
    bpy.types.Object.whirpool_strength = bpy.props.StringProperty(name="Strength", default="-30")
    bpy.types.Object.waterBoxType = bpy.props.EnumProperty(
        name="Water Box Type", items=enumWaterBoxType, default="Water"
    )

    bpy.types.Object.sm64_obj_use_act1 = bpy.props.BoolProperty(name="Act 1", default=True)
    bpy.types.Object.sm64_obj_use_act2 = bpy.props.BoolProperty(name="Act 2", default=True)
    bpy.types.Object.sm64_obj_use_act3 = bpy.props.BoolProperty(name="Act 3", default=True)
    bpy.types.Object.sm64_obj_use_act4 = bpy.props.BoolProperty(name="Act 4", default=True)
    bpy.types.Object.sm64_obj_use_act5 = bpy.props.BoolProperty(name="Act 5", default=True)
    bpy.types.Object.sm64_obj_use_act6 = bpy.props.BoolProperty(name="Act 6", default=True)

    bpy.types.Object.sm64_obj_set_bparam = bpy.props.BoolProperty(name="Set Behaviour Parameter", default=True)

    bpy.types.Object.sm64_obj_set_yaw = bpy.props.BoolProperty(name="Set Yaw", default=False)

    bpy.types.Object.useBackgroundColor = bpy.props.BoolProperty(name="Use Solid Color For Background", default=False)

    # bpy.types.Object.backgroundID = bpy.props.StringProperty(
    # 	name = 'Background ID', default = 'BACKGROUND_OCEAN_SKY')

    bpy.types.Object.background = bpy.props.EnumProperty(name="Background", items=enumBackground, default="OCEAN_SKY")

    bpy.types.Object.backgroundColor = bpy.props.FloatVectorProperty(
        name="Background Color", subtype="COLOR", size=4, min=0, max=1, default=(0, 0, 0, 1)
    )

    bpy.types.Object.screenPos = bpy.props.IntVectorProperty(
        name="Screen Position", size=2, default=(160, 120), min=-(2**15), max=2**15 - 1
    )

    bpy.types.Object.screenSize = bpy.props.IntVectorProperty(
        name="Screen Size", size=2, default=(160, 120), min=-(2**15), max=2**15 - 1
    )

    bpy.types.Object.useDefaultScreenRect = bpy.props.BoolProperty(name="Use Default Screen Rect", default=True)

    bpy.types.Object.clipPlanes = bpy.props.IntVectorProperty(
        name="Clip Planes", size=2, min=0, default=(100, 30000), update=sm64_on_update_area_render_settings
    )

    bpy.types.Object.area_fog_color = bpy.props.FloatVectorProperty(
        name="Area Fog Color",
        subtype="COLOR",
        size=4,
        min=0,
        max=1,
        default=(0, 0, 0, 1),
        update=sm64_on_update_area_render_settings,
    )

    bpy.types.Object.area_fog_position = bpy.props.FloatVectorProperty(
        name="Area Fog Position",
        size=2,
        min=0,
        max=0x7FFFFFFF,
        step=100,
        default=(985, 1000),
        update=sm64_on_update_area_render_settings,
    )

    bpy.types.Object.areaOverrideBG = bpy.props.BoolProperty(name="Override Background")

    bpy.types.Object.areaBGColor = bpy.props.FloatVectorProperty(
        name="Background Color", subtype="COLOR", size=4, min=0, max=1, default=(0, 0, 0, 1)
    )

    bpy.types.Object.camOption = bpy.props.EnumProperty(items=enumCameraMode, default="CAMERA_MODE_8_DIRECTIONS")

    bpy.types.Object.camType = bpy.props.StringProperty(name="Camera Type", default="CAMERA_MODE_8_DIRECTIONS")

    bpy.types.Object.envOption = bpy.props.EnumProperty(items=enumEnvFX, default="ENVFX_MODE_NONE")

    bpy.types.Object.envType = bpy.props.StringProperty(name="Environment Type", default="ENVFX_MODE_NONE")

    bpy.types.Object.fov = bpy.props.FloatProperty(name="Field Of View", min=0, max=180, default=45)

    bpy.types.Object.dynamicFOV = bpy.props.BoolProperty(name="Dynamic FOV", default=True)

    bpy.types.Object.cameraVolumeFunction = bpy.props.StringProperty(
        name="Camera Function", default="cam_castle_hmc_start_pool_cutscene"
    )
    bpy.types.Object.cameraVolumeGlobal = bpy.props.BoolProperty(name="Is Global")

    bpy.types.Object.starGetCutscenes = bpy.props.PointerProperty(
        name="Star Get Cutscenes", type=StarGetCutscenesProperty
    )

    bpy.types.Object.acousticReach = bpy.props.StringProperty(name="Acoustic Reach", default="20000")

    bpy.types.Object.echoLevel = bpy.props.StringProperty(name="Echo Level", default="0x00")

    bpy.types.Object.zoomOutOnPause = bpy.props.BoolProperty(name="Zoom Out On Pause", default=True)

    bpy.types.Object.areaIndex = bpy.props.IntProperty(name="Index", min=0, default=1)

    bpy.types.Object.music_preset = bpy.props.StringProperty(name="Music Preset", default="0x00")
    bpy.types.Object.music_seq = bpy.props.StringProperty(name="Music Sequence Value", default="SEQ_LEVEL_GRASS")
    bpy.types.Object.noMusic = bpy.props.BoolProperty(name="No Music", default=False)
    bpy.types.Object.terrain_type = bpy.props.StringProperty(name="Terrain Type", default="TERRAIN_GRASS")
    bpy.types.Object.terrainEnum = bpy.props.EnumProperty(name="Terrain", items=enumTerrain, default="TERRAIN_GRASS")
    bpy.types.Object.musicSeqEnum = bpy.props.EnumProperty(
        name="Music Sequence", items=enumMusicSeq, default="SEQ_LEVEL_GRASS"
    )

    bpy.types.Object.areaCamera = bpy.props.PointerProperty(type=bpy.types.Camera)
    bpy.types.Object.warpNodes = bpy.props.CollectionProperty(type=WarpNodeProperty)

    bpy.types.Object.showStartDialog = bpy.props.BoolProperty(name="Show Start Dialog")
    bpy.types.Object.startDialog = bpy.props.StringProperty(name="Start Dialog", default="DIALOG_000")
    bpy.types.Object.actSelectorIgnore = bpy.props.BoolProperty(name="Skip Act Selector")
    bpy.types.Object.setAsStartLevel = bpy.props.BoolProperty(name="Set As Start Level")

    bpy.types.Object.switchFunc = bpy.props.StringProperty(
        name="Function", default="", description="Name of function for C, hex address for binary."
    )

    bpy.types.Object.switchParam = bpy.props.IntProperty(
        name="Function Parameter", min=-(2 ** (15)), max=2 ** (15) - 1, default=0
    )

    bpy.types.Object.useDLReference = bpy.props.BoolProperty(name="Use displaylist reference")
    bpy.types.Object.dlReference = bpy.props.StringProperty(name="Displaylist variable name or hex address for binary.")

    bpy.types.Object.geoReference = bpy.props.StringProperty(name="Geolayout variable name or hex address for binary")

    bpy.types.Object.customGeoCommand = bpy.props.StringProperty(name="Geolayout macro command", default="")
    bpy.types.Object.customGeoCommandArgs = bpy.props.StringProperty(name="Geolayout macro arguments", default="")

    bpy.types.Object.enableRoomSwitch = bpy.props.BoolProperty(name="Enable Room System")


def sm64_obj_unregister():
    del bpy.types.Object.sm64_model_enum
    del bpy.types.Object.sm64_macro_enum
    del bpy.types.Object.sm64_special_enum
    del bpy.types.Object.sm64_behaviour_enum

    # del bpy.types.Object.sm64_model
    # del bpy.types.Object.sm64_macro
    # del bpy.types.Object.sm64_special
    # del bpy.types.Object.sm64_behaviour

    del bpy.types.Object.sm64_obj_type
    del bpy.types.Object.sm64_obj_model
    del bpy.types.Object.sm64_obj_preset
    del bpy.types.Object.sm64_obj_behaviour

    del bpy.types.Object.whirpool_index
    del bpy.types.Object.whirpool_condition
    del bpy.types.Object.whirpool_strength

    del bpy.types.Object.waterBoxType

    del bpy.types.Object.sm64_obj_use_act1
    del bpy.types.Object.sm64_obj_use_act2
    del bpy.types.Object.sm64_obj_use_act3
    del bpy.types.Object.sm64_obj_use_act4
    del bpy.types.Object.sm64_obj_use_act5
    del bpy.types.Object.sm64_obj_use_act6

    del bpy.types.Object.sm64_obj_set_bparam
    del bpy.types.Object.sm64_obj_set_yaw

    del bpy.types.Object.useBackgroundColor
    # del bpy.types.Object.backgroundID
    del bpy.types.Object.background
    del bpy.types.Object.backgroundColor

    del bpy.types.Object.screenPos
    del bpy.types.Object.screenSize
    del bpy.types.Object.useDefaultScreenRect
    del bpy.types.Object.clipPlanes
    del bpy.types.Object.area_fog_color
    del bpy.types.Object.area_fog_position
    del bpy.types.Object.areaOverrideBG
    del bpy.types.Object.areaBGColor
    del bpy.types.Object.camOption
    del bpy.types.Object.camType
    del bpy.types.Object.envOption
    del bpy.types.Object.envType
    del bpy.types.Object.fov
    del bpy.types.Object.dynamicFOV

    del bpy.types.Object.cameraVolumeFunction
    del bpy.types.Object.cameraVolumeGlobal

    del bpy.types.Object.starGetCutscenes

    del bpy.types.Object.acousticReach
    del bpy.types.Object.echoLevel
    del bpy.types.Object.zoomOutOnPause

    del bpy.types.Object.areaIndex
    del bpy.types.Object.music_preset
    del bpy.types.Object.music_seq
    del bpy.types.Object.terrain_type
    del bpy.types.Object.areaCamera
    del bpy.types.Object.noMusic

    del bpy.types.Object.showStartDialog
    del bpy.types.Object.startDialog
    del bpy.types.Object.actSelectorIgnore
    del bpy.types.Object.setAsStartLevel
    del bpy.types.Object.switchFunc
    del bpy.types.Object.switchParam
    del bpy.types.Object.enableRoomSwitch

    for cls in reversed(sm64_obj_classes):
        unregister_class(cls)


"""
object: model, bparam, behaviour, acts
macro: preset, [bparam]
special: preset, [yaw, [bparam]]
trajectory: id
"""
