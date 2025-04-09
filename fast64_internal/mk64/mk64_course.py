# ------------------------------------------------------------------------
#    Header
# ------------------------------------------------------------------------
from __future__ import annotations

import bpy

import os, struct, math
from pathlib import Path
from mathutils import Vector, Euler, Matrix
from dataclasses import dataclass, fields

from .mk64_constants import MODEL_HEADER
from .mk64_properties import MK64_ObjectProperties, MK64_CurveProperties

from ..f3d.f3d_writer import exportF3DCommon, getInfoDict, TriangleConverterInfo, saveStaticModel
from ..f3d.f3d_bleed import BleedGraphics
from ..f3d.f3d_gbi import (
    DLFormat,
    GfxListTag,
    GfxMatWriteMethod,
    GfxFormatter,
    ScrollMethod,
    GfxList,
    FModel,
    FMesh,
    FMaterial,
    DPSetTextureImage,
    TextureExportSettings,
)

from ..utility import (
    transform_mtx_blender_to_n64,
    cleanupDuplicatedObjects,
    duplicateHierarchy,
    parentObject,
    PluginError,
    CData,
    writeCData,
)

# ------------------------------------------------------------------------
#    Classes
# ------------------------------------------------------------------------


class MK64_BpyCourse:
    """
    Interim class that transforms course data back
    and forth between blender and internal data
    """

    def __init__(self, course_root: bpy.types.Object):
        self.root = course_root

    def make_mk64_course_from_bpy(self, context: bpy.Types.Context, scale: float, mat_write_method: GfxMatWriteMethod):
        """
        Creates a MK64_fModel class with all model data ready to exported to c
        also generates lists for items, pathing and collision (in future)
        """
        fModel = MK64_fModel(self.root, mat_write_method)
        # create duplicate objects to export from
        transform = Matrix.Diagonal(Vector((scale, scale, scale))).to_4x4()
        # create duplicate objects to work on
        self.temp_obj, self.all_objs = duplicateHierarchy(self.root, None, True, None)
        # fMeshes = exportF3DCommon(self.root, fModel, transform, True, "mk64", DLFormat.Static, 1)
        print(self.all_objs)

        # retrieve data for items and pathing
        def loop_children(obj, fModel, parent_transform):
            for child in obj.children:
                if child.type == "MESH":
                    self.export_f3d_from_obj(context, child, fModel, parent_transform @ child.matrix_local)
                if self.is_mk64_actor(child):
                    self.add_actor(child, parent_transform, fModel)
                if child.type == "CURVE":
                    self.add_path(child, parent_transform, fModel)
                if child.children:
                    loop_children(child, fModel, parent_transform @ child.matrix_local)

        loop_children(self.root, fModel, transform)

        return fModel

    def is_mk64_actor(self, obj: bpy.Types.Object):
        mk64_props: MK64_ObjectProperties = obj.fast64.mk64
        return mk64_props.obj_type == "Actor"

    def add_actor(self, obj: bpy.Types.Object, transform: Matrix, fModel: FModel):
        mk64_props: MK64_ObjectProperties = obj.fast64.mk64
        position = (transform @ obj.matrix_local).translation
        fModel.actors.append(MK64_Actor(position, mk64_props.actor_type))
        return

    def add_path(self, obj: bpy.Types.Object, transform: Matrix, fModel: FModel):
        curve_data = obj.data

        points = []

        for spline in curve_data.splines:
            if spline.type != 'BEZIER':
                continue  # Only support Bezier splines for now

            for point in spline.bezier_points:
                # Get world position of the bezier point handle (center point)
                local_pos = point.co
                world_pos = (transform @ obj.matrix_world @ local_pos)
                points.append((world_pos, 0))

        if points:
            fModel.path.append(MK64_Path(points))
            return

    # look into speeding this up by calculating just the apprent
    # transform using transformMatrix vs clearing parent and applying
    # transform
    def export_f3d_from_obj(
        self, context: bpy.Types.Context, obj: bpy.types.Object, fModel: MK64_fModel, transformMatrix: Matrix
    ):
        if obj and obj.type == "MESH":
            try:
                with context.temp_override(active_object=obj, selected_objects=[obj]):
                    bpy.ops.object.parent_clear(type="CLEAR_KEEP_TRANSFORM")
                    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True, properties=False)
                infoDict = getInfoDict(obj)
                triConverterInfo = TriangleConverterInfo(obj, None, fModel.f3d, transformMatrix, infoDict)
                fMeshes = saveStaticModel(
                    triConverterInfo,
                    fModel,
                    obj,
                    transformMatrix,
                    fModel.name,
                    1,
                    False,
                    None,
                )
            except Exception as e:
                self.cleanup_course()
                raise PluginError(str(e))
            return list(fMeshes.values())
        else:
            return 0

    def cleanup_course(self):
        cleanupDuplicatedObjects(self.all_objs)
        self.root.select_set(True)
        bpy.context.view_layer.objects.active = self.root
        return


class MK64_fModel(FModel):
    def __init__(self, rt: bpy.types.Object, mat_write_method, name="mk64"):
        super().__init__(name, DLFormat.Static, mat_write_method)
        self.actors: list[MK64_Actor] = []
        self.track_sections: list[MK64_TrackSection] = []
        self.path: list[MK64_Path] = []

    # parent override so I can keep track of original mesh data
    # to lookup collision data later
    def onAddMesh(self, fMesh: FMesh, obj: bpy.Types.Object):
        if not self.has_mk64_collision(obj):
            return
        mk64_props: MK64_ObjectProperties = obj.fast64.mk64
        self.track_sections.append(MK64_TrackSection(fMesh.draw.name, mk64_props.col_type, 255, 0))
        return

    def has_mk64_collision(self, obj: bpy.Types.Object):
        if obj.type != "MESH":
            return False
        mk64_props: MK64_ObjectProperties = obj.fast64.mk64
        return mk64_props.has_col

    def to_c(self, *args):
        export_data = super().to_c(*args)
        export_data.staticData.append(self.to_c_track_actors())
        export_data.staticData.append(self.to_c_track_sections())
        export_data.staticData.append(self.to_c_dl_array())

        return export_data

    def to_c_dl_array(self):
        data = CData()
        if not self.meshes:
            return data
        data.header = f"extern const Gfx* d_{self.name}_dls[];\n"
        data.source = f"const Gfx* d_{self.name}_dls[] = {{\n"
        # cleaner oneline for this?
        for index, fMesh in enumerate(self.meshes.values()):
            data.source += f"{fMesh.draw.name}, " + ("\n\t" if index % 3 == 0 else "")
        data.source += "};\n\n"
        return data

    def to_c_track_actors(self):
        data = CData()
        if not self.actors:
            return data
        data.header = f"extern struct ActorSpawnData d_{self.name}_item_spawns[];\n"
        actors = ",\n\t".join([actor.to_c() for actor in self.actors])
        data.source = "\n".join(
            (
                f"struct ActorSpawnData d_{self.name}_item_spawns[] = {{",
                f"\t{actors}",
                "\t{ { -32768, 0,    0 }, {0}},",
                "};\n\n",
            )
        )
        return data

    def to_c_track_sections(self):
        data = CData()
        if not self.track_sections:
            return data
        data.header = f"extern TrackSections d_{self.name}_addr[];\n"
        sections = ",\n\t".join([track_section.to_c() for track_section in self.track_sections])
        data.source = "\n".join(
            (
                f"TrackSections d_{self.name}_addr[] = {{",
                f"\t{sections}",
                "\t{{ 0x00000000, 0, 0, 0x00000 }},",
                "};\n\n",
            )
        )
        return data

    def to_c_path(self):
        data = CData()
        if not self.path_points:
            return data

        data.header = f"extern TrackWaypoint d_{self.name}_path[];\n"

        waypoints = ",\n\t".join(
            [f"{{ {wp.x:.2f}f, {wp.y:.2f}f, {wp.z:.2f}f, {wp.id} }}" for wp in self.path_points]
        )

        data.source = "\n".join(
            (
                f"TrackWaypoint d_{self.name}_path[] = {{",
                f"\t{waypoints},",
                "};\n\n",
            )
        )
        return data


@dataclass
class MK64_TrackSection:
    """
    dataclass representing an TrackSections struct which points
    to display lists that also have collision, along with col type
    section ID will default to 255
    """

    gfx_list_name: str
    surface_type: str
    section_id: Int
    flags: Int

    def to_c(self):
        data = (
            self.gfx_list_name,
            self.surface_type,
            f"0x{self.section_id:X}",
            f"0x{self.flags:X}",
        )
        return f"{{ {', '.join(data)} }}"


@dataclass
class MK64_Actor:
    """
    Represents an ActorSpawnData struct for spawning an actor in the game
    id is used only by some actors for behaviour.

    May be re-implemented in the future as an 'actor type' selector
    """

    pos: Vector
    id: Int

    def to_c(self):
        pos = ", ".join(f"{int(coord):6}" for coord in self.pos)
        return f"{{ {{{pos}}}, {{{self.id}}} }}"

@dataclass
class MK64_Path:
    """
    Represents a path that CPUs or actors follow.
    A level can have up to four paths
    """

    # List of {x, y, z, id},
    points: List[Tuple[Vector, int]] # unsigned int

    def to_c(self):
        lines = []
        for pos, pid in self.points:
            pos_str = ", ".join(str(int(coord)) for coord in pos)
            lines.append(f"{{{pos_str}, {pid}}},")
        return "\n".join(lines)

# ------------------------------------------------------------------------
#    Exporter Functions
# ------------------------------------------------------------------------


def export_course_c(obj: bpy.types.Object, context: bpy.types.Context, export_dir: Path):
    """
    this is similar to exportF3DtoC except that we
    pay attention to other objects within the course
    namely paths, items and collision
    """
    inline = context.scene.exportInlineF3D
    mk64_props: MK64_Properties = context.scene.fast64.mk64
    scale = mk64_props.scale
    mat_write_method = GfxMatWriteMethod.WriteDifferingAndRevert if not inline else GfxMatWriteMethod.WriteAll

    bpy_course = MK64_BpyCourse(obj)
    mk64_fModel = bpy_course.make_mk64_course_from_bpy(context, scale, mat_write_method)
    bpy_course.cleanup_course()

    if inline:
        bleed_gfx = BleedGraphics()
        bleed_gfx.bleed_fModel(mk64_fModel, mk64_fModel.meshes)

    # idk how scrolls would actually affect this export
    gfxFormatter = GfxFormatter(ScrollMethod.Vertex, 64, None)
    export_data = mk64_fModel.to_c(TextureExportSettings(False, False, export_dir, export_dir), gfxFormatter)
    staticData = export_data.staticData
    dynamicData = export_data.dynamicData

    model_data = CData()
    model_data.source += MODEL_HEADER
    model_data.append(staticData)
    model_data.append(dynamicData)

    writeCData(model_data, os.path.join(export_dir, "header.h"), os.path.join(export_dir, "model.inc.c"))
