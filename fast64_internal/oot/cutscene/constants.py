ootEnumCSListTypeListC = {
    "TextList": "CS_TEXT_LIST",
    "Transition": "CS_TRANSITION",
    "LightSettingsList": "CS_LIGHT_SETTING_LIST",
    "TimeList": "CS_TIME_LIST",
    "StartSeqList": "CS_START_SEQ_LIST",
    "StopSeqList": "CS_STOP_SEQ_LIST",
    "FadeOutSeqList": "CS_FADE_OUT_SEQ_LIST",
    "MiscList": "CS_MISC_LIST",
    "RumbleList": "CS_RUMBLE_CONTROLLER_LIST",
}

ootEnumCSWriteType = [
    ("Custom", "Custom", "Provide the name of a cutscene header variable", "", 0),
    ("Object", "Object", "Reference to Blender object representing cutscene", "", 2),
]

# order here sets order on the UI
ootEnumCSListType = [
    ("TextList", "Text List", "Textbox", "ALIGN_BOTTOM", 0),
    ("TimeList", "Time List", "Time", "TIME", 3),
    ("FadeOutSeqList", "Fade-Out Seq List", "Fade BGM", "IPO_EASE_IN_OUT", 6),
    ("Transition", "Transition", "Transition", "COLORSET_10_VEC", 1),
    ("StartSeqList", "Start Seq List", "Play BGM", "PLAY", 4),
    ("MiscList", "Misc List", "Misc", "OPTIONS", 7),
    ("LightSettingsList", "Light Settings List", "Lighting", "LIGHT_SUN", 2),
    ("StopSeqList", "Stop Seq List", "Stop BGM", "SNAP_FACE", 5),
    ("RumbleList", "Rumble List", "Rumble Controller", "OUTLINER_OB_FORCE_FIELD", 8),
]

csListTypeToIcon = {
    "TextList": "ALIGN_BOTTOM",
    "Transition": "COLORSET_10_VEC",
    "LightSettingsList": "LIGHT_SUN",
    "TimeList": "TIME",
    "StartSeqList": "PLAY",
    "StopSeqList": "SNAP_FACE",
    "FadeOutSeqList": "IPO_EASE_IN_OUT",
    "MiscList": "OPTIONS",
    "RumbleList": "OUTLINER_OB_FORCE_FIELD",
}

ootEnumCSTextboxType = [
    ("Text", "Text", "Text"),
    ("None", "None", "None"),
    ("OcarinaAction", "Ocarina Action", "Learn Song"),
]

ootEnumCSTextboxTypeIcons = ["FILE_TEXT", "HIDE_ON", "FILE_SOUND"]

ootCSSubPropToName = {
    "startFrame": "Start Frame",
    "endFrame": "End Frame",
    # TextBox
    "textID": "Text ID",
    "ocarinaAction": "Ocarina Action",
    "csTextType": "Text Type",
    "topOptionTextID": "Text ID for Top Option",
    "bottomOptionTextID": "Text ID for Bottom Option",
    "ocarinaMessageId": "Ocarina Message ID",
    # Lighting
    "lightSettingsIndex": "Light Settings Index",
    # Time
    "hour": "Hour",
    "minute": "Minute",
    # Seq
    "csSeqID": "Seq ID",
    "csSeqPlayer": "Seq Player Type",
    # Misc
    "csMiscType": "Misc Type",
    # Rumble
    "rumbleSourceStrength": "Source Strength",
    "rumbleDuration": "Duration",
    "rumbleDecreaseRate": "Decrease Rate",
    # Lists
    "TextList": "Text List",
    "TimeList": "Time List",
    "FadeOutSeqList": "Fade-Out Seq List",
    "Transition": "Transition",
    "StartSeqList": "Start Seq List",
    "MiscList": "Misc List",
    "LightSettingsList": "Light Settings List",
    "StopSeqList": "Stop Seq Lis",
    "RumbleList": "Rumble List",
}
