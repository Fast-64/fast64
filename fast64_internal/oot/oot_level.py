import math, os, bpy, bmesh, mathutils
from bpy.utils import register_class, unregister_class
from io import BytesIO

from .oot_constants import *
from .oot_utility import *
from .oot_lights import *
#from .oot_function_map import func_map
#from .oot_spline import *

from ..utility import *

ootEnumActorID = [
	("Custom", "Custom", "Custom"),
	("ACTOR_PLAYER", "PLAYER", "PLAYER"),
    ("ACTOR_EN_TEST", "EN_TEST", "EN_TEST"),
    ("ACTOR_EN_GIRLA", "EN_GIRLA", "EN_GIRLA"),
    ("ACTOR_EN_PART", "EN_PART", "EN_PART"),
    ("ACTOR_EN_LIGHT", "EN_LIGHT", "EN_LIGHT"),
    ("ACTOR_EN_DOOR", "EN_DOOR", "EN_DOOR"),
    ("ACTOR_EN_BOX", "EN_BOX", "EN_BOX"),
    ("ACTOR_BG_DY_YOSEIZO", "BG_DY_YOSEIZO", "BG_DY_YOSEIZO"),
    ("ACTOR_BG_HIDAN_FIREWALL", "BG_HIDAN_FIREWALL", "BG_HIDAN_FIREWALL"),
    ("ACTOR_EN_POH", "EN_POH", "EN_POH"),
    ("ACTOR_EN_OKUTA", "EN_OKUTA", "EN_OKUTA"),
    ("ACTOR_BG_YDAN_SP", "BG_YDAN_SP", "BG_YDAN_SP"),
    ("ACTOR_EN_BOM", "EN_BOM", "EN_BOM"),
    ("ACTOR_EN_WALLMAS", "EN_WALLMAS", "EN_WALLMAS"),
    ("ACTOR_EN_DODONGO", "EN_DODONGO", "EN_DODONGO"),
    ("ACTOR_EN_FIREFLY", "EN_FIREFLY", "EN_FIREFLY"),
    ("ACTOR_EN_HORSE", "EN_HORSE", "EN_HORSE"),
    ("ACTOR_EN_ITEM00", "EN_ITEM00", "EN_ITEM00"),
    ("ACTOR_EN_ARROW", "EN_ARROW", "EN_ARROW"),
    ("ACTOR_EN_ELF", "EN_ELF", "EN_ELF"),
    ("ACTOR_EN_NIW", "EN_NIW", "EN_NIW"),
    ("ACTOR_EN_TITE", "EN_TITE", "EN_TITE"),
    ("ACTOR_EN_REEBA", "EN_REEBA", "EN_REEBA"),
    ("ACTOR_EN_PEEHAT", "EN_PEEHAT", "EN_PEEHAT"),
    ("ACTOR_EN_BUTTE", "EN_BUTTE", "EN_BUTTE"),
    ("ACTOR_EN_INSECT", "EN_INSECT", "EN_INSECT"),
    ("ACTOR_EN_FISH", "EN_FISH", "EN_FISH"),
    ("ACTOR_EN_HOLL", "EN_HOLL", "EN_HOLL"),
    ("ACTOR_EN_SCENE_CHANGE", "EN_SCENE_CHANGE", "EN_SCENE_CHANGE"),
    ("ACTOR_EN_ZF", "EN_ZF", "EN_ZF"),
    ("ACTOR_EN_HATA", "EN_HATA", "EN_HATA"),
    ("ACTOR_BOSS_DODONGO", "BOSS_DODONGO", "BOSS_DODONGO"),
    ("ACTOR_BOSS_GOMA", "BOSS_GOMA", "BOSS_GOMA"),
    ("ACTOR_EN_ZL1", "EN_ZL1", "EN_ZL1"),
    ("ACTOR_EN_VIEWER", "EN_VIEWER", "EN_VIEWER"),
    ("ACTOR_EN_GOMA", "EN_GOMA", "EN_GOMA"),
    ("ACTOR_BG_PUSHBOX", "BG_PUSHBOX", "BG_PUSHBOX"),
    ("ACTOR_EN_BUBBLE", "EN_BUBBLE", "EN_BUBBLE"),
    ("ACTOR_DOOR_SHUTTER", "DOOR_SHUTTER", "DOOR_SHUTTER"),
    ("ACTOR_EN_DODOJR", "EN_DODOJR", "EN_DODOJR"),
    ("ACTOR_EN_BDFIRE", "EN_BDFIRE", "EN_BDFIRE"),
    ("ACTOR_EN_BOOM", "EN_BOOM", "EN_BOOM"),
    ("ACTOR_EN_TORCH2", "EN_TORCH2", "EN_TORCH2"),
    ("ACTOR_EN_BILI", "EN_BILI", "EN_BILI"),
    ("ACTOR_EN_TP", "EN_TP", "EN_TP"),
    ("ACTOR_EN_ST", "EN_ST", "EN_ST"),
    ("ACTOR_EN_BW", "EN_BW", "EN_BW"),
    ("ACTOR_EN_A_OBJ", "EN_A_OBJ", "EN_A_OBJ"),
    ("ACTOR_EN_EIYER", "EN_EIYER", "EN_EIYER"),
    ("ACTOR_EN_RIVER_SOUND", "EN_RIVER_SOUND", "EN_RIVER_SOUND"),
    ("ACTOR_EN_HORSE_NORMAL", "EN_HORSE_NORMAL", "EN_HORSE_NORMAL"),
    ("ACTOR_EN_OSSAN", "EN_OSSAN", "EN_OSSAN"),
    ("ACTOR_BG_TREEMOUTH", "BG_TREEMOUTH", "BG_TREEMOUTH"),
    ("ACTOR_BG_DODOAGO", "BG_DODOAGO", "BG_DODOAGO"),
    ("ACTOR_BG_HIDAN_DALM", "BG_HIDAN_DALM", "BG_HIDAN_DALM"),
    ("ACTOR_BG_HIDAN_HROCK", "BG_HIDAN_HROCK", "BG_HIDAN_HROCK"),
    ("ACTOR_EN_HORSE_GANON", "EN_HORSE_GANON", "EN_HORSE_GANON"),
    ("ACTOR_BG_HIDAN_ROCK", "BG_HIDAN_ROCK", "BG_HIDAN_ROCK"),
    ("ACTOR_BG_HIDAN_RSEKIZOU", "BG_HIDAN_RSEKIZOU", "BG_HIDAN_RSEKIZOU"),
    ("ACTOR_BG_HIDAN_SEKIZOU", "BG_HIDAN_SEKIZOU", "BG_HIDAN_SEKIZOU"),
    ("ACTOR_BG_HIDAN_SIMA", "BG_HIDAN_SIMA", "BG_HIDAN_SIMA"),
    ("ACTOR_BG_HIDAN_SYOKU", "BG_HIDAN_SYOKU", "BG_HIDAN_SYOKU"),
    ("ACTOR_EN_XC", "EN_XC", "EN_XC"),
    ("ACTOR_BG_HIDAN_CURTAIN", "BG_HIDAN_CURTAIN", "BG_HIDAN_CURTAIN"),
    ("ACTOR_BG_SPOT00_HANEBASI", "BG_SPOT00_HANEBASI", "BG_SPOT00_HANEBASI"),
    ("ACTOR_EN_MB", "EN_MB", "EN_MB"),
    ("ACTOR_EN_BOMBF", "EN_BOMBF", "EN_BOMBF"),
    ("ACTOR_EN_ZL2", "EN_ZL2", "EN_ZL2"),
    ("ACTOR_BG_HIDAN_FSLIFT", "BG_HIDAN_FSLIFT", "BG_HIDAN_FSLIFT"),
    ("ACTOR_EN_OE2", "EN_OE2", "EN_OE2"),
    ("ACTOR_BG_YDAN_HASI", "BG_YDAN_HASI", "BG_YDAN_HASI"),
    ("ACTOR_BG_YDAN_MARUTA", "BG_YDAN_MARUTA", "BG_YDAN_MARUTA"),
    ("ACTOR_BOSS_GANONDROF", "BOSS_GANONDROF", "BOSS_GANONDROF"),
    ("ACTOR_EN_AM", "EN_AM", "EN_AM"),
    ("ACTOR_EN_DEKUBABA", "EN_DEKUBABA", "EN_DEKUBABA"),
    ("ACTOR_EN_M_FIRE1", "EN_M_FIRE1", "EN_M_FIRE1"),
    ("ACTOR_EN_M_THUNDER", "EN_M_THUNDER", "EN_M_THUNDER"),
    ("ACTOR_BG_DDAN_JD", "BG_DDAN_JD", "BG_DDAN_JD"),
    ("ACTOR_BG_BREAKWALL", "BG_BREAKWALL", "BG_BREAKWALL"),
    ("ACTOR_EN_JJ", "EN_JJ", "EN_JJ"),
    ("ACTOR_EN_HORSE_ZELDA", "EN_HORSE_ZELDA", "EN_HORSE_ZELDA"),
    ("ACTOR_BG_DDAN_KD", "BG_DDAN_KD", "BG_DDAN_KD"),
    ("ACTOR_DOOR_WARP1", "DOOR_WARP1", "DOOR_WARP1"),
    ("ACTOR_OBJ_SYOKUDAI", "OBJ_SYOKUDAI", "OBJ_SYOKUDAI"),
    ("ACTOR_ITEM_B_HEART", "ITEM_B_HEART", "ITEM_B_HEART"),
    ("ACTOR_EN_DEKUNUTS", "EN_DEKUNUTS", "EN_DEKUNUTS"),
    ("ACTOR_BG_MENKURI_KAITEN", "BG_MENKURI_KAITEN", "BG_MENKURI_KAITEN"),
    ("ACTOR_BG_MENKURI_EYE", "BG_MENKURI_EYE", "BG_MENKURI_EYE"),
    ("ACTOR_EN_VALI", "EN_VALI", "EN_VALI"),
    ("ACTOR_BG_MIZU_MOVEBG", "BG_MIZU_MOVEBG", "BG_MIZU_MOVEBG"),
    ("ACTOR_BG_MIZU_WATER", "BG_MIZU_WATER", "BG_MIZU_WATER"),
    ("ACTOR_ARMS_HOOK", "ARMS_HOOK", "ARMS_HOOK"),
    ("ACTOR_EN_FHG", "EN_FHG", "EN_FHG"),
    ("ACTOR_BG_MORI_HINERI", "BG_MORI_HINERI", "BG_MORI_HINERI"),
    ("ACTOR_EN_BB", "EN_BB", "EN_BB"),
    ("ACTOR_BG_TOKI_HIKARI", "BG_TOKI_HIKARI", "BG_TOKI_HIKARI"),
    ("ACTOR_EN_YUKABYUN", "EN_YUKABYUN", "EN_YUKABYUN"),
    ("ACTOR_BG_TOKI_SWD", "BG_TOKI_SWD", "BG_TOKI_SWD"),
    ("ACTOR_EN_FHG_FIRE", "EN_FHG_FIRE", "EN_FHG_FIRE"),
    ("ACTOR_BG_MJIN", "BG_MJIN", "BG_MJIN"),
    ("ACTOR_BG_HIDAN_KOUSI", "BG_HIDAN_KOUSI", "BG_HIDAN_KOUSI"),
    ("ACTOR_DOOR_TOKI", "DOOR_TOKI", "DOOR_TOKI"),
    ("ACTOR_BG_HIDAN_HAMSTEP", "BG_HIDAN_HAMSTEP", "BG_HIDAN_HAMSTEP"),
    ("ACTOR_EN_BIRD", "EN_BIRD", "EN_BIRD"),
    ("ACTOR_EN_WOOD02", "EN_WOOD02", "EN_WOOD02"),
    ("ACTOR_EN_LIGHTBOX", "EN_LIGHTBOX", "EN_LIGHTBOX"),
    ("ACTOR_EN_PU_BOX", "EN_PU_BOX", "EN_PU_BOX"),
    ("ACTOR_EN_TRAP", "EN_TRAP", "EN_TRAP"),
    ("ACTOR_EN_AROW_TRAP", "EN_AROW_TRAP", "EN_AROW_TRAP"),
    ("ACTOR_EN_VASE", "EN_VASE", "EN_VASE"),
    ("ACTOR_EN_TA", "EN_TA", "EN_TA"),
    ("ACTOR_EN_TK", "EN_TK", "EN_TK"),
    ("ACTOR_BG_MORI_BIGST", "BG_MORI_BIGST", "BG_MORI_BIGST"),
    ("ACTOR_BG_MORI_ELEVATOR", "BG_MORI_ELEVATOR", "BG_MORI_ELEVATOR"),
    ("ACTOR_BG_MORI_KAITENKABE", "BG_MORI_KAITENKABE", "BG_MORI_KAITENKABE"),
    ("ACTOR_BG_MORI_RAKKATENJO", "BG_MORI_RAKKATENJO", "BG_MORI_RAKKATENJO"),
    ("ACTOR_EN_VM", "EN_VM", "EN_VM"),
    ("ACTOR_DEMO_EFFECT", "DEMO_EFFECT", "DEMO_EFFECT"),
    ("ACTOR_DEMO_KANKYO", "DEMO_KANKYO", "DEMO_KANKYO"),
    ("ACTOR_BG_HIDAN_FWBIG", "BG_HIDAN_FWBIG", "BG_HIDAN_FWBIG"),
    ("ACTOR_EN_FLOORMAS", "EN_FLOORMAS", "EN_FLOORMAS"),
    ("ACTOR_EN_HEISHI1", "EN_HEISHI1", "EN_HEISHI1"),
    ("ACTOR_EN_RD", "EN_RD", "EN_RD"),
    ("ACTOR_EN_PO_SISTERS", "EN_PO_SISTERS", "EN_PO_SISTERS"),
    ("ACTOR_BG_HEAVY_BLOCK", "BG_HEAVY_BLOCK", "BG_HEAVY_BLOCK"),
    ("ACTOR_BG_PO_EVENT", "BG_PO_EVENT", "BG_PO_EVENT"),
    ("ACTOR_OBJ_MURE", "OBJ_MURE", "OBJ_MURE"),
    ("ACTOR_EN_SW", "EN_SW", "EN_SW"),
    ("ACTOR_BOSS_FD", "BOSS_FD", "BOSS_FD"),
    ("ACTOR_OBJECT_KANKYO", "OBJECT_KANKYO", "OBJECT_KANKYO"),
    ("ACTOR_EN_DU", "EN_DU", "EN_DU"),
    ("ACTOR_EN_FD", "EN_FD", "EN_FD"),
    ("ACTOR_EN_HORSE_LINK_CHILD", "EN_HORSE_LINK_CHILD", "EN_HORSE_LINK_CHILD"),
    ("ACTOR_DOOR_ANA", "DOOR_ANA", "DOOR_ANA"),
    ("ACTOR_BG_SPOT02_OBJECTS", "BG_SPOT02_OBJECTS", "BG_SPOT02_OBJECTS"),
    ("ACTOR_BG_HAKA", "BG_HAKA", "BG_HAKA"),
    ("ACTOR_MAGIC_WIND", "MAGIC_WIND", "MAGIC_WIND"),
    ("ACTOR_MAGIC_FIRE", "MAGIC_FIRE", "MAGIC_FIRE"),
    ("ACTOR_EN_RU1", "EN_RU1", "EN_RU1"),
    ("ACTOR_BOSS_FD2", "BOSS_FD2", "BOSS_FD2"),
    ("ACTOR_EN_FD_FIRE", "EN_FD_FIRE", "EN_FD_FIRE"),
    ("ACTOR_EN_DH", "EN_DH", "EN_DH"),
    ("ACTOR_EN_DHA", "EN_DHA", "EN_DHA"),
    ("ACTOR_EN_RL", "EN_RL", "EN_RL"),
    ("ACTOR_EN_ENCOUNT1", "EN_ENCOUNT1", "EN_ENCOUNT1"),
    ("ACTOR_DEMO_DU", "DEMO_DU", "DEMO_DU"),
    ("ACTOR_DEMO_IM", "DEMO_IM", "DEMO_IM"),
    ("ACTOR_DEMO_TRE_LGT", "DEMO_TRE_LGT", "DEMO_TRE_LGT"),
    ("ACTOR_EN_FW", "EN_FW", "EN_FW"),
    ("ACTOR_BG_VB_SIMA", "BG_VB_SIMA", "BG_VB_SIMA"),
    ("ACTOR_EN_VB_BALL", "EN_VB_BALL", "EN_VB_BALL"),
    ("ACTOR_BG_HAKA_MEGANE", "BG_HAKA_MEGANE", "BG_HAKA_MEGANE"),
    ("ACTOR_BG_HAKA_MEGANEBG", "BG_HAKA_MEGANEBG", "BG_HAKA_MEGANEBG"),
    ("ACTOR_BG_HAKA_SHIP", "BG_HAKA_SHIP", "BG_HAKA_SHIP"),
    ("ACTOR_BG_HAKA_SGAMI", "BG_HAKA_SGAMI", "BG_HAKA_SGAMI"),
    ("ACTOR_EN_HEISHI2", "EN_HEISHI2", "EN_HEISHI2"),
    ("ACTOR_EN_ENCOUNT2", "EN_ENCOUNT2", "EN_ENCOUNT2"),
    ("ACTOR_EN_FIRE_ROCK", "EN_FIRE_ROCK", "EN_FIRE_ROCK"),
    ("ACTOR_EN_BROB", "EN_BROB", "EN_BROB"),
    ("ACTOR_MIR_RAY", "MIR_RAY", "MIR_RAY"),
    ("ACTOR_BG_SPOT09_OBJ", "BG_SPOT09_OBJ", "BG_SPOT09_OBJ"),
    ("ACTOR_BG_SPOT18_OBJ", "BG_SPOT18_OBJ", "BG_SPOT18_OBJ"),
    ("ACTOR_BOSS_VA", "BOSS_VA", "BOSS_VA"),
    ("ACTOR_BG_HAKA_TUBO", "BG_HAKA_TUBO", "BG_HAKA_TUBO"),
    ("ACTOR_BG_HAKA_TRAP", "BG_HAKA_TRAP", "BG_HAKA_TRAP"),
    ("ACTOR_BG_HAKA_HUTA", "BG_HAKA_HUTA", "BG_HAKA_HUTA"),
    ("ACTOR_BG_HAKA_ZOU", "BG_HAKA_ZOU", "BG_HAKA_ZOU"),
    ("ACTOR_BG_SPOT17_FUNEN", "BG_SPOT17_FUNEN", "BG_SPOT17_FUNEN"),
    ("ACTOR_EN_SYATEKI_ITM", "EN_SYATEKI_ITM", "EN_SYATEKI_ITM"),
    ("ACTOR_EN_SYATEKI_MAN", "EN_SYATEKI_MAN", "EN_SYATEKI_MAN"),
    ("ACTOR_EN_TANA", "EN_TANA", "EN_TANA"),
    ("ACTOR_EN_NB", "EN_NB", "EN_NB"),
    ("ACTOR_BOSS_MO", "BOSS_MO", "BOSS_MO"),
    ("ACTOR_EN_SB", "EN_SB", "EN_SB"),
    ("ACTOR_EN_BIGOKUTA", "EN_BIGOKUTA", "EN_BIGOKUTA"),
    ("ACTOR_EN_KAREBABA", "EN_KAREBABA", "EN_KAREBABA"),
    ("ACTOR_BG_BDAN_OBJECTS", "BG_BDAN_OBJECTS", "BG_BDAN_OBJECTS"),
    ("ACTOR_DEMO_SA", "DEMO_SA", "DEMO_SA"),
    ("ACTOR_DEMO_GO", "DEMO_GO", "DEMO_GO"),
    ("ACTOR_EN_IN", "EN_IN", "EN_IN"),
    ("ACTOR_EN_TR", "EN_TR", "EN_TR"),
    ("ACTOR_BG_SPOT16_BOMBSTONE", "BG_SPOT16_BOMBSTONE", "BG_SPOT16_BOMBSTONE"),
    ("ACTOR_BG_HIDAN_KOWARERUKABE", "BG_HIDAN_KOWARERUKABE", "BG_HIDAN_KOWARERUKABE"),
    ("ACTOR_BG_BOMBWALL", "BG_BOMBWALL", "BG_BOMBWALL"),
    ("ACTOR_BG_SPOT08_ICEBLOCK", "BG_SPOT08_ICEBLOCK", "BG_SPOT08_ICEBLOCK"),
    ("ACTOR_EN_RU2", "EN_RU2", "EN_RU2"),
    ("ACTOR_OBJ_DEKUJR", "OBJ_DEKUJR", "OBJ_DEKUJR"),
    ("ACTOR_BG_MIZU_UZU", "BG_MIZU_UZU", "BG_MIZU_UZU"),
    ("ACTOR_BG_SPOT06_OBJECTS", "BG_SPOT06_OBJECTS", "BG_SPOT06_OBJECTS"),
    ("ACTOR_BG_ICE_OBJECTS", "BG_ICE_OBJECTS", "BG_ICE_OBJECTS"),
    ("ACTOR_BG_HAKA_WATER", "BG_HAKA_WATER", "BG_HAKA_WATER"),
    ("ACTOR_EN_MA2", "EN_MA2", "EN_MA2"),
    ("ACTOR_EN_BOM_CHU", "EN_BOM_CHU", "EN_BOM_CHU"),
    ("ACTOR_EN_HORSE_GAME_CHECK", "EN_HORSE_GAME_CHECK", "EN_HORSE_GAME_CHECK"),
    ("ACTOR_BOSS_TW", "BOSS_TW", "BOSS_TW"),
    ("ACTOR_EN_RR", "EN_RR", "EN_RR"),
    ("ACTOR_EN_BA", "EN_BA", "EN_BA"),
    ("ACTOR_EN_BX", "EN_BX", "EN_BX"),
    ("ACTOR_EN_ANUBICE", "EN_ANUBICE", "EN_ANUBICE"),
    ("ACTOR_EN_ANUBICE_FIRE", "EN_ANUBICE_FIRE", "EN_ANUBICE_FIRE"),
    ("ACTOR_BG_MORI_HASHIGO", "BG_MORI_HASHIGO", "BG_MORI_HASHIGO"),
    ("ACTOR_BG_MORI_HASHIRA4", "BG_MORI_HASHIRA4", "BG_MORI_HASHIRA4"),
    ("ACTOR_BG_MORI_IDOMIZU", "BG_MORI_IDOMIZU", "BG_MORI_IDOMIZU"),
    ("ACTOR_BG_SPOT16_DOUGHNUT", "BG_SPOT16_DOUGHNUT", "BG_SPOT16_DOUGHNUT"),
    ("ACTOR_BG_BDAN_SWITCH", "BG_BDAN_SWITCH", "BG_BDAN_SWITCH"),
    ("ACTOR_EN_MA1", "EN_MA1", "EN_MA1"),
    ("ACTOR_BOSS_GANON", "BOSS_GANON", "BOSS_GANON"),
    ("ACTOR_BOSS_SST", "BOSS_SST", "BOSS_SST"),
    ("ACTOR_EN_NY", "EN_NY", "EN_NY"),
    ("ACTOR_EN_FR", "EN_FR", "EN_FR"),
    ("ACTOR_ITEM_SHIELD", "ITEM_SHIELD", "ITEM_SHIELD"),
    ("ACTOR_BG_ICE_SHELTER", "BG_ICE_SHELTER", "BG_ICE_SHELTER"),
    ("ACTOR_EN_ICE_HONO", "EN_ICE_HONO", "EN_ICE_HONO"),
    ("ACTOR_ITEM_OCARINA", "ITEM_OCARINA", "ITEM_OCARINA"),
    ("ACTOR_MAGIC_DARK", "MAGIC_DARK", "MAGIC_DARK"),
    ("ACTOR_DEMO_6K", "DEMO_6K", "DEMO_6K"),
    ("ACTOR_EN_ANUBICE_TAG", "EN_ANUBICE_TAG", "EN_ANUBICE_TAG"),
    ("ACTOR_BG_HAKA_GATE", "BG_HAKA_GATE", "BG_HAKA_GATE"),
    ("ACTOR_BG_SPOT15_SAKU", "BG_SPOT15_SAKU", "BG_SPOT15_SAKU"),
    ("ACTOR_BG_JYA_GOROIWA", "BG_JYA_GOROIWA", "BG_JYA_GOROIWA"),
    ("ACTOR_BG_JYA_ZURERUKABE", "BG_JYA_ZURERUKABE", "BG_JYA_ZURERUKABE"),
    ("ACTOR_BG_JYA_COBRA", "BG_JYA_COBRA", "BG_JYA_COBRA"),
    ("ACTOR_BG_JYA_KANAAMI", "BG_JYA_KANAAMI", "BG_JYA_KANAAMI"),
    ("ACTOR_FISHING", "FISHING", "FISHING"),
    ("ACTOR_OBJ_OSHIHIKI", "OBJ_OSHIHIKI", "OBJ_OSHIHIKI"),
    ("ACTOR_BG_GATE_SHUTTER", "BG_GATE_SHUTTER", "BG_GATE_SHUTTER"),
    ("ACTOR_EFF_DUST", "EFF_DUST", "EFF_DUST"),
    ("ACTOR_BG_SPOT01_FUSYA", "BG_SPOT01_FUSYA", "BG_SPOT01_FUSYA"),
    ("ACTOR_BG_SPOT01_IDOHASHIRA", "BG_SPOT01_IDOHASHIRA", "BG_SPOT01_IDOHASHIRA"),
    ("ACTOR_BG_SPOT01_IDOMIZU", "BG_SPOT01_IDOMIZU", "BG_SPOT01_IDOMIZU"),
    ("ACTOR_BG_PO_SYOKUDAI", "BG_PO_SYOKUDAI", "BG_PO_SYOKUDAI"),
    ("ACTOR_BG_GANON_OTYUKA", "BG_GANON_OTYUKA", "BG_GANON_OTYUKA"),
    ("ACTOR_BG_SPOT15_RRBOX", "BG_SPOT15_RRBOX", "BG_SPOT15_RRBOX"),
    ("ACTOR_BG_UMAJUMP", "BG_UMAJUMP", "BG_UMAJUMP"),
    ("ACTOR_ARROW_FIRE", "ARROW_FIRE", "ARROW_FIRE"),
    ("ACTOR_ARROW_ICE", "ARROW_ICE", "ARROW_ICE"),
    ("ACTOR_ARROW_LIGHT", "ARROW_LIGHT", "ARROW_LIGHT"),
    ("ACTOR_ITEM_ETCETERA", "ITEM_ETCETERA", "ITEM_ETCETERA"),
    ("ACTOR_OBJ_KIBAKO", "OBJ_KIBAKO", "OBJ_KIBAKO"),
    ("ACTOR_OBJ_TSUBO", "OBJ_TSUBO", "OBJ_TSUBO"),
    ("ACTOR_EN_WONDER_ITEM", "EN_WONDER_ITEM", "EN_WONDER_ITEM"),
    ("ACTOR_EN_IK", "EN_IK", "EN_IK"),
    ("ACTOR_DEMO_IK", "DEMO_IK", "DEMO_IK"),
    ("ACTOR_EN_SKJ", "EN_SKJ", "EN_SKJ"),
    ("ACTOR_EN_SKJNEEDLE", "EN_SKJNEEDLE", "EN_SKJNEEDLE"),
    ("ACTOR_EN_G_SWITCH", "EN_G_SWITCH", "EN_G_SWITCH"),
    ("ACTOR_DEMO_EXT", "DEMO_EXT", "DEMO_EXT"),
    ("ACTOR_DEMO_SHD", "DEMO_SHD", "DEMO_SHD"),
    ("ACTOR_EN_DNS", "EN_DNS", "EN_DNS"),
    ("ACTOR_ELF_MSG", "ELF_MSG", "ELF_MSG"),
    ("ACTOR_EN_HONOTRAP", "EN_HONOTRAP", "EN_HONOTRAP"),
    ("ACTOR_EN_TUBO_TRAP", "EN_TUBO_TRAP", "EN_TUBO_TRAP"),
    ("ACTOR_OBJ_ICE_POLY", "OBJ_ICE_POLY", "OBJ_ICE_POLY"),
    ("ACTOR_BG_SPOT03_TAKI", "BG_SPOT03_TAKI", "BG_SPOT03_TAKI"),
    ("ACTOR_BG_SPOT07_TAKI", "BG_SPOT07_TAKI", "BG_SPOT07_TAKI"),
    ("ACTOR_EN_FZ", "EN_FZ", "EN_FZ"),
    ("ACTOR_EN_PO_RELAY", "EN_PO_RELAY", "EN_PO_RELAY"),
    ("ACTOR_BG_RELAY_OBJECTS", "BG_RELAY_OBJECTS", "BG_RELAY_OBJECTS"),
    ("ACTOR_EN_DIVING_GAME", "EN_DIVING_GAME", "EN_DIVING_GAME"),
    ("ACTOR_EN_KUSA", "EN_KUSA", "EN_KUSA"),
    ("ACTOR_OBJ_BEAN", "OBJ_BEAN", "OBJ_BEAN"),
    ("ACTOR_OBJ_BOMBIWA", "OBJ_BOMBIWA", "OBJ_BOMBIWA"),
    ("ACTOR_OBJ_SWITCH", "OBJ_SWITCH", "OBJ_SWITCH"),
    ("ACTOR_OBJ_ELEVATOR", "OBJ_ELEVATOR", "OBJ_ELEVATOR"),
    ("ACTOR_OBJ_LIFT", "OBJ_LIFT", "OBJ_LIFT"),
    ("ACTOR_OBJ_HSBLOCK", "OBJ_HSBLOCK", "OBJ_HSBLOCK"),
    ("ACTOR_EN_OKARINA_TAG", "EN_OKARINA_TAG", "EN_OKARINA_TAG"),
    ("ACTOR_EN_YABUSAME_MARK", "EN_YABUSAME_MARK", "EN_YABUSAME_MARK"),
    ("ACTOR_EN_GOROIWA", "EN_GOROIWA", "EN_GOROIWA"),
    ("ACTOR_EN_EX_RUPPY", "EN_EX_RUPPY", "EN_EX_RUPPY"),
    ("ACTOR_EN_TORYO", "EN_TORYO", "EN_TORYO"),
    ("ACTOR_EN_DAIKU", "EN_DAIKU", "EN_DAIKU"),
    ("ACTOR_EN_NWC", "EN_NWC", "EN_NWC"),
    ("ACTOR_EN_BLKOBJ", "EN_BLKOBJ", "EN_BLKOBJ"),
    ("ACTOR_ITEM_INBOX", "ITEM_INBOX", "ITEM_INBOX"),
    ("ACTOR_EN_GE1", "EN_GE1", "EN_GE1"),
    ("ACTOR_OBJ_BLOCKSTOP", "OBJ_BLOCKSTOP", "OBJ_BLOCKSTOP"),
    ("ACTOR_EN_SDA", "EN_SDA", "EN_SDA"),
    ("ACTOR_EN_CLEAR_TAG", "EN_CLEAR_TAG", "EN_CLEAR_TAG"),
    ("ACTOR_EN_NIW_LADY", "EN_NIW_LADY", "EN_NIW_LADY"),
    ("ACTOR_EN_GM", "EN_GM", "EN_GM"),
    ("ACTOR_EN_MS", "EN_MS", "EN_MS"),
    ("ACTOR_EN_HS", "EN_HS", "EN_HS"),
    ("ACTOR_BG_INGATE", "BG_INGATE", "BG_INGATE"),
    ("ACTOR_EN_KANBAN", "EN_KANBAN", "EN_KANBAN"),
    ("ACTOR_EN_HEISHI3", "EN_HEISHI3", "EN_HEISHI3"),
    ("ACTOR_EN_SYATEKI_NIW", "EN_SYATEKI_NIW", "EN_SYATEKI_NIW"),
    ("ACTOR_EN_ATTACK_NIW", "EN_ATTACK_NIW", "EN_ATTACK_NIW"),
    ("ACTOR_BG_SPOT01_IDOSOKO", "BG_SPOT01_IDOSOKO", "BG_SPOT01_IDOSOKO"),
    ("ACTOR_EN_SA", "EN_SA", "EN_SA"),
    ("ACTOR_EN_WONDER_TALK", "EN_WONDER_TALK", "EN_WONDER_TALK"),
    ("ACTOR_BG_GJYO_BRIDGE", "BG_GJYO_BRIDGE", "BG_GJYO_BRIDGE"),
    ("ACTOR_EN_DS", "EN_DS", "EN_DS"),
    ("ACTOR_EN_MK", "EN_MK", "EN_MK"),
    ("ACTOR_EN_BOM_BOWL_MAN", "EN_BOM_BOWL_MAN", "EN_BOM_BOWL_MAN"),
    ("ACTOR_EN_BOM_BOWL_PIT", "EN_BOM_BOWL_PIT", "EN_BOM_BOWL_PIT"),
    ("ACTOR_EN_OWL", "EN_OWL", "EN_OWL"),
    ("ACTOR_EN_ISHI", "EN_ISHI", "EN_ISHI"),
    ("ACTOR_OBJ_HANA", "OBJ_HANA", "OBJ_HANA"),
    ("ACTOR_OBJ_LIGHTSWITCH", "OBJ_LIGHTSWITCH", "OBJ_LIGHTSWITCH"),
    ("ACTOR_OBJ_MURE2", "OBJ_MURE2", "OBJ_MURE2"),
    ("ACTOR_EN_GO", "EN_GO", "EN_GO"),
    ("ACTOR_EN_FU", "EN_FU", "EN_FU"),
    ("ACTOR_EN_CHANGER", "EN_CHANGER", "EN_CHANGER"),
    ("ACTOR_BG_JYA_MEGAMI", "BG_JYA_MEGAMI", "BG_JYA_MEGAMI"),
    ("ACTOR_BG_JYA_LIFT", "BG_JYA_LIFT", "BG_JYA_LIFT"),
    ("ACTOR_BG_JYA_BIGMIRROR", "BG_JYA_BIGMIRROR", "BG_JYA_BIGMIRROR"),
    ("ACTOR_BG_JYA_BOMBCHUIWA", "BG_JYA_BOMBCHUIWA", "BG_JYA_BOMBCHUIWA"),
    ("ACTOR_BG_JYA_AMISHUTTER", "BG_JYA_AMISHUTTER", "BG_JYA_AMISHUTTER"),
    ("ACTOR_BG_JYA_BOMBIWA", "BG_JYA_BOMBIWA", "BG_JYA_BOMBIWA"),
    ("ACTOR_BG_SPOT18_BASKET", "BG_SPOT18_BASKET", "BG_SPOT18_BASKET"),
    ("ACTOR_EN_GANON_ORGAN", "EN_GANON_ORGAN", "EN_GANON_ORGAN"),
    ("ACTOR_EN_SIOFUKI", "EN_SIOFUKI", "EN_SIOFUKI"),
    ("ACTOR_EN_STREAM", "EN_STREAM", "EN_STREAM"),
    ("ACTOR_EN_MM", "EN_MM", "EN_MM"),
    ("ACTOR_EN_KO", "EN_KO", "EN_KO"),
    ("ACTOR_EN_KZ", "EN_KZ", "EN_KZ"),
    ("ACTOR_EN_WEATHER_TAG", "EN_WEATHER_TAG", "EN_WEATHER_TAG"),
    ("ACTOR_BG_SST_FLOOR", "BG_SST_FLOOR", "BG_SST_FLOOR"),
    ("ACTOR_EN_ANI", "EN_ANI", "EN_ANI"),
    ("ACTOR_EN_EX_ITEM", "EN_EX_ITEM", "EN_EX_ITEM"),
    ("ACTOR_BG_JYA_IRONOBJ", "BG_JYA_IRONOBJ", "BG_JYA_IRONOBJ"),
    ("ACTOR_EN_JS", "EN_JS", "EN_JS"),
    ("ACTOR_EN_JSJUTAN", "EN_JSJUTAN", "EN_JSJUTAN"),
    ("ACTOR_EN_CS", "EN_CS", "EN_CS"),
    ("ACTOR_EN_MD", "EN_MD", "EN_MD"),
    ("ACTOR_EN_HY", "EN_HY", "EN_HY"),
    ("ACTOR_EN_GANON_MANT", "EN_GANON_MANT", "EN_GANON_MANT"),
    ("ACTOR_EN_OKARINA_EFFECT", "EN_OKARINA_EFFECT", "EN_OKARINA_EFFECT"),
    ("ACTOR_EN_MAG", "EN_MAG", "EN_MAG"),
    ("ACTOR_DOOR_GERUDO", "DOOR_GERUDO", "DOOR_GERUDO"),
    ("ACTOR_ELF_MSG2", "ELF_MSG2", "ELF_MSG2"),
    ("ACTOR_DEMO_GT", "DEMO_GT", "DEMO_GT"),
    ("ACTOR_EN_PO_FIELD", "EN_PO_FIELD", "EN_PO_FIELD"),
    ("ACTOR_EFC_ERUPC", "EFC_ERUPC", "EFC_ERUPC"),
    ("ACTOR_BG_ZG", "BG_ZG", "BG_ZG"),
    ("ACTOR_EN_HEISHI4", "EN_HEISHI4", "EN_HEISHI4"),
    ("ACTOR_EN_ZL3", "EN_ZL3", "EN_ZL3"),
    ("ACTOR_BOSS_GANON2", "BOSS_GANON2", "BOSS_GANON2"),
    ("ACTOR_EN_KAKASI", "EN_KAKASI", "EN_KAKASI"),
    ("ACTOR_EN_TAKARA_MAN", "EN_TAKARA_MAN", "EN_TAKARA_MAN"),
    ("ACTOR_OBJ_MAKEOSHIHIKI", "OBJ_MAKEOSHIHIKI", "OBJ_MAKEOSHIHIKI"),
    ("ACTOR_OCEFF_SPOT", "OCEFF_SPOT", "OCEFF_SPOT"),
    ("ACTOR_END_TITLE", "END_TITLE", "END_TITLE"),
    ("ACTOR_EN_TORCH", "EN_TORCH", "EN_TORCH"),
    ("ACTOR_DEMO_EC", "DEMO_EC", "DEMO_EC"),
    ("ACTOR_SHOT_SUN", "SHOT_SUN", "SHOT_SUN"),
    ("ACTOR_EN_DY_EXTRA", "EN_DY_EXTRA", "EN_DY_EXTRA"),
    ("ACTOR_EN_WONDER_TALK2", "EN_WONDER_TALK2", "EN_WONDER_TALK2"),
    ("ACTOR_EN_GE2", "EN_GE2", "EN_GE2"),
    ("ACTOR_OBJ_ROOMTIMER", "OBJ_ROOMTIMER", "OBJ_ROOMTIMER"),
    ("ACTOR_EN_SSH", "EN_SSH", "EN_SSH"),
    ("ACTOR_EN_STH", "EN_STH", "EN_STH"),
    ("ACTOR_OCEFF_WIPE", "OCEFF_WIPE", "OCEFF_WIPE"),
    ("ACTOR_OCEFF_STORM", "OCEFF_STORM", "OCEFF_STORM"),
    ("ACTOR_EN_WEIYER", "EN_WEIYER", "EN_WEIYER"),
    ("ACTOR_BG_SPOT05_SOKO", "BG_SPOT05_SOKO", "BG_SPOT05_SOKO"),
    ("ACTOR_BG_JYA_1FLIFT", "BG_JYA_1FLIFT", "BG_JYA_1FLIFT"),
    ("ACTOR_BG_JYA_HAHENIRON", "BG_JYA_HAHENIRON", "BG_JYA_HAHENIRON"),
    ("ACTOR_BG_SPOT12_GATE", "BG_SPOT12_GATE", "BG_SPOT12_GATE"),
    ("ACTOR_BG_SPOT12_SAKU", "BG_SPOT12_SAKU", "BG_SPOT12_SAKU"),
    ("ACTOR_EN_HINTNUTS", "EN_HINTNUTS", "EN_HINTNUTS"),
    ("ACTOR_EN_NUTSBALL", "EN_NUTSBALL", "EN_NUTSBALL"),
    ("ACTOR_BG_SPOT00_BREAK", "BG_SPOT00_BREAK", "BG_SPOT00_BREAK"),
    ("ACTOR_EN_SHOPNUTS", "EN_SHOPNUTS", "EN_SHOPNUTS"),
    ("ACTOR_EN_IT", "EN_IT", "EN_IT"),
    ("ACTOR_EN_GELDB", "EN_GELDB", "EN_GELDB"),
    ("ACTOR_OCEFF_WIPE2", "OCEFF_WIPE2", "OCEFF_WIPE2"),
    ("ACTOR_OCEFF_WIPE3", "OCEFF_WIPE3", "OCEFF_WIPE3"),
    ("ACTOR_EN_NIW_GIRL", "EN_NIW_GIRL", "EN_NIW_GIRL"),
    ("ACTOR_EN_DOG", "EN_DOG", "EN_DOG"),
    ("ACTOR_EN_SI", "EN_SI", "EN_SI"),
    ("ACTOR_BG_SPOT01_OBJECTS2", "BG_SPOT01_OBJECTS2", "BG_SPOT01_OBJECTS2"),
    ("ACTOR_OBJ_COMB", "OBJ_COMB", "OBJ_COMB"),
    ("ACTOR_BG_SPOT11_BAKUDANKABE", "BG_SPOT11_BAKUDANKABE", "BG_SPOT11_BAKUDANKABE"),
    ("ACTOR_OBJ_KIBAKO2", "OBJ_KIBAKO2", "OBJ_KIBAKO2"),
    ("ACTOR_EN_DNT_DEMO", "EN_DNT_DEMO", "EN_DNT_DEMO"),
    ("ACTOR_EN_DNT_JIJI", "EN_DNT_JIJI", "EN_DNT_JIJI"),
    ("ACTOR_EN_DNT_NOMAL", "EN_DNT_NOMAL", "EN_DNT_NOMAL"),
    ("ACTOR_EN_GUEST", "EN_GUEST", "EN_GUEST"),
    ("ACTOR_BG_BOM_GUARD", "BG_BOM_GUARD", "BG_BOM_GUARD"),
    ("ACTOR_EN_HS2", "EN_HS2", "EN_HS2"),
    ("ACTOR_DEMO_KEKKAI", "DEMO_KEKKAI", "DEMO_KEKKAI"),
    ("ACTOR_BG_SPOT08_BAKUDANKABE", "BG_SPOT08_BAKUDANKABE", "BG_SPOT08_BAKUDANKABE"),
    ("ACTOR_BG_SPOT17_BAKUDANKABE", "BG_SPOT17_BAKUDANKABE", "BG_SPOT17_BAKUDANKABE"),
    ("ACTOR_OBJ_MURE3", "OBJ_MURE3", "OBJ_MURE3"),
    ("ACTOR_EN_TG", "EN_TG", "EN_TG"),
    ("ACTOR_EN_MU", "EN_MU", "EN_MU"),
    ("ACTOR_EN_GO2", "EN_GO2", "EN_GO2"),
    ("ACTOR_EN_WF", "EN_WF", "EN_WF"),
    ("ACTOR_EN_SKB", "EN_SKB", "EN_SKB"),
    ("ACTOR_DEMO_GJ", "DEMO_GJ", "DEMO_GJ"),
    ("ACTOR_DEMO_GEFF", "DEMO_GEFF", "DEMO_GEFF"),
    ("ACTOR_BG_GND_FIREMEIRO", "BG_GND_FIREMEIRO", "BG_GND_FIREMEIRO"),
    ("ACTOR_BG_GND_DARKMEIRO", "BG_GND_DARKMEIRO", "BG_GND_DARKMEIRO"),
    ("ACTOR_BG_GND_SOULMEIRO", "BG_GND_SOULMEIRO", "BG_GND_SOULMEIRO"),
    ("ACTOR_BG_GND_NISEKABE", "BG_GND_NISEKABE", "BG_GND_NISEKABE"),
    ("ACTOR_BG_GND_ICEBLOCK", "BG_GND_ICEBLOCK", "BG_GND_ICEBLOCK"),
    ("ACTOR_EN_GB", "EN_GB", "EN_GB"),
    ("ACTOR_EN_GS", "EN_GS", "EN_GS"),
    ("ACTOR_BG_MIZU_BWALL", "BG_MIZU_BWALL", "BG_MIZU_BWALL"),
    ("ACTOR_BG_MIZU_SHUTTER", "BG_MIZU_SHUTTER", "BG_MIZU_SHUTTER"),
    ("ACTOR_EN_DAIKU_KAKARIKO", "EN_DAIKU_KAKARIKO", "EN_DAIKU_KAKARIKO"),
    ("ACTOR_BG_BOWL_WALL", "BG_BOWL_WALL", "BG_BOWL_WALL"),
    ("ACTOR_EN_WALL_TUBO", "EN_WALL_TUBO", "EN_WALL_TUBO"),
    ("ACTOR_EN_PO_DESERT", "EN_PO_DESERT", "EN_PO_DESERT"),
    ("ACTOR_EN_CROW", "EN_CROW", "EN_CROW"),
    ("ACTOR_DOOR_KILLER", "DOOR_KILLER", "DOOR_KILLER"),
    ("ACTOR_BG_SPOT11_OASIS", "BG_SPOT11_OASIS", "BG_SPOT11_OASIS"),
    ("ACTOR_BG_SPOT18_FUTA", "BG_SPOT18_FUTA", "BG_SPOT18_FUTA"),
    ("ACTOR_BG_SPOT18_SHUTTER", "BG_SPOT18_SHUTTER", "BG_SPOT18_SHUTTER"),
    ("ACTOR_EN_MA3", "EN_MA3", "EN_MA3"),
    ("ACTOR_EN_COW", "EN_COW", "EN_COW"),
    ("ACTOR_BG_ICE_TURARA", "BG_ICE_TURARA", "BG_ICE_TURARA"),
    ("ACTOR_BG_ICE_SHUTTER", "BG_ICE_SHUTTER", "BG_ICE_SHUTTER"),
    ("ACTOR_EN_KAKASI2", "EN_KAKASI2", "EN_KAKASI2"),
    ("ACTOR_EN_KAKASI3", "EN_KAKASI3", "EN_KAKASI3"),
    ("ACTOR_OCEFF_WIPE4", "OCEFF_WIPE4", "OCEFF_WIPE4"),
    ("ACTOR_EN_EG", "EN_EG", "EN_EG"),
    ("ACTOR_BG_MENKURI_NISEKABE", "BG_MENKURI_NISEKABE", "BG_MENKURI_NISEKABE"),
    ("ACTOR_EN_ZO", "EN_ZO", "EN_ZO"),
    ("ACTOR_OBJ_MAKEKINSUTA", "OBJ_MAKEKINSUTA", "OBJ_MAKEKINSUTA"),
    ("ACTOR_EN_GE3", "EN_GE3", "EN_GE3"),
    ("ACTOR_OBJ_TIMEBLOCK", "OBJ_TIMEBLOCK", "OBJ_TIMEBLOCK"),
    ("ACTOR_OBJ_HAMISHI", "OBJ_HAMISHI", "OBJ_HAMISHI"),
    ("ACTOR_EN_ZL4", "EN_ZL4", "EN_ZL4"),
    ("ACTOR_EN_MM2", "EN_MM2", "EN_MM2"),
    ("ACTOR_BG_JYA_BLOCK", "BG_JYA_BLOCK", "BG_JYA_BLOCK"),
    ("ACTOR_OBJ_WARP2BLOCK", "OBJ_WARP2BLOCK", "OBJ_WARP2BLOCK"),
]

ootEnumWaterBoxLighting = [
	("Custom", "Custom", "Custom"),
	("Default", "Default", "Default"),
]

ootEnumWaterBoxCamera = [
	("Custom", "Custom", "Custom"),
	("Default", "Default", "Default"),
]

ootEnumLinkIdle = [
	("Custom", "Custom", "Custom"),
	("Default", "Default", "Default"),
	("Sneezing", "Sneezing", "Sneezing"),
	("Wiping Forehead", "Wiping Forehead", "Wiping Forehead"),
	("Too Hot", "Too Hot", "Too Hot (Triggers Heat Timer)"),
	("Yawning", "Yawning", "Yawning"),
	("Gasping For Breath", "Gasping For Breath", "Gasping For Breath"),
	("Brandish Sword", "Brandish Sword", "Brandish Sword"),
	("Adjust Tunic", "Adjust Tunic", "Adjust Tunic"),
	("Hops On Epona", "Hops On Epona", "Hops On Epona"),
]

# Make sure to add exceptions in utility.py - selectMeshChildrenOnly
ootEnumEmptyType = [
	('None', 'None', 'None'),
	('Scene', 'Scene', 'Scene'),
	('Room', 'Room', 'Room'),
	('Actor', 'Actor', 'Actor'),
	('Entrance', 'Entrance', 'Entrance'),
	('Water Box', 'Water Box', 'Water Box'),
	#('Camera Volume', 'Camera Volume', 'Camera Volume'),
]

ootEnumCloudiness = [
	("Custom", "Custom", "Custom"),
	("Sunny", "Sunny", "Sunny"),
	("Cloudy", "Cloudy", "Cloudy"),
]

ootEnumCameraMode = [
	("Custom", "Custom", "Custom"),
	("Default", "Default", "Default"),
	("Two Views, No C-Up", "Two Views, No C-Up", "Two Views, No C-Up"),
	("Rotating Background, Bird's Eye C-Up", "Rotating Background, Bird's Eye C-Up", "Rotating Background, Bird's Eye C-Up"),
	("Fixed Background, No C-Up", "Fixed Background, No C-Up", "Fixed Background, No C-Up"),
	("Rotating Background, No C-Up", "Rotating Background, No C-Up", "Rotating Background, No C-Up"),
	("Shooting Gallery", "Shooting Gallery", "Shooting Gallery"),
]

ootEnumMapLocation = [
	("Custom", "Custom", "Custom"),
	("Hyrule Field", "Hyrule Field", "Hyrule Field"),
	("Kakariko Village", "Kakariko Village", "Kakariko Village"),
	("Graveyard", "Graveyard", "Graveyard"),
	("Zora's River", "Zora's River", "Zora's River"),
	("Kokiri Forest", "Kokiri Forest", "Kokiri Forest"),
	("Sacred Forest Meadow", "Sacred Forest Meadow", "Sacred Forest Meadow"),
	("Lake Hylia", "Lake Hylia", "Lake Hylia"),
	("Zora's Domain", "Zora's Domain", "Zora's Domain"),
	("Zora's Fountain", "Zora's Fountain", "Zora's Fountain"),
	("Gerudo Valley", "Gerudo Valley", "Gerudo Valley"),
	("Lost Woods", "Lost Woods", "Lost Woods"),
	("Desert Colossus", "Desert Colossus", "Desert Colossus"),
	("Gerudo's Fortress", "Gerudo's Fortress", "Gerudo's Fortress"),
	("Haunted Wasteland", "Haunted Wasteland", "Haunted Wasteland"),
	("Market", "Market", "Market"),
	("Hyrule Castle", "Hyrule Castle", "Hyrule Castle"),
	("Death Mountain Trail", "Death Mountain Trail", "Death Mountain Trail"),
	("Death Mountain Crater", "Death Mountain Crater", "Death Mountain Crater"),
	("Goron City", "Goron City", "Goron City"),
	("Lon Lon Ranch", "Lon Lon Ranch", "Lon Lon Ranch"),
	("Dampe's Grave & Windmill", "Dampe's Grave & Windmill", "Dampe's Grave & Windmill"),
	("Ganon's Castle", "Ganon's Castle", "Ganon's Castle"),
	("Grottos & Fairy Fountains", "Grottos & Fairy Fountains", "Grottos & Fairy Fountains"),
]

ootEnumSkybox = [
	("Custom", "Custom", "Custom"),
	("None", "None", "None"), 
	("Standard Sky", "Standard Sky", "Standard Sky"),
	("Hylian Bazaar", "Hylian Bazaar", "Hylian Bazaar"),
	("Brown Cloudy Sky", "Brown Cloudy Sky", "Brown Cloudy Sky"),
	("Market Ruins", "Market Ruins", "Market Ruins"),
	("Black Cloudy Night", "Black Cloudy Night", "Black Cloudy Night"),
	("Link's House", "Link's House", "Link's House"),
	("Market (Main Square, Day)", "Market (Main Square, Day)", "Market (Main Square, Day)"),
	("Market (Main Square, Night)", "Market (Main Square, Night)", "Market (Main Square, Night)"),
	("Happy Mask Shop", "Happy Mask Shop", "Happy Mask Shop"),
	("Know-It-All Brothers' House", "Know-It-All Brothers' House", "Know-It-All Brothers' House"),
	("Kokiri Twins' House", "Kokiri Twins' House", "Kokiri Twins' House"),
	("Stable", "Stable", "Stable"),
	("Stew Lady's House", "Stew Lady's House", "Stew Lady's House"),
	("Kokiri Shop", "Kokiri Shop", "Kokiri Shop"),
	("Goron Shop", "Goron Shop", "Goron Shop"),
	("Zora Shop", "Zora Shop", "Zora Shop"),
	("Kakariko Potions Shop", "Kakariko Potions Shop", "Kakariko Potions Shop"),
	("Hylian Potions Shop", "Hylian Potions Shop", "Hylian Potions Shop"),
	("Bomb Shop", "Bomb Shop", "Bomb Shop"),
	("Dog Lady's House", "Dog Lady's House", "Dog Lady's House"),
	("Impa's House", "Impa's House", "Impa's House"),
	("Gerudo Tent", "Gerudo Tent", "Gerudo Tent"),
	("Environment Color", "Environment Color", "Environment Color"),
	("Mido's House", "Mido's House", "Mido's House"),
	("Saria's House", "Saria's House", "Saria's House"),
	("Dog Guy's House", "Dog Guy's House", "Dog Guy's House"),
]

ootEnumSkyboxLighting = [
	("Custom", "Custom", "Custom"),
	("Time Of Day", "Time Of Day", "Time Of Day"),
	("Indoor", "Indoor", "Indoor"),
]

ootEnumMusicSeq = [	
	("Custom", "Custom", "Custom"),
	("NA_BGM_FIELD1", "Hyrule Field", "Hyrule Field"),		
	("NA_BGM_FIELD2", "Hyrule Field (Initial Segment From Loading Area)", "Hyrule Field (Initial Segment From Loading Area)"), 	
	("NA_BGM_FIELD3", "Hyrule Field (Moving Segment 1)", "Hyrule Field (Moving Segment 1)"),	
	("NA_BGM_FIELD4", "Hyrule Field (Moving Segment 2)", "Hyrule Field (Moving Segment 2)"),
	("NA_BGM_FIELD5", "Hyrule Field (Moving Segment 3)", "Hyrule Field (Moving Segment 3)"),
	("NA_BGM_FIELD6", "Hyrule Field (Moving Segment 4)", "Hyrule Field (Moving Segment 4)"),
	("NA_BGM_FIELD7", "Hyrule Field (Moving Segment 5)", "Hyrule Field (Moving Segment 5)"),
	("NA_BGM_FIELD8", "Hyrule Field (Moving Segment 6)", "Hyrule Field (Moving Segment 6)"),
	("NA_BGM_FIELD9", "Hyrule Field (Moving Segment 7)", "Hyrule Field (Moving Segment 7)"),
	("NA_BGM_FIELD10", "Hyrule Field (Moving Segment 8)", "Hyrule Field (Moving Segment 8)"),
	("NA_BGM_FIELD11", "Hyrule Field (Moving Segment 9)", "Hyrule Field (Moving Segment 9)"),
	("NA_BGM_FIELD12", "Hyrule Field (Moving Segment 10)", "Hyrule Field (Moving Segment 10)"),
	("NA_BGM_FIELD13", "Hyrule Field (Moving Segment 11)", "Hyrule Field (Moving Segment 11)"),
	("NA_BGM_FIELD14", "Hyrule Field (Enemy Approaches)", "Hyrule Field (Enemy Approaches)"),
	("NA_BGM_FIELD15", "Hyrule Field (Enemy Near Segment 1)", "Hyrule Field (Enemy Near Segment 1)"),
	("NA_BGM_FIELD16", "Hyrule Field (Enemy Near Segment 2)", "Hyrule Field (Enemy Near Segment 2)"),
	("NA_BGM_FIELD17", "Hyrule Field (Enemy Near Segment 3)", "Hyrule Field (Enemy Near Segment 3)"),
	("NA_BGM_FIELD18", "Hyrule Field (Enemy Near Segment 4)", "Hyrule Field (Enemy Near Segment 4)"),
	("NA_BGM_FIELD19", "Hyrule Field (Standing Still Segment 1)", "Hyrule Field (Standing Still Segment 1)"),
	("NA_BGM_FIELD20", "Hyrule Field (Standing Still Segment 2)", "Hyrule Field (Standing Still Segment 2)"),
	("NA_BGM_FIELD21", "Hyrule Field (Standing Still Segment 3)", "Hyrule Field (Standing Still Segment 3)"),
	("NA_BGM_FIELD22", "Hyrule Field (Standing Still Segment 4)", "Hyrule Field (Standing Still Segment 4)"),
	("NA_BGM_DUNGEON", "Dodongo's Cavern", "Dodongo's Cavern"), 		
	("NA_BGM_KAKARIKO_ADULT", "Kakariko Village (Adult)", "Kakariko Village (Adult)"), 		
	("NA_BGM_ENEMY", "Enemy Battle", "Enemy Battle"), 		
	("NA_BGM_BOSS00", "Boss Battle 00", "Boss Battle 00"),
	("NA_BGM_FAIRY_DUNGEON", "Inside the Deku Tree", "Inside the Deku Tree"),
	("NA_BGM_MARKET", "Market", "Market"), 		
	("NA_BGM_TITLE", "Title Theme", "Title Theme"),
	("NA_BGM_LINK_HOUSE", "Link's House", "Link's House"),
	("NA_BGM_GAME_OVER", "Game Over", "Game Over"),
	("NA_BGM_BOSS_CLEAR", "Boss Clear", "Boss Clear"),
	("NA_BGM_ITEM_GET", "Item Get", "Item Get"),		
	("NA_BGM_OPENING_GANON", "Opening Ganon", "Opening Ganon"),
	("NA_BGM_HEART_GET", "Heart Get", "Heart Get"),
	("NA_BGM_OCA_LIGHT", "Prelude Of Light", "Prelude Of Light"),
	("NA_BGM_BUYO_DUNGEON", "Inside Jabu-Jabu's Belly", "Inside Jabu-Jabu's Belly"),
	("NA_BGM_KAKARIKO_KID", "Kakariko Village (Child)", "Kakariko Village (Child)"),
	("NA_BGM_GODESS", "Great Fairy's Fountain", "Great Fairy's Fountain"),
	("NA_BGM_HIME", "Zelda's Theme", "Zelda's Theme"),
	("NA_BGM_FIRE_DUNGEON", "Fire Temple", "Fire Temple"),
	("NA_BGM_OPEN_TRE_BOX", "Open Treasure Chest", "Open Treasure Chest"),
	("NA_BGM_FORST_DUNGEON", "Forest Temple", "Forest Temple"),
	("NA_BGM_HIRAL_GARDEN", "Hyrule Castle Courtyard", "Hyrule Castle Courtyard"),
	("NA_BGM_GANON_TOWER", "Ganondorf's Theme", "Ganondorf's Theme"), 
	("NA_BGM_RONRON", "Lon Lon Ranch", "Lon Lon Ranch"),
	("NA_BGM_GORON", "Goron City", "Goron City "),		
	("NA_BGM_FIELD23", "Hyrule Field Morning Theme", "Hyrule Field Morning Theme"), 		
	("NA_BGM_SPIRIT_STONE", "Spiritual Stone Get", "Spiritual Stone Get"),
	("NA_BGM_OCA_FLAME", "Bolero of Fire", "Bolero of Fire"),
	("NA_BGM_OCA_WIND", "Minuet of Woods", "Minuet of Woods"),
	("NA_BGM_OCA_WATER", "Serenade of Water", "Serenade of Water"), 
	("NA_BGM_OCA_SOUL", "Requiem of Spirit", "Requiem of Spirit"),
	("NA_BGM_OCA_DARKNESS", "Nocturne of Shadow", "Nocturne of Shadow"),
	("NA_BGM_MIDDLE_BOSS", "Mini-Boss Battle", "Mini-Boss Battle"),
	("NA_BGM_S_ITEM_GET", "Obtain Small Item", "Obtain Small Item"),
	("NA_BGM_SHRINE_OF_TIME", "Temple of Time", "Temple of Time"),
	("NA_BGM_EVENT_CLEAR", "Escape from Lon Lon Ranch", "Escape from Lon Lon Ranch"),
	("NA_BGM_KOKIRI", "Kokiri Forest", "Kokiri Forest"),
	("NA_BGM_OCA_YOUSEI", "Obtain Fairy Ocarina", "Obtain Fairy Ocarina"),
	("NA_BGM_MAYOIMORI", "Lost Woods", "Lost Woods"),
	("NA_BGM_SOUL_DUNGEON", "Spirit Temple", "Spirit Temple"),
	("NA_BGM_HORSE", "Horse Race", "Horse Race"),
	("NA_BGM_HORSE_GOAL", "Horse Race Goal", "Horse Race Goal"),
	("NA_BGM_INGO", "Ingo's Theme", "Ingo's Theme"),
	("NA_BGM_MEDAL_GET", "Obtain Medallion", "Obtain Medallion"),
	("NA_BGM_OCA_SARIA", "Ocarina Saria's Song", "Ocarina Saria's Song"),
	("NA_BGM_OCA_EPONA", "Ocarina Epona's Song", "Ocarina Epona's Song"),
	("NA_BGM_OCA_ZELDA", "Ocarina Zelda's Lullaby", "Ocarina Zelda's Lullaby"),
	("NA_BGM_OCA_SUNMOON", "Sun's Song", "Sun's Song"), 		
	("NA_BGM_OCA_TIME", "Song of Time", "Song of Time"), 		
	("NA_BGM_OCA_STORM", "Song of Storms", "Song of Storms"), 		
	("NA_BGM_NAVI", "Fairy Flying", "Fairy Flying"),
	("NA_BGM_DEKUNOKI", "Deku Tree", "Deku Tree"), 		
	("NA_BGM_FUSHA", "Windmill Hut", "Windmill Hut"), 		
	("NA_BGM_HIRAL_DEMO", "Legend of Hyrule", "Legend of Hyrule"), 		
	("NA_BGM_MINI_GAME", "Shooting Gallery", "Shooting Gallery"),
	("NA_BGM_SEAK", "Sheik's Theme", "Sheik's Theme"),
	("NA_BGM_ZORA", "Zora's Domain", "Zora's Domain"),
	("NA_BGM_APPEAR", "Enter Zelda", "Enter Zelda"),
	("NA_BGM_ADULT_LINK", "Goodbye to Zelda", "Goodbye to Zelda"),
	("NA_BGM_MASTER_SWORD", "Master Sword", "Master Sword"),
	("NA_BGM_INTRO_GANON", "Ganon Intro", "Ganon Intro"),
	("NA_BGM_SHOP", "Shop", "Shop"),
	("NA_BGM_KENJA", "Chamber of the Sages", "Chamber of the Sages"),
	("NA_BGM_FILE_SELECT", "File Select", "File Select"),
	("NA_BGM_ICE_DUNGEON", "Ice Cavern", "Ice Cavern"),
	("NA_BGM_GATE_OPEN", "Open Door of Temple of Time", "Open Door of Temple of Time"),
	("NA_BGM_OWL", "Kaepora Gaebora's Theme", "Kaepora Gaebora's Theme"),
	("NA_BGM_DARKNESS_DUNGEON", "Shadow Temple", "Shadow Temple"),
	("NA_BGM_AQUA_DUNGEON", "Water Temple", "Water Temple"),
	("NA_BGM_BRIDGE", "Ganon's Castle Bridge", "Ganon's Castle Bridge"),
	("NA_BGM_SARIA", "Ocarina of Time", "Ocarina of Time"),
	("NA_BGM_GERUDO", "Gerudo Valley", "Gerudo Valley"),
	("NA_BGM_DRUGSTORE", "Potion Shop", "Potion Shop"),
	("NA_BGM_KOTAKE_KOUME", "Kotake & Koume's Theme", "Kotake & Koume's Theme"),
	("NA_BGM_ESCAPE", "Escape from Ganon's Castle", "Escape from Ganon's Castle"),
	("NA_BGM_UNDERGROUND", "Ganon's Castle Under Ground", "Ganon's Castle Under Ground"),
	("NA_BGM_GANON_BATTLE_1", "Ganondorf Battle", "Ganondorf Battle"),
	("NA_BGM_GANON_BATTLE_2", "Ganon Battle", "Ganon Battle"),
	("NA_BGM_END_DEMO", "Seal of Six Sages", "Seal of Six Sages"),
	("NA_BGM_STAFF_1", "End Credits I", "End Credits I"),
	("NA_BGM_STAFF_2", "End Credits II", "End Credits II"),
	("NA_BGM_STAFF_3", "End Credits III", "End Credits III"),
	("NA_BGM_STAFF_4", "End Credits IV", "End Credits IV"),
	("NA_BGM_BOSS01", "King Dodongo & Volvagia Boss Battle", "King Dodongo & Volvagia Boss Battle"),
	("NA_BGM_MINI_GAME_2", "Mini-Game", "Mini-Game"),
]

ootEnumNightSeq = [
	("Custom", "Custom", "Custom"),
	("Standard night [day and night cycle]", "Standard night [day and night cycle]", "Standard night [day and night cycle]"),
	("Standard night [Kakariko]", "Standard night [Kakariko]", "Standard night [Kakariko]"),
	("Distant storm [Graveyard]", "Distant storm [Graveyard]", "Distant storm [Graveyard]"),
	("Howling wind and cawing [Ganon's Castle]", "Howling wind and cawing [Ganon's Castle]", "Howling wind and cawing [Ganon's Castle]"),
	("Wind + night birds [Kokiri]", "Wind + night birds [Kokiri]", "Wind + night birds [Kokiri]"),
	("Wind + crickets", "Wind + crickets", "Wind + crickets"),
	("Wind", "Wind", "Wind"),
	("Howling wind", "Howling wind", "Howling wind"),
	("Tubed howling wind [Wasteland]", "Tubed howling wind [Wasteland]", "Tubed howling wind [Wasteland]"),
	("Tubed howling wind [Colossus]", "Tubed howling wind [Colossus]", "Tubed howling wind [Colossus]"),
	("Wind + birds", "Wind + birds", "Wind + birds"),
	("Day music always playing", "Day music always playing", "Day music always playing"),
	("Rain", "Rain", "Rain"),
	("High tubed wind + rain", "High tubed wind + rain", "High tubed wind + rain"),
	("Silence", "Silence", "Silence"),
]

ootEnumObjectID = [
	("Custom", "Custom", "Custom"),
	("OBJECT_HUMAN", "Human", "Human"),
	("OBJECT_OKUTA", "Okuta", "Okuta"),
	("OBJECT_CROW", "Crow", "Crow"),
	("OBJECT_POH", "Poh", "Poh"),
	("OBJECT_DY_OBJ", "Dy Obj", "Dy Obj"),
	("OBJECT_WALLMASTER", "Wallmaster", "Wallmaster"),
	("OBJECT_DODONGO", "Dodongo", "Dodongo"),
	("OBJECT_FIREFLY", "Firefly", "Firefly"),
	("OBJECT_BOX", "Box", "Box"),
	("OBJECT_FIRE", "Fire", "Fire"),
	("OBJECT_BUBBLE", "Bubble", "Bubble"),
	("OBJECT_NIW", "Niw", "Niw"),
	("OBJECT_TITE", "Tite", "Tite"),
	("OBJECT_REEBA", "Reeba", "Reeba"),
	("OBJECT_PEEHAT", "Peehat", "Peehat"),
	("OBJECT_KINGDODONGO", "Kingdodongo", "Kingdodongo"),
	("OBJECT_HORSE", "Horse", "Horse"),
	("OBJECT_ZF", "Zf", "Zf"),
	("OBJECT_GOMA", "Goma", "Goma"),
	("OBJECT_ZL1", "Zl1", "Zl1"),
	("OBJECT_GOL", "Gol", "Gol"),
	("OBJECT_DODOJR", "Dodojr", "Dodojr"),
	("OBJECT_TORCH2", "Torch2", "Torch2"),
	("OBJECT_BL", "Bl", "Bl"),
	("OBJECT_TP", "Tp", "Tp"),
	("OBJECT_OA1", "Oa1", "Oa1"),
	("OBJECT_ST", "St", "St"),
	("OBJECT_BW", "Bw", "Bw"),
	("OBJECT_EI", "Ei", "Ei"),
	("OBJECT_HORSE_NORMAL", "Horse Normal", "Horse Normal"),
	("OBJECT_OB1", "Ob1", "Ob1"),
	("OBJECT_O_ANIME", "O Anime", "O Anime"),
	("OBJECT_SPOT04_OBJECTS", "Spot04 Objects", "Spot04 Objects"),
	("OBJECT_DDAN_OBJECTS", "Ddan Objects", "Ddan Objects"),
	("OBJECT_HIDAN_OBJECTS", "Hidan Objects", "Hidan Objects"),
	("OBJECT_HORSE_GANON", "Horse Ganon", "Horse Ganon"),
	("OBJECT_OA2", "Oa2", "Oa2"),
	("OBJECT_SPOT00_OBJECTS", "Spot00 Objects", "Spot00 Objects"),
	("OBJECT_MB", "Mb", "Mb"),
	("OBJECT_BOMBF", "Bombf", "Bombf"),
	("OBJECT_SK2", "Sk2", "Sk2"),
	("OBJECT_OE1", "Oe1", "Oe1"),
	("OBJECT_OE_ANIME", "Oe Anime", "Oe Anime"),
	("OBJECT_OE2", "Oe2", "Oe2"),
	("OBJECT_YDAN_OBJECTS", "Ydan Objects", "Ydan Objects"),
	("OBJECT_GND", "Gnd", "Gnd"),
	("OBJECT_AM", "Am", "Am"),
	("OBJECT_DEKUBABA", "Dekubaba", "Dekubaba"),
	("OBJECT_OA3", "Oa3", "Oa3"),
	("OBJECT_OA4", "Oa4", "Oa4"),
	("OBJECT_OA5", "Oa5", "Oa5"),
	("OBJECT_OA6", "Oa6", "Oa6"),
	("OBJECT_OA7", "Oa7", "Oa7"),
	("OBJECT_JJ", "Jj", "Jj"),
	("OBJECT_OA8", "Oa8", "Oa8"),
	("OBJECT_OA9", "Oa9", "Oa9"),
	("OBJECT_OB2", "Ob2", "Ob2"),
	("OBJECT_OB3", "Ob3", "Ob3"),
	("OBJECT_OB4", "Ob4", "Ob4"),
	("OBJECT_HORSE_ZELDA", "Horse Zelda", "Horse Zelda"),
	("OBJECT_OPENING_DEMO1", "Opening Demo1", "Opening Demo1"),
	("OBJECT_WARP1", "Warp1", "Warp1"),
	("OBJECT_B_HEART", "B Heart", "B Heart"),
	("OBJECT_DEKUNUTS", "Dekunuts", "Dekunuts"),
	("OBJECT_OE3", "Oe3", "Oe3"),
	("OBJECT_OE4", "Oe4", "Oe4"),
	("OBJECT_MENKURI_OBJECTS", "Menkuri Objects", "Menkuri Objects"),
	("OBJECT_OE5", "Oe5", "Oe5"),
	("OBJECT_OE6", "Oe6", "Oe6"),
	("OBJECT_OE7", "Oe7", "Oe7"),
	("OBJECT_OE8", "Oe8", "Oe8"),
	("OBJECT_OE9", "Oe9", "Oe9"),
	("OBJECT_OE10", "Oe10", "Oe10"),
	("OBJECT_OE11", "Oe11", "Oe11"),
	("OBJECT_OE12", "Oe12", "Oe12"),
	("OBJECT_VALI", "Vali", "Vali"),
	("OBJECT_OA10", "Oa10", "Oa10"),
	("OBJECT_OA11", "Oa11", "Oa11"),
	("OBJECT_MIZU_OBJECTS", "Mizu Objects", "Mizu Objects"),
	("OBJECT_FHG", "Fhg", "Fhg"),
	("OBJECT_OSSAN", "Ossan", "Ossan"),
	("OBJECT_MORI_HINERI1", "Mori Hineri1", "Mori Hineri1"),
	("OBJECT_BB", "Bb", "Bb"),
	("OBJECT_TOKI_OBJECTS", "Toki Objects", "Toki Objects"),
	("OBJECT_YUKABYUN", "Yukabyun", "Yukabyun"),
	("OBJECT_ZL2", "Zl2", "Zl2"),
	("OBJECT_MJIN", "Mjin", "Mjin"),
	("OBJECT_MJIN_FLASH", "Mjin Flash", "Mjin Flash"),
	("OBJECT_MJIN_DARK", "Mjin Dark", "Mjin Dark"),
	("OBJECT_MJIN_FLAME", "Mjin Flame", "Mjin Flame"),
	("OBJECT_MJIN_ICE", "Mjin Ice", "Mjin Ice"),
	("OBJECT_MJIN_SOUL", "Mjin Soul", "Mjin Soul"),
	("OBJECT_MJIN_WIND", "Mjin Wind", "Mjin Wind"),
	("OBJECT_MJIN_OKA", "Mjin Oka", "Mjin Oka"),
	("OBJECT_HAKA_OBJECTS", "Haka Objects", "Haka Objects"),
	("OBJECT_SPOT06_OBJECTS", "Spot06 Objects", "Spot06 Objects"),
	("OBJECT_ICE_OBJECTS", "Ice Objects", "Ice Objects"),
	("OBJECT_RELAY_OBJECTS", "Relay Objects", "Relay Objects"),
	("OBJECT_PO_FIELD", "Po Field", "Po Field"),
	("OBJECT_PO_COMPOSER", "Po Composer", "Po Composer"),
	("OBJECT_MORI_HINERI1A", "Mori Hineri1a", "Mori Hineri1a"),
	("OBJECT_MORI_HINERI2", "Mori Hineri2", "Mori Hineri2"),
	("OBJECT_MORI_HINERI2A", "Mori Hineri2a", "Mori Hineri2a"),
	("OBJECT_MORI_OBJECTS", "Mori Objects", "Mori Objects"),
	("OBJECT_MORI_TEX", "Mori Tex", "Mori Tex"),
	("OBJECT_SPOT08_OBJ", "Spot08 Obj", "Spot08 Obj"),
	("OBJECT_WARP2", "Warp2", "Warp2"),
	("OBJECT_HATA", "Hata", "Hata"),
	("OBJECT_BIRD", "Bird", "Bird"),
	("OBJECT_WOOD02", "Wood02", "Wood02"),
	("OBJECT_LIGHTBOX", "Lightbox", "Lightbox"),
	("OBJECT_PU_BOX", "Pu Box", "Pu Box"),
	("OBJECT_TRAP", "Trap", "Trap"),
	("OBJECT_VASE", "Vase", "Vase"),
	("OBJECT_IM", "Im", "Im"),
	("OBJECT_TA", "Ta", "Ta"),
	("OBJECT_TK", "Tk", "Tk"),
	("OBJECT_XC", "Xc", "Xc"),
	("OBJECT_VM", "Vm", "Vm"),
	("OBJECT_BV", "Bv", "Bv"),
	("OBJECT_HAKACH_OBJECTS", "Hakach Objects", "Hakach Objects"),
	("OBJECT_EFC_CRYSTAL_LIGHT", "Efc Crystal Light", "Efc Crystal Light"),
	("OBJECT_EFC_FIRE_BALL", "Efc Fire Ball", "Efc Fire Ball"),
	("OBJECT_EFC_FLASH", "Efc Flash", "Efc Flash"),
	("OBJECT_EFC_LGT_SHOWER", "Efc Lgt Shower", "Efc Lgt Shower"),
	("OBJECT_EFC_STAR_FIELD", "Efc Star Field", "Efc Star Field"),
	("OBJECT_GOD_LGT", "God Lgt", "God Lgt"),
	("OBJECT_LIGHT_RING", "Light Ring", "Light Ring"),
	("OBJECT_TRIFORCE_SPOT", "Triforce Spot", "Triforce Spot"),
	("OBJECT_BDAN_OBJECTS", "Bdan Objects", "Bdan Objects"),
	("OBJECT_SD", "Sd", "Sd"),
	("OBJECT_RD", "Rd", "Rd"),
	("OBJECT_PO_SISTERS", "Po Sisters", "Po Sisters"),
	("OBJECT_HEAVY_OBJECT", "Heavy Object", "Heavy Object"),
	("OBJECT_GNDD", "Gndd", "Gndd"),
	("OBJECT_FD", "Fd", "Fd"),
	("OBJECT_DU", "Du", "Du"),
	("OBJECT_FW", "Fw", "Fw"),
	("OBJECT_MEDAL", "Medal", "Medal"),
	("OBJECT_HORSE_LINK_CHILD", "Horse Link Child", "Horse Link Child"),
	("OBJECT_SPOT02_OBJECTS", "Spot02 Objects", "Spot02 Objects"),
	("OBJECT_HAKA", "Haka", "Haka"),
	("OBJECT_RU1", "Ru1", "Ru1"),
	("OBJECT_SYOKUDAI", "Syokudai", "Syokudai"),
	("OBJECT_FD2", "Fd2", "Fd2"),
	("OBJECT_DH", "Dh", "Dh"),
	("OBJECT_RL", "Rl", "Rl"),
	("OBJECT_EFC_TW", "Efc Tw", "Efc Tw"),
	("OBJECT_DEMO_TRE_LGT", "Demo Tre Lgt", "Demo Tre Lgt"),
	("OBJECT_GI_KEY", "Gi Key", "Gi Key"),
	("OBJECT_MIR_RAY", "Mir Ray", "Mir Ray"),
	("OBJECT_BROB", "Brob", "Brob"),
	("OBJECT_GI_JEWEL", "Gi Jewel", "Gi Jewel"),
	("OBJECT_SPOT09_OBJ", "Spot09 Obj", "Spot09 Obj"),
	("OBJECT_SPOT18_OBJ", "Spot18 Obj", "Spot18 Obj"),
	("OBJECT_BDOOR", "Bdoor", "Bdoor"),
	("OBJECT_SPOT17_OBJ", "Spot17 Obj", "Spot17 Obj"),
	("OBJECT_SHOP_DUNGEN", "Shop Dungen", "Shop Dungen"),
	("OBJECT_NB", "Nb", "Nb"),
	("OBJECT_MO", "Mo", "Mo"),
	("OBJECT_SB", "Sb", "Sb"),
	("OBJECT_GI_MELODY", "Gi Melody", "Gi Melody"),
	("OBJECT_GI_HEART", "Gi Heart", "Gi Heart"),
	("OBJECT_GI_COMPASS", "Gi Compass", "Gi Compass"),
	("OBJECT_GI_BOSSKEY", "Gi Bosskey", "Gi Bosskey"),
	("OBJECT_GI_MEDAL", "Gi Medal", "Gi Medal"),
	("OBJECT_GI_NUTS", "Gi Nuts", "Gi Nuts"),
	("OBJECT_SA", "Sa", "Sa"),
	("OBJECT_GI_HEARTS", "Gi Hearts", "Gi Hearts"),
	("OBJECT_GI_ARROWCASE", "Gi Arrowcase", "Gi Arrowcase"),
	("OBJECT_GI_BOMBPOUCH", "Gi Bombpouch", "Gi Bombpouch"),
	("OBJECT_IN", "In", "In"),
	("OBJECT_TR", "Tr", "Tr"),
	("OBJECT_SPOT16_OBJ", "Spot16 Obj", "Spot16 Obj"),
	("OBJECT_OE1S", "Oe1s", "Oe1s"),
	("OBJECT_OE4S", "Oe4s", "Oe4s"),
	("OBJECT_OS_ANIME", "Os Anime", "Os Anime"),
	("OBJECT_GI_BOTTLE", "Gi Bottle", "Gi Bottle"),
	("OBJECT_GI_STICK", "Gi Stick", "Gi Stick"),
	("OBJECT_GI_MAP", "Gi Map", "Gi Map"),
	("OBJECT_OF1D_MAP", "Of1d Map", "Of1d Map"),
	("OBJECT_RU2", "Ru2", "Ru2"),
	("OBJECT_GI_SHIELD_1", "Gi Shield 1", "Gi Shield 1"),
	("OBJECT_DEKUJR", "Dekujr", "Dekujr"),
	("OBJECT_GI_MAGICPOT", "Gi Magicpot", "Gi Magicpot"),
	("OBJECT_GI_BOMB_1", "Gi Bomb 1", "Gi Bomb 1"),
	("OBJECT_OF1S", "Of1s", "Of1s"),
	("OBJECT_MA2", "Ma2", "Ma2"),
	("OBJECT_GI_PURSE", "Gi Purse", "Gi Purse"),
	("OBJECT_HNI", "Hni", "Hni"),
	("OBJECT_TW", "Tw", "Tw"),
	("OBJECT_RR", "Rr", "Rr"),
	("OBJECT_BXA", "Bxa", "Bxa"),
	("OBJECT_ANUBICE", "Anubice", "Anubice"),
	("OBJECT_GI_GERUDO", "Gi Gerudo", "Gi Gerudo"),
	("OBJECT_GI_ARROW", "Gi Arrow", "Gi Arrow"),
	("OBJECT_GI_BOMB_2", "Gi Bomb 2", "Gi Bomb 2"),
	("OBJECT_GI_EGG", "Gi Egg", "Gi Egg"),
	("OBJECT_GI_SCALE", "Gi Scale", "Gi Scale"),
	("OBJECT_GI_SHIELD_2", "Gi Shield 2", "Gi Shield 2"),
	("OBJECT_GI_HOOKSHOT", "Gi Hookshot", "Gi Hookshot"),
	("OBJECT_GI_OCARINA", "Gi Ocarina", "Gi Ocarina"),
	("OBJECT_GI_MILK", "Gi Milk", "Gi Milk"),
	("OBJECT_MA1", "Ma1", "Ma1"),
	("OBJECT_GANON", "Ganon", "Ganon"),
	("OBJECT_SST", "Sst", "Sst"),
	("OBJECT_NY_UNUSED", "Ny Unused", "Ny Unused"),
	("OBJECT_NY", "Ny", "Ny"),
	("OBJECT_FR", "Fr", "Fr"),
	("OBJECT_GI_PACHINKO", "Gi Pachinko", "Gi Pachinko"),
	("OBJECT_GI_BOOMERANG", "Gi Boomerang", "Gi Boomerang"),
	("OBJECT_GI_BOW", "Gi Bow", "Gi Bow"),
	("OBJECT_GI_GLASSES", "Gi Glasses", "Gi Glasses"),
	("OBJECT_GI_LIQUID", "Gi Liquid", "Gi Liquid"),
	("OBJECT_ANI", "Ani", "Ani"),
	("OBJECT_DEMO_6K", "Demo 6k", "Demo 6k"),
	("OBJECT_GI_SHIELD_3", "Gi Shield 3", "Gi Shield 3"),
	("OBJECT_GI_LETTER", "Gi Letter", "Gi Letter"),
	("OBJECT_SPOT15_OBJ", "Spot15 Obj", "Spot15 Obj"),
	("OBJECT_JYA_OBJ", "Jya Obj", "Jya Obj"),
	("OBJECT_GI_CLOTHES", "Gi Clothes", "Gi Clothes"),
	("OBJECT_GI_BEAN", "Gi Bean", "Gi Bean"),
	("OBJECT_GI_FISH", "Gi Fish", "Gi Fish"),
	("OBJECT_GI_SAW", "Gi Saw", "Gi Saw"),
	("OBJECT_GI_HAMMER", "Gi Hammer", "Gi Hammer"),
	("OBJECT_GI_GRASS", "Gi Grass", "Gi Grass"),
	("OBJECT_GI_LONGSWORD", "Gi Longsword", "Gi Longsword"),
	("OBJECT_SPOT01_OBJECTS", "Spot01 Objects", "Spot01 Objects"),
	("OBJECT_MD_UNUSED", "Md Unused", "Md Unused"),
	("OBJECT_MD", "Md", "Md"),
	("OBJECT_KM1", "Km1", "Km1"),
	("OBJECT_KW1", "Kw1", "Kw1"),
	("OBJECT_ZO", "Zo", "Zo"),
	("OBJECT_KZ", "Kz", "Kz"),
	("OBJECT_UMAJUMP", "Umajump", "Umajump"),
	("OBJECT_MASTERKOKIRI", "Masterkokiri", "Masterkokiri"),
	("OBJECT_MASTERKOKIRIHEAD", "Masterkokirihead", "Masterkokirihead"),
	("OBJECT_MASTERGOLON", "Mastergolon", "Mastergolon"),
	("OBJECT_MASTERZOORA", "Masterzoora", "Masterzoora"),
	("OBJECT_AOB", "Aob", "Aob"),
	("OBJECT_IK", "Ik", "Ik"),
	("OBJECT_AHG", "Ahg", "Ahg"),
	("OBJECT_CNE", "Cne", "Cne"),
	("OBJECT_GI_NIWATORI", "Gi Niwatori", "Gi Niwatori"),
	("OBJECT_SKJ", "Skj", "Skj"),
	("OBJECT_GI_BOTTLE_LETTER", "Gi Bottle Letter", "Gi Bottle Letter"),
	("OBJECT_BJI", "Bji", "Bji"),
	("OBJECT_BBA", "Bba", "Bba"),
	("OBJECT_GI_OCARINA_0", "Gi Ocarina 0", "Gi Ocarina 0"),
	("OBJECT_DS", "Ds", "Ds"),
	("OBJECT_ANE", "Ane", "Ane"),
	("OBJECT_BOJ", "Boj", "Boj"),
	("OBJECT_SPOT03_OBJECT", "Spot03 Object", "Spot03 Object"),
	("OBJECT_SPOT07_OBJECT", "Spot07 Object", "Spot07 Object"),
	("OBJECT_FZ", "Fz", "Fz"),
	("OBJECT_BOB", "Bob", "Bob"),
	("OBJECT_GE1", "Ge1", "Ge1"),
	("OBJECT_YABUSAME_POINT", "Yabusame Point", "Yabusame Point"),
	("OBJECT_GI_BOOTS_2", "Gi Boots 2", "Gi Boots 2"),
	("OBJECT_GI_SEED", "Gi Seed", "Gi Seed"),
	("OBJECT_GND_MAGIC", "Gnd Magic", "Gnd Magic"),
	("OBJECT_D_ELEVATOR", "D Elevator", "D Elevator"),
	("OBJECT_D_HSBLOCK", "D Hsblock", "D Hsblock"),
	("OBJECT_D_LIFT", "D Lift", "D Lift"),
	("OBJECT_MAMENOKI", "Mamenoki", "Mamenoki"),
	("OBJECT_GOROIWA", "Goroiwa", "Goroiwa"),
	("OBJECT_TORYO", "Toryo", "Toryo"),
	("OBJECT_DAIKU", "Daiku", "Daiku"),
	("OBJECT_NWC", "Nwc", "Nwc"),
	("OBJECT_BLKOBJ", "Blkobj", "Blkobj"),
	("OBJECT_GM", "Gm", "Gm"),
	("OBJECT_MS", "Ms", "Ms"),
	("OBJECT_HS", "Hs", "Hs"),
	("OBJECT_INGATE", "Ingate", "Ingate"),
	("OBJECT_LIGHTSWITCH", "Lightswitch", "Lightswitch"),
	("OBJECT_KUSA", "Kusa", "Kusa"),
	("OBJECT_TSUBO", "Tsubo", "Tsubo"),
	("OBJECT_GI_GLOVES", "Gi Gloves", "Gi Gloves"),
	("OBJECT_GI_COIN", "Gi Coin", "Gi Coin"),
	("OBJECT_KANBAN", "Kanban", "Kanban"),
	("OBJECT_GJYO_OBJECTS", "Gjyo Objects", "Gjyo Objects"),
	("OBJECT_OWL", "Owl", "Owl"),
	("OBJECT_MK", "Mk", "Mk"),
	("OBJECT_FU", "Fu", "Fu"),
	("OBJECT_GI_KI_TAN_MASK", "Gi Ki Tan Mask", "Gi Ki Tan Mask"),
	("OBJECT_GI_REDEAD_MASK", "Gi Redead Mask", "Gi Redead Mask"),
	("OBJECT_GI_SKJ_MASK", "Gi Skj Mask", "Gi Skj Mask"),
	("OBJECT_GI_RABIT_MASK", "Gi Rabit Mask", "Gi Rabit Mask"),
	("OBJECT_GI_TRUTH_MASK", "Gi Truth Mask", "Gi Truth Mask"),
	("OBJECT_GANON_OBJECTS", "Ganon Objects", "Ganon Objects"),
	("OBJECT_SIOFUKI", "Siofuki", "Siofuki"),
	("OBJECT_STREAM", "Stream", "Stream"),
	("OBJECT_MM", "Mm", "Mm"),
	("OBJECT_FA", "Fa", "Fa"),
	("OBJECT_OS", "Os", "Os"),
	("OBJECT_GI_EYE_LOTION", "Gi Eye Lotion", "Gi Eye Lotion"),
	("OBJECT_GI_POWDER", "Gi Powder", "Gi Powder"),
	("OBJECT_GI_MUSHROOM", "Gi Mushroom", "Gi Mushroom"),
	("OBJECT_GI_TICKETSTONE", "Gi Ticketstone", "Gi Ticketstone"),
	("OBJECT_GI_BROKENSWORD", "Gi Brokensword", "Gi Brokensword"),
	("OBJECT_JS", "Js", "Js"),
	("OBJECT_CS", "Cs", "Cs"),
	("OBJECT_GI_PRESCRIPTION", "Gi Prescription", "Gi Prescription"),
	("OBJECT_GI_BRACELET", "Gi Bracelet", "Gi Bracelet"),
	("OBJECT_GI_SOLDOUT", "Gi Soldout", "Gi Soldout"),
	("OBJECT_GI_FROG", "Gi Frog", "Gi Frog"),
	("OBJECT_MAG", "Mag", "Mag"),
	("OBJECT_DOOR_GERUDO", "Door Gerudo", "Door Gerudo"),
	("OBJECT_GT", "Gt", "Gt"),
	("OBJECT_EFC_ERUPC", "Efc Erupc", "Efc Erupc"),
	("OBJECT_ZL2_ANIME1", "Zl2 Anime1", "Zl2 Anime1"),
	("OBJECT_ZL2_ANIME2", "Zl2 Anime2", "Zl2 Anime2"),
	("OBJECT_GI_GOLONMASK", "Gi Golonmask", "Gi Golonmask"),
	("OBJECT_GI_ZORAMASK", "Gi Zoramask", "Gi Zoramask"),
	("OBJECT_GI_GERUDOMASK", "Gi Gerudomask", "Gi Gerudomask"),
	("OBJECT_GANON2", "Ganon2", "Ganon2"),
	("OBJECT_KA", "Ka", "Ka"),
	("OBJECT_TS", "Ts", "Ts"),
	("OBJECT_ZG", "Zg", "Zg"),
	("OBJECT_GI_HOVERBOOTS", "Gi Hoverboots", "Gi Hoverboots"),
	("OBJECT_GI_M_ARROW", "Gi M Arrow", "Gi M Arrow"),
	("OBJECT_DS2", "Ds2", "Ds2"),
	("OBJECT_EC", "Ec", "Ec"),
	("OBJECT_FISH", "Fish", "Fish"),
	("OBJECT_GI_SUTARU", "Gi Sutaru", "Gi Sutaru"),
	("OBJECT_GI_GODDESS", "Gi Goddess", "Gi Goddess"),
	("OBJECT_SSH", "Ssh", "Ssh"),
	("OBJECT_BIGOKUTA", "Bigokuta", "Bigokuta"),
	("OBJECT_BG", "Bg", "Bg"),
	("OBJECT_SPOT05_OBJECTS", "Spot05 Objects", "Spot05 Objects"),
	("OBJECT_SPOT12_OBJ", "Spot12 Obj", "Spot12 Obj"),
	("OBJECT_BOMBIWA", "Bombiwa", "Bombiwa"),
	("OBJECT_HINTNUTS", "Hintnuts", "Hintnuts"),
	("OBJECT_RS", "Rs", "Rs"),
	("OBJECT_SPOT00_BREAK", "Spot00 Break", "Spot00 Break"),
	("OBJECT_GLA", "Gla", "Gla"),
	("OBJECT_SHOPNUTS", "Shopnuts", "Shopnuts"),
	("OBJECT_GELDB", "Geldb", "Geldb"),
	("OBJECT_GR", "Gr", "Gr"),
	("OBJECT_DOG", "Dog", "Dog"),
	("OBJECT_JYA_IRON", "Jya Iron", "Jya Iron"),
	("OBJECT_JYA_DOOR", "Jya Door", "Jya Door"),
	("OBJECT_SPOT11_OBJ", "Spot11 Obj", "Spot11 Obj"),
	("OBJECT_KIBAKO2", "Kibako2", "Kibako2"),
	("OBJECT_DNS", "Dns", "Dns"),
	("OBJECT_DNK", "Dnk", "Dnk"),
	("OBJECT_GI_FIRE", "Gi Fire", "Gi Fire"),
	("OBJECT_GI_INSECT", "Gi Insect", "Gi Insect"),
	("OBJECT_GI_BUTTERFLY", "Gi Butterfly", "Gi Butterfly"),
	("OBJECT_GI_GHOST", "Gi Ghost", "Gi Ghost"),
	("OBJECT_GI_SOUL", "Gi Soul", "Gi Soul"),
	("OBJECT_BOWL", "Bowl", "Bowl"),
	("OBJECT_DEMO_KEKKAI", "Demo Kekkai", "Demo Kekkai"),
	("OBJECT_EFC_DOUGHNUT", "Efc Doughnut", "Efc Doughnut"),
	("OBJECT_GI_DEKUPOUCH", "Gi Dekupouch", "Gi Dekupouch"),
	("OBJECT_GANON_ANIME1", "Ganon Anime1", "Ganon Anime1"),
	("OBJECT_GANON_ANIME2", "Ganon Anime2", "Ganon Anime2"),
	("OBJECT_GANON_ANIME3", "Ganon Anime3", "Ganon Anime3"),
	("OBJECT_GI_RUPY", "Gi Rupy", "Gi Rupy"),
	("OBJECT_SPOT01_MATOYA", "Spot01 Matoya", "Spot01 Matoya"),
	("OBJECT_SPOT01_MATOYAB", "Spot01 Matoyab", "Spot01 Matoyab"),
	("OBJECT_MU", "Mu", "Mu"),
	("OBJECT_WF", "Wf", "Wf"),
	("OBJECT_SKB", "Skb", "Skb"),
	("OBJECT_GJ", "Gj", "Gj"),
	("OBJECT_GEFF", "Geff", "Geff"),
	("OBJECT_HAKA_DOOR", "Haka Door", "Haka Door"),
	("OBJECT_GS", "Gs", "Gs"),
	("OBJECT_PS", "Ps", "Ps"),
	("OBJECT_BWALL", "Bwall", "Bwall"),
	("OBJECT_COW", "Cow", "Cow"),
	("OBJECT_COB", "Cob", "Cob"),
	("OBJECT_GI_SWORD_1", "Gi Sword 1", "Gi Sword 1"),
	("OBJECT_DOOR_KILLER", "Door Killer", "Door Killer"),
	("OBJECT_OUKE_HAKA", "Ouke Haka", "Ouke Haka"),
	("OBJECT_TIMEBLOCK", "Timeblock", "Timeblock"),
]

ootEnumGlobalObject = [
	("Custom", "Custom", "Custom"),
	("0", "None", "None"),
	("gameplay_field_keep", "Overworld", "Overworld"),
	("gameplay_dangeon_keep", "Dungeon", "Dungeon"),
]

ootEnumNaviHints = [
	("Custom", "Custom", "Custom"),
	("0", "None", "None"),
	("elf_message_field", "Overworld", "Overworld"),
	("elf_message_ydan", "Dungeon", "Dungeon"),
]

class OOT_Actor:
	def __init__(self, actorID, position, rotation, actorParam, sceneSetups):
		self.actorID = actorID
		self.actorParam = actorParam
		self.sceneSetups = sceneSetups
		self.position = position
		self.rotation = rotation
	
	def toC(self):
		return 'ACTOR(' + str(self.actorID) + ', ' + \
			str(int(round(self.position[0]))) + ', ' + \
			str(int(round(self.position[1]))) + ', ' + \
			str(int(round(self.position[2]))) + ', ' + \
			str(int(round(math.degrees(self.rotation[0])))) + ', ' + \
			str(int(round(math.degrees(self.rotation[1])))) + ', ' + \
			str(int(round(math.degrees(self.rotation[2])))) + ', ' + \
			str(self.actorParam) + ')'

class OOT_Entrance:
	def __init__(self, position, rotation, room):
		self.room = room
		self.position = position
		self.rotation = rotation
	
	def toCStartPositions(self):
		return 'ENTRANCE(' +\
			str(int(round(self.position[0]))) + ', ' + \
			str(int(round(self.position[1]))) + ', ' + \
			str(int(round(self.position[2]))) + ', ' + \
			str(int(round(math.degrees(self.rotation[0])))) + ', ' + \
			str(int(round(math.degrees(self.rotation[1])))) + ', ' + \
			str(int(round(math.degrees(self.rotation[2])))) + ')'

	def toCEntranceList(self):
		pass

class OOT_Light:
	def __init__(self):
		self.ambient = (0,0,0)
		self.diffuse0 = (0,0,0)
		self.diffuseDir0 = (0,0,0)
		self.diffuse1 = (0,0,0)
		self.diffuseDir1 = (0,0,0)
		self.fogColor = (0,0,0)
		self.fogDistance = 0
		self.transitionSpeed = 0
		self.drawDistance = 0

class OOT_Scene:
	def __init__(self, name):
		self.name = toAlnum(name)
		self.rooms = []
		self.transitionActors = []
		self.lights = []

		# Skybox
		self.skyboxID = None
		self.skyboxCloudiness = None
		self.skyboxLighting = None

		# Camera
		self.mapLocation = None
		self.cameraMode = None

class OOT_Room:
	def __init__(self, index, name):
		self.name = toAlnum(name)
		self.collision = None
		self.index = index
		self.actors = []
		self.transitionActors = []
		self.water_boxes = []

		self.entrances = []
		self.exits = []
		self.pathways = []

		# Room behaviour
		self.disableSunSongEffect = False
		self.disableActionJumping = False
		self.disableWarpSongs = False
		self.showInvisibleActors = False
		self.linkIdleMode = None

		self.customBehaviourX = None
		self.customBehaviourY = None

		# Wind 
		self.setWind = False
		self.windVector = mathutils.Vector((1,1,1))

		# Time
		self.timeValue = 0xFFFF
		self.timeSpeed = 0xA

		# Skybox
		self.disableSkybox = False
		self.disableSunMoon = False

		# Echo
		self.echo = 0x00

	def toCWindCommand(self):
		normalizedVector = convertNormalizedVectorToShort(self.windVector.normalized()[0:2])
		magnitude = clampShort(self.windVector.length)

		return "SET_WIND(" + '0x' + format(normalizedVector[0], 'X') + ', ' +\
			'0x' + format(normalizedVector[1], 'X') + ', ' +\
			'0x' + format(normalizedVector[2], 'X') + ', ' +\
			'0x' + format(magnitude, 'X') + ')'

	def toCScript(self, includeRooms):
		data = ''
		data += '\tAREA(' + str(self.index) + ', ' + self.geolayout.name + '),\n'
		for warpNode in self.warpNodes:
			data += '\t\t' + warpNode + ',\n'
		for obj in self.objects:
			data += '\t\t' + obj.to_c() + ',\n'
		data += '\t\tTERRAIN(' + self.collision.name + '),\n'
		if includeRooms:
			data += '\t\tROOMS(' + self.collision.rooms_name() + '),\n'
		data += '\t\tMACRO_OBJECTS(' + self.macros_name() + '),\n'
		if self.music_seq is None:
			data += '\t\tSTOP_MUSIC(0),\n'
		else:
			data += '\t\tSET_BACKGROUND_MUSIC(' + self.music_preset + ', ' + self.music_seq + '),\n'
		if self.startDialog is not None:
			data += '\t\tSHOW_DIALOG(0x00, ' + self.startDialog + '),\n'
		data += '\t\tTERRAIN_TYPE(' + self.terrain_type + '),\n'
		data += '\tEND_AREA(),\n\n'
		return data
	
	def toCPathways(self):
		data = ''
		for spline in self.pathways:
			data += spline.to_c() + '\n'
		return data
	
	def toCDefSplines(self):
		data = ''
		for spline in self.splines:
			data += spline.to_c_def()
		return data

class OOT_WaterBox(BoxEmpty):
	def __init__(self, waterBoxType, position, scale, emptyScale):
		self.waterBoxType = waterBoxType
		BoxEmpty.__init__(self, position, scale, emptyScale)
	
	def to_c(self):
		data = 'WATER_BOX(' + \
			str(self.waterBoxType) + ', ' + \
			str(int(round(self.low[0]))) + ', ' + \
			str(int(round(self.low[1]))) + ', ' + \
			str(int(round(self.high[0]))) + ', ' + \
			str(int(round(self.high[1]))) + ', ' + \
			str(int(round(self.height))) + '),\n'
		return data

def exportAreaCommon(areaObj, transformMatrix, geolayout, collision, name):
	bpy.ops.object.select_all(action = 'DESELECT')
	areaObj.select_set(True)

	if not areaObj.noMusic:
		if areaObj.musicSeqEnum != 'Custom':
			musicSeq = areaObj.musicSeqEnum
		else:
			musicSeq = areaObj.music_seq
	else:
		musicSeq = None

	if areaObj.terrainEnum != 'Custom':
		terrainType = areaObj.terrainEnum
	else:
		terrainType = areaObj.terrain_type

	area = SM64_Area(areaObj.areaIndex, musicSeq, areaObj.music_preset, 
		terrainType, geolayout, collision, 
		[areaObj.warpNodes[i].to_c() for i in range(len(areaObj.warpNodes))],
		name, areaObj.startDialog if areaObj.showStartDialog else None)

	start_process_sm64_objects(areaObj, area, transformMatrix, False)

	return area

# These are all done in reference to refresh 8
def handleRefreshDiffModelIDs(modelID):
	if bpy.context.scene.refreshVer == 'Refresh 8' or \
		bpy.context.scene.refreshVer == 'Refresh 7':
		pass
	elif bpy.context.scene.refreshVer == 'Refresh 6':
		if modelID == 'MODEL_TWEESTER':
			modelID = 'MODEL_TORNADO'
	elif bpy.context.scene.refreshVer == 'Refresh 5' or \
		bpy.context.scene.refreshVer == 'Refresh 4' or \
		bpy.context.scene.refreshVer == 'Refresh 3':
		if modelID == 'MODEL_TWEESTER':
			modelID = 'MODEL_TORNADO'
		elif modelID == 'MODEL_WAVE_TRAIL':
			modelID = "MODEL_WATER_WAVES"
		elif modelID == 'MODEL_IDLE_WATER_WAVE':
			modelID = 'MODEL_WATER_WAVES_SURF'
		elif modelID == 'MODEL_SMALL_WATER_SPLASH':
			modelID = 'MODEL_SPOT_ON_GROUND'

	return modelID

def handleRefreshDiffSpecials(preset):
	if bpy.context.scene.refreshVer == 'Refresh 8' or \
		bpy.context.scene.refreshVer == 'Refresh 7' or \
		bpy.context.scene.refreshVer == 'Refresh 6' or \
		bpy.context.scene.refreshVer == 'Refresh 5' or \
		bpy.context.scene.refreshVer == 'Refresh 4' or \
		bpy.context.scene.refreshVer == 'Refresh 3':
		pass
	return preset

def handleRefreshDiffMacros(preset):
	if bpy.context.scene.refreshVer == 'Refresh 8' or \
		bpy.context.scene.refreshVer == 'Refresh 7' or \
		bpy.context.scene.refreshVer == 'Refresh 6' or \
		bpy.context.scene.refreshVer == 'Refresh 5' or \
		bpy.context.scene.refreshVer == 'Refresh 4' or \
		bpy.context.scene.refreshVer == 'Refresh 3':
		pass
	return preset

def start_process_sm64_objects(obj, area, transformMatrix, specialsOnly):
	#spaceRotation = mathutils.Quaternion((1, 0, 0), math.radians(90.0)).to_matrix().to_4x4()

	# We want translations to be relative to area obj, but rotation/scale to be world space
	translation, rotation, scale = obj.matrix_world.decompose()
	process_sm64_objects(obj, area, 
		mathutils.Matrix.Translation(translation), transformMatrix, specialsOnly)

def process_sm64_objects(obj, area, rootMatrix, transformMatrix, specialsOnly):
	translation, originalRotation, scale = \
			(transformMatrix @ rootMatrix.inverted() @ obj.matrix_world).decompose()

	finalTransform = mathutils.Matrix.Translation(translation) @ \
		originalRotation.to_matrix().to_4x4() @ \
		mathutils.Matrix.Diagonal(scale).to_4x4()

	# Hacky solution to handle Z-up to Y-up conversion
	rotation = originalRotation @ mathutils.Quaternion((1, 0, 0), math.radians(90.0))

	if obj.data is None:
		if obj.sm64_obj_type == 'Area Root' and obj.areaIndex != area.index:
			return
		if specialsOnly:
			if obj.sm64_obj_type == 'Special':
				preset = obj.sm64_special_enum if obj.sm64_special_enum != 'Custom' else obj.sm64_obj_preset
				preset = handleRefreshDiffSpecials(preset)
				area.specials.append(SM64_Special_Object(preset, translation, 
					rotation.to_euler() if obj.sm64_obj_set_yaw else None, 
					obj.sm64_obj_bparam if (obj.sm64_obj_set_yaw and obj.sm64_obj_set_bparam) else None))
			elif obj.sm64_obj_type == 'Water Box':
				checkIdentityRotation(obj, rotation, False)
				area.water_boxes.append(CollisionWaterBox(obj.waterBoxType, 
					translation, scale, obj.empty_display_size))
		else:
			if obj.sm64_obj_type == 'Object':
				modelID = obj.sm64_model_enum if obj.sm64_model_enum != 'Custom' else obj.sm64_obj_model
				modelID = handleRefreshDiffModelIDs(modelID)
				behaviour = func_map[bpy.context.scene.refreshVer][obj.sm64_behaviour_enum] if \
					obj.sm64_behaviour_enum != 'Custom' else obj.sm64_obj_behaviour
				area.objects.append(SM64_Object(modelID, translation, rotation.to_euler(), 
					behaviour, obj.sm64_obj_bparam, get_act_string(obj)))
			elif obj.sm64_obj_type == 'Macro':
				macro = obj.sm64_macro_enum if obj.sm64_macro_enum != 'Custom' else obj.sm64_obj_preset
				area.macros.append(SM64_Macro_Object(macro, translation, rotation.to_euler(), 
					obj.sm64_obj_bparam if obj.sm64_obj_set_bparam else None))
			elif obj.sm64_obj_type == 'Mario Start':
				mario_start = SM64_Mario_Start(obj.sm64_obj_mario_start_area, translation, rotation.to_euler())
				area.objects.append(mario_start)
				area.mario_start = mario_start
			elif obj.sm64_obj_type == 'Trajectory':
				pass
			elif obj.sm64_obj_type == 'Whirpool':
				area.objects.append(SM64_Whirpool(obj.whirlpool_index, 
					obj.whirpool_condition, obj.whirpool_strength, translation))
			elif obj.sm64_obj_type == 'Camera Volume':
				checkIdentityRotation(obj, rotation, True)
				if obj.cameraVolumeGlobal:
					triggerIndex = -1
				else:
					triggerIndex = area.index
				area.cameraVolumes.append(CameraVolume(triggerIndex, obj.cameraVolumeFunction,
					translation, rotation.to_euler(), scale, obj.empty_display_size))

	elif not specialsOnly and isCurveValid(obj):
		area.splines.append(convertSplineObject(area.name + '_spline_' + obj.name , obj, finalTransform))
			

	for child in obj.children:
		process_sm64_objects(child, area, rootMatrix, transformMatrix, specialsOnly)

def get_act_string(obj):
	if obj.sm64_obj_use_act1 and obj.sm64_obj_use_act2 and obj.sm64_obj_use_act3 and \
		obj.sm64_obj_use_act4 and obj.sm64_obj_use_act5 and obj.sm64_obj_use_act6:
		return 0x1F
	elif not obj.sm64_obj_use_act1 and not obj.sm64_obj_use_act2 and not obj.sm64_obj_use_act3 and \
		not obj.sm64_obj_use_act4 and not obj.sm64_obj_use_act5 and not obj.sm64_obj_use_act6:
		return 0
	else:
		data = ''
		if obj.sm64_obj_use_act1:
			data += (" | " if len(data) > 0 else '') + 'ACT_1'
		if obj.sm64_obj_use_act2:
			data += (" | " if len(data) > 0 else '') + 'ACT_2'
		if obj.sm64_obj_use_act3:
			data += (" | " if len(data) > 0 else '') + 'ACT_3'
		if obj.sm64_obj_use_act4:
			data += (" | " if len(data) > 0 else '') + 'ACT_4'
		if obj.sm64_obj_use_act5:
			data += (" | " if len(data) > 0 else '') + 'ACT_5'
		if obj.sm64_obj_use_act6:
			data += (" | " if len(data) > 0 else '') + 'ACT_6'
		return data

class OOT_SearchActorIDEnumOperator(bpy.types.Operator):
	bl_idname = "object.oot_search_actor_id_enum_operator"
	bl_label = "Search Actor IDs"
	bl_property = "ootEnumActorID"
	bl_options = {'REGISTER', 'UNDO'} 

	ootEnumActorID : bpy.props.EnumProperty(items = ootEnumActorID, default = "ACTOR_PLAYER")

	def execute(self, context):
		context.object.ootActorProperty.actorID = self.ootEnumActorID
		bpy.context.region.tag_redraw()
		self.report({'INFO'}, "Selected: " + self.ootEnumActorID)
		return {'FINISHED'}

	def invoke(self, context, event):
		context.window_manager.invoke_search_popup(self)
		return {'RUNNING_MODAL'}

class OOT_SearchMusicSeqEnumOperator(bpy.types.Operator):
	bl_idname = "object.oot_search_music_seq_enum_operator"
	bl_label = "Search Music Sequence"
	bl_property = "ootMusicSeq"
	bl_options = {'REGISTER', 'UNDO'} 

	ootMusicSeq : bpy.props.EnumProperty(items = ootEnumMusicSeq, default = "NA_BGM_FIELD1")
	headerIndex : bpy.props.IntProperty(default = 0, min = 0)

	def execute(self, context):
		if self.headerIndex == 0:
			sceneHeader = context.object.ootSceneHeader
		elif self.headerIndex == 1:
			sceneHeader = context.object.ootAlternateSceneHeaders.childNightHeader
		elif self.headerIndex == 2:
			sceneHeader = context.object.ootAlternateSceneHeaders.adultDayHeader
		elif self.headerIndex == 3:
			sceneHeader = context.object.ootAlternateSceneHeaders.adultNightHeader
		else:
			sceneHeader = context.object.ootAlternateSceneHeaders.cutsceneHeaders[self.headerIndex - 4]

		sceneHeader.musicSeq = self.ootMusicSeq
		bpy.context.region.tag_redraw()
		self.report({'INFO'}, "Selected: " + self.ootMusicSeq)
		return {'FINISHED'}

	def invoke(self, context, event):
		context.window_manager.invoke_search_popup(self)
		return {'RUNNING_MODAL'}

class OOT_SearchObjectEnumOperator(bpy.types.Operator):
	bl_idname = "object.oot_search_object_enum_operator"
	bl_label = "Search Object ID"
	bl_property = "ootObjectID"
	bl_options = {'REGISTER', 'UNDO'} 

	ootObjectID : bpy.props.EnumProperty(items = ootEnumObjectID, default = "OBJECT_HUMAN")
	headerIndex : bpy.props.IntProperty(default = 0, min = 0)
	index : bpy.props.IntProperty(default = 0, min = 0)

	def execute(self, context):
		if self.headerIndex == 0:
			roomHeader = context.object.ootRoomHeader
		elif self.headerIndex == 1:
			roomHeader = context.object.ootAlternateRoomHeaders.childNightHeader
		elif self.headerIndex == 2:
			roomHeader = context.object.ootAlternateRoomHeaders.adultDayHeader
		elif self.headerIndex == 3:
			roomHeader = context.object.ootAlternateRoomHeaders.adultNightHeader
		else:
			roomHeader = context.object.ootAlternateRoomHeaders.cutsceneHeaders[self.headerIndex - 4]

		roomHeader.objectList[self.index].objectID = self.ootObjectID
		bpy.context.region.tag_redraw()
		self.report({'INFO'}, "Selected: " + self.ootObjectID)
		return {'FINISHED'}

	def invoke(self, context, event):
		context.window_manager.invoke_search_popup(self)
		return {'RUNNING_MODAL'}

class OOTObjectPanel(bpy.types.Panel):
	bl_label = "Object Inspector"
	bl_idname = "OBJECT_PT_OOT_Object_Inspector"
	bl_space_type = 'PROPERTIES'
	bl_region_type = 'WINDOW'
	bl_context = "object"
	bl_options = {'HIDE_HEADER'} 

	@classmethod
	def poll(cls, context):
		return context.scene.gameEditorMode == "OOT" and (context.object is not None and context.object.data is None)

	def draw(self, context):
		box = self.layout.box()
		box.box().label(text = 'OOT Object Inspector')
		obj = context.object
		prop_split(box, obj, 'ootEmptyType', 'Object Type')
		if obj.ootEmptyType == 'Actor':
			drawActorProperty(box, obj.ootActorProperty)

		elif obj.ootEmptyType == 'Water Box':
			drawWaterBoxProperty(box, obj.ootWaterBoxProperty)

		elif obj.ootEmptyType == 'Scene':
			drawSceneHeaderProperty(box, obj.ootSceneHeader, None, None)
			drawAlternateSceneHeaderProperty(box, obj.ootAlternateSceneHeaders)

		elif obj.ootEmptyType == 'Room':
			drawRoomHeaderProperty(box, obj.ootRoomHeader, None, None)
			drawAlternateRoomHeaderProperty(box, obj.ootAlternateRoomHeaders)
		
		elif obj.ootEmptyType == 'Entrance':
			if obj.parent is not None and obj.parent.data is None and obj.parent.ootEmptyType == "Room":
				box.label(text = 'Room Index: ' + str(obj.parent.ootRoomHeader.roomIndex))
			else:
				box.label(text = "Entrance must be parented to a Room.")
		
		elif obj.ootEmptyType == 'None':
			box.box().label(text = 'This can be used as an empty transform node in a geolayout hierarchy.')

def onUpdateObjectType(self, context):
	if self.sm64_obj_type == 'Water Box':
		self.empty_display_type = "CUBE"

class OOTSceneHeaderProperty(bpy.types.PropertyGroup):
	expandTab : bpy.props.BoolProperty(name = "Expand Tab")
	usePreviousHeader : bpy.props.BoolProperty(name = "Use Previous Header", default = True)

	globalObject : bpy.props.EnumProperty(name = "Global Object", default = "gameplay_field_keep", items = ootEnumGlobalObject)
	globalObjectCustom : bpy.props.StringProperty(name = "Global Object Custom", default = "0x00")
	naviCup : bpy.props.EnumProperty(name = "Navi Hints", default = 'elf_message_field', items = ootEnumNaviHints)
	naviCupCustom : bpy.props.StringProperty(name = "Navi Hints Custom", default = '0x00')

	skyboxID : bpy.props.EnumProperty(name = "Skybox", items = ootEnumSkybox, default = "None")
	skyboxIDCustom : bpy.props.StringProperty(name = "Skybox ID", default = '0')
	skyboxCloudiness : bpy.props.EnumProperty(name = "Cloudiness", items = ootEnumCloudiness, default = "Sunny")
	skyboxCloudinessCustom : bpy.props.StringProperty(name = "Cloudiness ID", default = '0x00')
	skyboxLighting : bpy.props.EnumProperty(name = "Skybox Lighting", items = ootEnumSkyboxLighting, default = "Time Of Day")
	skyboxLightingCustom : bpy.props.StringProperty(name = "Skybox Lighting Custom", default = '0x00')

	mapLocation : bpy.props.EnumProperty(name = "Map Location", items = ootEnumMapLocation, default = "Hyrule Field")
	mapLocationCustom : bpy.props.StringProperty(name = "Skybox Lighting Custom", default = '0x00')
	cameraMode : bpy.props.EnumProperty(name = "Camera Mode", items = ootEnumCameraMode, default = "Default")
	cameraModeCustom : bpy.props.StringProperty(name = "Camera Mode Custom", default = '0x00')

	musicSeq : bpy.props.EnumProperty(name = "Music Sequence", items = ootEnumMusicSeq, default = 'NA_BGM_FIELD1')
	musicSeqCustom : bpy.props.StringProperty(name = "Music Sequence ID", default = '0x00')
	nightSeq : bpy.props.EnumProperty(name = "Nighttime SFX", items = ootEnumNightSeq, default = "Standard night [day and night cycle]")
	nightSeqCustom : bpy.props.StringProperty(name = "Nighttime SFX ID", default = '0x00')

	lightList : bpy.props.CollectionProperty(type = OOTLightProperty, name = 'Lighting List')

def drawSceneHeaderProperty(layout, sceneProp, dropdownLabel, headerIndex):
	if dropdownLabel is not None:
		layout.prop(sceneProp, 'expandTab', text = dropdownLabel, 
			icon = 'TRIA_DOWN' if sceneProp.expandTab else 'TRIA_RIGHT')
		if not sceneProp.expandTab:
			return

	if headerIndex is not None and headerIndex > 0 and headerIndex < 4:
		layout.prop(sceneProp, "usePreviousHeader", text = "Use Previous Header")
		if sceneProp.usePreviousHeader:
			return

	general = layout.box()
	general.box().label(text = "General")
	drawEnumWithCustom(general, sceneProp, 'globalObject', "Global Object", "")
	drawEnumWithCustom(general, sceneProp, 'naviCup', "Navi Hints", "")

	skyboxAndSound = layout.box()
	skyboxAndSound.box().label(text = "Skybox And Sound")
	drawEnumWithCustom(skyboxAndSound, sceneProp, 'skyboxID', "Skybox", "")
	drawEnumWithCustom(skyboxAndSound, sceneProp, 'skyboxCloudiness', "Cloudiness", "")
	drawEnumWithCustom(skyboxAndSound, sceneProp, 'musicSeq', "Music Sequence", "")
	musicSearch = skyboxAndSound.operator(OOT_SearchMusicSeqEnumOperator.bl_idname, icon = 'VIEWZOOM')
	musicSearch.headerIndex = headerIndex if headerIndex is not None else 0
	drawEnumWithCustom(skyboxAndSound, sceneProp, 'nightSeq', "Nighttime SFX", "")

	cameraAndWorldMap = layout.box()
	cameraAndWorldMap.box().label(text = "Camera And World Map")
	drawEnumWithCustom(cameraAndWorldMap, sceneProp, 'mapLocation', "Map Location", "")
	drawEnumWithCustom(cameraAndWorldMap, sceneProp, 'cameraMode', "Camera Mode", "")

	lighting = layout.box()
	lighting.box().label(text = "Lighting List")
	drawAddButton(lighting, len(sceneProp.lightList), "Light", headerIndex)
	for i in range(len(sceneProp.lightList)):
		drawLightProperty(lighting, sceneProp.lightList[i], i, headerIndex)

	if headerIndex is not None and headerIndex > 3:
		drawCollectionOps(layout, headerIndex - 4, "Scene", None)

class OOTObjectProperty(bpy.types.PropertyGroup):
	expandTab : bpy.props.BoolProperty(name = "Expand Tab")
	objectID : bpy.props.EnumProperty(items = ootEnumObjectID, default = 'OBJECT_HUMAN')

class OOTRoomHeaderProperty(bpy.types.PropertyGroup):
	expandTab : bpy.props.BoolProperty(name = "Expand Tab")
	usePreviousHeader : bpy.props.BoolProperty(name = "Use Previous Header", default = True)

	roomIndex : bpy.props.IntProperty(name = 'Room Index', default = 0, min = 0)
	disableSunSongEffect : bpy.props.BoolProperty(name = "Disable Sun Song Effect")
	disableActionJumping : bpy.props.BoolProperty(name = "Disable Action Jumping")
	disableWarpSongs : bpy.props.BoolProperty(name = "Disable Warp Songs")
	showInvisibleActors : bpy.props.BoolProperty(name = "Show Invisible Actors")
	linkIdleMode : bpy.props.EnumProperty(name = "Link Idle Mode",items = ootEnumLinkIdle, default = "Default")
	linkIdleModeCustom : bpy.props.StringProperty(name = "Link Idle Mode Custom", default = '0x00')

	useCustomBehaviourX : bpy.props.BoolProperty(name = "Use Custom Behaviour X")
	useCustomBehaviourY : bpy.props.BoolProperty(name = "Use Custom Behaviour Y")

	customBehaviourX : bpy.props.StringProperty(name = 'Custom Behaviour X', default = '0x00')

	customBehaviourY : bpy.props.StringProperty(name = 'Custom Behaviour Y', default = '0x00')

	setWind : bpy.props.BoolProperty(name = "Set Wind")
	windVector : bpy.props.FloatVectorProperty(name = "Wind Vector", size = 3)

	timeValue : bpy.props.FloatProperty(name = "Time", default = 24, min = 0, max = 24) #0xFFFF
	timeSpeed : bpy.props.FloatProperty(name = "Time Speed", default = 1, min = 0) #0xA

	disableSkybox : bpy.props.BoolProperty(name = "Disable Skybox")
	disableSunMoon : bpy.props.BoolProperty(name = "Disable Sun/Moon")

	echo : bpy.props.StringProperty(name = "Echo", default = '0x00')

	objectList : bpy.props.CollectionProperty(type = OOTObjectProperty)

def drawRoomHeaderProperty(layout, roomProp, dropdownLabel, headerIndex):

	if dropdownLabel is not None:
		layout.prop(roomProp, 'expandTab', text = dropdownLabel, 
			icon = 'TRIA_DOWN' if roomProp.expandTab else 'TRIA_RIGHT')
		if not roomProp.expandTab:
			return

	if headerIndex is not None and headerIndex > 0 and headerIndex < 4:
		layout.prop(roomProp, "usePreviousHeader", text = "Use Previous Header")
		if roomProp.usePreviousHeader:
			return

	if headerIndex is None or headerIndex == 0:
		prop_split(layout, roomProp, 'roomIndex', 'Room Index')

	skyboxAndTime = layout.box()
	skyboxAndTime.box().label(text = "Skybox And Time")

	# Time
	prop_split(skyboxAndTime, roomProp, "timeValue", "Time Of Day")
	prop_split(skyboxAndTime, roomProp, "timeSpeed", "Time Speed")

	# Echo
	prop_split(skyboxAndTime, roomProp, "echo", "Echo")

	# Skybox
	skyboxAndTime.prop(roomProp, "disableSkybox", text = "Disable Skybox")
	skyboxAndTime.prop(roomProp, "disableSunMoon", text = "Disable Sun/Moon")

	# Wind 
	windBox = layout.box()
	windBox.box().label(text = 'Wind')
	windBox.prop(roomProp, "setWind", text = "Set Wind")
	if roomProp.setWind:
		prop_split(windBox, roomProp, "windVector", "Wind Vector")

	behaviourBox = layout.box()
	behaviourBox.box().label(text = 'Behaviour')
	behaviourBox.prop(roomProp, "disableSunSongEffect", text = "Disable Sun Song Effect")
	behaviourBox.prop(roomProp, "disableActionJumping", text = "Disable Action Jumping")
	behaviourBox.prop(roomProp, "disableWarpSongs", text = "Disable Warp Songs")
	behaviourBox.prop(roomProp, "showInvisibleActors", text = "Show Invisible Actors")
	drawEnumWithCustom(behaviourBox, roomProp, 'linkIdleMode', "Link Idle Mode", "")

	objBox = layout.box()
	objBox.box().label(text = "Objects")
	drawAddButton(objBox, len(roomProp.objectList), "Object", headerIndex)
	for i in range(len(roomProp.objectList)):
		drawObjectProperty(objBox, roomProp.objectList[i], headerIndex, i)

	if headerIndex is not None and headerIndex > 3:
		drawCollectionOps(layout, headerIndex - 4, "Room", None)

def drawObjectProperty(layout, objectProp, headerIndex, index):
	objItemBox = layout.box()
	objItemBox.prop(objectProp, 'expandTab', text = str(objectProp.objectID), 
		icon = 'TRIA_DOWN' if objectProp.expandTab else \
		'TRIA_RIGHT')
	if objectProp.expandTab:
		objItemBox.box().label(text = "ID: " + objectProp.objectID)
		#prop_split(objItemBox, objectProp, "objectID", name = "ID")
		objSearch = objItemBox.operator(OOT_SearchObjectEnumOperator.bl_idname, icon = 'VIEWZOOM')
		objSearch.headerIndex = headerIndex if headerIndex is not None else 0
		objSearch.index = index
		drawCollectionOps(objItemBox, index, "Object", headerIndex)

class OOTActorHeaderItemProperty(bpy.types.PropertyGroup):
	headerIndex : bpy.props.IntProperty(name = "Scene Setup", min = 4, default = 4)
	expandTab : bpy.props.BoolProperty(name = "Expand Tab")

class OOTActorHeaderProperty(bpy.types.PropertyGroup):
	inAllSceneSetups : bpy.props.BoolProperty(name = "Actor Exists In All Scene Setups", default = True)
	childDayHeader : bpy.props.BoolProperty(name = "Child Day Header", default = True)
	childNightHeader : bpy.props.BoolProperty(name = "Child Night Header", default = True)
	adultDayHeader : bpy.props.BoolProperty(name = "Adult Day Header", default = True)
	adultNightHeader : bpy.props.BoolProperty(name = "Adult Night Header", default = True)
	cutsceneHeaders : bpy.props.CollectionProperty(type = OOTActorHeaderItemProperty)

def drawActorHeaderProperty(layout, headerProp):
	headerSetup = layout.box()
	headerSetup.box().label(text = "Alternate Headers")
	headerSetup.prop(headerProp, "inAllSceneSetups", text = "Actor Exists In All Scene Setups")
	if not headerProp.inAllSceneSetups:
		headerSetupBox = headerSetup.box()
		headerSetupBox.prop(headerProp, 'childDayHeader', text = "Child Day")
		headerSetupBox.prop(headerProp, 'childNightHeader', text = "Child Night")
		headerSetupBox.prop(headerProp, 'adultDayHeader', text = "Adult Day")
		headerSetupBox.prop(headerProp, 'adultNightHeader', text = "Adult Night")
		drawAddButton(headerSetup, len(headerProp.cutsceneHeaders), "Actor", None)
		for i in range(len(headerProp.cutsceneHeaders)):
			drawActorHeaderItemProperty(headerSetup, headerProp.cutsceneHeaders[i], i)

def drawActorHeaderItemProperty(layout, headerItemProp, index):
	box = layout.box()
	box.prop(headerItemProp, 'expandTab', text = 'Header ' + \
		str(headerItemProp.headerIndex), icon = 'TRIA_DOWN' if headerItemProp.expandTab else \
		'TRIA_RIGHT')
	if headerItemProp.expandTab:
		prop_split(box, headerItemProp, 'headerIndex', 'Header Index')
		drawCollectionOps(box, index, "Actor", None)
		
class OOTAlternateSceneHeaderProperty(bpy.types.PropertyGroup):
	childNightHeader : bpy.props.PointerProperty(name = "Child Night Header", type = OOTSceneHeaderProperty)
	adultDayHeader : bpy.props.PointerProperty(name = "Adult Day Header", type = OOTSceneHeaderProperty)
	adultNightHeader : bpy.props.PointerProperty(name = "Adult Night Header", type = OOTSceneHeaderProperty)
	cutsceneHeaders : bpy.props.CollectionProperty(type = OOTSceneHeaderProperty)

def drawAlternateSceneHeaderProperty(layout, headerProp):
	headerSetup = layout.box()
	headerSetup.box().label(text = "Alternate Headers")
	headerSetupBox = headerSetup.box()

	drawSceneHeaderProperty(headerSetupBox, headerProp.childNightHeader, "Child Night", 1)
	drawSceneHeaderProperty(headerSetupBox, headerProp.adultDayHeader, "Adult Day", 2)
	drawSceneHeaderProperty(headerSetupBox, headerProp.adultNightHeader, "Adult Night", 3)
	headerSetup.box().label(text = "Cutscene Headers")
	drawAddButton(headerSetup, len(headerProp.cutsceneHeaders), "Scene", None)
	for i in range(len(headerProp.cutsceneHeaders)):
		box = headerSetup.box()
		drawSceneHeaderProperty(box, headerProp.cutsceneHeaders[i], "Header " + str(i + 4), i + 4)

class OOTAlternateRoomHeaderProperty(bpy.types.PropertyGroup):
	childNightHeader : bpy.props.PointerProperty(name = "Child Night Header", type = OOTRoomHeaderProperty)
	adultDayHeader : bpy.props.PointerProperty(name = "Adult Day Header", type = OOTRoomHeaderProperty)
	adultNightHeader : bpy.props.PointerProperty(name = "Adult Night Header", type = OOTRoomHeaderProperty)
	cutsceneHeaders : bpy.props.CollectionProperty(type = OOTRoomHeaderProperty)

def drawAlternateRoomHeaderProperty(layout, headerProp):
	headerSetup = layout.box()
	headerSetup.box().label(text = "Alternate Headers")
	headerSetupBox = headerSetup.box()

	drawRoomHeaderProperty(headerSetupBox, headerProp.childNightHeader, "Child Night", 1)
	drawRoomHeaderProperty(headerSetupBox, headerProp.adultDayHeader, "Adult Day", 2)
	drawRoomHeaderProperty(headerSetupBox, headerProp.adultNightHeader, "Adult Night", 3)
	headerSetup.box().label(text = "Cutscene Headers")
	drawAddButton(headerSetup, len(headerProp.cutsceneHeaders), "Room", None)
	for i in range(len(headerProp.cutsceneHeaders)):
		box = headerSetup.box()
		drawRoomHeaderProperty(box, headerProp.cutsceneHeaders[i], "Header " + str(i + 4), i + 4)

class OOTActorProperty(bpy.types.PropertyGroup):
	actorID : bpy.props.EnumProperty(name = 'Actor', items = ootEnumActorID, default = 'ACTOR_PLAYER')
	actorIDCustom : bpy.props.StringProperty(name = 'Actor ID', default = 'ACTOR_PLAYER')
	actorParam : bpy.props.StringProperty(name = 'Actor Parameter', default = '0x0000')
	headerSettings : bpy.props.PointerProperty(type = OOTActorHeaderProperty)

def drawActorProperty(layout, actorProp):
	#prop_split(layout, actorProp, 'actorID', 'Actor')
	actorIDBox = layout.box()
	actorIDBox.box().label(text = "Actor ID: " + actorProp.actorID)
	if actorProp.actorID == 'Custom':
		#actorIDBox.prop(actorProp, 'actorIDCustom', text = 'Actor ID')
		prop_split(actorIDBox, actorProp, 'actorIDCustom', 'Actor ID')

	actorIDBox.operator(OOT_SearchActorIDEnumOperator.bl_idname, icon = 'VIEWZOOM')
	#layout.box().label(text = 'Actor IDs defined in include/z64actors.h.')
	prop_split(layout, actorProp, "actorParam", 'Actor Parameter')

	drawActorHeaderProperty(layout, actorProp.headerSettings)

class OOTWaterBoxProperty(bpy.types.PropertyGroup):
	lighting : bpy.props.EnumProperty(
		name = 'Lighting', items = ootEnumWaterBoxLighting, default = 'Default')
	lightingCustom : bpy.props.StringProperty(name = 'Lighting Custom', default = '0x00')
	camera : bpy.props.EnumProperty(
		name = "Camera Mode", items = ootEnumWaterBoxCamera, default = "Default")
	cameraCustom : bpy.props.StringProperty(name = "Camera Mode Custom", default = "0x00")

def drawWaterBoxProperty(layout, waterBoxProp):
	box = layout.box()
	box.box().label(text = "Properties")
	drawEnumWithCustom(box, waterBoxProp, 'lighting', "Lighting", "")
	drawEnumWithCustom(box, waterBoxProp, 'camera', "Camera", "")
	box.label(text = "Water box area defined by top face of box shaped empty.")
	box.label(text = "No rotation allowed.")

oot_obj_classes = (
	OOT_SearchActorIDEnumOperator,
	OOT_SearchMusicSeqEnumOperator,
	OOT_SearchObjectEnumOperator,
	OOTLightProperty,
	OOTObjectProperty,

	OOTActorHeaderItemProperty,
	OOTActorHeaderProperty,
	OOTActorProperty,

	OOTSceneHeaderProperty,
	OOTAlternateSceneHeaderProperty,

	OOTRoomHeaderProperty,
	OOTAlternateRoomHeaderProperty,
	OOTWaterBoxProperty,
)

oot_obj_panel_classes = (
	OOTObjectPanel,
)

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
		name = 'OOT Object Type', items = ootEnumEmptyType, default = 'None', update = onUpdateObjectType)
	
	bpy.types.Object.ootActorProperty = bpy.props.PointerProperty(type = OOTActorProperty)
	bpy.types.Object.ootWaterBoxProperty = bpy.props.PointerProperty(type = OOTWaterBoxProperty)
	bpy.types.Object.ootRoomHeader = bpy.props.PointerProperty(type = OOTRoomHeaderProperty)
	bpy.types.Object.ootSceneHeader = bpy.props.PointerProperty(type = OOTSceneHeaderProperty)
	bpy.types.Object.ootAlternateSceneHeaders = bpy.props.PointerProperty(type = OOTAlternateSceneHeaderProperty)
	bpy.types.Object.ootAlternateRoomHeaders = bpy.props.PointerProperty(type = OOTAlternateRoomHeaderProperty)


def oot_obj_unregister():
	
	del bpy.types.Object.ootEmptyType

	del bpy.types.Object.ootActorProperty 
	del bpy.types.Object.ootRoomHeader
	del bpy.types.Object.ootSceneHeader
	del bpy.types.Object.ootWaterBoxType
	del bpy.types.Object.ootAlternateSceneHeaders
	del bpy.types.Object.ootAlternateRoomHeaders

	for cls in reversed(oot_obj_classes):
		unregister_class(cls)