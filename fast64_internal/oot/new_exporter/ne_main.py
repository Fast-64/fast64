import bpy

from mathutils import Matrix, Vector
from bpy.ops import object
from bpy.types import Object
from ...utility import PluginError
from ..oot_utility import ExportInfo, sceneNameFromID
from .classes import OOTSceneExport


def getSceneObject() -> Object:
    """Returns the selected OoT scene empty object to export"""
    if bpy.context.mode != "OBJECT":
        object.mode_set(mode="OBJECT")

    sceneObj = bpy.context.scene.ootSceneExportObj

    if sceneObj is None:
        raise PluginError("Scene object input not set.")
    elif sceneObj.type != "EMPTY" or sceneObj.ootEmptyType != "Scene":
        raise PluginError("The input object is not an empty with the Scene type.")

    return sceneObj


def exportScene(exportInfo: ExportInfo):
    """Returns the initialised scene exporter"""

    ootBlenderScale = bpy.context.scene.ootBlenderScale
    bootOptions = bpy.context.scene.fast64.oot.bootupSceneOptions
    hackerFeaturesEnabled = bpy.context.scene.fast64.oot.hackerFeaturesEnabled

    return OOTSceneExport(
        exportInfo,
        getSceneObject(),
        exportInfo.name,
        ootBlenderScale,
        Matrix.Diagonal(Vector((ootBlenderScale, ootBlenderScale, ootBlenderScale))).to_4x4(),
        bpy.context.scene.f3d_type,
        bpy.context.scene.saveTextures,
        bootOptions if hackerFeaturesEnabled else None
    )
