from .scene import getIncludes, getSceneC
from .scene_table_c import modifySceneTable, getDrawConfig
from .spec import editSpecFile
from .scene_folder import modifySceneFiles, deleteSceneFiles
from .scene_bootup import (
    OOTBootupSceneOptions,
    OOT_ClearBootupScene,
    setBootupScene,
    ootSceneBootupRegister,
    ootSceneBootupUnregister,
)
