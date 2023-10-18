ootEnumCSTextboxTypeEntryC = {
    "Text": "CS_TEXT",
    "None": "CS_TEXT_NONE",
    "OcarinaAction": "CS_TEXT_OCARINA_ACTION",
}

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

ootEnumCSListTypeEntryC = {
    "Text": None,  # special case
    "Transition": None,  # no list entries
    "LightSettings": "CS_LIGHT_SETTING",
    "Time": "CS_TIME",
    "StartSeq": "CS_START_SEQ",
    "StopSeq": "CS_STOP_SEQ",
    "FadeOutSeq": "CS_FADE_OUT_SEQ",
    "Misc": "CS_MISC",
    "Rumble": "CS_RUMBLE_CONTROLLER",
}

ootEnumCSWriteType = [
    ("Custom", "Custom", "Provide the name of a cutscene header variable"),
    ("Embedded", "(Deprecated) Embedded", "Cutscene data is within scene header"),
    ("Object", "Object", "Reference to Blender object representing cutscene"),
]

ootEnumCSListType = [
    ("TextList", "Text List", "Textbox"),
    ("Transition", "Transition", "Transition"),
    ("LightSettingsList", "Light Settings List", "Lighting"),
    ("TimeList", "Time List", "Time"),
    ("StartSeqList", "Start Seq List", "Play BGM"),
    ("StopSeqList", "Stop Seq List", "Stop BGM"),
    ("FadeOutSeqList", "Fade-Out Seq List", "Fade BGM"),
    ("MiscList", "Misc List", "Misc"),
    ("RumbleList", "Rumble List", "Rumble Controller"),
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
    "OUTLINER_OB_FORCE_FIELD",
]

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
}
