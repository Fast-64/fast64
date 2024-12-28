import bpy

from typing import Optional
from .classes import CutsceneImport


def importCutsceneData(filePath: Optional[str], sceneData: Optional[str], csName: Optional[str] = None):
    """Initialises and imports the cutscene data from either a file or the scene data"""
    # NOTE: ``sceneData`` is the data read when importing a scene
    csMotionImport = CutsceneImport(filePath, sceneData, csName)
    return csMotionImport.setCutsceneData(bpy.context.scene.ootCSNumber)
