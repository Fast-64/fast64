import bpy

from collections import OrderedDict
from dataclasses import dataclass
from typing import Optional
from bpy.types import Context
from .enum_data import Z64_EnumData
from .object_data import Z64_ObjectData
from .actor_data import Z64_ActorData

# ---

# TODO: get this from XML

oot_enum_nature_id = [
    ("Custom", "Custom", "Custom"),
    ("0x00", "General Night", "NATURE_ID_GENERAL_NIGHT"),
    ("0x01", "Market Entrance", "NATURE_ID_MARKET_ENTRANCE"),
    ("0x02", "Kakariko Region", "NATURE_ID_KAKARIKO_REGION"),
    ("0x03", "Market Ruins", "NATURE_ID_MARKET_RUINS"),
    ("0x04", "Kokiri Region", "NATURE_ID_KOKIRI_REGION"),
    ("0x05", "Market Night", "NATURE_ID_MARKET_NIGHT"),
    ("0x06", "NATURE_ID_06", "NATURE_ID_06"),
    ("0x07", "Ganon's Lair", "NATURE_ID_GANONS_LAIR"),
    ("0x08", "NATURE_ID_08", "NATURE_ID_08"),
    ("0x09", "NATURE_ID_09", "NATURE_ID_09"),
    ("0x0A", "Wasteland", "NATURE_ID_WASTELAND"),
    ("0x0B", "Colossus", "NATURE_ID_COLOSSUS"),
    ("0x0C", "Nature DMT", "NATURE_ID_DEATH_MOUNTAIN_TRAIL"),
    ("0x0D", "NATURE_ID_0D", "NATURE_ID_0D"),
    ("0x0E", "NATURE_ID_0E", "NATURE_ID_0E"),
    ("0x0F", "NATURE_ID_0F", "NATURE_ID_0F"),
    ("0x10", "NATURE_ID_10", "NATURE_ID_10"),
    ("0x11", "NATURE_ID_11", "NATURE_ID_11"),
    ("0x12", "NATURE_ID_12", "NATURE_ID_12"),
    ("0x13", "None", "NATURE_ID_NONE"),
    ("0xFF", "Disabled", "NATURE_ID_DISABLED"),
]

enum_ambiance_id = [
    ("Custom", "Custom", "Custom"),
    ("0x00", "AMBIENCE_ID_00", "AMBIENCE_ID_00"),
    ("0x01", "AMBIENCE_ID_01", "AMBIENCE_ID_01"),
    ("0x02", "AMBIENCE_ID_02", "AMBIENCE_ID_02"),
    ("0x03", "AMBIENCE_ID_03", "AMBIENCE_ID_03"),
    ("0x04", "AMBIENCE_ID_04", "AMBIENCE_ID_04"),
    ("0x05", "AMBIENCE_ID_05", "AMBIENCE_ID_05"),
    ("0x06", "AMBIENCE_ID_06", "AMBIENCE_ID_06"),
    ("0x07", "AMBIENCE_ID_07", "AMBIENCE_ID_07"),
    ("0x08", "AMBIENCE_ID_08", "AMBIENCE_ID_08"),
    ("0x09", "AMBIENCE_ID_09", "AMBIENCE_ID_09"),
    ("0x0A", "AMBIENCE_ID_0A", "AMBIENCE_ID_0A"),
    ("0x0B", "AMBIENCE_ID_0B", "AMBIENCE_ID_0B"),
    ("0x0C", "AMBIENCE_ID_0C", "AMBIENCE_ID_0C"),
    ("0x0D", "AMBIENCE_ID_0D", "AMBIENCE_ID_0D"),
    ("0x0E", "AMBIENCE_ID_0E", "AMBIENCE_ID_0E"),
    ("0x0F", "AMBIENCE_ID_0F", "AMBIENCE_ID_0F"),
    ("0x10", "AMBIENCE_ID_10", "AMBIENCE_ID_10"),
    ("0x11", "AMBIENCE_ID_11", "AMBIENCE_ID_11"),
    ("0x12", "AMBIENCE_ID_12", "AMBIENCE_ID_12"),
    ("0x13", "AMBIENCE_ID_13", "AMBIENCE_ID_13"),
    ("0xFF", "AMBIENCE_ID_DISABLED", "AMBIENCE_ID_DISABLED"),
]

# ---

oot_enum_skybox = [
    ("Custom", "Custom", "Custom"),
    ("0x00", "None", "None"),
    ("0x01", "Standard Sky", "Standard Sky"),
    ("0x02", "Hylian Bazaar", "Hylian Bazaar"),
    ("0x03", "Brown Cloudy Sky", "Brown Cloudy Sky"),
    ("0x04", "Market Ruins", "Market Ruins"),
    ("0x05", "Black Cloudy Night", "Black Cloudy Night"),
    ("0x07", "Link's House", "Link's House"),
    ("0x09", "Market (Main Square, Day)", "Market (Main Square, Day)"),
    ("0x0A", "Market (Main Square, Night)", "Market (Main Square, Night)"),
    ("0x0B", "Happy Mask Shop", "Happy Mask Shop"),
    ("0x0C", "Know-It-All Brothers' House", "Know-It-All Brothers' House"),
    ("0x0E", "Kokiri Twins' House", "Kokiri Twins' House"),
    ("0x0F", "Stable", "Stable"),
    ("0x10", "Stew Lady's House", "Stew Lady's House"),
    ("0x11", "Kokiri Shop", "Kokiri Shop"),
    ("0x13", "Goron Shop", "Goron Shop"),
    ("0x14", "Zora Shop", "Zora Shop"),
    ("0x16", "Kakariko Potions Shop", "Kakariko Potions Shop"),
    ("0x17", "Hylian Potions Shop", "Hylian Potions Shop"),
    ("0x18", "Bomb Shop", "Bomb Shop"),
    ("0x1A", "Dog Lady's House", "Dog Lady's House"),
    ("0x1B", "Impa's House", "Impa's House"),
    ("0x1C", "Gerudo Tent", "Gerudo Tent"),
    ("0x1D", "Environment Color", "Environment Color"),
    ("0x20", "Mido's House", "Mido's House"),
    ("0x21", "Saria's House", "Saria's House"),
    ("0x22", "Dog Guy's House", "Dog Guy's House"),
]

mm_enum_skybox = [
    ("Custom", "Custom", "Custom"),
    ("SKYBOX_NONE", "None", "0x00"),
    ("SKYBOX_NORMAL_SKY", "Standard Sky", "0x01"),
    ("SKYBOX_2", "SKYBOX_2", "0x02"),
    ("SKYBOX_3", "SKYBOX_3", "0x03"),
    ("SKYBOX_CUTSCENE_MAP", "Cutscene Map", "0x05"),
]

oot_enum_skybox_config = [
    ("Custom", "Custom", "Custom"),
    ("0x00", "Sunny", "Sunny"),
    ("0x01", "Cloudy", "Cloudy"),
]

mm_enum_skybox_config = [
    ("Custom", "Custom", "Custom"),
    ("SKYBOX_CONFIG_0", "SKYBOX_CONFIG_0", "0x00"),
    ("SKYBOX_CONFIG_1", "SKYBOX_CONFIG_1", "0x01"),
    ("SKYBOX_CONFIG_2", "SKYBOX_CONFIG_2", "0x02"),
    ("SKYBOX_CONFIG_3", "SKYBOX_CONFIG_3", "0x03"),
    ("SKYBOX_CONFIG_4", "SKYBOX_CONFIG_4", "0x04"),
    ("SKYBOX_CONFIG_5", "SKYBOX_CONFIG_5", "0x05"),
    ("SKYBOX_CONFIG_6", "SKYBOX_CONFIG_6", "0x06"),
    ("SKYBOX_CONFIG_7", "SKYBOX_CONFIG_7", "0x07"),
    ("SKYBOX_CONFIG_8", "SKYBOX_CONFIG_8", "0x08"),
    ("SKYBOX_CONFIG_9", "SKYBOX_CONFIG_9", "0x09"),
    ("SKYBOX_CONFIG_10", "SKYBOX_CONFIG_10", "0x0A"),
    ("SKYBOX_CONFIG_11", "SKYBOX_CONFIG_11", "0x0B"),
    ("SKYBOX_CONFIG_12", "SKYBOX_CONFIG_12", "0x0C"),
    ("SKYBOX_CONFIG_13", "SKYBOX_CONFIG_13", "0x0D"),
    ("SKYBOX_CONFIG_14", "SKYBOX_CONFIG_14", "0x0E"),
    ("SKYBOX_CONFIG_15", "SKYBOX_CONFIG_15", "0x0F"),
    ("SKYBOX_CONFIG_16", "SKYBOX_CONFIG_16", "0x10"),
    ("SKYBOX_CONFIG_17", "SKYBOX_CONFIG_17", "0x11"),
    ("SKYBOX_CONFIG_18", "SKYBOX_CONFIG_18", "0x12"),
    ("SKYBOX_CONFIG_19", "SKYBOX_CONFIG_19", "0x13"),
    ("SKYBOX_CONFIG_20", "SKYBOX_CONFIG_20", "0x14"),
    ("SKYBOX_CONFIG_21", "SKYBOX_CONFIG_21", "0x15"),
    ("SKYBOX_CONFIG_22", "SKYBOX_CONFIG_22", "0x16"),
    ("SKYBOX_CONFIG_23", "SKYBOX_CONFIG_23", "0x17"),
    ("SKYBOX_CONFIG_24", "SKYBOX_CONFIG_24", "0x18"),
    ("SKYBOX_CONFIG_25", "SKYBOX_CONFIG_25", "0x19"),
    ("SKYBOX_CONFIG_26", "SKYBOX_CONFIG_26", "0x1A"),
    ("SKYBOX_CONFIG_27", "SKYBOX_CONFIG_27", "0x1B"),
]

oot_enum_environment_type = [
    ("Custom", "Custom", "Custom"),
    ("0x00", "Default", "Default"),
    ("0x01", "Sneezing", "Sneezing"),
    ("0x02", "Wiping Forehead", "Wiping Forehead"),
    ("0x04", "Yawning", "Yawning"),
    ("0x07", "Gasping For Breath", "Gasping For Breath"),
    ("0x09", "Brandish Sword", "Brandish Sword"),
    ("0x0A", "Adjust Tunic", "Adjust Tunic"),
    ("0xFF", "Hops On Epona", "Hops On Epona"),
]

mm_enum_environment_type = [
    ("Custom", "Custom", "Custom"),
    ("ROOM_ENV_DEFAULT", "Default", "0x00"),
    ("ROOM_ENV_COLD", "Cold", "0x01"),
    ("ROOM_ENV_WARM", "Warm", "0x02"),
    ("ROOM_ENV_HOT", "Hot", "0x03"),
    ("ROOM_ENV_UNK_STRETCH_1", "Unknown Stretch 1", "0x04"),
    ("ROOM_ENV_UNK_STRETCH_2", "Unknown Stretch 2", "0x05"),
    ("ROOM_ENV_UNK_STRETCH_3", "Unknown Stretch 3", "0x06"),
]

oot_enum_room_type = [
    ("Custom", "Custom", "Custom"),
    ("0x00", "Default", "Default"),
    ("0x01", "Dungeon Behavior (Z-Target, Sun's Song)", "Dungeon Behavior (Z-Target, Sun's Song)"),
    ("0x02", "Disable Backflips/Sidehops", "Disable Backflips/Sidehops"),
    ("0x03", "Disable Color Dither", "Disable Color Dither"),
    ("0x04", "(?) Horse Camera Related", "(?) Horse Camera Related"),
    ("0x05", "Disable Darker Screen Effect (NL/Spins)", "Disable Darker Screen Effect (NL/Spins)"),
]

mm_enum_room_type = [
    ("Custom", "Custom", "Custom"),
    ("ROOM_TYPE_NORMAL", "Normal", "0x00"),
    ("ROOM_TYPE_DUNGEON", "Dungeon", "0x01"),
    ("ROOM_TYPE_INDOORS", "Indoors", "0x02"),
    ("ROOM_TYPE_3", "Type 3", "0x03"),
    ("ROOM_TYPE_4", "Type 4 (Horse related)", "0x04"),
    ("ROOM_TYPE_BOSS", "Boss", "0x05"),
]

oot_enum_floor_property = [
    ("Custom", "Custom", "Custom"),
    ("0x00", "Default", "Default"),
    ("0x05", "Trigger Respawn", "Trigger Respawn"),
    ("0x06", "Grab Wall", "Grab Wall"),
    ("0x08", "Stop Air Momentum", "Stop Air Momentum"),
    ("0x09", "Fall Instead Of Jumping", "Fall Instead Of Jumping"),
    ("0x0B", "Dive Animation", "Dive Animation"),
    ("0x0C", "Trigger Void", "Trigger Void"),
]

mm_enum_floor_property = [
    ("Custom", "Custom", "Custom"),
    ("0x00", "Default", "FLOOR_PROPERTY_0"),
    ("0x01", "Frontflip Jump Animation", "FLOOR_PROPERTY_1"),
    ("0x02", "Sideflip Jump Animation", "FLOOR_PROPERTY_2"),
    ("0x05", "Trigger Respawn (sets human no mask)", "FLOOR_PROPERTY_5"),
    ("0x06", "Grab Wall", "FLOOR_PROPERTY_6"),
    ("0x07", "Unknown (sets speed to 0)", "FLOOR_PROPERTY_7"),
    ("0x08", "Stop Air Momentum", "FLOOR_PROPERTY_8"),
    ("0x09", "Fall Instead Of Jumping", "FLOOR_PROPERTY_9"),
    ("0x0B", "Dive Animation", "FLOOR_PROPERTY_11"),
    ("0x0C", "Trigger Void", "FLOOR_PROPERTY_12"),
    ("0x0D", "Trigger Void (runs `Player_Action_1`)", "FLOOR_PROPERTY_13"),
]

oot_enum_floor_type = [
    ("Custom", "Custom", "Custom"),
    ("0x00", "Default", "Default"),
    ("0x01", "Haunted Wasteland Camera", "Haunted Wasteland Camera"),
    ("0x02", "Fire (damages every 6s)", "Fire (damages every 6s)"),
    ("0x03", "Fire (damages every 3s)", "Fire (damages every 3s)"),
    ("0x04", "Shallow Sand", "Shallow Sand"),
    ("0x05", "Slippery", "Slippery"),
    ("0x06", "Ignore Fall Damage", "Ignore Fall Damage"),
    ("0x07", "Quicksand Crossing (Blocks Epona)", "Quicksand Crossing (Epona Uncrossable)"),
    ("0x08", "Jabu Jabu's Belly Floor", "Jabu Jabu's Belly Floor"),
    ("0x09", "Trigger Void", "Trigger Void"),
    ("0x0A", "Stops Air Momentum", "Stops Air Momentum"),
    ("0x0B", "Grotto Exit Animation", "Link Looks Up"),
    ("0x0C", "Quicksand Crossing (Epona Crossable)", "Quicksand Crossing (Epona Crossable)"),
]

mm_enum_floor_type = [
    ("Custom", "Custom", "Custom"),
    ("0x00", "Default", "FLOOR_TYPE_0"),
    ("0x01", "Unused (?)", "FLOOR_TYPE_1"),
    ("0x02", "Fire Damages (burns Player every second)", "FLOOR_TYPE_2"),
    ("0x03", "Fire Damages 2 (burns Player every second)", "FLOOR_TYPE_3"),
    ("0x04", "Shallow Sand", "FLOOR_TYPE_4"),
    ("0x05", "Ice (Slippery)", "FLOOR_TYPE_5"),
    ("0x06", "Ignore Fall Damages", "FLOOR_TYPE_6"),
    ("0x07", "Quicksand (blocks Epona)", "FLOOR_TYPE_7"),
    ("0x08", "Jabu Jabu's Belly Floor (Unused)", "FLOOR_TYPE_8"),
    ("0x09", "Triggers Void", "FLOOR_TYPE_9"),
    ("0x0A", "Stops Air Momentum", "FLOOR_TYPE_10"),
    ("0x0B", "Grotto Exit Animation", "FLOOR_TYPE_11"),
    ("0x0C", "Quicksand (doesn't block Epona)", "FLOOR_TYPE_12"),
    ("0x0D", "Deeper Shallow Sand", "FLOOR_TYPE_13"),
    ("0x0E", "Shallow Snow", "FLOOR_TYPE_14"),
    ("0x0F", "Deeper Shallow Snow", "FLOOR_TYPE_15"),
]

enum_floor_effect = [
    ("Custom", "Custom", "Custom"),
    ("0x00", "Default", "FLOOR_EFFECT_0"),
    ("0x01", "Steep/Slippery Slope", "FLOOR_EFFECT_1"),
    ("0x02", "Walkable (Preserves Exit Flags)", "FLOOR_EFFECT_2"),
]

oot_enum_camera_setting_type = [
    ("Custom", "Custom", "Custom"),
    ("CAM_SET_NONE", "None", "None"),
    ("CAM_SET_NORMAL0", "Normal0", "Normal0"),
    ("CAM_SET_NORMAL1", "Normal1", "Normal1"),
    ("CAM_SET_DUNGEON0", "Dungeon0", "Dungeon0"),
    ("CAM_SET_DUNGEON1", "Dungeon1", "Dungeon1"),
    ("CAM_SET_NORMAL3", "Normal3", "Normal3"),
    ("CAM_SET_HORSE0", "Horse", "Horse"),
    ("CAM_SET_BOSS_GOMA", "Boss_gohma", "Boss_gohma"),
    ("CAM_SET_BOSS_DODO", "Boss_dodongo", "Boss_dodongo"),
    ("CAM_SET_BOSS_BARI", "Boss_barinade", "Boss_barinade"),
    ("CAM_SET_BOSS_FGANON", "Boss_phantom_ganon", "Boss_phantom_ganon"),
    ("CAM_SET_BOSS_BAL", "Boss_volvagia", "Boss_volvagia"),
    ("CAM_SET_BOSS_SHADES", "Boss_bongo", "Boss_bongo"),
    ("CAM_SET_BOSS_MOFA", "Boss_morpha", "Boss_morpha"),
    ("CAM_SET_TWIN0", "Twinrova_platform", "Twinrova_platform"),
    ("CAM_SET_TWIN1", "Twinrova_floor", "Twinrova_floor"),
    ("CAM_SET_BOSS_GANON1", "Boss_ganondorf", "Boss_ganondorf"),
    ("CAM_SET_BOSS_GANON2", "Boss_ganon", "Boss_ganon"),
    ("CAM_SET_TOWER0", "Tower_climb", "Tower_climb"),
    ("CAM_SET_TOWER1", "Tower_unused", "Tower_unused"),
    ("CAM_SET_FIXED0", "Market_balcony", "Market_balcony"),
    ("CAM_SET_FIXED1", "Chu_bowling", "Chu_bowling"),
    ("CAM_SET_CIRCLE0", "Pivot_crawlspace", "Pivot_crawlspace"),
    ("CAM_SET_CIRCLE2", "Pivot_shop_browsing", "Pivot_shop_browsing"),
    ("CAM_SET_CIRCLE3", "Pivot_in_front", "Pivot_in_front"),
    ("CAM_SET_PREREND0", "Prerend_fixed", "Prerend_fixed"),
    ("CAM_SET_PREREND1", "Prerend_pivot", "Prerend_pivot"),
    ("CAM_SET_PREREND3", "Prerend_side_scroll", "Prerend_side_scroll"),
    ("CAM_SET_DOOR0", "Door0", "Door0"),
    ("CAM_SET_DOORC", "Doorc", "Doorc"),
    ("CAM_SET_RAIL3", "Crawlspace", "Crawlspace"),
    ("CAM_SET_START0", "Start0", "Start0"),
    ("CAM_SET_START1", "Start1", "Start1"),
    ("CAM_SET_FREE0", "Free0", "Free0"),
    ("CAM_SET_FREE2", "Free2", "Free2"),
    ("CAM_SET_CIRCLE4", "Pivot_corner", "Pivot_corner"),
    ("CAM_SET_CIRCLE5", "Pivot_water_surface", "Pivot_water_surface"),
    ("CAM_SET_DEMO0", "Cs_0", "Cs_0"),
    ("CAM_SET_DEMO1", "Twisted_Hallway", "Twisted_Hallway"),
    ("CAM_SET_MORI1", "Forest_birds_eye", "Forest_birds_eye"),
    ("CAM_SET_ITEM0", "Slow_chest_cs", "Slow_chest_cs"),
    ("CAM_SET_ITEM1", "Item_unused", "Item_unused"),
    ("CAM_SET_DEMO3", "Cs_3", "Cs_3"),
    ("CAM_SET_DEMO4", "Cs_attention", "Cs_attention"),
    ("CAM_SET_UFOBEAN", "Bean_generic", "Bean_generic"),
    ("CAM_SET_LIFTBEAN", "Bean_lost_woods", "Bean_lost_woods"),
    ("CAM_SET_SCENE0", "Scene_unused", "Scene_unused"),
    ("CAM_SET_SCENE1", "Scene_transition", "Scene_transition"),
    ("CAM_SET_HIDAN1", "Fire_platform", "Fire_platform"),
    ("CAM_SET_HIDAN2", "Fire_staircase", "Fire_staircase"),
    ("CAM_SET_MORI2", "Forest_unused", "Forest_unused"),
    ("CAM_SET_MORI3", "Defeat_poe", "Defeat_poe"),
    ("CAM_SET_TAKO", "Big_octo", "Big_octo"),
    ("CAM_SET_SPOT05A", "Meadow_birds_eye", "Meadow_birds_eye"),
    ("CAM_SET_SPOT05B", "Meadow_unused", "Meadow_unused"),
    ("CAM_SET_HIDAN3", "Fire_birds_eye", "Fire_birds_eye"),
    ("CAM_SET_ITEM2", "Turn_around", "Turn_around"),
    ("CAM_SET_CIRCLE6", "Pivot_vertical", "Pivot_vertical"),
    ("CAM_SET_NORMAL2", "Normal2", "Normal2"),
    ("CAM_SET_FISHING", "Fishing", "Fishing"),
    ("CAM_SET_DEMOC", "Cs_c", "Cs_c"),
    ("CAM_SET_UO_FIBER", "Jabu_tentacle", "Jabu_tentacle"),
    ("CAM_SET_DUNGEON2", "Dungeon2", "Dungeon2"),
    ("CAM_SET_TEPPEN", "Directed_yaw", "Directed_yaw"),
    ("CAM_SET_CIRCLE7", "Pivot_from_side", "Pivot_from_side"),
    ("CAM_SET_NORMAL4", "Normal4", "Normal4"),
]

mm_enum_camera_setting_type = [
    ("Custom", "Custom", "Custom"),
    ("CAM_SET_NONE", "None", "None"),
    ("CAM_SET_NORMAL0", "Normal0", "Generic camera 0, used in various places 'NORMAL0'"),
    ("CAM_SET_NORMAL3", "Normal3", "Generic camera 3, used in various places 'NORMAL3'"),
    (
        "CAM_SET_PIVOT_DIVING",
        "Pivot_Diving",
        "Player diving from the surface of the water to underwater not as zora 'CIRCLE5'",
    ),
    ("CAM_SET_HORSE", "Horse", "Reiding a horse 'HORSE0'"),
    (
        "CAM_SET_ZORA_DIVING",
        "Zora_Diving",
        "Parallel's Pivot Diving, but as Zora. However, Zora does not dive like a human. So this setting appears to not be used 'ZORA0'",
    ),
    (
        "CAM_SET_PREREND_FIXED",
        "Prerend_Fixed",
        "Unused remnant of OoT: camera is fixed in position and rotation 'PREREND0'",
    ),
    (
        "CAM_SET_PREREND_PIVOT",
        "Prerend_Pivot",
        "Unused remnant of OoT: Camera is fixed in position with fixed pitch, but is free to rotate in the yaw direction 360 degrees 'PREREND1'",
    ),
    (
        "CAM_SET_DOORC",
        "Doorc",
        "Generic room door transitions, camera moves and follows player as the door is open and closed 'DOORC'",
    ),
    ("CAM_SET_DEMO0", "Demo0", "Unknown, possibly related to treasure chest game as goron? 'DEMO0'"),
    ("CAM_SET_FREE0", "Free0", "Free Camera, manual control is given, no auto-updating eye or at 'FREE0'"),
    ("CAM_SET_BIRDS_EYE_VIEW_0", "Birds_Eye_View_0", "Appears unused. Camera is a top-down view 'FUKAN0'"),
    ("CAM_SET_NORMAL1", "Normal1", "Generic camera 1, used in various places 'NORMAL1'"),
    (
        "CAM_SET_NANAME",
        "Naname",
        "Unknown, slanted or tilted. Behaves identical to Normal0 except with added roll 'NANAME'",
    ),
    ("CAM_SET_CIRCLE0", "Circle0", "Used in Curiosity Shop, Pirates Fortress, Mayor's Residence 'CIRCLE0'"),
    ("CAM_SET_FIXED0", "Fixed0", "Used in Sakon's Hideout puzzle rooms, milk bar stage 'FIXED0'"),
    ("CAM_SET_SPIRAL_DOOR", "Spiral_Door", "Exiting a Spiral Staircase 'SPIRAL'"),
    ("CAM_SET_DUNGEON0", "Dungeon0", "Generic dungeon camera 0, used in various places 'DUNGEON0'"),
    (
        "CAM_SET_ITEM0",
        "Item0",
        "Getting an item and holding it above Player's head (from small chest, freestanding, npc, ...) 'ITEM0'",
    ),
    ("CAM_SET_ITEM1", "Item1", "Looking at player while playing the ocarina 'ITEM1'"),
    ("CAM_SET_ITEM2", "Item2", "Bottles: drinking, releasing fairy, dropping fish 'ITEM2'"),
    ("CAM_SET_ITEM3", "Item3", "Bottles: catching fish or bugs, showing an item 'ITEM3'"),
    ("CAM_SET_NAVI", "Navi", "Song of Soaring, variations of playing Song of Time 'NAVI'"),
    ("CAM_SET_WARP_PAD_MOON", "Warp_Pad_Moon", "Warp circles from Goron Trial on the moon 'WARP0'"),
    ("CAM_SET_DEATH", "Death", "Player death animation when health goes to 0 'DEATH'"),
    ("CAM_SET_REBIRTH", "Rebirth", "Unknown set with camDataId = -9 (it's not being revived by a fairy) 'REBIRTH'"),
    (
        "CAM_SET_LONG_CHEST_OPENING",
        "Long_Chest_Opening",
        "Long cutscene when opening a big chest with a major item 'TREASURE'",
    ),
    ("CAM_SET_MASK_TRANSFORMATION", "Mask_Transformation", "Putting on a transformation mask 'TRANSFORM'"),
    ("CAM_SET_ATTENTION", "Attention", "Unknown, set with camDataId = -15 'ATTENTION'"),
    ("CAM_SET_WARP_PAD_ENTRANCE", "Warp_Pad_Entrance", "Warp pad from start of a dungeon to the boss-room 'WARP1'"),
    ("CAM_SET_DUNGEON1", "Dungeon1", "Generic dungeon camera 1, used in various places 'DUNGEON1'"),
    (
        "CAM_SET_FIXED1",
        "Fixed1",
        "Fixes camera in place, used in various places eg. entering Stock Pot Inn, hiting a switch, giving witch a red potion, shop browsing 'FIXED1'",
    ),
    (
        "CAM_SET_FIXED2",
        "Fixed2",
        "Used in Pinnacle Rock after defeating Sea Monsters, and by Tatl in Fortress 'FIXED2'",
    ),
    ("CAM_SET_MAZE", "Maze", "Unused. Set to use Camera_Parallel2(), which is only Camera_Noop() 'MAZE'"),
    (
        "CAM_SET_REMOTEBOMB",
        "Remotebomb",
        "Unused. Set to use Camera_Parallel2(), which is only Camera_Noop(). But also related to Play_ChangeCameraSetting? 'REMOTEBOMB'",
    ),
    ("CAM_SET_CIRCLE1", "Circle1", "Unknown 'CIRCLE1'"),
    (
        "CAM_SET_CIRCLE2",
        "Circle2",
        "Looking at far-away NPCs eg. Garo in Road to Ikana, Hungry Goron, Tingle 'CIRCLE2'",
    ),
    (
        "CAM_SET_CIRCLE3",
        "Circle3",
        "Used in curiosity shop, goron racetrack, final room in Sakon's hideout, other places 'CIRCLE3'",
    ),
    ("CAM_SET_CIRCLE4", "Circle4", "Used during the races on the doggy racetrack 'CIRCLE4'"),
    ("CAM_SET_FIXED3", "Fixed3", "Used in Stock Pot Inn Toilet and Tatl cutscene after woodfall 'FIXED3'"),
    (
        "CAM_SET_TOWER_ASCENT",
        "Tower_Ascent",
        "Various climbing structures (Snowhead climb to the temple entrance) 'TOWER0'",
    ),
    ("CAM_SET_PARALLEL0", "Parallel0", "Unknown 'PARALLEL0'"),
    ("CAM_SET_NORMALD", "Normald", "Unknown, set with camDataId = -20 'NORMALD'"),
    ("CAM_SET_SUBJECTD", "Subjectd", "Unknown, set with camDataId = -21 'SUBJECTD'"),
    (
        "CAM_SET_START0",
        "Start0",
        "Entering a room, either Dawn of a New Day reload, or entering a door where the camera is fixed on the other end 'START0'",
    ),
    (
        "CAM_SET_START2",
        "Start2",
        "Entering a scene, camera is put at a low angle eg. Grottos, Deku Palace, Stock Pot Inn 'START2'",
    ),
    ("CAM_SET_STOP0", "Stop0", "Called in z_play 'STOP0'"),
    ("CAM_SET_BOAT_CRUISE", "Boat_Cruise", " Koume's boat cruise 'JCRUISING'"),
    (
        "CAM_SET_VERTICAL_CLIMB",
        "Vertical_Climb",
        "Large vertical climbs, such as Mountain Village wall or Pirates Fortress ladder. 'CLIMBMAZE'",
    ),
    ("CAM_SET_SIDED", "Sided", "Unknown, set with camDataId = -24 'SIDED'"),
    ("CAM_SET_DUNGEON2", "Dungeon2", "Generic dungeon camera 2, used in various places 'DUNGEON2'"),
    ("CAM_SET_BOSS_ODOLWA", "Boss_Odolwa", "Odolwa's Lair, also used in GBT entrance: 'BOSS_SHIGE'"),
    ("CAM_SET_KEEPBACK", "Keepback", "Unknown. Possibly related to climbing something? 'KEEPBACK'"),
    ("CAM_SET_CIRCLE6", "Circle6", "Used in select regions from Ikana 'CIRCLE6'"),
    ("CAM_SET_CIRCLE7", "Circle7", "Unknown 'CIRCLE7'"),
    ("CAM_SET_MINI_BOSS", "Mini_Boss", "Used during the various minibosses of the 'CHUBOSS'"),
    ("CAM_SET_RFIXED1", "Rfixed1", "Talking to Koume stuck on the floor in woods of mystery 'RFIXED1'"),
    (
        "CAM_SET_TREASURE_CHEST_MINIGAME",
        "Treasure_Chest_Minigame",
        "Treasure Chest Shop in East Clock Town, minigame location 'TRESURE1'",
    ),
    ("CAM_SET_HONEY_AND_DARLING_1", "Honey_And_Darling_1", "Honey and Darling Minigames 'BOMBBASKET'"),
    (
        "CAM_SET_CIRCLE8",
        "Circle8",
        "Used by Stone Tower moving platforms, Falling eggs in Marine Lab, Bugs into soilpatch cutscene 'CIRCLE8'",
    ),
    (
        "CAM_SET_BIRDS_EYE_VIEW_1",
        "Birds_Eye_View_1",
        "Camera is a top-down view. Used in Fisherman's minigame and Deku Palace 'FUKAN1'",
    ),
    ("CAM_SET_DUNGEON3", "Dungeon3", "Generic dungeon camera 3, used in various places 'DUNGEON3'"),
    ("CAM_SET_TELESCOPE", "Telescope", "Observatory telescope and Curiosity Shop Peep-Hole 'TELESCOPE'"),
    ("CAM_SET_ROOM0", "Room0", "Certain rooms eg. inside the clock tower 'ROOM0'"),
    ("CAM_SET_RCIRC0", "Rcirc0", "Used by a few NPC cutscenes, focus close on the NPC 'RCIRC0'"),
    ("CAM_SET_CIRCLE9", "Circle9", "Used by Sakon Hideout entrance and Deku Palace Maze 'CIRCLE9'"),
    ("CAM_SET_ONTHEPOLE", "Onthepole", "Somewhere in Snowhead Temple and Woodfall Temple 'ONTHEPOLE'"),
    (
        "CAM_SET_INBUSH",
        "Inbush",
        "Various bush environments eg. grottos, Swamp Spider House, Termina Field grass bushes, Deku Palace near bean 'INBUSH'",
    ),
    ("CAM_SET_BOSS_MAJORA", "Boss_Majora", "Majora's Lair: 'BOSS_LAST'"),
    ("CAM_SET_BOSS_TWINMOLD", "Boss_Twinmold", "Twinmold's Lair: 'BOSS_INI'"),
    ("CAM_SET_BOSS_GOHT", "Boss_Goht", "Goht's Lair: 'BOSS_HAK'"),
    ("CAM_SET_BOSS_GYORG", "Boss_Gyorg", "Gyorg's Lair: 'BOSS_KON'"),
    ("CAM_SET_CONNECT0", "Connect0", "Smoothly and gradually return camera to Player after a cutscene 'CONNECT0'"),
    ("CAM_SET_PINNACLE_ROCK", "Pinnacle_Rock", "Pinnacle Rock pit 'MORAY'"),
    ("CAM_SET_NORMAL2", "Normal2", "Generic camera 2, used in various places 'NORMAL2'"),
    ("CAM_SET_HONEY_AND_DARLING_2", "Honey_And_Darling_2", "'BOMBBOWL'"),
    ("CAM_SET_CIRCLEA", "Circlea", "Unknown, Circle 10 'CIRCLEA'"),
    ("CAM_SET_WHIRLPOOL", "Whirlpool", "Great Bay Temple Central Room Whirlpool 'WHIRLPOOL'"),
    ("CAM_SET_CUCCO_SHACK", "Cucco_Shack", "'KOKKOGAME'"),
    ("CAM_SET_GIANT", "Giant", "Giants Mask in Twinmold's Lair 'GIANT'"),
    ("CAM_SET_SCENE0", "Scene0", "Entering doors to a new scene 'SCENE0'"),
    ("CAM_SET_ROOM1", "Room1", "Certain rooms eg. some rooms in Stock Pot Inn 'ROOM1'"),
    ("CAM_SET_WATER2", "Water2", "Swimming as Zora in Great Bay Temple 'WATER2'"),
    ("CAM_SET_WOODFALL_SWAMP", "Woodfall_Swamp", "Woodfall inside the swamp, but not on the platforms, 'SOKONASI'"),
    ("CAM_SET_FORCEKEEP", "Forcekeep", "Unknown 'FORCEKEEP'"),
    ("CAM_SET_PARALLEL1", "Parallel1", "Unknown 'PARALLEL1'"),
    ("CAM_SET_START1", "Start1", "Used when entering the lens cave 'START1'"),
    ("CAM_SET_ROOM2", "Room2", "Certain rooms eg. Deku King's Chamber, Ocean Spider House 'ROOM2'"),
    ("CAM_SET_NORMAL4", "Normal4", "Generic camera 4, used in Ikana Graveyard 'NORMAL4'"),
    ("CAM_SET_ELEGY_SHELL", "Elegy_Shell", "cutscene after playing elegy of emptyness and spawning a shell 'SHELL'"),
    ("CAM_SET_DUNGEON4", "Dungeon4", "Used in Pirates Fortress Interior, hidden room near hookshot 'DUNGEON4'"),
]

# order here sets order on the UI
oot_enum_cs_list_type = [
    # Col 1
    ("TextList", "Text List", "Textbox", "ALIGN_BOTTOM", 0),
    ("MiscList", "Misc List", "Misc", "OPTIONS", 7),
    ("RumbleList", "Rumble List", "Rumble Controller", "OUTLINER_OB_FORCE_FIELD", 8),
    # Col 2
    ("Transition", "Transition List", "Transition List", "COLORSET_10_VEC", 1),
    ("LightSettingsList", "Light Settings List", "Lighting", "LIGHT_SUN", 2),
    ("TimeList", "Time List", "Time", "TIME", 3),
    # Col 3
    ("StartSeqList", "Start Seq List", "Play BGM", "PLAY", 4),
    ("StopSeqList", "Stop Seq List", "Stop BGM", "SNAP_FACE", 5),
    ("FadeOutSeqList", "Fade-Out Seq List", "Fade BGM", "IPO_EASE_IN_OUT", 6),
]

mm_enum_cs_list_type = [
    # Col 1
    ("TextList", "Text List", "Textbox", "ALIGN_BOTTOM", 0),
    ("MiscList", "Misc List", "Misc", "OPTIONS", 7),
    ("RumbleList", "Rumble List", "Rumble Controller", "OUTLINER_OB_FORCE_FIELD", 8),
    ("MotionBlurList", "Motion Blur List", "Motion Blur", "ONIONSKIN_ON", 9),
    ("CreditsSceneList", "Choose Credits Scene List", "Choose Credits Scene", "WORLD", 11),
    # Col 2
    ("Transition", "Transition", "Transition", "COLORSET_10_VEC", 1),
    ("LightSettingsList", "Light Settings List", "Lighting", "LIGHT_SUN", 2),
    ("TimeList", "Time List", "Time", "TIME", 3),
    ("TransitionGeneralList", "Transition General List", "Transition General", "COLORSET_06_VEC", 12),
    ("ModifySeqList", "Modify Seq List", "Modify Seq", "IPO_CONSTANT", 10),
    # Col 3
    ("StartSeqList", "Start Seq List", "Play BGM", "PLAY", 4),
    ("StopSeqList", "Stop Seq List", "Stop BGM", "SNAP_FACE", 5),
    ("FadeOutSeqList", "Fade-Out Seq List", "Fade BGM", "IPO_EASE_IN_OUT", 6),
    ("StartAmbienceList", "Start Ambience List", "Start Ambience", "SNAP_FACE", 13),
    ("FadeOutAmbienceList", "Fade-Out Ambience List", "Fade-Out Ambience", "IPO_EASE_IN_OUT", 14),
]

# Adding new rest pose entry:
# 1. Import a generic skeleton
# 2. Pose into a usable rest pose
# 3. Select skeleton, then run bpy.ops.object.oot_save_rest_pose()
# 4. Copy array data from console into an OOTSkeletonImportInfo object
#       - list of tuples, first is root position, rest are euler XYZ rotations
# 5. Add object to oot_skeleton_dict/mm_skeleton_dict

link_skeleton_names = {
    "gLinkAdultSkel",
    "gLinkChildSkel",
    "gLinkHumanSkel",
    "gLinkDekuSkel",
    "gLinkGoronSkel",
    "gLinkZoraSkel",
    "gLinkFierceDeitySkel",
}


# Link overlay will be "", since Link texture array data is handled as a special case.
class OOTSkeletonImportInfo:
    def __init__(
        self,
        skeletonName: str,
        folderName: str,
        actorOverlayName: str,
        flipbookArrayIndex2D: int | None,
        restPoseData: list[tuple[float, float, float]] | None,
    ):
        self.skeletonName = skeletonName
        self.folderName = folderName
        self.actorOverlayName = actorOverlayName  # Note that overlayName = None will disable texture array reading.
        self.flipbookArrayIndex2D = flipbookArrayIndex2D
        self.isLink = skeletonName in link_skeleton_names
        self.restPoseData = restPoseData


oot_skeleton_dict = OrderedDict(
    {
        "Adult Link": OOTSkeletonImportInfo(
            "gLinkAdultSkel",
            "object_link_boy",
            "",
            0,
            [
                (0.0, 3.6050000190734863, 0.0),
                (0.0, -0.0, 0.0),
                (-1.5708922147750854, -0.0, -1.5707963705062866),
                (0.0, -0.0, 0.0),
                (0.0, 0.05235987901687622, 0.0),
                (0.0, -0.0, 0.0),
                (0.0, 0.0, -1.5707964897155762),
                (0.0, -0.05235987901687622, 0.0),
                (0.0, -0.0, 0.0),
                (0.0, 0.0, -1.5707964897155762),
                (1.5707963705062866, -0.0, 1.5707963705062866),
                (-4.740638548383913e-09, -5.356494803265832e-09, 1.4546878337860107),
                (-4.114889869409654e-15, -1.1733899984468776e-14, 1.9080803394317627),
                (0.0, -0.0, 0.0),
                (1.0222795112391236e-15, -0.6981316804885864, -3.141592502593994),
                (0.0, -0.0, 0.0),
                (0.0, 0.0, -1.5707964897155762),
                (-1.0222795112391236e-15, 0.6981316804885864, -3.141592502593994),
                (0.0, -0.0, 0.0),
                (0.0, 0.0, -1.5707964897155762),
                (-1.5707963705062866, 2.611602306365967, -0.08726644515991211),
                (0.0, -0.0, 0.0),
            ],
        ),
        "Child Link": OOTSkeletonImportInfo(
            "gLinkChildSkel",
            "object_link_child",
            "",
            1,
            [
                (0.0, 2.3559017181396484, 0.0),
                (0.0, -0.0, 0.0),
                (-1.5708922147750854, -0.0, -1.5707963705062866),
                (0.0, -0.0, 0.0),
                (0.0, 0.05235987901687622, 0.0),
                (0.0, -0.0, 0.0),
                (0.0, 0.0, -1.5707964897155762),
                (0.0, -0.05235987901687622, 0.0),
                (0.0, -0.0, 0.0),
                (0.0, 0.0, -1.5707964897155762),
                (1.5707963705062866, -0.0, 1.5707963705062866),
                (-4.740638548383913e-09, -5.356494803265832e-09, 1.4546878337860107),
                (-4.114889869409654e-15, -1.1733899984468776e-14, 1.9080803394317627),
                (0.0, -0.0, 0.0),
                (1.0222795112391236e-15, -0.6981316804885864, -3.141592502593994),
                (0.0, -0.0, 0.0),
                (0.0, 0.0, -1.5707964897155762),
                (-1.0222795112391236e-15, 0.6981316804885864, -3.141592502593994),
                (0.0, -0.0, 0.0),
                (0.0, 0.0, -1.5707964897155762),
                (-1.5707963705062866, 2.611602306365967, -0.08726644515991211),
                (0.0, -0.0, 0.0),
            ],
        ),
    }
)
oot_enum_skeleton_mode = [
    ("Generic", "Generic", "Generic"),
]
for name, info in oot_skeleton_dict.items():
    oot_enum_skeleton_mode.append((name, name, name))

mm_skeleton_dict = OrderedDict(
    {
        "Human Link": OOTSkeletonImportInfo(
            "gLinkHumanSkel",
            "object_link_child",
            "",
            4,
            [
                (0.0, 2.3559017181396484, 0.0),
                (0.0, -0.0, 0.0),
                (-1.5708922147750854, -0.0, -1.5707963705062866),
                (0.0, -0.0, 0.0),
                (0.0, 0.05235987901687622, 0.0),
                (0.0, -0.0, 0.0),
                (0.0, 0.0, -1.5707964897155762),
                (0.0, -0.05235987901687622, 0.0),
                (0.0, -0.0, 0.0),
                (0.0, 0.0, -1.5707964897155762),
                (1.5707963705062866, -0.0, 1.5707963705062866),
                (-4.740638548383913e-09, -5.356494803265832e-09, 1.4546878337860107),
                (-4.114889869409654e-15, -1.1733899984468776e-14, 1.9080803394317627),
                (0.0, -0.0, 0.0),
                (1.0222795112391236e-15, -0.6981316804885864, -3.141592502593994),
                (0.0, -0.0, 0.0),
                (0.0, 0.0, -1.5707964897155762),
                (-1.0222795112391236e-15, 0.6981316804885864, -3.141592502593994),
                (0.0, -0.0, 0.0),
                (0.0, 0.0, -1.5707964897155762),
                (-1.5707963705062866, 2.611602306365967, -0.08726644515991211),
                (0.0, -0.0, 0.0),
            ],
        ),
        "Deku Link": OOTSkeletonImportInfo(
            "gLinkDekuSkel",
            "object_link_nuts",
            None,
            3,
            [
                (0.0, 2.3559017181396484, 0.0),
                (0.0, -0.0, 0.0),
                (-1.5708922147750854, -0.0, -1.5707963705062866),
                (0.0, -0.0, 0.0),
                (0.0, 0.05235987901687622, 0.0),
                (0.0, -0.0, 0.0),
                (0.0, 0.0, -1.5707964897155762),
                (0.0, -0.05235987901687622, 0.0),
                (0.0, -0.0, 0.0),
                (0.0, 0.0, -1.5707964897155762),
                (1.5707963705062866, -0.0, 1.5707963705062866),
                (-4.740638548383913e-09, -5.356494803265832e-09, 1.4546878337860107),
                (-4.114889869409654e-15, -1.1733899984468776e-14, 1.9080803394317627),
                (0.0, -0.0, 0.0),
                (1.0222795112391236e-15, -0.6981316804885864, -3.141592502593994),
                (0.0, -0.0, 0.0),
                (0.0, 0.0, -1.5707964897155762),
                (-1.0222795112391236e-15, 0.6981316804885864, -3.141592502593994),
                (0.0, -0.0, 0.0),
                (0.0, 0.0, -1.5707964897155762),
                (-1.5707963705062866, 2.611602306365967, -0.08726644515991211),
                (0.0, -0.0, 0.0),
            ],
        ),
        "Goron Link": OOTSkeletonImportInfo(
            "gLinkGoronSkel",
            "object_link_goron",
            "",
            1,
            [
                (0.0, 2.3559017181396484, 0.0),
                (0.0, -0.0, 0.0),
                (-1.5708922147750854, -0.0, -1.5707963705062866),
                (0.0, -0.0, 0.0),
                (0.0, 0.05235987901687622, 0.0),
                (0.0, -0.0, 0.0),
                (0.0, 0.0, -1.5707964897155762),
                (0.0, -0.05235987901687622, 0.0),
                (0.0, -0.0, 0.0),
                (0.0, 0.0, -1.5707964897155762),
                (1.5707963705062866, -0.0, 1.5707963705062866),
                (-4.740638548383913e-09, -5.356494803265832e-09, 1.4546878337860107),
                (-4.114889869409654e-15, -1.1733899984468776e-14, 1.9080803394317627),
                (0.0, -0.0, 0.0),
                (1.0222795112391236e-15, -0.6981316804885864, -3.141592502593994),
                (0.0, -0.0, 0.0),
                (0.0, 0.0, -1.5707964897155762),
                (-1.0222795112391236e-15, 0.6981316804885864, -3.141592502593994),
                (0.0, -0.0, 0.0),
                (0.0, 0.0, -1.5707964897155762),
                (-1.5707963705062866, 2.611602306365967, -0.08726644515991211),
                (0.0, -0.0, 0.0),
            ],
        ),
        "Zora Link": OOTSkeletonImportInfo(
            "gLinkZoraSkel",
            "object_link_zora",
            "",
            2,
            [
                (0.0, 2.3559017181396484, 0.0),
                (0.0, -0.0, 0.0),
                (-1.5708922147750854, -0.0, -1.5707963705062866),
                (0.0, -0.0, 0.0),
                (0.0, 0.05235987901687622, 0.0),
                (0.0, -0.0, 0.0),
                (0.0, 0.0, -1.5707964897155762),
                (0.0, -0.05235987901687622, 0.0),
                (0.0, -0.0, 0.0),
                (0.0, 0.0, -1.5707964897155762),
                (1.5707963705062866, -0.0, 1.5707963705062866),
                (-4.740638548383913e-09, -5.356494803265832e-09, 1.4546878337860107),
                (-4.114889869409654e-15, -1.1733899984468776e-14, 1.9080803394317627),
                (0.0, -0.0, 0.0),
                (1.0222795112391236e-15, -0.6981316804885864, -3.141592502593994),
                (0.0, -0.0, 0.0),
                (0.0, 0.0, -1.5707964897155762),
                (-1.0222795112391236e-15, 0.6981316804885864, -3.141592502593994),
                (0.0, -0.0, 0.0),
                (0.0, 0.0, -1.5707964897155762),
                (-1.5707963705062866, 2.611602306365967, -0.08726644515991211),
                (0.0, -0.0, 0.0),
            ],
        ),
        "Fierce Deity Link": OOTSkeletonImportInfo(
            "gLinkFierceDeitySkel",
            "object_link_boy",
            None,
            0,
            [
                (0.0, 3.6050000190734863, 0.0),
                (0.0, -0.0, 0.0),
                (-1.5708922147750854, -0.0, -1.5707963705062866),
                (0.0, -0.0, 0.0),
                (0.0, 0.05235987901687622, 0.0),
                (0.0, -0.0, 0.0),
                (0.0, 0.0, -1.5707964897155762),
                (0.0, -0.05235987901687622, 0.0),
                (0.0, -0.0, 0.0),
                (0.0, 0.0, -1.5707964897155762),
                (1.5707963705062866, -0.0, 1.5707963705062866),
                (-4.740638548383913e-09, -5.356494803265832e-09, 1.4546878337860107),
                (-4.114889869409654e-15, -1.1733899984468776e-14, 1.9080803394317627),
                (0.0, -0.0, 0.0),
                (1.0222795112391236e-15, -0.6981316804885864, -3.141592502593994),
                (0.0, -0.0, 0.0),
                (0.0, 0.0, -1.5707964897155762),
                (-1.0222795112391236e-15, 0.6981316804885864, -3.141592502593994),
                (0.0, -0.0, 0.0),
                (0.0, 0.0, -1.5707964897155762),
                (-1.5707963705062866, 2.611602306365967, -0.08726644515991211),
                (0.0, -0.0, 0.0),
            ],
        ),
    }
)
mm_enum_skeleton_mode = [
    ("Generic", "Generic", "Generic"),
]
for name, info in mm_skeleton_dict.items():
    mm_enum_skeleton_mode.append((name, name, name))

# ---


@dataclass
class Z64_Data:
    """Contains data related to OoT/MM, like actors or objects"""

    def __init__(self, game: str):
        self.game = game
        self.is_registering = True
        self.update(None, game, True)  # forcing the update as we're in the init function

        self.enum_floor_effect = enum_floor_effect

    def is_oot(self):
        self.update(bpy.context, None)
        return self.game == "OOT"

    def is_mm(self):
        self.update(bpy.context, None)
        return self.game == "MM"

    def update(self, context: Optional[Context], game: Optional[str], force: bool = False):
        if context is not None and self.is_registering:
            self.is_registering = False

        if not force and self.is_registering:
            next_game = "OOT"
        elif game is not None:
            next_game = game
        elif context is not None:
            next_game = context.scene.gameEditorMode
        else:
            raise ValueError("ERROR: invalid values for context and game")

        # don't update if the game is the same (or we don't want to force one)
        if not force and next_game == self.game:
            return

        self.cs_list_type_to_cmd = {
            "TextList": "CS_TEXT_LIST",
            "LightSettingsList": "CS_LIGHT_SETTING_LIST",
            "TimeList": "CS_TIME_LIST",
            "StartSeqList": "CS_START_SEQ_LIST",
            "StopSeqList": "CS_STOP_SEQ_LIST",
            "FadeOutSeqList": "CS_FADE_OUT_SEQ_LIST",
            "MiscList": "CS_MISC_LIST",
            "DestinationList": "CS_DESTINATION_LIST",
            "MotionBlurList": "CS_MOTION_BLUR_LIST",
            "ModifySeqList": "CS_MODIFY_SEQ_LIST",
            "CreditsSceneList": "CS_CHOOSE_CREDITS_SCENES_LIST",
            "TransitionGeneralList": "CS_TRANSITION_GENERAL_LIST",
            "GiveTatlList": "CS_GIVE_TATL_LIST",
        }

        self.game = next_game
        self.enums = Z64_EnumData(self.game)
        self.objects = Z64_ObjectData(self.game)
        self.actors = Z64_ActorData(self.game)

        if self.game == "OOT":
            self.cs_index_start = 4
            self.cs_list_type_to_cmd["Transition"] = "CS_TRANSITION"
            self.cs_list_type_to_cmd["RumbleList"] = "CS_RUMBLE_CONTROLLER_LIST"
            self.enum_nature_id = oot_enum_nature_id
            self.enum_skybox = oot_enum_skybox
            self.enum_skybox_config = oot_enum_skybox_config
            self.enum_environment_type = oot_enum_environment_type
            self.enum_room_type = oot_enum_room_type
            self.enum_floor_property = oot_enum_floor_property
            self.enum_floor_type = oot_enum_floor_type
            self.enum_camera_setting_type = oot_enum_camera_setting_type
            self.enum_cs_list_type = oot_enum_cs_list_type
            self.skeleton_dict = oot_skeleton_dict
            self.enum_skeleton_mode = oot_enum_skeleton_mode
        elif self.game == "MM":
            self.cs_index_start = 1
            self.cs_list_type_to_cmd["Transition"] = "CS_TRANSITION_LIST"
            self.cs_list_type_to_cmd["RumbleList"] = "CS_RUMBLE_LIST"
            self.enum_nature_id = enum_ambiance_id
            self.enum_skybox = mm_enum_skybox
            self.enum_skybox_config = mm_enum_skybox_config
            self.enum_environment_type = mm_enum_environment_type
            self.enum_room_type = mm_enum_room_type
            self.enum_floor_property = mm_enum_floor_property
            self.enum_floor_type = mm_enum_floor_type
            self.enum_camera_setting_type = mm_enum_camera_setting_type
            self.enum_cs_list_type = mm_enum_cs_list_type
            self.skeleton_dict = mm_skeleton_dict
            self.enum_skeleton_mode = mm_enum_skeleton_mode
        else:
            raise ValueError(f"ERROR: unsupported game {repr(self.game)}")

        self.enum_map: dict[str, list[tuple[str, str, str]]] = {
            "globalObject": self.enums.enum_global_object,
            "musicSeq": self.enums.enum_seq_id,
            "drawConfig": self.enums.enum_draw_config,
            "sound": self.enums.enum_surface_material,
            "csDestination": self.enums.enum_cs_destination,
            "seqId": self.enums.enum_seq_id,
            "playerCueID": self.enums.enum_cs_player_cue_id,
            "ocarinaAction": self.enums.enum_ocarina_song_action_id,
            "csTextType": self.enums.enum_cs_text_type,
            "csSeqPlayer": self.enums.enum_cs_fade_out_seq_player,
            "csMiscType": self.enums.enum_cs_misc_type,
            "transitionType": self.enums.enum_cs_transition_type,
            "actor_cue_list_cmd_type": self.enums.enum_cs_actor_cue_list_cmd_type,
            "spline_interp_type": self.enums.enum_cs_spline_interp_type,
            "spline_rel_to": self.enums.enum_cs_spline_rel,
            "trans_general": self.enums.enum_cs_transition_general,
            "blur_type": self.enums.enum_cs_motion_blur_type,
            "credits_scene_type": self.enums.enum_cs_credits_scene_type,
            "mod_seq_type": self.enums.enum_cs_modify_seq_type,
            "objectKey": self.objects.ootEnumObjectKey,
            "actor_id": self.actors.ootEnumActorID,
            "chest_content": self.actors.ootEnumChestContent,
            "navi_msg_id": self.actors.ootEnumNaviMessageData,
            "collectibles": self.actors.ootEnumCollectibleItems,
            "skybox": self.enum_skybox,
            "skybox_config": self.enum_skybox_config,
            "nature_id": self.enum_nature_id,
            "room_type": self.enum_room_type,
            "environment_type": self.enum_environment_type,
            "floor_property": self.enum_floor_property,
            "floor_type": self.enum_floor_type,
            "camera_setting_type": self.enum_camera_setting_type,
            "cs_list_type": self.enum_cs_list_type,
            "skeleton_mode": self.enum_skeleton_mode,
        }

    def get_enum(self, prop_name: str):
        self.update(bpy.context, None)
        return self.enum_map[prop_name]
