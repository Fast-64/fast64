import bpy
import ctypes

from pathlib import Path
from dataclasses import dataclass
from mathutils import Matrix, Vector
from bpy.types import Mesh, Object
from bpy.ops import object
from typing import Optional

from ....utility import (
    PluginError,
    CData,
    toAlnum,
    unhideAllAndGetHiddenState,
    restoreHiddenState,
    cleanupDuplicatedObjects,
    indent,
)

from ...utility import (
    OOTObjectCategorizer,
    convertIntTo2sComplement,
    ootDuplicateHierarchy,
    ootGetPath,
    ootGetObjectPath,
)

from ...collision.properties import OOTCollisionExportSettings
from ..utility import Utility
from .polygons import CollisionPoly, CollisionPolygons
from .surface import SurfaceType, SurfaceTypes
from .camera import BgCamInformations
from .waterbox import WaterBoxes
from .vertex import CollisionVertex, CollisionVertices


@dataclass
class CollisionUtility:
    """This class hosts different functions used to convert mesh data"""

    @staticmethod
    def updateBounds(position: tuple[int, int, int], colBounds: list[tuple[int, int, int]]):
        """This is used to update the scene's boundaries"""

        if len(colBounds) == 0:
            colBounds.append([position[0], position[1], position[2]])
            colBounds.append([position[0], position[1], position[2]])
            return

        minBounds = colBounds[0]
        maxBounds = colBounds[1]
        for i in range(3):
            if position[i] < minBounds[i]:
                minBounds[i] = position[i]
            if position[i] > maxBounds[i]:
                maxBounds[i] = position[i]

    @staticmethod
    def getVertexIndex(vertexPos: tuple[int, int, int], vertexList: list[CollisionVertex]):
        """Returns the index of a CollisionVertex based on position data, returns None if no match found"""

        for i in range(len(vertexList)):
            if vertexList[i].pos == vertexPos:
                return i
        return None

    @staticmethod
    def getMeshObjects(
        dataHolder: Object, curTransform: Matrix, transformFromMeshObj: dict[Object, Matrix], includeChildren: bool
    ):
        """Returns and updates a dictionnary containing mesh objects associated with their correct transforms"""

        if includeChildren:
            for obj in dataHolder.children:
                newTransform = curTransform @ obj.matrix_local

                if obj.type == "MESH" and not obj.ignore_collision:
                    transformFromMeshObj[obj] = newTransform

                if len(obj.children) > 0:
                    CollisionUtility.getMeshObjects(obj, newTransform, transformFromMeshObj, includeChildren)

        return transformFromMeshObj

    @staticmethod
    def getCollisionData(dataHolder: Optional[Object], transform: Matrix, useMacros: bool, includeChildren: bool):
        """Returns collision data, surface types and vertex positions from mesh objects"""

        object.select_all(action="DESELECT")
        dataHolder.select_set(True)

        colPolyFromSurfaceType: dict[SurfaceType, list[CollisionPoly]] = {}
        surfaceList: list[SurfaceType] = []
        polyList: list[CollisionPoly] = []
        vertexList: list[CollisionVertex] = []
        colBounds: list[tuple[int, int, int]] = []

        transformFromMeshObj: dict[Object, Matrix] = {}
        if dataHolder.type == "MESH" and not dataHolder.ignore_collision:
            transformFromMeshObj[dataHolder] = transform
        transformFromMeshObj = CollisionUtility.getMeshObjects(
            dataHolder, transform, transformFromMeshObj, includeChildren
        )
        for meshObj, transform in transformFromMeshObj.items():
            # Note: ``isinstance``only used to get the proper type hints
            if not meshObj.ignore_collision and isinstance(meshObj.data, Mesh):
                if len(meshObj.data.materials) == 0:
                    raise PluginError(f"'{meshObj.name}' must have a material associated with it.")

                meshObj.data.calc_loop_triangles()
                for i, face in enumerate(meshObj.data.loop_triangles):
                    material = meshObj.material_slots[face.material_index].material
                    colProp = material.ootCollisionProperty
                    raise_error = False

                    # get bounds and vertices data
                    planePoint = transform @ meshObj.data.vertices[face.vertices[0]].co
                    (x1, y1, z1) = Utility.roundPosition(planePoint)
                    (x2, y2, z2) = Utility.roundPosition(transform @ meshObj.data.vertices[face.vertices[1]].co)
                    (x3, y3, z3) = Utility.roundPosition(transform @ meshObj.data.vertices[face.vertices[2]].co)
                    CollisionUtility.updateBounds((x1, y1, z1), colBounds)
                    CollisionUtility.updateBounds((x2, y2, z2), colBounds)
                    CollisionUtility.updateBounds((x3, y3, z3), colBounds)

                    normal = (transform.inverted().transposed() @ face.normal).normalized()
                    distance = round(
                        -1 * (normal[0] * planePoint[0] + normal[1] * planePoint[1] + normal[2] * planePoint[2])
                    )
                    distance = convertIntTo2sComplement(distance, 2, True)

                    def sq(val):
                        return val * val

                    nx = (y2 - y1) * (z3 - z2) - (z2 - z1) * (y3 - y2)
                    ny = (z2 - z1) * (x3 - x2) - (x2 - x1) * (z3 - z2)
                    nz = (x2 - x1) * (y3 - y2) - (y2 - y1) * (x3 - x2)
                    magSqr = sq(nx) + sq(ny) + sq(nz)
                    if magSqr <= 0:
                        raise_error = True

                    # for walls only, see https://github.com/zeldaret/oot/blob/eb5dac74d6435baf85ced9158d3ff915ba8872ca/src/code/z_bgcheck.c#L751
                    if normal[1] >= -0.8 and normal[1] <= 0.5:
                        normal_xz = math.sqrt(sq(normal[0]) + sq(normal[2]))
                        if math.fabs(normal_xz) < 0.008:
                            raise_error = True

                    if raise_error:
                        raise PluginError(
                            f"degenerate triangle detected on mesh object '{meshObj.name}' (material name is '{material.name}')"
                        )

                    if normal[0] == 0 and normal[2] == 0:
                        raise PluginError("unexpected degenerate triangle")

                    indices: list[int] = []
                    for pos in [(x1, y1, z1), (x2, y2, z2), (x3, y3, z3)]:
                        vertexIndex = CollisionUtility.getVertexIndex(pos, vertexList)
                        if vertexIndex is None:
                            vertexList.append(CollisionVertex(pos))
                            indices.append(len(vertexList) - 1)
                        else:
                            indices.append(vertexIndex)
                    assert len(indices) == 3

                    # We need to ensure two things about the order in which the vertex indices are:
                    #
                    # 1) The vertex with the minimum y coordinate should be first.
                    # This prevents a bug due to an optimization in OoT's CollisionPoly_GetMinY.
                    # https://github.com/zeldaret/oot/blob/873c55faad48a67f7544be713cc115e2b858a4e8/src/code/z_bgcheck.c#L202
                    #
                    # 2) The vertices should wrap around the polygon normal **counter-clockwise**.
                    # This is needed for OoT's dynapoly, which is collision that can move.
                    # When it moves, the vertex coordinates and normals are recomputed.
                    # The normal is computed based on the vertex coordinates, which makes the order of vertices matter.
                    # https://github.com/zeldaret/oot/blob/873c55faad48a67f7544be713cc115e2b858a4e8/src/code/z_bgcheck.c#L2976

                    # Address 1): sort by ascending y coordinate
                    indices.sort(key=lambda index: vertexList[index].pos[1])

                    # Address 2):
                    # swap indices[1] and indices[2],
                    # if the normal computed from the vertices in the current order is the wrong way.
                    v0 = Vector(vertexList[indices[0]].pos)
                    v1 = Vector(vertexList[indices[1]].pos)
                    v2 = Vector(vertexList[indices[2]].pos)
                    if (v1 - v0).cross(v2 - v0).dot(Vector(normal)) < 0:
                        indices[1], indices[2] = indices[2], indices[1]

                    # get surface type and collision poly data
                    surfaceType = SurfaceType.new(colProp, useMacros, material)

                    if surfaceType not in colPolyFromSurfaceType:
                        colPolyFromSurfaceType[surfaceType] = []

                    new_col_poly = CollisionPoly(
                        indices,
                        colProp.ignoreCameraCollision,
                        colProp.ignoreActorCollision,
                        colProp.ignoreProjectileCollision,
                        colProp.conveyorOption == "Land",
                        normal,
                        ctypes.c_short(distance).value,
                        useMacros,
                    )
                    new_col_poly.index_to_obj = {i: meshObj}
                    colPolyFromSurfaceType[surfaceType].append(new_col_poly)

        count = 0
        for surface, colPolyList in colPolyFromSurfaceType.items():
            for colPoly in colPolyList:
                colPoly.type = count
                polyList.append(colPoly)
            surfaceList.append(surface)
            count += 1

        return colBounds, vertexList, polyList, surfaceList


@dataclass
class CollisionHeader:
    """This class defines the collision header used by the scene"""

    name: str
    minBounds: tuple[int, int, int]
    maxBounds: tuple[int, int, int]
    filename: Optional[str]
    settings: Optional[OOTCollisionExportSettings]
    vertices: CollisionVertices
    collisionPoly: CollisionPolygons
    surfaceType: SurfaceTypes
    bgCamInfo: BgCamInformations
    waterbox: WaterBoxes

    @staticmethod
    def new(
        name: str,
        sceneName: str,
        dataHolder: Object,
        transform: Matrix,
        useMacros: bool,
        includeChildren: bool,
        filename: Optional[str] = None,
        settings: Optional[OOTCollisionExportSettings] = None,
    ):
        # Ideally everything would be separated but this is complicated since it's all tied together
        colBounds, vertexList, polyList, surfaceTypeList = CollisionUtility.getCollisionData(
            dataHolder, transform, useMacros, includeChildren
        )

        return CollisionHeader(
            name,
            colBounds[0],
            colBounds[1],
            filename,
            settings,
            CollisionVertices(f"{sceneName}_vertices", vertexList),
            CollisionPolygons(f"{sceneName}_polygons", polyList),
            SurfaceTypes(f"{sceneName}_polygonTypes", surfaceTypeList),
            BgCamInformations.new(f"{sceneName}_bgCamInfo", f"{sceneName}_camPosData", dataHolder, transform),
            WaterBoxes.new(f"{sceneName}_waterBoxes", dataHolder, transform, useMacros),
        )

    @staticmethod
    def export(original_obj: Object, transform: Matrix, settings: OOTCollisionExportSettings):
        """Exports collision data as C files, this should be called to do a separate export from the scene."""
        name = toAlnum(original_obj.name)
        filename = settings.filename if settings.isCustomFilename else f"{name}_collision"
        exportPath = ootGetObjectPath(
            settings.customExport, bpy.path.abspath(settings.exportPath), settings.folder, True
        )

        if bpy.context.scene.exportHiddenGeometry:
            hiddenState = unhideAllAndGetHiddenState(bpy.context.scene)

        # Don't remove ignore_render, as we want to resuse this for collision
        obj, _ = ootDuplicateHierarchy(original_obj, None, True, OOTObjectCategorizer())

        if bpy.context.scene.exportHiddenGeometry:
            restoreHiddenState(hiddenState)

        # write file
        if not obj.ignore_collision:
            # create the collision header
            col_header = CollisionHeader.new(
                f"{name}_collisionHeader",
                name,
                obj,
                transform,
                bpy.context.scene.fast64.oot.useDecompFeatures,
                settings.includeChildren,
            )

            filedata = col_header.get_file(filename, settings)
            base_path = Path(
                ootGetPath(exportPath, settings.customExport, "assets/objects/", settings.folder, True, True)
            ).resolve()

            header_path = base_path / f"{filename}.h"
            header_path.write_text(filedata.header, encoding="utf-8", newline="\n")

            source_path = base_path / f"{filename}.c"
            source_path.write_text(filedata.source, encoding="utf-8", newline="\n")
        else:
            raise PluginError("ERROR: exporting collision with ignore collision enabled!")

        cleanupDuplicatedObjects([obj])

    def getCmd(self):
        """Returns the collision header scene command"""

        return indent + f"SCENE_CMD_COL_HEADER(&{self.name}),\n"

    def getC(self):
        """Returns the collision header for the selected scene"""

        headerData = CData()
        colData = CData()
        varName = f"CollisionHeader {self.name}"

        wBoxPtrLine = colPolyPtrLine = vtxPtrLine = "0, NULL"
        camPtrLine = surfacePtrLine = "NULL"

        # Add waterbox data if necessary
        if len(self.waterbox.waterboxList) > 0:
            colData.append(self.waterbox.getC())
            wBoxPtrLine = f"ARRAY_COUNT({self.waterbox.name}), {self.waterbox.name}"

        # Add camera data if necessary
        if len(self.bgCamInfo.bgCamInfoList) > 0 or len(self.bgCamInfo.crawlspacePosList) > 0:
            infoData = self.bgCamInfo.getInfoArrayC()
            if "&" in infoData.source:
                colData.append(self.bgCamInfo.getDataArrayC())
            colData.append(infoData)
            camPtrLine = f"{self.bgCamInfo.name}"

        # Add surface types
        if len(self.surfaceType.surfaceTypeList) > 0:
            colData.append(self.surfaceType.getC())
            surfacePtrLine = f"{self.surfaceType.name}"

        # Add vertex data
        if len(self.vertices.vertexList) > 0:
            colData.append(self.vertices.getC())
            vtxPtrLine = f"ARRAY_COUNT({self.vertices.name}), {self.vertices.name}"

        # Add collision poly data
        if len(self.collisionPoly.polyList) > 0:
            colData.append(self.collisionPoly.getC())
            colPolyPtrLine = f"ARRAY_COUNT({self.collisionPoly.name}), {self.collisionPoly.name}"

        # build the C data of the collision header
        headerData.append(colData)

        # .h
        headerData.header += f"extern {varName};\n"

        # .c
        headerData.source += (
            (varName + " = {\n")
            + ",\n".join(
                indent + val
                for val in [
                    ("{ " + ", ".join(f"{val}" for val in self.minBounds) + " }"),
                    ("{ " + ", ".join(f"{val}" for val in self.maxBounds) + " }"),
                    vtxPtrLine,
                    colPolyPtrLine,
                    surfacePtrLine,
                    camPtrLine,
                    wBoxPtrLine,
                ]
            )
            + "\n};\n\n"
        )

        return headerData

    def get_file(self, filename: str, settings: OOTCollisionExportSettings):
        filedata = CData()

        if bpy.context.scene.fast64.oot.is_globalh_present():
            includes = [
                '#include "ultra64.h"',
                '#include "z64.h"',
                '#include "macros.h"',
            ]
        elif bpy.context.scene.fast64.oot.is_z64sceneh_present():
            includes = [
                '#include "ultra64.h"',
                '#include "z64math.h"',
                '#include "z64bgcheck.h"',
                '#include "array_count.h"',
            ]
        else:
            includes = [
                '#include "ultra64.h"',
                '#include "z_math.h"',
                '#include "bgcheck.h"',
                '#include "array_count.h"',
            ]

        filedata.header = (
            f"#ifndef {filename.upper()}_H\n" + f"#define {filename.upper()}_H\n\n" + "\n".join(includes) + "\n\n"
        )
        filedata.source = f'#include "{filename}.h"\n'

        if not settings.customExport:
            filedata.source += f'#include "{settings.folder}.h"\n\n'
        else:
            filedata.source += "\n"

        filedata.append(self.getC())
        filedata.header += "\n#endif\n"

        return filedata
