from ..oot_constants import ootData
from .io_classes import (
    OOTCSMotionActorCueList,
    OOTCSMotionActorCue,
    OOTCSMotionCamEyeSpline,
    OOTCSMotionCamATSpline,
    OOTCSMotionCamEyeSplineRelToPlayer,
    OOTCSMotionCamATSplineRelToPlayer,
    OOTCSMotionCamEye,
    OOTCSMotionCamAT,
    OOTCSMotionCamPoint,
    OOTCSMotionMisc,
    OOTCSMotionMiscList,
    OOTCSMotionTransition,
    OOTCSMotionText,
    OOTCSMotionTextNone,
    OOTCSMotionTextOcarinaAction,
    OOTCSMotionTextList,
    OOTCSMotionLightSetting,
    OOTCSMotionLightSettingList,
    OOTCSMotionTime,
    OOTCSMotionTimeList,
    OOTCSMotionStartStopSeq,
    OOTCSMotionStartStopSeqList,
    OOTCSMotionFadeSeq,
    OOTCSMotionFadeSeqList,
    OOTCSMotionRumbleController,
    OOTCSMotionRumbleControllerList,
    OOTCSMotionDestination,
)


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

ootEnumCSMotionCamMode = [
    ("splineEyeOrAT", "Eye/AT Spline", "Eye/AT Spline"),
    ("splineEyeOrATRelPlayer", "Spline Rel. Player", "Relative to Player's location/yaw"),
    ("eyeOrAT", "Eye/AT Point", "Single Eye/AT point (not recommended)"),
]

ootEnumCSActorCueListCommandType = [
    item for item in ootData.enumData.ootEnumCsCmd if "actor_cue" in item[0] or "player_cue" in item[0]
]
ootEnumCSActorCueListCommandType.sort()
ootEnumCSActorCueListCommandType.insert(0, ("Custom", "Custom", "Custom"))

ootCSMotionLegacyToNewCmdNames = {
    "CS_CAM_POS_LIST": "CS_CAM_EYE_SPLINE",
    "CS_CAM_FOCUS_POINT_LIST": "CS_CAM_AT_SPLINE",
    "CS_CAM_POS_PLAYER_LIST": "CS_CAM_EYE_SPLINE_REL_TO_PLAYER",
    "CS_CAM_FOCUS_POINT_PLAYER_LIST": "CS_CAM_AT_SPLINE_REL_TO_PLAYER",
    "CS_NPC_ACTION_LIST": "CS_ACTOR_CUE_LIST",
    "CS_PLAYER_ACTION_LIST": "CS_PLAYER_CUE_LIST",
    "CS_CMD_07": "CS_CAM_EYE",
    "CS_CMD_08": "CS_CAM_AT",
    "CS_CAM_POS": "CS_CAM_POINT",
    "CS_CAM_FOCUS_POINT": "CS_CAM_POINT",
    "CS_CAM_POS_PLAYER": "CS_CAM_POINT",
    "CS_CAM_FOCUS_POINT_PLAYER": "CS_CAM_POINT",
    "CS_NPC_ACTION": "CS_ACTOR_CUE",
    "CS_PLAYER_ACTION": "CS_PLAYER_CUE",
    "CS_CMD_09_LIST": "CS_RUMBLE_CONTROLLER_LIST",
    "CS_CMD_09": "CS_RUMBLE_CONTROLLER",
    "CS_TEXT_DISPLAY_TEXTBOX": "CS_TEXT",
    "CS_TEXT_LEARN_SONG": "CS_TEXT_OCARINA_ACTION",
    "CS_SCENE_TRANS_FX": "CS_TRANSITION",
    "CS_FADE_BGM_LIST": "CS_FADE_OUT_SEQ_LIST",
    "CS_FADE_BGM": "CS_FADE_OUT_SEQ",
    "CS_TERMINATOR": "CS_DESTINATION",
    "CS_LIGHTING_LIST": "CS_LIGHT_SETTING_LIST",
    "CS_LIGHTING": "L_CS_LIGHT_SETTING",
    "CS_PLAY_BGM_LIST": "CS_START_SEQ_LIST",
    "CS_PLAY_BGM": "L_CS_START_SEQ",
    "CS_STOP_BGM_LIST": "CS_STOP_SEQ_LIST",
    "CS_STOP_BGM": "L_CS_STOP_SEQ",
}

ootCSMotionListCommands = [
    "CS_ACTOR_CUE_LIST",
    "CS_PLAYER_CUE_LIST",
    "CS_CAM_EYE_SPLINE",
    "CS_CAM_AT_SPLINE",
    "CS_CAM_EYE_SPLINE_REL_TO_PLAYER",
    "CS_CAM_AT_SPLINE_REL_TO_PLAYER",
    "CS_CAM_EYE",
    "CS_CAM_AT",
    "CS_MISC_LIST",
    "CS_LIGHT_SETTING_LIST",
    "CS_RUMBLE_CONTROLLER_LIST",
    "CS_TEXT_LIST",
    "CS_START_SEQ_LIST",
    "CS_STOP_SEQ_LIST",
    "CS_FADE_OUT_SEQ_LIST",
    "CS_TIME_LIST",
    "CS_UNK_DATA_LIST",
    "CS_PLAY_BGM_LIST",
    "CS_STOP_BGM_LIST",
    "CS_LIGHTING_LIST",
]

ootCSMotionListEntryCommands = [
    "CS_ACTOR_CUE",
    "CS_PLAYER_CUE",
    "CS_CAM_POINT",
    "CS_MISC",
    "CS_LIGHT_SETTING",
    "CS_RUMBLE_CONTROLLER",
    "CS_TEXT",
    "CS_TEXT_NONE",
    "CS_TEXT_OCARINA_ACTION",
    "CS_START_SEQ",
    "CS_STOP_SEQ",
    "CS_FADE_OUT_SEQ",
    "CS_TIME",
    "CS_UNK_DATA",
    "CS_PLAY_BGM",
    "CS_STOP_BGM",
    "CS_LIGHTING",
    # some old commands need to remove 1 to the first argument to stay accurate
    "L_CS_LIGHT_SETTING",
    "L_CS_START_SEQ",
    "L_CS_STOP_SEQ",
]

ootCSMotionSingleCommands = [
    "CS_BEGIN_CUTSCENE",
    "CS_END",
    "CS_TRANSITION",
    "CS_DESTINATION",
]

ootCSMotionListAndSingleCommands = ootCSMotionSingleCommands + ootCSMotionListCommands
ootCSMotionListAndSingleCommands.remove("CS_BEGIN_CUTSCENE")
ootCSMotionCSCommands = ootCSMotionSingleCommands + ootCSMotionListCommands + ootCSMotionListEntryCommands

cmdToClass = {
    "CS_CAM_POINT": OOTCSMotionCamPoint,
    "CS_MISC": OOTCSMotionMisc,
    "CS_LIGHT_SETTING": OOTCSMotionLightSetting,
    "CS_TIME": OOTCSMotionTime,
    "CS_FADE_OUT_SEQ": OOTCSMotionFadeSeq,
    "CS_RUMBLE_CONTROLLER": OOTCSMotionRumbleController,
    "CS_TEXT": OOTCSMotionText,
    "CS_TEXT_NONE": OOTCSMotionTextNone,
    "CS_TEXT_OCARINA_ACTION": OOTCSMotionTextOcarinaAction,
    "CS_START_SEQ": OOTCSMotionStartStopSeq,
    "CS_STOP_SEQ": OOTCSMotionStartStopSeq,
    "CS_ACTOR_CUE": OOTCSMotionActorCue,
    "CS_PLAYER_CUE": OOTCSMotionActorCue,
    "CS_CAM_EYE_SPLINE": OOTCSMotionCamEyeSpline,
    "CS_CAM_AT_SPLINE": OOTCSMotionCamATSpline,
    "CS_CAM_EYE_SPLINE_REL_TO_PLAYER": OOTCSMotionCamEyeSplineRelToPlayer,
    "CS_CAM_AT_SPLINE_REL_TO_PLAYER": OOTCSMotionCamATSplineRelToPlayer,
    "CS_CAM_EYE": OOTCSMotionCamEye,
    "CS_CAM_AT": OOTCSMotionCamAT,
    "CS_MISC_LIST": OOTCSMotionMiscList,
    "CS_TRANSITION": OOTCSMotionTransition,
    "CS_TEXT_LIST": OOTCSMotionTextList,
    "CS_LIGHT_SETTING_LIST": OOTCSMotionLightSettingList,
    "CS_TIME_LIST": OOTCSMotionTimeList,
    "CS_FADE_OUT_SEQ_LIST": OOTCSMotionFadeSeqList,
    "CS_RUMBLE_CONTROLLER_LIST": OOTCSMotionRumbleControllerList,
    "CS_START_SEQ_LIST": OOTCSMotionStartStopSeqList,
    "CS_STOP_SEQ_LIST": OOTCSMotionStartStopSeqList,
    "CS_ACTOR_CUE_LIST": OOTCSMotionActorCueList,
    "CS_PLAYER_CUE_LIST": OOTCSMotionActorCueList,
    "CS_DESTINATION": OOTCSMotionDestination,
}
