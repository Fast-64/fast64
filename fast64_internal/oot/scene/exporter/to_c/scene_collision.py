from .....utility import CData
from ....oot_collision import ootCollisionToC


# Writes the collision data for a scene
def ootSceneCollisionToC(scene):
    sceneCollisionC = CData()
    sceneCollisionC.append(ootCollisionToC(scene.collision))
    return sceneCollisionC
