import os, bpy, mathutils
from ....f3d.f3d_writer import TriangleConverterInfo, saveStaticModel, getInfoDict

from ....utility import (
    PluginError,
    toAlnum,
)

from ...oot_utility import (
    CullGroup,
    checkUniformScale,
    ootConvertTranslation,
)

from ...oot_level_classes import OOTDLGroup


class BoundingBox:
    def __init__(self):
        self.minPoint = None
        self.maxPoint = None
        self.points = []

    def addPoint(self, point: tuple[float, float, float]):
        if self.minPoint is None:
            self.minPoint = list(point[:])
        else:
            for i in range(3):
                if point[i] < self.minPoint[i]:
                    self.minPoint[i] = point[i]
        if self.maxPoint is None:
            self.maxPoint = list(point[:])
        else:
            for i in range(3):
                if point[i] > self.maxPoint[i]:
                    self.maxPoint[i] = point[i]
        self.points.append(point)

    def addMeshObj(self, obj: bpy.types.Object, transform: mathutils.Matrix):
        mesh = obj.data
        for vertex in mesh.vertices:
            self.addPoint(transform @ vertex.co)

    def getEnclosingSphere(self) -> tuple[float, float]:
        centroid = (mathutils.Vector(self.minPoint) + mathutils.Vector(self.maxPoint)) / 2
        radius = 0
        for point in self.points:
            distance = (mathutils.Vector(point) - centroid).length
            if distance > radius:
                radius = distance

        # print(f"Radius: {radius}, Centroid: {centroid}")

        transformedCentroid = [round(value) for value in centroid]
        transformedRadius = round(radius)
        return transformedCentroid, transformedRadius


# This function should be called on a copy of an object
# The copy will have modifiers / scale applied and will be made single user
# When we duplicated obj hierarchy we stripped all ignore_renders from hierarchy.
def ootProcessMesh(
    roomMesh, DLGroup, sceneObj, obj, transformMatrix, convertTextureData, LODHierarchyObject, boundingBox: BoundingBox
):
    relativeTransform = transformMatrix @ sceneObj.matrix_world.inverted() @ obj.matrix_world
    translation, rotation, scale = relativeTransform.decompose()

    if obj.type == "EMPTY" and obj.ootEmptyType == "Cull Group":
        if LODHierarchyObject is not None:
            raise PluginError(
                obj.name
                + " cannot be used as a cull group because it is "
                + "in the sub-hierarchy of the LOD group empty "
                + LODHierarchyObject.name
            )

        cullProp = obj.ootCullGroupProperty
        checkUniformScale(scale, obj)
        DLGroup = roomMesh.addMeshGroup(
            CullGroup(
                ootConvertTranslation(translation),
                scale if cullProp.sizeControlsCull else [cullProp.manualRadius],
                obj.empty_display_size if cullProp.sizeControlsCull else 1,
            )
        ).DLGroup

    elif obj.type == "MESH" and not obj.ignore_render:
        triConverterInfo = TriangleConverterInfo(obj, None, roomMesh.model.f3d, relativeTransform, getInfoDict(obj))
        fMeshes = saveStaticModel(
            triConverterInfo,
            roomMesh.model,
            obj,
            relativeTransform,
            roomMesh.model.name,
            convertTextureData,
            False,
            "oot",
        )
        if fMeshes is not None:
            for drawLayer, fMesh in fMeshes.items():
                DLGroup.addDLCall(fMesh.draw, drawLayer)

        boundingBox.addMeshObj(obj, relativeTransform)

    alphabeticalChildren = sorted(obj.children, key=lambda childObj: childObj.original_name.lower())
    for childObj in alphabeticalChildren:
        if childObj.type == "EMPTY" and childObj.ootEmptyType == "LOD":
            ootProcessLOD(
                roomMesh,
                DLGroup,
                sceneObj,
                childObj,
                transformMatrix,
                convertTextureData,
                LODHierarchyObject,
                boundingBox,
            )
        else:
            ootProcessMesh(
                roomMesh,
                DLGroup,
                sceneObj,
                childObj,
                transformMatrix,
                convertTextureData,
                LODHierarchyObject,
                boundingBox,
            )


def ootProcessLOD(
    roomMesh, DLGroup, sceneObj, obj, transformMatrix, convertTextureData, LODHierarchyObject, boundingBox: BoundingBox
):
    relativeTransform = transformMatrix @ sceneObj.matrix_world.inverted() @ obj.matrix_world
    translation, rotation, scale = relativeTransform.decompose()
    ootTranslation = ootConvertTranslation(translation)

    LODHierarchyObject = obj
    name = toAlnum(roomMesh.model.name + "_" + obj.name + "_lod")
    opaqueLOD = roomMesh.model.addLODGroup(name + "_opaque", ootTranslation, obj.f3d_lod_always_render_farthest)
    transparentLOD = roomMesh.model.addLODGroup(
        name + "_transparent", ootTranslation, obj.f3d_lod_always_render_farthest
    )

    index = 0
    for childObj in obj.children:
        # This group will not be converted to C directly, but its display lists will be converted through the FLODGroup.
        childDLGroup = OOTDLGroup(name + str(index), roomMesh.model.DLFormat)
        index += 1

        if childObj.type == "EMPTY" and childObj.ootEmptyType == "LOD":
            ootProcessLOD(
                roomMesh,
                childDLGroup,
                sceneObj,
                childObj,
                transformMatrix,
                convertTextureData,
                LODHierarchyObject,
                boundingBox,
            )
        else:
            ootProcessMesh(
                roomMesh,
                childDLGroup,
                sceneObj,
                childObj,
                transformMatrix,
                convertTextureData,
                LODHierarchyObject,
                boundingBox,
            )

        # We handle case with no geometry, for the cases where we have "gaps" in the LOD hierarchy.
        # This can happen if a LOD does not use transparency while the levels above and below it does.
        childDLGroup.createDLs()
        childDLGroup.terminateDLs()

        # Add lod AFTER processing hierarchy, so that DLs will be built by then
        opaqueLOD.add_lod(childDLGroup.opaque, childObj.f3d_lod_z * bpy.context.scene.ootBlenderScale)
        transparentLOD.add_lod(childDLGroup.transparent, childObj.f3d_lod_z * bpy.context.scene.ootBlenderScale)

    opaqueLOD.create_data()
    transparentLOD.create_data()

    DLGroup.addDLCall(opaqueLOD.draw, "Opaque")
    DLGroup.addDLCall(transparentLOD.draw, "Transparent")
