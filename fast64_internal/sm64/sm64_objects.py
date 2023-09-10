import math, bpy, mathutils
from bpy.utils import register_class, unregister_class
from re import findall
from .sm64_function_map import func_map

from ..utility import (
    PluginError,
    CData,
    Vector,
    toAlnum,
    convertRadiansToS16,
    checkIdentityRotation,
    obj_scale_is_unified,
    all_values_equal_x,
    checkIsSM64PreInlineGeoLayout,
    prop_split,
)

from .sm64_constants import (
    levelIDNames,
    enumLevelNames,
    enumModelIDs,
    enumMacrosNames,
    enumSpecialsNames,
    enumBehaviourPresets,
    groups_seg_5_lvl_load,
    groups_seg_6_lvl_load,
)

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
    def __init__(self, model, position, rotation, behaviour, bparam, acts):
        self.model = model
        self.behaviour = behaviour
        self.bparam = bparam
        self.acts = acts
        self.position = position
        self.rotation = rotation

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
        for obj in self.objects:
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
        data += "\tEND_AREA(),\n\n"
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
        camScaleValue = bpy.context.scene.blenderToSM64Scale

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
    if bpy.context.scene.refreshVer == "Refresh 8" or bpy.context.scene.refreshVer == "Refresh 7":
        pass
    elif bpy.context.scene.refreshVer == "Refresh 6":
        if modelID == "MODEL_TWEESTER":
            modelID = "MODEL_TORNADO"
    elif (
        bpy.context.scene.refreshVer == "Refresh 5"
        or bpy.context.scene.refreshVer == "Refresh 4"
        or bpy.context.scene.refreshVer == "Refresh 3"
    ):
        if modelID == "MODEL_TWEESTER":
            modelID = "MODEL_TORNADO"
        elif modelID == "MODEL_WAVE_TRAIL":
            modelID = "MODEL_WATER_WAVES"
        elif modelID == "MODEL_IDLE_WATER_WAVE":
            modelID = "MODEL_WATER_WAVES_SURF"
        elif modelID == "MODEL_SMALL_WATER_SPLASH":
            modelID = "MODEL_SPOT_ON_GROUND"

    return modelID


def handleRefreshDiffSpecials(preset):
    if (
        bpy.context.scene.refreshVer == "Refresh 8"
        or bpy.context.scene.refreshVer == "Refresh 7"
        or bpy.context.scene.refreshVer == "Refresh 6"
        or bpy.context.scene.refreshVer == "Refresh 5"
        or bpy.context.scene.refreshVer == "Refresh 4"
        or bpy.context.scene.refreshVer == "Refresh 3"
    ):
        pass
    return preset


def handleRefreshDiffMacros(preset):
    if (
        bpy.context.scene.refreshVer == "Refresh 8"
        or bpy.context.scene.refreshVer == "Refresh 7"
        or bpy.context.scene.refreshVer == "Refresh 6"
        or bpy.context.scene.refreshVer == "Refresh 5"
        or bpy.context.scene.refreshVer == "Refresh 4"
        or bpy.context.scene.refreshVer == "Refresh 3"
    ):
        pass
    return preset


def start_process_sm64_objects(obj, area, transformMatrix, specialsOnly):
    # spaceRotation = mathutils.Quaternion((1, 0, 0), math.radians(90.0)).to_matrix().to_4x4()

    # We want translations to be relative to area obj, but rotation/scale to be world space
    translation, rotation, scale = obj.matrix_world.decompose()
    process_sm64_objects(obj, area, mathutils.Matrix.Translation(translation), transformMatrix, specialsOnly)


def process_sm64_objects(obj, area, rootMatrix, transformMatrix, specialsOnly):
    translation, originalRotation, scale = (transformMatrix @ rootMatrix.inverted() @ obj.matrix_world).decompose()

    finalTransform = (
        mathutils.Matrix.Translation(translation)
        @ originalRotation.to_matrix().to_4x4()
        @ mathutils.Matrix.Diagonal(scale).to_4x4()
    )

    # Hacky solution to handle Z-up to Y-up conversion
    rotation = originalRotation @ mathutils.Quaternion((1, 0, 0), math.radians(90.0))

    if obj.data is None:
        if obj.sm64_obj_type == "Area Root" and obj.areaIndex != area.index:
            return
        if specialsOnly:
            if obj.sm64_obj_type == "Special":
                preset = obj.sm64_special_enum if obj.sm64_special_enum != "Custom" else obj.sm64_obj_preset
                preset = handleRefreshDiffSpecials(preset)
                area.specials.append(
                    SM64_Special_Object(
                        preset,
                        translation,
                        rotation.to_euler() if obj.sm64_obj_set_yaw else None,
                        obj.fast64.sm64.game_object.get_behavior_params()
                        if (obj.sm64_obj_set_yaw and obj.sm64_obj_set_bparam)
                        else None,
                    )
                )
            elif obj.sm64_obj_type == "Water Box":
                checkIdentityRotation(obj, rotation, False)
                area.water_boxes.append(CollisionWaterBox(obj.waterBoxType, translation, scale, obj.empty_display_size))
        else:
            if obj.sm64_obj_type == "Object":
                modelID = obj.sm64_model_enum if obj.sm64_model_enum != "Custom" else obj.sm64_obj_model
                modelID = handleRefreshDiffModelIDs(modelID)
                behaviour = (
                    func_map[bpy.context.scene.refreshVer][obj.sm64_behaviour_enum]
                    if obj.sm64_behaviour_enum != "Custom"
                    else obj.sm64_obj_behaviour
                )
                area.objects.append(
                    SM64_Object(
                        modelID,
                        translation,
                        rotation.to_euler(),
                        behaviour,
                        obj.fast64.sm64.game_object.get_behavior_params(),
                        get_act_string(obj),
                    )
                )
            elif obj.sm64_obj_type == "Macro":
                macro = obj.sm64_macro_enum if obj.sm64_macro_enum != "Custom" else obj.sm64_obj_preset
                area.macros.append(
                    SM64_Macro_Object(
                        macro,
                        translation,
                        rotation.to_euler(),
                        obj.fast64.sm64.game_object.get_behavior_params() if obj.sm64_obj_set_bparam else None,
                    )
                )
            elif obj.sm64_obj_type == "Mario Start":
                mario_start = SM64_Mario_Start(obj.sm64_obj_mario_start_area, translation, rotation.to_euler())
                area.objects.append(mario_start)
                area.mario_start = mario_start
            elif obj.sm64_obj_type == "Trajectory":
                pass
            elif obj.sm64_obj_type == "Whirpool":
                area.objects.append(
                    SM64_Whirpool(obj.whirlpool_index, obj.whirpool_condition, obj.whirpool_strength, translation)
                )
            elif obj.sm64_obj_type == "Camera Volume":
                checkIdentityRotation(obj, rotation, True)
                if obj.cameraVolumeGlobal:
                    triggerIndex = -1
                else:
                    triggerIndex = area.index
                area.cameraVolumes.append(
                    CameraVolume(
                        triggerIndex,
                        obj.cameraVolumeFunction,
                        translation,
                        rotation.to_euler(),
                        scale,
                        obj.empty_display_size,
                    )
                )

            elif obj.sm64_obj_type == "Puppycam Volume":
                checkIdentityRotation(obj, rotation, False)

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
                        levelIDNames[bpy.data.scenes["Scene"].levelOption],
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
        area.splines.append(convertSplineObject(area.name + "_spline_" + obj.name, obj, finalTransform))

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
        name = (
            func_map[context.scene.refreshVer][self.sm64_behaviour_enum]
            if self.sm64_behaviour_enum != "Custom"
            else "Custom"
        )
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
        return context.scene.gameEditorMode == "SM64" and (context.object is not None and context.object.data is None)

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
                        text=f"Exported Segment: _{levelObj.backgroundSegment}_{context.scene.compressionFormat}SegmentRomStart"
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

            fogBox = box.box()
            fogInfoBox = fogBox.box()
            fogInfoBox.label(text="Warning: Fog only applies to materials that:")
            fogInfoBox.label(text="- use fog")
            fogInfoBox.label(text="- have global fog enabled.")
            prop_split(fogBox, obj, "area_fog_color", "Area Fog Color")
            prop_split(fogBox, obj, "area_fog_position", "Area Fog Position")

            if obj.areaIndex == 1 or obj.areaIndex == 2 or obj.areaIndex == 3:
                prop_split(box, obj, "echoLevel", "Echo Level")

            if obj.areaIndex == 1 or obj.areaIndex == 2 or obj.areaIndex == 3 or obj.areaIndex == 4:
                box.prop(obj, "zoomOutOnPause")

            box.prop(obj.fast64.sm64.area, "disable_background")

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

            if self.destLevelEnum == "custom":
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
            if warpNode.destLevelEnum == "custom":
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

        func = obj.get("geoASMFunc") or obj.get("geo_func") or geo_asm.func
        geo_asm.func = func

        param = obj.get("geoASMParam") or obj.get("func_param") or geo_asm.param
        geo_asm.param = str(param)


class SM64_AreaProperties(bpy.types.PropertyGroup):
    name = "Area Properties"
    disable_background: bpy.props.BoolProperty(
        name="Disable Background",
        default=False,
        description="Disable rendering background. Ideal for interiors or areas that should never see a background.",
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

        game_object.bparams = obj.get("sm64_obj_bparam", game_object.bparams)

        # delete legacy property
        if "sm64_obj_bparam" in obj:
            del obj["sm64_obj_bparam"]

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
    seg5_enum: bpy.props.EnumProperty(name="Segment 5 Group", default="Do Not Write", items=groups_seg_5_lvl_load)
    seg6_enum: bpy.props.EnumProperty(name="Segment 6 Group", default="Do Not Write", items=groups_seg_6_lvl_load)

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
    SM64_GeoASMProperties,
    SM64_LevelProperties,
    SM64_AreaProperties,
    SM64_GameObjectProperties,
    SM64_SegmentProperties,
    SM64_ObjectProperties,
)


sm64_obj_panel_classes = (SM64ObjectPanel,)


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
