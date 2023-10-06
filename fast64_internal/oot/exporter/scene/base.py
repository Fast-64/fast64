from dataclasses import dataclass, field
from bpy.types import Object
from typing import TYPE_CHECKING
from ....utility import PluginError, exportColor, ootGetBaseOrCustomLight
from ...scene.properties import OOTSceneHeaderProperty, OOTLightProperty
from ...oot_constants import ootData
from ...oot_model_classes import OOTModel
from ..commands import SceneCommands
from ..base import altHeaderList
from ..collision import CollisionBase
from .classes import TransitionActor, EntranceActor, EnvLightSettings, Path
from .header import SceneAlternateHeader, SceneHeader

if TYPE_CHECKING:
    from ..room import Room


@dataclass
class SceneBase(CollisionBase, SceneCommands):
    """This class hosts various data and functions related to a scene file"""
