ootEnumCSTextboxTypeEntryC = {
    "Text": "CS_TEXT_DISPLAY_TEXTBOX",
    "None": "CS_TEXT_NONE",
    "LearnSong": "CS_TEXT_LEARN_SONG",
}

ootEnumCSListTypeListC = {
    "Textbox": "CS_TEXT_LIST",
    "FX": "CS_SCENE_TRANS_FX",
    "Lighting": "CS_LIGHTING_LIST",
    "Time": "CS_TIME_LIST",
    "PlayBGM": "CS_PLAY_BGM_LIST",
    "StopBGM": "CS_STOP_BGM_LIST",
    "FadeBGM": "CS_FADE_BGM_LIST",
    "Misc": "CS_MISC_LIST",
    "0x09": "CS_CMD_09_LIST",
    "Unk": "CS_UNK_DATA_LIST",
}

ootEnumCSListTypeEntryC = {
    "Textbox": None,  # special case
    "FX": None,  # no list entries
    "Lighting": "CS_LIGHTING",
    "Time": "CS_TIME",
    "PlayBGM": "CS_PLAY_BGM",
    "StopBGM": "CS_STOP_BGM",
    "FadeBGM": "CS_FADE_BGM",
    "Misc": "CS_MISC",
    "0x09": "CS_CMD_09",
    "Unk": "CS_UNK_DATA",
}

ootEnumCSWriteType = [
    ("Custom", "Custom", "Provide the name of a cutscene header variable"),
    ("Embedded", "Embedded", "Cutscene data is within scene header (deprecated)"),
    ("Object", "Object", "Reference to Blender object representing cutscene"),
]

ootEnumCSListType = [
    ("Textbox", "Textbox", "Textbox"),
    ("FX", "Scene Trans FX", "Scene Trans FX"),
    ("Lighting", "Lighting", "Lighting"),
    ("Time", "Time", "Time"),
    ("PlayBGM", "Play BGM", "Play BGM"),
    ("StopBGM", "Stop BGM", "Stop BGM"),
    ("FadeBGM", "Fade BGM", "Fade BGM"),
    ("Misc", "Misc", "Misc"),
    ("0x09", "Cmd 09", "Cmd 09"),
    ("Unk", "Unknown Data", "Unknown Data"),
]

ootEnumCSListTypeIcons = [
    "ALIGN_BOTTOM",
    "COLORSET_10_VEC",
    "LIGHT_SUN",
    "TIME",
    "PLAY",
    "SNAP_FACE",
    "IPO_EASE_IN_OUT",
    "OPTIONS",
    "EVENT_F9",
    "QUESTION",
]

ootEnumCSTextboxType = [("Text", "Text", "Text"), ("None", "None", "None"), ("LearnSong", "Learn Song", "Learn Song")]

ootEnumCSTextboxTypeIcons = ["FILE_TEXT", "HIDE_ON", "FILE_SOUND"]

ootEnumCSTransitionType = [
    ("1", "To White +", "Also plays whiteout sound for certain scenes/entrances"),
    ("2", "To Blue", "To Blue"),
    ("3", "From Red", "From Red"),
    ("4", "From Green", "From Green"),
    ("5", "From White", "From White"),
    ("6", "From Blue", "From Blue"),
    ("7", "To Red", "To Red"),
    ("8", "To Green", "To Green"),
    ("9", "Set Unk", "gSaveContext.unk_1410 = 1, works with scene xn 11/17"),
    ("10", "From Black", "From Black"),
    ("11", "To Black", "To Black"),
    ("12", "To Dim Unk", "Fade gSaveContext.unk_1410 255>100, works with scene xn 11/17"),
    ("13", "From Dim", "Alpha 100>255"),
]
