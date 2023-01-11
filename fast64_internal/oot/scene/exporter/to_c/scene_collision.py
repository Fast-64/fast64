from ....oot_collision import ootCollisionToC
from ....oot_level_classes import OOTScene


# Writes the collision data for a scene
def getSceneCollision(outScene: OOTScene):
    # @TODO: delete this function and rename ``ootCollisionToC`` into ``getSceneCollision``
    # when the ``oot_collision.py`` code is cleaned up
    return ootCollisionToC(outScene.collision)
