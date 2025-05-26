import bpy

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from bpy.types import Object

from ....utility import PluginError, CData, indent
from ...oot_utility import getCustomProperty
from ...scene.properties import OOTSceneHeaderProperty
from .data import CutsceneData


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

    paramNumber: int = field(init=False, default=2)

    @staticmethod
    def new(name: Optional[str], csObj: Optional[Object], useMacros: bool, motionOnly: bool):
        # when csObj is None it means we're in import context
        if csObj is not None:
            if name is None:
                name = csObj.name.removeprefix("Cutscene.").replace(".", "_")
            data = CutsceneData.new(csObj, useMacros, motionOnly)
            return Cutscene(name, data, data.totalEntries, data.frameCount, useMacros, motionOnly)

        return None
        
    @staticmethod
    def export(cs_obj: Object, skip_includes: bool = False, skip_endif: bool = False):
        # create the cutscene
        cutscene = Cutscene.new(
            cs_obj.name.removeprefix("Cutscene."),
            cs_obj,
            bpy.context.scene.fast64.oot.useDecompFeatures,
            bpy.context.scene.fast64.oot.exportMotionOnly,
        )

        # write file
        source_path = Path(bpy.context.scene.ootCutsceneExportPath).resolve()

        if source_path.suffix != ".c":
            raise PluginError("ERROR: output file must end with '.c'")

        header_path = source_path.with_suffix(".h")
        filedata = cutscene.get_file(source_path.stem, skip_includes, skip_endif)

        if not skip_includes:
            # export the data in writing mode (single cutscene or first cutscene of the multiple export)

            header_path.write_text(filedata.header, encoding="utf-8", newline="\n")
            source_path.write_text(filedata.source, encoding="utf-8", newline="\n")
        else:
            # export the data in append mode (the other cutscenes of the multiple export)

            with header_path.open("a", encoding="utf-8", newline="\n") as file:
                file.write(filedata.header)

            with source_path.open("a", encoding="utf-8", newline="\n") as file:
                file.write(filedata.source)

    def getC(self):
        """Returns the cutscene data"""

        if self.data is not None:
            csData = CData()
            declarationBase = f"CutsceneData {self.name}[]"

            # this list's order defines the order of the commands in the cutscene array
            dataListNames = []

            if not self.motionOnly:
                dataListNames = [
                    "textList",
                    "miscList",
                    "rumbleList",
                    "transitionList",
                    "lightSettingsList",
                    "timeList",
                    "seqList",
                    "fadeSeqList",
                ]

            dataListNames.extend(
                [
                    "playerCueList",
                    "actorCueList",
                    "camEyeSplineList",
                    "camATSplineList",
                    "camEyeSplineRelPlayerList",
                    "camATSplineRelPlayerList",
                    "camEyeList",
                    "camATList",
                ]
            )

            if self.data.motionFrameCount > self.frameCount:
                self.frameCount += self.data.motionFrameCount - self.frameCount

            # .h
            csData.header = f"extern {declarationBase};\n"

            # .c
            csData.source = (
                declarationBase
                + " = {\n"
                + (indent + f"CS_HEADER({self.totalEntries}, {self.frameCount}),\n")
                + (self.data.destination.getCmd() if self.data.destination is not None else "")
                + "".join(entry.getCmd() for curList in dataListNames for entry in getattr(self.data, curList))
                + (indent + "CS_END_OF_SCRIPT(),\n")
                + "};\n\n"
            )

            return csData
        else:
            raise PluginError("ERROR: CutsceneData not initialised!")
    
    def get_file(self, filename: str, skip_includes: bool, skip_endif: bool):
        filedata = CData()

        if not skip_includes:
            if bpy.context.scene.fast64.oot.is_globalh_present():
                includes = [
                    '#include "ultra64.h"',
                    '#include "z64.h"',
                    '#include "macros.h"',
                    '#include "command_macros_base.h"',
                    '#include "z64cutscene_commands.h"',
                ]
            else:
                includes = [
                    '#include "ultra64.h"',
                    '#include "sequence.h"',
                    '#include "z64math.h"',
                    '#include "z64cutscene.h"',
                    '#include "z64cutscene_commands.h"',
                ]

            filedata.header = (
                f"#ifndef {filename.upper()}_H\n" + f"#define {filename.upper()}_H\n\n" + "\n".join(includes) + "\n\n"
            )
            filedata.source = f'#include "{filename}.h"\n\n'

        filedata.append(self.getC())

        if not skip_endif:
            filedata.header += "\n#endif\n"

        return filedata


@dataclass
class SceneCutscene:
    """This class hosts cutscene data"""

    entries: list[Cutscene]

    @staticmethod
    def new(props: OOTSceneHeaderProperty, headerIndex: int, useMacros: bool):
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
        return SceneCutscene(entries)

    def getCmd(self):
        """Returns the cutscene data scene command"""
        if len(self.entries) == 0:
            raise PluginError("ERROR: Cutscene entry list is empty!")

        # entry No. 0 is always self.csObj
        return indent + f"SCENE_CMD_CUTSCENE_DATA({self.entries[0].name}),\n"
