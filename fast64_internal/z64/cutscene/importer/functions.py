import bpy

from typing import Optional
from .classes import CutsceneImport

from ....game_data import game_data
from ...utility import is_hackeroot


def importCutsceneData(filePath: Optional[str], sceneData: Optional[str], csName: Optional[str] = None):
    """Initialises and imports the cutscene data from either a file or the scene data"""
    # NOTE: `sceneData` is the data read when importing a scene
    csMotionImport = CutsceneImport(filePath, sceneData, csName, game_data.z64.is_mm())
    return csMotionImport.setCutsceneData(
        bpy.context.scene.ootCSNumber,
        is_hackeroot() or bpy.context.scene.fast64.oot.useDecompFeatures,
        bpy.context.scene.fast64.oot.exportMotionOnly,
    )
