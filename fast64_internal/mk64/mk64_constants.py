MODEL_HEADER = """#include <ultra64.h>
#include <macros.h>
#include <PR/gbi.h>

"""

enum_surface_types = [
    ("SURFACE_DEFAULT", "SURFACE_DEFAULT", "SURFACE_DEFAULT"),
    ("AIRBORNE", "AIRBORNE", "AIRBORNE"),
    ("ASPHALT", "ASPHALT", "ASPHALT"),
    ("DIRT", "DIRT", "DIRT"),
    ("SAND", "SAND", "SAND"),
    ("STONE", "STONE", "STONE"),
    ("SNOW", "SNOW", "SNOW"),
    ("BRIDGE", "BRIDGE", "BRIDGE"),
    ("SAND_OFFROAD", "SAND_OFFROAD", "SAND_OFFROAD"),
    ("GRASS", "GRASS", "GRASS"),
    ("ICE", "ICE", "ICE"),
    ("WET_SAND", "WET_SAND", "WET_SAND"),
    ("SNOW_OFFROAD", "SNOW_OFFROAD", "SNOW_OFFROAD"),
    ("CLIFF", "CLIFF", "CLIFF"),
    ("DIRT_OFFROAD", "DIRT_OFFROAD", "DIRT_OFFROAD"),
    ("TRAIN_TRACK", "TRAIN_TRACK", "TRAIN_TRACK"),
    ("CAVE", "CAVE", "CAVE"),
    ("ROPE_BRIDGE", "ROPE_BRIDGE", "ROPE_BRIDGE"),
    ("WOOD_BRIDGE", "WOOD_BRIDGE", "WOOD_BRIDGE"),
    ("BOOST_RAMP_WOOD", "BOOST_RAMP_WOOD", "BOOST_RAMP_WOOD"),
    ("OUT_OF_BOUNDS", "OUT_OF_BOUNDS", "OUT_OF_BOUNDS"),
    ("BOOST_RAMP_ASPHALT", "BOOST_RAMP_ASPHALT", "BOOST_RAMP_ASPHALT"),
    ("RAMP", "RAMP", "RAMP"),
]

enum_actor_types = [
    ("Piranha_Plant", "Piranha Plant", "Piranha Plant"),
    ("Other", "Other", "Other"),
]

mk64_world_defaults = {
    "geometryMode": {
        "zBuffer": True,
        "shade": True,
        "cullBack": True,
        "lighting": True,
        "shadeSmooth": True,
    },
    "otherModeH": {
        "alphaDither": "G_AD_NOISE",
        "textureFilter": "G_TF_BILERP",
        "perspectiveCorrection": "G_TP_PERSP",
        "textureConvert": "G_TC_FILT",
        "cycleType": "G_CYC_2CYCLE",
    },
}

