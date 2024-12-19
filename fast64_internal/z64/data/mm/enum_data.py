from dataclasses import dataclass, field
from os import path
from pathlib import Path
from .getters import get_xml_root
from .data import MM_BaseElement

# Note: "enumData" in this context refers to an MM Object file (like ``gameplay_keep``)


@dataclass
class MM_ItemElement(MM_BaseElement):
    parent_key: str

    def __post_init__(self):
        # generate the name from the id
        if self.name is None:
            key_to_prefix = {
                "cmd": "CS_CMD",
                "miscType": "CS_MISC",
                "textType": "CS_TEXT",
                "fadeOutSeqPlayer": "CS_FADE_OUT",
                "modifySeqType": "CS_MOD",
                "transitionType": "CS_TRANS",
                "destinationType": "CS_DESTINATION",
                "chooseCreditsSceneType": "CS_CREDITS",
                "motionBlurType": "CS_MOTION_BLUR",
                "rumbleType": "CS_RUMBLE",
                "transitionGeneralType": "CS_TRANS_GENERAL",
                "spawnFlag": "CS_SPAWN_FLAG",
                "endSfx": "CS_END_SFX",
                "csSplineInterpType": "CS_CAM_INTERP",
                "csSplineRelTo": "CS_CAM_REL",
                "playerCueId": "PLAYER_CUEID",
                "naviQuestHintType": "NAVI_QUEST_HINTS",
                "ocarinaSongActionId": "OCARINA_ACTION",
            }

            self.name = self.id.removeprefix(f"{key_to_prefix[self.parent_key]}_")

            if self.parent_key in ["csCmd", "csPlayerCueId"]:
                split = self.name.split("_")
                if self.parent_key == "csCmd" and "ACTOR_CUE" in self.id:
                    self.name = f"Actor Cue {split[-2]}_{split[-1]}"
                else:
                    self.name = f"Player Cue Id {split[-1]}"
            else:
                self.name = self.name.replace("_", " ").title()


@dataclass
class MM_EnumElement(MM_BaseElement):
    items: list[MM_ItemElement]
    item_by_key: dict[str, MM_ItemElement] = field(default_factory=dict)
    item_by_index: dict[int, MM_ItemElement] = field(default_factory=dict)
    item_by_id: dict[int, MM_ItemElement] = field(default_factory=dict)

    def __post_init__(self):
        self.item_by_key = {item.key: item for item in self.items}
        self.item_by_index = {item.index: item for item in self.items}
        self.item_by_id = {item.id: item for item in self.items}


class MM_EnumData:
    """Cutscene and misc enum data"""

    def __init__(self):
        # general enumData list
        self.enum_data_list: list[MM_EnumElement] = []

        # Path to the ``EnumData.xml`` file
        enum_data_root = get_xml_root(Path(f"{path.dirname(path.abspath(__file__))}/xml/EnumData.xml").resolve())

        for enum in enum_data_root.iterfind("Enum"):
            self.enum_data_list.append(
                MM_EnumElement(
                    enum.attrib["ID"],
                    enum.attrib["Key"],
                    None,
                    None,
                    [
                        MM_ItemElement(
                            item.attrib["ID"],
                            item.attrib["Key"],
                            # note: the name sets automatically after the init if None
                            item.attrib["Name"] if enum.attrib["Key"] == "seqId" else None,
                            int(item.attrib["Index"]),
                            enum.attrib["Key"],
                        )
                        for item in enum
                    ],
                )
            )

        # create list of tuples used by Blender's enum properties
        self.deleted_entry = ("None", "(Deleted from the XML)", "None")

        self.enum_cs_cmd: list[tuple[str, str, str]] = []
        self.enum_cs_misc_type: list[tuple[str, str, str]] = []
        self.enum_cs_text_type: list[tuple[str, str, str]] = []
        self.enum_cs_fade_out_seq_player: list[tuple[str, str, str]] = []
        self.enum_cs_modify_seq_type: list[tuple[str, str, str]] = []
        self.enum_cs_transition_type: list[tuple[str, str, str]] = []
        self.enum_cs_destination_type: list[tuple[str, str, str]] = []
        self.enum_cs_credits_scene_type: list[tuple[str, str, str]] = []
        self.enum_cs_motion_blur_type: list[tuple[str, str, str]] = []
        self.enum_cs_rumble_type: list[tuple[str, str, str]] = []
        self.enum_cs_transition_general_type: list[tuple[str, str, str]] = []
        self.enum_cs_spawn_flag: list[tuple[str, str, str]] = []
        self.enum_cs_end_sfx: list[tuple[str, str, str]] = []
        self.enum_cs_split_interp_type: list[tuple[str, str, str]] = []
        self.enum_cs_spline_rel_to: list[tuple[str, str, str]] = []
        self.enum_cs_player_cue_id: list[tuple[str, str, str]] = []
        self.enum_navi_quest_hint_type: list[tuple[str, str, str]] = []
        self.enum_ocarina_song_action_id: list[tuple[str, str, str]] = []
        self.enum_seq_id: list[tuple[str, str, str]] = []

        self.enum_by_id = {enum.id: enum for enum in self.enum_data_list}
        self.enum_by_key = {enum.key: enum for enum in self.enum_data_list}

        key_to_enum = {
            "cmd": "enum_cs_cmd",
            "miscType": "enum_cs_misc_type",
            "textType": "enum_cs_text_type",
            "fadeOutSeqPlayer": "enum_cs_fade_out_seq_player",
            "modifySeqType": "enum_cs_modify_seq_type",
            "transitionType": "enum_cs_transition_type",
            "destinationType": "enum_cs_destination_type",
            "chooseCreditsSceneType": "enum_cs_credits_scene_type",
            "motionBlurType": "enum_cs_motion_blur_type",
            "rumbleType": "enum_cs_rumble_type",
            "transitionGeneralType": "enum_cs_transition_general_type",
            "spawnFlag": "enum_cs_spawn_flag",
            "endSfx": "enum_cs_end_sfx",
            "csSplineInterpType": "enum_cs_split_interp_type",
            "csSplineRelTo": "enum_cs_spline_rel_to",
            "playerCueId": "enum_cs_player_cue_id",
            "naviQuestHintType": "enum_navi_quest_hint_type",
            "ocarinaSongActionId": "enum_ocarina_song_action_id",
            "seqId": "enum_seq_id",
        }

        for key in self.enum_by_key.keys():
            setattr(self, key_to_enum[key], self.get_enum_data(key))

    def get_enum_data(self, enum_key: str):
        enum = self.enum_by_key[enum_key]
        first_index = min(1, *(item.index for item in enum.items))
        last_index = max(1, *(item.index for item in enum.items)) + 1
        enum_data = [self.deleted_entry] * last_index
        custom = ("Custom", "Custom", "Custom")

        for item in enum.items:
            if item.index < last_index:
                identifier = item.key
                enum_data[item.index] = (identifier, item.name, item.id)

        if first_index > 0:
            enum_data[0] = custom
        else:
            enum_data.insert(0, custom)

        return enum_data
