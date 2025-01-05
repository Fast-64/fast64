from dataclasses import dataclass, field
from os import path
from pathlib import Path
from .getters import get_xml_root
from .data import Z64_BaseElement

# Note: "enumData" in this context refers to an OoT Object file (like ``gameplay_keep``)


@dataclass
class Z64_ItemElement(Z64_BaseElement):
    parentKey: str
    game: str

    def __post_init__(self):
        # generate the name from the id

        if self.name is None:
            if self.game == "OOT":
                keyToPrefix = {
                    "csCmd": "CS_CMD",
                    "csMiscType": "CS_MISC",
                    "csTextType": "CS_TEXT",
                    "csFadeOutSeqPlayer": "CS_FADE_OUT",
                    "csTransitionType": "CS_TRANS",
                    "csDestination": "CS_DEST",
                    "csPlayerCueId": "PLAYER_CUEID",
                    "naviQuestHintType": "NAVI_QUEST_HINTS",
                    "ocarinaSongActionId": "OCARINA_ACTION",
                }
            else:
                keyToPrefix = {
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

            self.name = self.id.removeprefix(f"{keyToPrefix[self.parentKey]}_")

            if self.parentKey in ["csCmd", "csPlayerCueId"]:
                split = self.name.split("_")
                if self.parentKey == "csCmd" and "ACTOR_CUE" in self.id:
                    self.name = f"Actor Cue {split[-2]}_{split[-1]}"
                else:
                    self.name = f"Player Cue Id {split[-1]}"
            else:
                self.name = self.name.replace("_", " ").title()


@dataclass
class Z64_EnumElement(Z64_BaseElement):
    items: list[Z64_ItemElement]
    item_by_key: dict[str, Z64_ItemElement] = field(default_factory=dict)
    item_by_index: dict[int, Z64_ItemElement] = field(default_factory=dict)
    item_by_id: dict[int, Z64_ItemElement] = field(default_factory=dict)

    def __post_init__(self):
        self.item_by_key = {item.key: item for item in self.items}
        self.item_by_index = {item.index: item for item in self.items}
        self.item_by_id = {item.id: item for item in self.items}


class Z64_EnumData:
    """Cutscene and misc enum data"""

    def __init__(self, game: str):
        # general enumData list
        self.enumDataList: list[Z64_EnumElement] = []

        # Path to the ``EnumData.xml`` file
        xml_path = Path(f"{path.dirname(path.abspath(__file__))}/xml/{game.lower()}_enum_data.xml")
        enum_data_root = get_xml_root(xml_path.resolve())

        for enum in enum_data_root.iterfind("Enum"):
            self.enumDataList.append(
                Z64_EnumElement(
                    enum.attrib["ID"],
                    enum.attrib["Key"],
                    None,
                    None,
                    [
                        Z64_ItemElement(
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
        self.deletedEntry = ("None", "(Deleted from the XML)", "None")

        self.ootEnumCsCmd: list[tuple[str, str, str]] = []
        self.ootEnumCsMiscType: list[tuple[str, str, str]] = []
        self.ootEnumCsTextType: list[tuple[str, str, str]] = []
        self.ootEnumCsFadeOutSeqPlayer: list[tuple[str, str, str]] = []
        self.ootEnumCsTransitionType: list[tuple[str, str, str]] = []
        self.ootEnumCsDestination: list[tuple[str, str, str]] = []
        self.ootEnumCsPlayerCueId: list[tuple[str, str, str]] = []
        self.ootEnumNaviQuestHintType: list[tuple[str, str, str]] = []
        self.ootEnumOcarinaSongActionId: list[tuple[str, str, str]] = []
        self.ootEnumSeqId: list[tuple[str, str, str]] = []

        self.enum_modify_seq_type: list[tuple[str, str, str]] = []
        self.enum_credits_scene_type: list[tuple[str, str, str]] = []
        self.enum_motion_blur_type: list[tuple[str, str, str]] = []
        self.enum_rumble_type: list[tuple[str, str, str]] = []
        self.enum_transition_general_type: list[tuple[str, str, str]] = []
        self.enum_spawn_flag: list[tuple[str, str, str]] = []
        self.enum_end_sfx: list[tuple[str, str, str]] = []
        self.enum_split_interp_type: list[tuple[str, str, str]] = []
        self.enum_spline_rel_to: list[tuple[str, str, str]] = []

        self.enumByID = {enum.id: enum for enum in self.enumDataList}
        self.enumByKey = {enum.key: enum for enum in self.enumDataList}

        key_to_enum = {
            "cmd": "ootEnumCsCmd",
            "miscType": "ootEnumCsMiscType",
            "textType": "ootEnumCsTextType",
            "fadeOutSeqPlayer": "ootEnumCsFadeOutSeqPlayer",
            "modifySeqType": "enum_cs_modify_seq_type",
            "transitionType": "ootEnumCsTransitionType",
            "destinationType": "ootEnumCsDestination",
            "chooseCreditsSceneType": "enum_cs_credits_scene_type",
            "motionBlurType": "enum_cs_motion_blur_type",
            "rumbleType": "enum_cs_rumble_type",
            "transitionGeneralType": "enum_cs_transition_general_type",
            "spawnFlag": "enum_cs_spawn_flag",
            "endSfx": "enum_cs_end_sfx",
            "csSplineInterpType": "enum_cs_split_interp_type",
            "csSplineRelTo": "enum_cs_spline_rel_to",
            "playerCueId": "ootEnumCsPlayerCueId",
            "naviQuestHintType": "ootEnumNaviQuestHintType",
            "ocarinaSongActionId": "ootEnumOcarinaSongActionId",
            "seqId": "ootEnumSeqId",
        }

        for key in self.enumByKey.keys():
            name = ("ootEnum" + key[0].upper() + key[1:]) if game == "OOT" else key_to_enum[key]
            setattr(self, name, self.get_enum_data(key))

    def get_enum_data(self, enumKey: str):
        enum = self.enumByKey[enumKey]
        firstIndex = min(1, *(item.index for item in enum.items))
        lastIndex = max(1, *(item.index for item in enum.items)) + 1
        enumData = [self.deletedEntry] * lastIndex
        custom = ("Custom", "Custom", "Custom")

        for item in enum.items:
            if item.index < lastIndex:
                identifier = item.key
                enumData[item.index] = (identifier, item.name, item.id)

        if firstIndex > 0:
            enumData[0] = custom
        else:
            enumData.insert(0, custom)

        return enumData
