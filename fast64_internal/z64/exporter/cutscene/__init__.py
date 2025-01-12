import bpy

from dataclasses import dataclass, field
from typing import Optional, TYPE_CHECKING
from bpy.types import Object
from ....game_data import game_data
from ....utility import PluginError, CData, indent
from ...utility import getCustomProperty, is_oot_features
from ...scene.properties import Z64_SceneHeaderProperty
from .data import CutsceneData

if TYPE_CHECKING:
    from ...cutscene.properties import OOTCutsceneProperty


# NOTE: ``paramNumber`` is the expected number of parameters inside the parsed commands,
# this account for the unused parameters. Every classes are based on the commands arguments from ``z64cutscene_commands.h``

# NOTE: ``params`` is the list of parsed parameters, it can't be ``None`` if we're importing a scene,
# when it's ``None`` it will get the data from the cutscene objects


@dataclass
class Cutscene:
    """This class defines a cutscene, including its data and its informations"""

    name: str
    data: CutsceneData
    totalEntries: int
    frameCount: int
    useMacros: bool
    motionOnly: bool
    next_entrance: Optional[str]
    spawn: Optional[int]
    spawn_flags: Optional[str]

    paramNumber: int = field(init=False, default=2)

    @staticmethod
    def new(name: Optional[str], csObj: Optional[Object], useMacros: bool, motionOnly: bool):
        # when csObj is None it means we're in import context
        if csObj is not None:
            if name is None:
                name = csObj.name.removeprefix("Cutscene.").replace(".", "_")

            cs_prop: "OOTCutsceneProperty" = csObj.ootCutsceneProperty
            if cs_prop.spawn_flag_type == "Custom":
                spawn_flag: str = cs_prop.spawn_flags_custom
            elif cs_prop.spawn_flag_type == "CS_SPAWN_FLAG_ONCE":
                spawn_flag: str = f"CS_SPAWN_FLAG_ONCE({cs_prop.spawn_flag})"
            else:
                spawn_flag: str = cs_prop.spawn_flag_type

            data = CutsceneData.new(csObj, useMacros, motionOnly)
            return Cutscene(
                name,
                data,
                data.totalEntries,
                data.frameCount,
                useMacros,
                motionOnly,
                cs_prop.next_entrance if game_data.z64.is_mm() or not is_oot_features() else None,
                cs_prop.play_on_spawn if game_data.z64.is_mm() or not is_oot_features() else None,
                spawn_flag if game_data.z64.is_mm() or not is_oot_features() else None,
            )

    def get_entry(self):
        return "{ " + f"{self.name}, {self.next_entrance}, {self.spawn}, {self.spawn_flags}" + " }"

    def getC(self):
        """Returns the cutscene data"""

        if self.data is not None:
            csData = CData()
            declarationBase = f"CutsceneData {self.name}[]"

            # this list's order defines the order of the commands in the cutscene array
            dataListNames = []

            if not self.motionOnly:
                dataListNames.extend(
                    [
                        "textList",
                        "miscList",
                        "rumbleList",
                        "transitionList",
                        "lightSettingsList",
                        "timeList",
                        "seqList",
                        "fadeSeqList",
                        "motion_blur_list",
                        "credits_scene_list",
                        "transition_general_list",
                        "modify_seq_list",
                        "start_ambience_list",
                        "fade_out_ambience_list",
                    ]
                )

            if is_oot_features():
                dataListNames.extend(
                    [
                        "camEyeSplineList",
                        "camATSplineList",
                        "camEyeSplineRelPlayerList",
                        "camATSplineRelPlayerList",
                        "camEyeList",
                        "camATList",
                    ]
                )
            else:
                dataListNames.extend(
                    [
                        "camSplineList",
                    ]
                )

            dataListNames.extend(
                [
                    "playerCueList",
                    "actorCueList",
                ]
            )

            if self.data.motionFrameCount > self.frameCount:
                self.frameCount += self.data.motionFrameCount - self.frameCount

            # .h
            csData.header = f"extern {declarationBase};\n"

            # .c
            if game_data.z64.is_mm():
                cs_header = "CS_BEGIN_CUTSCENE"
                cs_end = "CS_END"
            else:
                cs_header = "CS_HEADER"
                cs_end = "CS_END_OF_SCRIPT"

            command_data = ""
            for curList in dataListNames:
                for entry in getattr(self.data, curList):
                    if len(entry.entries) > 0:
                        command_data += entry.getCmd()

            csData.source = (
                declarationBase
                + " = {\n"
                + (indent + f"{cs_header}({self.totalEntries}, {self.frameCount}),\n")
                + (self.data.destination.getCmd() if self.data.destination is not None else "")
                + (self.data.give_tatl.getCmd() if self.data.give_tatl is not None else "")
                + command_data
                + (indent + f"{cs_end}(),\n")
                + "};\n\n"
            )

            return csData
        else:
            raise PluginError("ERROR: CutsceneData not initialised!")


@dataclass
class SceneCutscene:
    """This class hosts cutscene data"""

    name: str
    entries: list[Cutscene]

    @staticmethod
    def new(name: str, props: Z64_SceneHeaderProperty, headerIndex: int, useMacros: bool):
        csObj: Object = props.csWriteObject
        cutsceneObjects: list[Object] = [csObj for csObj in props.extraCutscenes]
        entries: list[Cutscene] = []

        if headerIndex > 0 and len(cutsceneObjects) > 0:
            raise PluginError("ERROR: Extra cutscenes can only belong to the main header!")

        cutsceneObjects.insert(0, csObj)
        for csObj in cutsceneObjects:
            if csObj is not None:
                if csObj.ootEmptyType != "Cutscene":
                    raise PluginError(
                        "ERROR: Object selected as cutscene is wrong type, must be empty with Cutscene type"
                    )
                elif csObj.parent is not None:
                    raise PluginError("ERROR: Cutscene empty object should not be parented to anything")

                writeType = props.csWriteType
                csWriteCustom = None
                if writeType == "Custom":
                    csWriteCustom = getCustomProperty(props, "csWriteCustom")

                if props.writeCutscene:
                    # if csWriteCustom is None then the name will auto-set from the csObj passed in the class
                    entries.append(
                        Cutscene.new(csWriteCustom, csObj, useMacros, bpy.context.scene.fast64.oot.exportMotionOnly)
                    )
        return SceneCutscene(name, entries)

    def to_c(self):
        """Returns the cutscene script entry list (for MM)"""

        data = CData()
        array_name = f"CutsceneScriptEntry {self.name}[]"

        # .h
        data.header = f"extern {array_name};"

        # .c
        data.source = (
            array_name + " = {\n" + indent + f",\n{indent}".join(cs.get_entry() for cs in self.entries) + "\n};\n\n"
        )

        return data

    def getCmd(self):
        """Returns the cutscene data scene command"""
        if len(self.entries) == 0:
            raise PluginError("ERROR: Cutscene entry list is empty!")

        if is_oot_features():
            # entry No. 0 is always self.csObj
            return indent + f"SCENE_CMD_CUTSCENE_DATA({self.entries[0].name}),\n"
        else:
            return indent + f"SCENE_CMD_CUTSCENE_SCRIPT_LIST({len(self.entries)}, {self.name}),\n"
