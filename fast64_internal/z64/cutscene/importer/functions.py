import bpy

from typing import Optional
from .classes import CutsceneImport
from ...utility import is_oot_features


def importCutsceneData(filePath: Optional[str], sceneData: Optional[str], csName: Optional[str] = None):
    """Initialises and imports the cutscene data from either a file or the scene data"""
    # NOTE: ``sceneData`` is the data read when importing a scene
    csMotionImport = CutsceneImport(filePath, sceneData, csName, not is_oot_features())
    return csMotionImport.setCutsceneData(bpy.context.scene.ootCSNumber)
