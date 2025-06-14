import bpy

from ....utility import CData, toAlnum


def convertToUnsignedShort(value: int) -> int:
    return int.from_bytes(value.to_bytes(2, "big", signed=(value < 0)), "big", signed=False)


class OOTAnimation:
    def __init__(self, name, filename: str):
        self.name = toAlnum(name)
        self.filename = filename
        self.segmentID = None
        self.indices = {}
        self.values = []
        self.frameCount = None
        self.limit = None

    def valuesName(self):
        return self.name + "FrameData"

    def indicesName(self):
        return self.name + "JointIndices"

    def toC(self):
        data = CData()

        data.header = f"#ifndef {self.filename.upper()}_H\n" + f"#define {self.filename.upper()}_H\n\n"

        if bpy.context.scene.fast64.oot.is_globalh_present():
            data.header += '#include "ultra64.h"\n' + '#include "global.h"\n\n'
        elif bpy.context.scene.fast64.oot.is_z64sceneh_present():
            data.header += '#include "ultra64.h"\n' + '#include "array_count.h"\n' + '#include "z64animation.h"\n\n'
        else:
            data.header += '#include "ultra64.h"\n' + '#include "array_count.h"\n' + '#include "animation.h"\n\n'
        data.source = f'#include "{self.filename}.h"\n\n'

        # values
        data.source += "s16 " + self.valuesName() + "[" + str(len(self.values)) + "] = {\n"
        counter = 0
        for value in self.values:
            if counter == 0:
                data.source += "\t"
            data.source += format(convertToUnsignedShort(value), "#06x") + ", "
            counter += 1
            if counter >= 16:  # round number for finding/counting data
                counter = 0
                data.source += "\n"
        data.source += "};\n\n"

        # indices (index -1 => translation)
        data.source += "JointIndex " + self.indicesName() + "[" + str(len(self.indices)) + "] = {\n"
        for index in range(-1, len(self.indices) - 1):
            data.source += "\t{ "
            for field in range(3):
                data.source += (
                    format(
                        convertToUnsignedShort(self.indices[index][field]),
                        "#06x",
                    )
                    + ", "
                )
            data.source += "},\n"
        data.source += "};\n\n"

        # header
        data.header += "extern AnimationHeader " + self.name + ";\n"
        data.source += (
            "AnimationHeader "
            + self.name
            + " = { { "
            + str(self.frameCount)
            + " }, "
            + self.valuesName()
            + ", "
            + self.indicesName()
            + ", "
            + str(self.limit)
            + " };\n\n"
        )

        data.header += "\n#endif\n"
        return data


class OOTLinkAnimation:
    def __init__(self, name):
        self.headerName = toAlnum(name)
        self.frameCount = None
        self.data = []

    def dataName(self):
        return self.headerName + "Data"

    def toC(self, isCustomExport: bool):
        data = CData()
        animHeaderData = CData()

        data.header = f"#ifndef {self.dataName().upper()}_H\n" + f"#define {self.dataName().upper()}_H\n\n"

        animHeaderData.header = f"#ifndef {self.headerName.upper()}_H\n" + f"#define {self.headerName.upper()}_H\n\n"

        if bpy.context.scene.fast64.oot.is_globalh_present():
            data.header = '#include "ultra64.h"\n' + '#include "global.h"\n\n'
            animHeaderData.header = '#include "ultra64.h"\n' + '#include "global.h"\n\n'
        elif bpy.context.scene.fast64.oot.is_z64sceneh_present():
            data.header = '#include "ultra64.h"\n' + '#include "array_count.h"\n' + '#include "z64animation.h"\n\n'
            animHeaderData.header = (
                '#include "ultra64.h"\n' + '#include "array_count.h"\n' + '#include "z64animation.h"\n\n'
            )
        else:
            data.header = '#include "ultra64.h"\n' + '#include "array_count.h"\n' + '#include "animation.h"\n\n'
            animHeaderData.header = (
                '#include "ultra64.h"\n' + '#include "array_count.h"\n' + '#include "animation.h"\n\n'
            )

        data.source = f'#include "{self.dataName()}.h"\n\n'
        animHeaderData.source = f'#include "{self.headerName}.h"\n'

        # TODO: handle custom import?
        if isCustomExport:
            animHeaderData.source += f'#include "{self.dataName()}.h"\n\n'
        else:
            animHeaderData.source += f'#include "assets/misc/link_animetion/{self.dataName()}.h"\n\n'

        # data
        data.header += f"extern s16 {self.dataName()}[];\n"
        data.source += f"s16 {self.dataName()}[] = {{\n"
        counter = 0
        for value in self.data:
            if counter == 0:
                data.source += "\t"
            data.source += format(convertToUnsignedShort(value), "#06x") + ", "
            counter += 1
            if counter >= 8:  # round number for finding/counting data
                counter = 0
                data.source += "\n"
        data.source += "\n};\n\n"

        # header
        animHeaderData.header += f"extern LinkAnimationHeader {self.headerName};\n"
        animHeaderData.source += (
            f"LinkAnimationHeader {self.headerName} = {{\n\t{{ {str(self.frameCount)} }}, {self.dataName()} \n}};\n\n"
        )

        data.header += "\n#endif\n"
        animHeaderData.header += "\n#endif\n"
        return data, animHeaderData
