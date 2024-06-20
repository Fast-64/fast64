import re
import traceback
from mathutils import Vector
from ..f3d.f3d_gbi import F3D
from ..f3d.f3d_material import RDPSettings
from ..f3d.f3d_parser import F3DContext, F3DParsedCommands, ParsedMacro, math_eval, parseDLData, parseVertexData
from ..f3d.f3d_writer import F3DVert
from ..utility import PluginError, float_from_u16_str, gammaInverseValue, int_from_s16_str, readFile, unpackNormal


def courseVertexFormatPatterns():
    # position, uv, color/normal
    return (
        # decomp format
        r"\{\s*"
        r"\{+([^,\}]*),([^,\}]*),([^,\}]*)\}\s*,\s*"
        r"\{([^,\}]*),([^,\}]*)\}\s*,\s*"
        r"\{MACRO_COLOR_FLAG\(([^,\}]*),([^,\}]*),([^,\}]*),([^,\}])*\),([^,\}]*)\}\s*"
        r"\}"
    )


def parseCourseVtx(path: str, f3d):
    data = readFile(path)
    pattern = courseVertexFormatPatterns()
    vertexData = []
    for values in re.findall(pattern, data, re.DOTALL):
        values = [math_eval(g, f3d) for g in values]
        vertexData.append(
            F3DVert(
                Vector(values[0:3]),
                Vector(values[3:5]),
                Vector(values[5:8]),
                unpackNormal(values[8]),
                values[9],
            )
        )
    return vertexData


class MK64F3DContext(F3DContext):
    def getVertexDataStart(self, vertexDataParam: str, f3d: F3D):
        matchResult = re.search(r"\&?([A-Za-z0-9\_]*)\s*(\[([^\]]*)\])?\s*(\+(.*))?", vertexDataParam)
        if matchResult is None:
            raise PluginError(f"SPVertex param {vertexDataParam} is malformed.")

        offset = 0
        if matchResult.group(3):
            offset += math_eval(matchResult.group(3), f3d)
        if matchResult.group(5):
            offset += math_eval(matchResult.group(5), f3d)

        name = matchResult.group(1)

        if matchResult.group(1).startswith("0x04"):
            offset = (int(matchResult.group(1), 16) - 0x04000000) // 16
            name = hex(0x04000000)
        return name, offset
