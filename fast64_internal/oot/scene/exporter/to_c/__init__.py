from .scene_header import ootSceneMainToC, ootSceneTexturesToC
from .level_c import ootSceneIncludes, ootLevelToC
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
