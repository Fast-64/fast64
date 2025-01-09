from dataclasses import dataclass, field
from os import path
from pathlib import Path
from .common import Z64_BaseElement, get_xml_root


@dataclass
class Z64_ItemElement(Z64_BaseElement):
    parentKey: str
    game: str
    desc: str

    def __post_init__(self):
        # generate the name from the id

        if self.name is None:
            keyToPrefix = {
                "cs_cmd": "CS_CMD",
                "cs_misc_type": "CS_MISC",
                "cs_text_type": "CS_TEXT",
                "cs_fade_out_seq_player": "CS_FADE_OUT",
                "cs_transition_type": "CS_TRANS",
                "cs_destination": ("CS_DESTINATION" if self.game == "MM" else "CS_DEST"),
                "cs_player_cue_id": "PLAYER_CUEID",
                "cs_modify_seq_type": "CS_MOD",
                "cs_credits_scene_type": "CS_CREDITS",
                "cs_motion_blur_type": "CS_MOTION_BLUR",
                "cs_rumble_type": "CS_RUMBLE",
                "cs_transition_general": "CS_TRANS_GENERAL",
                "cs_spline_interp_type": "CS_CAM_INTERP",
                "cs_spline_rel": "",  # TODO: set the value to `CS_CAM_REL` once this is documented
                "cs_spawn_flag": "CS_SPAWN_FLAG",
                "actor_cs_end_sfx": "CS_END_SFX",
                "navi_quest_hint_type": "NAVI_QUEST_HINTS",
                "ocarina_song_action_id": "OCARINA_ACTION",
                "seq_id": "NA_BGM",
                "draw_config": ("SCENE_DRAW_CFG" if self.game == "MM" else "SDC"),
                "surface_material": "SURFACE_MATERIAL",
                "global_object": "OBJECT",
            }

            self.name = self.id.removeprefix(f"{keyToPrefix[self.parentKey]}_")

            if self.parentKey in ["cs_cmd", "cs_player_cue_id"]:
                split = self.name.split("_")
                if self.parentKey == "cs_cmd" and "ACTOR_CUE" in self.id:
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
                            game,
                            item.attrib.get("Description", "Unset"),
                        )
                        for item in enum
                    ],
                )
            )

        # create list of tuples used by Blender's enum properties
        self.deletedEntry = ("None", "(Deleted from the XML)", "None")

        self.enum_cs_cmd: list[tuple[str, str, str]] = []
        self.enum_cs_misc_type: list[tuple[str, str, str]] = []
        self.enum_cs_text_type: list[tuple[str, str, str]] = []
        self.enum_cs_fade_out_seq_player: list[tuple[str, str, str]] = []
        self.enum_cs_transition_type: list[tuple[str, str, str]] = []
        self.enum_cs_destination: list[tuple[str, str, str]] = []
        self.enum_cs_player_cue_id: list[tuple[str, str, str]] = []
        self.enum_cs_modify_seq_type: list[tuple[str, str, str]] = []
        self.enum_cs_credits_scene_type: list[tuple[str, str, str]] = []
        self.enum_cs_motion_blur_type: list[tuple[str, str, str]] = []
        self.enum_cs_rumble_type: list[tuple[str, str, str]] = []
        self.enum_cs_transition_general: list[tuple[str, str, str]] = []
        self.enum_cs_spline_interp_type: list[tuple[str, str, str]] = []
        self.enum_cs_spline_rel: list[tuple[str, str, str]] = []
        self.enum_cs_spawn_flag: list[tuple[str, str, str]] = []
        self.enum_actor_cs_end_sfx: list[tuple[str, str, str]] = []
        self.enum_navi_quest_hint_type: list[tuple[str, str, str]] = []
        self.enum_ocarina_song_action_id: list[tuple[str, str, str]] = []
        self.enum_seq_id: list[tuple[str, str, str]] = []
        self.enum_draw_config: list[tuple[str, str, str]] = []
        self.enum_surface_material: list[tuple[str, str, str]] = []
        self.enum_global_object: list[tuple[str, str, str]] = []

        self.enumByID = {enum.id: enum for enum in self.enumDataList}
        self.enumByKey = {enum.key: enum for enum in self.enumDataList}

        for key in self.enumByKey.keys():
            setattr(self, f"enum_{key}", self.get_enum_data(key))

        self.enum_cs_actor_cue_list_cmd_type = [
            item for item in self.enum_cs_cmd if "actor_cue" in item[0] or "player_cue" in item[0]
        ]
        self.enum_cs_actor_cue_list_cmd_type.sort()
        self.enum_cs_actor_cue_list_cmd_type.insert(0, ("Custom", "Custom", "Custom"))

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
