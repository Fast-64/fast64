# Default width is 16

CAM_LIST_PARAMS = [
    {"name": "continueFlag", "type": "continueFlag"},
    {"name": "roll", "type": "int", "width": 8},
    {"name": "frame", "type": "int"},
    {"name": "viewAngle", "type": "int_or_float", "min": 0.0, "max": 179.99},
    {"name": "xPos", "type": "int"},
    {"name": "yPos", "type": "int"},
    {"name": "zPos", "type": "int"},
    {"name": "unused", "type": "int"},
]

ACTOR_ACTION_PARAMS = [
    {"name": "action", "type": "string"},
    {"name": "startFrame", "type": "int"},
    {"name": "endFrame", "type": "int"},
    {"name": "rotX", "type": "hex"},
    {"name": "rotY", "type": "hex"},
    {"name": "rotZ", "type": "hex"},
    {"name": "startX", "type": "int", "width": 32},
    {"name": "startY", "type": "int", "width": 32},
    {"name": "startZ", "type": "int", "width": 32},
    {"name": "endX", "type": "int", "width": 32},
    {"name": "endY", "type": "int", "width": 32},
    {"name": "endZ", "type": "int", "width": 32},
    {"name": "normX", "type": "int_or_float", "width": 32},
    {"name": "normY", "type": "int_or_float", "width": 32},
    {"name": "normZ", "type": "int_or_float", "width": 32},
]

BGM_PARAMS = [
    {"name": "id", "type": "string"},
    {"name": "startFrame", "type": "int"},
    {"name": "endFrame", "type": "int"},
    {"name": "unused0", "type": "int"},
    {"name": "unused1", "type": "int", "width": 32},
    {"name": "unused2", "type": "int", "width": 32},
    {"name": "unused3", "type": "int", "width": 32},
    {"name": "unused4", "type": "int", "width": 32},
    {"name": "unused5", "type": "int", "width": 32},
    {"name": "unused6", "type": "int", "width": 32},
    {"name": "unused7", "type": "int", "width": 32},
]

CAM_TYPE_LISTS = [
    "CS_CAM_POS_LIST",
    "CS_CAM_FOCUS_POINT_LIST",
    "CS_CAM_POS_PLAYER_LIST",
    "CS_CAM_FOCUS_POINT_PLAYER_LIST",
    "CS_CMD_07_LIST",
    "CS_CMD_08_LIST",
]

CAM_TYPE_TO_TYPE = {
    "CS_CAM_POS_LIST": "pos",
    "CS_CAM_FOCUS_POINT_LIST": "at",
    "CS_CAM_POS_PLAYER_LIST": "pos",
    "CS_CAM_FOCUS_POINT_PLAYER_LIST": "at",
    "CS_CMD_07_LIST": "pos",
    "CS_CMD_08_LIST": "at",
}

CAM_TYPE_TO_MODE = {
    "CS_CAM_POS_LIST": "normal",
    "CS_CAM_FOCUS_POINT_LIST": "normal",
    "CS_CAM_POS_PLAYER_LIST": "rel_link",
    "CS_CAM_FOCUS_POINT_PLAYER_LIST": "rel_link",
    "CS_CMD_07_LIST": "0708",
    "CS_CMD_08_LIST": "0708",
}

ATMODE_TO_CMD = {
    False: {"normal": "CS_CAM_POS", "rel_link": "CS_CAM_POS_PLAYER", "0708": "CS_CMD_07"},
    True: {"normal": "CS_CAM_FOCUS_POINT", "rel_link": "CS_CAM_FOCUS_POINT_PLAYER", "0708": "CS_CMD_08"},
}

ACTION_LISTS = ["CS_PLAYER_ACTION_LIST", "CS_NPC_ACTION_LIST"]

LISTS_DEF = [
    {
        "name": "CS_CAM_POS_LIST",
        "params": [{"name": "startFrame", "type": "int"}, {"name": "endFrame", "type": "int"}],
        "commands": [{"name": "CS_CAM_POS", "params": CAM_LIST_PARAMS}],
    },
    {
        "name": "CS_CAM_FOCUS_POINT_LIST",
        "params": [{"name": "startFrame", "type": "int"}, {"name": "endFrame", "type": "int"}],
        "commands": [{"name": "CS_CAM_FOCUS_POINT", "params": CAM_LIST_PARAMS}],
    },
    {
        "name": "CS_MISC_LIST",
        "params": [{"name": "entries", "type": "int", "min": 1}],
        "commands": [
            {
                "name": "CS_MISC",
                "params": [
                    {"name": "unk", "type": "hex"},
                    {"name": "startFrame", "type": "int"},
                    {"name": "endFrame", "type": "int"},
                    {"name": "unused0", "type": "hex"},
                    {"name": "unused1", "type": "hex", "width": 32},
                    {"name": "unused2", "type": "hex", "width": 32},
                    {"name": "unused3", "type": "int", "width": 32},
                    {"name": "unused4", "type": "int", "width": 32},
                    {"name": "unused5", "type": "int", "width": 32},
                    {"name": "unused6", "type": "int", "width": 32},
                    {"name": "unused7", "type": "int", "width": 32},
                    {"name": "unused8", "type": "int", "width": 32},
                    {"name": "unused9", "type": "int", "width": 32},
                    {"name": "unused10", "type": "int", "width": 32},
                ],
            }
        ],
    },
    {
        "name": "CS_LIGHTING_LIST",
        "params": [{"name": "entries", "type": "int", "min": 1}],
        "commands": [
            {
                "name": "CS_LIGHTING",
                "params": [
                    {"name": "setting", "type": "int"},
                    {"name": "startFrame", "type": "int"},
                    {"name": "endFrame", "type": "int"},
                    {"name": "unused0", "type": "int"},
                    {"name": "unused1", "type": "int", "width": 32},
                    {"name": "unused2", "type": "int", "width": 32},
                    {"name": "unused3", "type": "int", "width": 32},
                    {"name": "unused4", "type": "int", "width": 32},
                    {"name": "unused5", "type": "int", "width": 32},
                    {"name": "unused6", "type": "int", "width": 32},
                    {"name": "unused7", "type": "int", "width": 32},
                ],
            }
        ],
    },
    {
        "name": "CS_CAM_POS_PLAYER_LIST",
        "params": [{"name": "startFrame", "type": "int"}, {"name": "endFrame", "type": "int"}],
        "commands": [{"name": "CS_CAM_POS_PLAYER", "params": CAM_LIST_PARAMS}],
    },
    {
        "name": "CS_CAM_FOCUS_POINT_PLAYER_LIST",
        "params": [{"name": "startFrame", "type": "int"}, {"name": "endFrame", "type": "int"}],
        "commands": [{"name": "CS_CAM_FOCUS_POINT_PLAYER", "params": CAM_LIST_PARAMS}],
    },
    {
        "name": "CS_CMD_07_LIST",
        "params": [
            {"name": "unk", "type": "hex"},
            {"name": "startFrame", "type": "int"},
            {"name": "endFrame", "type": "int"},
            {"name": "unused", "type": "hex"},
        ],
        "commands": [{"name": "CS_CMD_07", "params": CAM_LIST_PARAMS}],
    },
    {
        "name": "CS_CMD_08_LIST",
        "params": [
            {"name": "unk", "type": "hex"},
            {"name": "startFrame", "type": "int"},
            {"name": "endFrame", "type": "int"},
            {"name": "unused", "type": "hex"},
        ],
        "commands": [{"name": "CS_CMD_08", "params": CAM_LIST_PARAMS}],
    },
    {
        "name": "CS_CMD_09_LIST",
        "params": [{"name": "entries", "type": "int", "min": 1}],
        "commands": [
            {
                "name": "CS_CMD_09",
                "params": [
                    {"name": "unk", "type": "int"},
                    {"name": "startFrame", "type": "int"},
                    {"name": "endFrame", "type": "int"},
                    {"name": "unk2", "type": "int", "width": 8},
                    {"name": "unk3", "type": "int", "width": 8},
                    {"name": "unk4", "type": "int", "width": 8},
                    {"name": "unused0", "type": "int", "width": 8},
                    {"name": "unused1", "type": "int"},
                ],
            }
        ],
    },
    {
        "name": "CS_UNK_DATA_LIST",
        "params": [{"name": "cmdType", "type": "int"}, {"name": "entries", "type": "int", "min": 1}],
        "commands": [
            {
                "name": "CS_UNK_DATA",
                "params": [
                    {"name": "unk1", "type": "int", "width": 32},
                    {"name": "unk2", "type": "int", "width": 32},
                    {"name": "unk3", "type": "int", "width": 32},
                    {"name": "unk4", "type": "int", "width": 32},
                    {"name": "unk5", "type": "int", "width": 32},
                    {"name": "unk6", "type": "int", "width": 32},
                    {"name": "unk7", "type": "int", "width": 32},
                    {"name": "unk8", "type": "int", "width": 32},
                    {"name": "unk9", "type": "int", "width": 32},
                    {"name": "unk10", "type": "int", "width": 32},
                    {"name": "unk11", "type": "int", "width": 32},
                    {"name": "unk12", "type": "int", "width": 32},
                ],
            }
        ],
    },
    {
        "name": "CS_NPC_ACTION_LIST",
        "params": [{"name": "cmdType", "type": "int"}, {"name": "entries", "type": "int", "min": 1}],
        "commands": [{"name": "CS_NPC_ACTION", "params": ACTOR_ACTION_PARAMS}],
    },
    {
        "name": "CS_PLAYER_ACTION_LIST",
        "params": [{"name": "entries", "type": "int", "min": 1}],
        "commands": [{"name": "CS_PLAYER_ACTION", "params": ACTOR_ACTION_PARAMS}],
    },
    {
        "name": "CS_TEXT_LIST",
        "params": [{"name": "entries", "type": "int", "min": 1}],
        "commands": [
            {
                "name": "CS_TEXT_DISPLAY_TEXTBOX",
                "params": [
                    {"name": "messageId", "type": "int"},
                    {"name": "startFrame", "type": "int"},
                    {"name": "endFrame", "type": "int"},
                    {"name": "type", "type": "int"},
                    {"name": "topOptionBranch", "type": "int"},
                    {"name": "bottomOptionBranch", "type": "int"},
                ],
            },
            {
                "name": "CS_TEXT_NONE",
                "params": [{"name": "startFrame", "type": "int"}, {"name": "endFrame", "type": "int"}],
            },
            {
                "name": "CS_TEXT_LEARN_SONG",
                "params": [
                    {"name": "ocarinaSongAction", "type": "int"},
                    {"name": "startFrame", "type": "int"},
                    {"name": "endFrame", "type": "int"},
                    {"name": "messageId", "type": "int"},
                ],
            },
        ],
    },
    {
        "name": "CS_PLAY_BGM_LIST",
        "params": [{"name": "entries", "type": "int", "min": 1}],
        "commands": [{"name": "CS_PLAY_BGM", "params": BGM_PARAMS}],
    },
    {
        "name": "CS_STOP_BGM_LIST",
        "params": [{"name": "entries", "type": "int", "min": 1}],
        "commands": [{"name": "CS_STOP_BGM", "params": BGM_PARAMS}],
    },
    {
        "name": "CS_FADE_BGM_LIST",
        "params": [{"name": "entries", "type": "int", "min": 1}],
        "commands": [{"name": "CS_FADE_BGM", "params": BGM_PARAMS}],
    },
    {
        "name": "CS_TIME_LIST",
        "params": [{"name": "entries", "type": "int", "min": 1}],
        "commands": [
            {
                "name": "CS_TIME",
                "params": [
                    {"name": "unk", "type": "int"},
                    {"name": "startFrame", "type": "int"},
                    {"name": "endFrame", "type": "int"},
                    {"name": "hour", "type": "int", "width": 8},
                    {"name": "min", "type": "int", "width": 8},
                    {"name": "unused", "type": "int", "width": 32},
                ],
            }
        ],
    },
]

NONLISTS_DEF = [
    {
        "name": "CS_BEGIN_CUTSCENE",
        "params": [
            {"name": "totalEntries", "type": "int", "min": 0},
            {"name": "endFrame", "type": "int", "min": 1},
        ],
    },
    {
        "name": "CS_SCENE_TRANS_FX",
        "params": [
            {"name": "transitionType", "type": "int"},
            {"name": "startFrame", "type": "int"},
            {"name": "endFrame", "type": "int"},
        ],
    },
    {
        "name": "CS_TERMINATOR",
        "params": [
            {"name": "dest", "type": "hex"},
            {"name": "startFrame", "type": "int"},
            {"name": "endFrame", "type": "int"},
        ],
    },
    {"name": "CS_END", "params": []},
]
