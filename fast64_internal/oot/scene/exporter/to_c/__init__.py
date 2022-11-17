from .scene_header import ootSceneMainToC, ootSceneTexturesToC
from .scene import getIncludes, getSceneC
from .scene_table_c import modifySceneTable, getDrawConfig
from .spec import modifySegmentDefinition
from .scene_folder import modifySceneFiles, deleteSceneFiles
from .scene_bootup import (
    OOTBootupSceneOptions,
    OOT_ClearBootupScene,
    setBootupScene,
    ootSceneBootupRegister,
    ootSceneBootupUnregister,
)
from .room_header import ootRoomMainToC
from .room_shape import ootRoomMeshToC