from .classes import Common, altHeaderList
from .collision import CollisionCommon
from .scene import SceneCommon


includeData = {
    "common": (
        "\n".join(
            [
                '#include "ultra64/ultratypes.h"',
                '#include "ultra64/gbi.h"',
                '#include "libc/stddef.h"',
                '#include "libc/stdint.h"',
                '#include "z64math.h"',
            ]
        )
        + "\n"
    ),
    "roomMain": (
        "\n".join(
            [
                '#include "z64object.h"',
                '#include "z64actor.h"',
                '#include "z64scene.h"',
            ]
        )
        + "\n"
    ),
    "roomShapeInfo": (
        "\n".join(
            [
                '#include "macros.h"',
                '#include "z64scene.h"',
            ]
        )
        + "\n"
    ),
    "sceneMain": (
        "\n".join(
            [
                '#include "z64dma.h"',
                '#include "z64actor.h"',
                '#include "z64scene.h"',
                '#include "z64environment.h"',
            ]
        )
        + "\n"
    ),
    "collision": (
        "\n".join(
            [
                '#include "macros.h"',
                '#include "z64camera.h"',
                '#include "z64bgcheck.h"',
            ]
        )
        + "\n"
    ),
    "cutscene": (
        "\n".join(
            [
                '#include "z64cutscene.h"',
                '#include "z64cutscene_commands.h"',
            ]
        )
        + "\n"
    ),
}
