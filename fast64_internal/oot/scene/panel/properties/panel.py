from bpy.utils import register_class, unregister_class
from bpy.types import Object
from bpy.props import PointerProperty
from .operators import OOT_SearchMusicSeqEnumOperator, OOT_SearchSceneEnumOperator
from .classes import (
    OOTExitProperty,
    OOTLightProperty,
    OOTLightGroupProperty,
    OOTSceneTableEntryProperty,
    OOTExtraCutsceneProperty,
    OOTSceneHeaderProperty,
    OOTAlternateSceneHeaderProperty,
)


classes = (
    OOT_SearchMusicSeqEnumOperator,
    OOT_SearchSceneEnumOperator,

    OOTExitProperty,
    OOTLightProperty,
    OOTLightGroupProperty,
    OOTSceneTableEntryProperty,
    OOTExtraCutsceneProperty,
    OOTSceneHeaderProperty,
    OOTAlternateSceneHeaderProperty,
)


def scene_props_classes_register():
    for cls in classes:
        register_class(cls)

    Object.ootSceneHeader = PointerProperty(type=OOTSceneHeaderProperty)
    Object.ootAlternateSceneHeaders = PointerProperty(type=OOTAlternateSceneHeaderProperty)


def scene_props_classes_unregister():
    del Object.ootSceneHeader
    del Object.ootAlternateSceneHeaders

    for cls in reversed(classes):
        unregister_class(cls)
