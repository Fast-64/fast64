from ...oot_constants import ootData

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
