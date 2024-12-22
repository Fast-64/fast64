import bpy
import shutil
import os

from dataclasses import dataclass, field
from typing import Optional
from ....utility import PluginError, CData, toAlnum, indent
from ....f3d.f3d_gbi import SPDisplayList, SPEndDisplayList, GfxListTag, GfxList, DLFormat
from ....f3d.f3d_writer import TriangleConverterInfo, saveStaticModel, getInfoDict
from ...room.properties import Z64_RoomHeaderProperty, Z64_BGProperty
from ...model_classes import OOTModel
from ..utility import Utility
from bpy.types import Object
from mathutils import Matrix, Vector
from ....f3d.occlusion_planes.exporter import addOcclusionQuads, OcclusionPlaneCandidatesList

from ...utility import (
    CullGroup,
    checkUniformScale,
    ootConvertTranslation,
    get_game_props,
)


@dataclass
class RoomShapeDListsEntry:  # previously OOTDLGroup + OOTRoomMeshGroup
    name: str
    opaque: Optional[GfxList] = field(init=False, default=None)
    transparent: Optional[GfxList] = field(init=False, default=None)

    def __post_init__(self):
        self.name = toAlnum(self.name)

    def to_c(self):
        opaque = self.opaque.name if self.opaque else "NULL"
        transparent = self.transparent.name if self.transparent else "NULL"
        return f"{opaque}, {transparent}"

    def add_dl_call(self, display_list: GfxList, draw_layer: str):
        if draw_layer == "Opaque":
            if self.opaque is None:
                self.opaque = GfxList(self.name + "_opaque", GfxListTag.Draw, DLFormat.Static)
            self.opaque.commands.append(SPDisplayList(display_list))
        elif draw_layer == "Transparent":
            if self.transparent is None:
                self.transparent = GfxList(self.name + "_transparent", GfxListTag.Draw, DLFormat.Static)
            self.transparent.commands.append(SPDisplayList(display_list))
        else:
            raise PluginError("Unhandled draw layer: " + str(draw_layer))

    def terminate_dls(self):
        if self.opaque is not None:
            self.opaque.commands.append(SPEndDisplayList())

        if self.transparent is not None:
            self.transparent.commands.append(SPEndDisplayList())

    def create_dls(self):
        if self.opaque is None:
            self.opaque = GfxList(self.name + "_opaque", GfxListTag.Draw, DLFormat.Static)
        if self.transparent is None:
            self.transparent = GfxList(self.name + "_transparent", GfxListTag.Draw, DLFormat.Static)

    def is_empty(self):
        return self.opaque is None and self.transparent is None


@dataclass
class RoomShape:  # previously OOTRoomMesh
    """This class is the base class for all room shapes."""

    name: str
    """Name of struct itself"""

    model: OOTModel
    """Stores all graphical data"""

    dl_entry_array_name: str
    """Name of RoomShapeDListsEntry list"""

    dl_entries: list[RoomShapeDListsEntry] = field(init=False, default_factory=list)
    """List of DL entries"""

    occlusion_planes: OcclusionPlaneCandidatesList = field(init=False)
    """F3DEX3 occlusion planes"""

    def __post_init__(self):
        self.occlusion_planes = OcclusionPlaneCandidatesList(self.name)

    def to_c_dl_entries(self):
        """Converts list of dl entries to c. This is usually appended to end of CData in to_c()."""
        info_data = CData()
        list_name = f"RoomShapeDListsEntry {self.dl_entry_array_name}" + f"[{len(self.dl_entries)}]"

        # .h
        info_data.header = f"extern {list_name};\n"

        # .c
        info_data.source = (
            (list_name + " = {\n")
            + (indent + f",\n{indent}".join("{ " + elem.to_c() + " }" for elem in self.dl_entries))
            + "\n};\n\n"
        )

        return info_data

    def to_c(self) -> CData:
        raise PluginError("to_c() not implemented.")

    def to_c_img(self, include_dir: str):
        """Returns C representation of image data in room shape"""
        return CData()

    def get_type(self) -> str:
        """Returns value in oot_constants.ootEnumRoomShapeType"""
        raise PluginError("get_type() not implemented.")

    def add_dl_entry(self, cull_group: Optional[CullGroup] = None) -> RoomShapeDListsEntry:
        entry = RoomShapeDListsEntry(f"{self.name}_entry_{len(self.dl_entries)}")
        self.dl_entries.append(entry)
        return entry

    def remove_unused_entries(self):
        new_list = []
        for entry in self.dl_entries:
            if not entry.is_empty():
                new_list.append(entry)
        self.dl_entries = new_list

    def terminate_dls(self):
        for entry in self.dl_entries:
            entry.terminate_dls()

    def get_occlusion_planes_cmd(self):
        return (
            indent
            + f"SCENE_CMD_OCCLUSION_PLANE_CANDIDATES_LIST({len(self.occlusion_planes.planes)}, {self.occlusion_planes.name}),\n"
        )

    def get_cmds(self) -> str:
        """Returns the room shape room commands"""
        cmds = indent + f"SCENE_CMD_ROOM_SHAPE(&{self.name}),\n"
        if len(self.occlusion_planes.planes) > 0:
            cmds += self.get_occlusion_planes_cmd()
        return cmds

    def copy_bg_images(self, export_path: str):
        return  # by default, do nothing


@dataclass
class RoomShapeNormal(RoomShape):
    """This class defines the basic informations shared by other image classes"""

    def to_c(self):
        """Returns the C data for the room shape"""

        info_data = CData()
        list_name = f"RoomShapeNormal {self.name}"

        # .h
        info_data.header = f"extern {list_name};\n"

        # .c
        num_entries = f"ARRAY_COUNT({self.dl_entry_array_name})"
        info_data.source = (
            (list_name + " = {\n" + indent)
            + f",\n{indent}".join(
                [
                    f"{self.get_type()}",
                    num_entries,
                    f"{self.dl_entry_array_name}",
                    f"{self.dl_entry_array_name} + {num_entries}",
                ]
            )
            + "\n};\n\n"
        )

        info_data.append(self.occlusion_planes.to_c())
        info_data.append(self.to_c_dl_entries())

        return info_data

    def get_type(self):
        return "ROOM_SHAPE_TYPE_NORMAL"


@dataclass
class RoomShapeImageEntry:  # OOTBGImage
    name: str  # source
    image: bpy.types.Image

    # width: str
    # height: str
    format: str  # fmt
    size: str  # siz
    other_mode_flags: str  # tlutMode
    # bg_cam_index: int = 0  # bgCamIndex: for which bg cam index is this entry for

    unk_00: int = field(init=False, default=130)  # for multi images only
    unk_0C: int = field(init=False, default=0)
    tlut: str = field(init=False, default="NULL")
    format: str = field(init=False, default="G_IM_FMT_RGBA")
    size: str = field(init=False, default="G_IM_SIZ_16b")
    tlut_count: int = field(init=False, default=0)  # tlutCount

    def get_width(self) -> int:
        return self.image.size[0] if self.image else 0

    def get_height(self) -> int:
        return self.image.size[1] if self.image else 0

    @staticmethod
    def new(name: str, prop: Z64_BGProperty):
        if prop.image is None:
            raise PluginError(
                'A room is has room shape "Image" but does not have an image set in one of its BG images.'
            )
        return RoomShapeImageEntry(
            toAlnum(f"{name}_bg_{prop.image.name}"),
            prop.image,
            prop.otherModeFlags,
        )

    def get_filename(self) -> str:
        return f"{self.name}.jpg"

    def to_c_multi(self, bg_cam_index: int):
        return (
            indent
            + "{\n"
            + indent * 2
            + f",\n{indent * 2}".join(
                [
                    f"0x{self.unk_00:04X}, {bg_cam_index}",
                    f"{self.name}",
                    f"0x{self.unk_0C:08X}",
                    f"{self.tlut}",
                    f"{self.get_width()}, {self.get_height()}",
                    f"{self.format}, {self.size}",
                    f"{self.other_mode_flags}, 0x{self.tlut_count:04X},",
                ]
            )
            + "\n"
            + indent
            + "},\n"
        )

    def to_c_single(self) -> str:
        return indent + f",\n{indent}".join(
            [
                f"{self.name}",
                f"0x{self.unk_0C:08X}",
                f"{self.tlut}",
                f"{self.get_width()}, {self.get_height()}",
                f"{self.format}, {self.size}",
                f"{self.other_mode_flags}, 0x{self.tlut_count:04X},",
            ]
        )


@dataclass
class RoomShapeImageBase(RoomShape):
    """This class defines the basic informations shared by other image classes"""

    def get_amount_type(self):
        raise PluginError("get_amount_type() not implemented.")

    def get_type(self):
        return "ROOM_SHAPE_TYPE_IMAGE"

    def to_c_dl_entries(self):
        if len(self.dl_entries) > 1:
            raise PluginError("RoomShapeImage only allows one one dl entry, but multiple found")

        info_data = CData()
        list_name = f"RoomShapeDListsEntry {self.dl_entry_array_name}"

        # .h
        info_data.header = f"extern {list_name};\n"

        # .c
        info_data.source = (list_name + " = {\n") + (indent + self.dl_entries[0].to_c()) + "\n};\n\n"

        return info_data

    def to_c_img_single(self, bg_entry: RoomShapeImageEntry, include_dir: str):
        """Gets C representation of image data"""
        bits_per_value = 64

        data = CData()

        # .h
        data.header = f"extern u{bits_per_value} {bg_entry.name}[];\n"

        # .c
        data.source = (
            # This is to force 8 byte alignment
            (f"Gfx {bg_entry.name}_aligner[] = " + "{ gsSPEndDisplayList() };\n" if bits_per_value != 64 else "")
            + (f"u{bits_per_value} {bg_entry.name}[SCREEN_WIDTH * SCREEN_HEIGHT / 4]" + " = {\n")
            + f'#include "{include_dir + bg_entry.get_filename()}.inc.c"'
            + "\n};\n\n"
        )
        return data

    def copy_bg_image(self, entry: RoomShapeImageEntry, export_path: str):
        jpeg_compatibility = False
        image = entry.image
        image_filename = entry.get_filename()
        if jpeg_compatibility:
            is_packed = image.packed_file is not None
            if not is_packed:
                image.pack()
            oldpath = image.filepath
            old_format = image.file_format
            try:
                image.filepath = bpy.path.abspath(os.path.join(export_path, image_filename))
                image.file_format = "JPEG"
                image.save()
                if not is_packed:
                    image.unpack()
                image.filepath = oldpath
                image.file_format = old_format
            except Exception as e:
                image.filepath = oldpath
                image.file_format = old_format
                raise Exception(str(e))
        else:
            filepath = bpy.path.abspath(os.path.join(export_path, image_filename))
            shutil.copy(bpy.path.abspath(image.filepath), filepath)

    def copy_bg_images(self, export_path: str):
        raise PluginError("BG image copying not handled!")


@dataclass
class RoomShapeImageSingle(RoomShapeImageBase):
    bg_entry: RoomShapeImageEntry

    def get_amount_type(self):
        return "ROOM_SHAPE_IMAGE_AMOUNT_SINGLE"

    def to_c(self):
        """Returns the single background image mode variable"""

        info_data = CData()
        list_name = f"RoomShapeImageSingle {self.name}"

        # .h
        info_data.header = f"extern {list_name};\n"

        # .c
        info_data.source = (
            f"{list_name} = {{\n"
            + f"{indent}{{ {self.get_type()}, {self.get_amount_type()}, &{self.dl_entry_array_name}, }},\n"
            + self.bg_entry.to_c_single()
            + f"\n}};\n\n"
        )

        info_data.append(self.occlusion_planes.to_c())
        info_data.append(self.to_c_dl_entries())

        return info_data

    def to_c_img(self, include_dir: str):
        """Returns the image data for image room shapes"""

        return self.to_c_img_single(self.bg_entry, include_dir)

    def copy_bg_images(self, export_path: str):
        self.copy_bg_image(self.bg_entry, export_path)


@dataclass
class RoomShapeImageMulti(RoomShapeImageBase):
    bg_entry_array_name: str
    bg_entries: list[RoomShapeImageEntry] = field(init=False, default_factory=list)

    def get_amount_type(self):
        return "ROOM_SHAPE_IMAGE_AMOUNT_MULTI"

    def to_c_bg_entries(self) -> CData:
        info_data = CData()
        list_name = f"RoomShapeImageMultiBgEntry {self.bg_entry_array_name}[{len(self.bg_entries)}]"

        # .h
        info_data.header = f"extern {list_name};\n"

        # .c
        info_data.source = (
            list_name + " = {\n" + f"".join(elem.to_c_multi(i) for i, elem in enumerate(self.bg_entries)) + "};\n\n"
        )

        return info_data

    def to_c(self) -> CData:
        """Returns the multiple background image mode variable"""

        info_data = CData()
        list_name = f"RoomShapeImageMulti {self.name}"

        # .h
        info_data.header = f"extern {list_name};\n"

        # .c
        info_data.source = (
            (list_name + " = {\n" + indent)
            + f",\n{indent}".join(
                [
                    "{ " + f"{self.get_type()}, {self.get_amount_type()}, &{self.dl_entry_array_name}" + " }",
                    f"ARRAY_COUNT({self.bg_entry_array_name})",
                    f"{self.bg_entry_array_name}",
                ]
            )
            + ",\n};\n\n"
        )

        info_data.append(self.occlusion_planes.to_c())
        info_data.append(self.to_c_bg_entries())
        info_data.append(self.to_c_dl_entries())

        return info_data

    def to_c_img(self, include_dir: str):
        """Returns the image data for image room shapes"""

        data = CData()

        for entry in self.bg_entries:
            data.append(self.to_c_img_single(entry, include_dir))

        return data

    def copy_bg_images(self, export_path: str):
        for bg_entry in self.bg_entries:
            self.copy_bg_image(bg_entry, export_path)


@dataclass
class RoomShapeCullableEntry(
    RoomShapeDListsEntry
):  # inheritance is due to functional relation, previously OOTRoomMeshGroup
    bounds_sphere_center: tuple[float, float, float]
    bounds_sphere_radius: float

    def to_c(self):
        center = ", ".join([f"{n}" for n in self.bounds_sphere_center])
        opaque = self.opaque.name if self.opaque else "NULL"
        transparent = self.transparent.name if self.transparent else "NULL"
        return f" {{ {center} }}, {self.bounds_sphere_radius}, {opaque}, {transparent}"


@dataclass
class RoomShapeCullable(RoomShape):
    def get_type(self):
        return "ROOM_SHAPE_TYPE_CULLABLE"

    def add_dl_entry(self, cull_group: Optional[CullGroup] = None) -> RoomShapeDListsEntry:
        if cull_group is None:
            raise PluginError("RoomShapeCullable should always be provided a cull group.")
        entry = RoomShapeCullableEntry(
            f"{self.name}_entry_{len(self.dl_entries)}", cull_group.position, cull_group.cullDepth
        )
        self.dl_entries.append(entry)
        return entry

    def to_c_dl_entries(self):
        info_data = CData()
        list_name = f"RoomShapeCullableEntry {self.dl_entry_array_name}[{len(self.dl_entries)}]"

        # .h
        info_data.header = f"extern {list_name};\n"

        # .c
        info_data.source = (
            (list_name + " = {\n")
            + (indent + f",\n{indent}".join("{ " + elem.to_c() + " }" for elem in self.dl_entries))
            + "\n};\n\n"
        )

        return info_data

    def to_c(self):
        """Returns the C data for the room shape"""

        info_data = CData()
        list_name = f"RoomShapeCullable {self.name}"

        # .h
        info_data.header = f"extern {list_name};\n"

        # .c
        num_entries = f"ARRAY_COUNTU({self.dl_entry_array_name})"  # U? see ddan_room_0
        info_data.source = (
            (list_name + " = {\n" + indent)
            + f",\n{indent}".join(
                [
                    f"{self.get_type()}",
                    num_entries,
                    f"{self.dl_entry_array_name}",
                    f"{self.dl_entry_array_name} + {num_entries}",
                ]
            )
            + "\n};\n\n"
        )

        info_data.append(self.occlusion_planes.to_c())
        info_data.append(self.to_c_dl_entries())

        return info_data


class RoomShapeUtility:
    @staticmethod
    def create_shape(
        scene_name: str,
        room_name: str,
        room_shape_type: str,
        model: OOTModel,
        transform: Matrix,
        sceneObj: Object,
        roomObj: Object,
        saveTexturesAsPNG: bool,
        props: Z64_RoomHeaderProperty,
    ):
        name = f"{room_name}_shapeHeader"
        dl_name = f"{room_name}_shapeDListsEntry"
        room_shape = None

        if room_shape_type == "ROOM_SHAPE_TYPE_CULLABLE":
            room_shape = RoomShapeCullable(name, model, dl_name)
        elif room_shape_type == "ROOM_SHAPE_TYPE_NORMAL":
            room_shape = RoomShapeNormal(name, model, dl_name)
        elif room_shape_type == "ROOM_SHAPE_TYPE_IMAGE":
            if len(props.bgImageList) == 0:
                raise PluginError("Cannot create room shape of type image without any images.")
            elif len(props.bgImageList) == 1:
                room_shape = RoomShapeImageSingle(
                    name, model, dl_name, RoomShapeImageEntry.new(scene_name, props.bgImageList[0])
                )
            else:
                bg_name = f"{room_name}_shapeMultiBg"
                room_shape = RoomShapeImageMulti(name, model, dl_name, bg_name)
                for bg_image in props.bgImageList:
                    room_shape.bg_entries.append(RoomShapeImageEntry.new(scene_name, bg_image))

        pos, _, scale, _ = Utility.getConvertedTransform(transform, sceneObj, roomObj, True)
        cull_group = CullGroup(pos, scale, get_game_props(roomObj, "room").defaultCullDistance)
        dl_entry = room_shape.add_dl_entry(cull_group)
        boundingBox = BoundingBox()
        ootProcessMesh(
            room_shape,
            dl_entry,
            sceneObj,
            roomObj,
            transform,
            not saveTexturesAsPNG,
            None,
            boundingBox,
        )
        if isinstance(dl_entry, RoomShapeCullableEntry):
            dl_entry.bounds_sphere_center, dl_entry.bounds_sphere_radius = boundingBox.getEnclosingSphere()

        if bpy.context.scene.f3d_type == "F3DEX3":
            addOcclusionQuads(roomObj, room_shape.occlusion_planes, True, transform @ sceneObj.matrix_world.inverted())

        room_shape.terminate_dls()
        room_shape.remove_unused_entries()
        return room_shape


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

    def addMeshObj(self, obj: bpy.types.Object, transform: Matrix):
        mesh = obj.data
        for vertex in mesh.vertices:
            self.addPoint(transform @ vertex.co)

    def getEnclosingSphere(self) -> tuple[float, float]:
        centroid = (Vector(self.minPoint) + Vector(self.maxPoint)) / 2
        radius = 0
        for point in self.points:
            distance = (Vector(point) - centroid).length
            if distance > radius:
                radius = distance

        transformedCentroid = [round(value) for value in centroid]
        transformedRadius = round(radius)
        return transformedCentroid, transformedRadius


# This function should be called on a copy of an object
# The copy will have modifiers / scale applied and will be made single user
# When we duplicated obj hierarchy we stripped all ignore_renders from hierarchy.
def ootProcessMesh(
    roomShape: RoomShape,
    dlEntry: RoomShapeDListsEntry,
    sceneObj,
    obj,
    transformMatrix,
    convertTextureData,
    LODHierarchyObject,
    boundingBox: BoundingBox,
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
        dlEntry = roomShape.add_dl_entry(
            CullGroup(
                ootConvertTranslation(translation),
                scale if cullProp.sizeControlsCull else [cullProp.manualRadius],
                obj.empty_display_size if cullProp.sizeControlsCull else 1,
            )
        )

    elif obj.type == "MESH" and not obj.ignore_render:
        triConverterInfo = TriangleConverterInfo(obj, None, roomShape.model.f3d, relativeTransform, getInfoDict(obj))
        fMeshes = saveStaticModel(
            triConverterInfo,
            roomShape.model,
            obj,
            relativeTransform,
            roomShape.model.name,
            convertTextureData,
            False,
            "oot",
        )
        if fMeshes is not None:
            for drawLayer, fMesh in fMeshes.items():
                dlEntry.add_dl_call(fMesh.draw, drawLayer)

        boundingBox.addMeshObj(obj, relativeTransform)

    alphabeticalChildren = sorted(obj.children, key=lambda childObj: childObj.original_name.lower())
    for childObj in alphabeticalChildren:
        if childObj.type == "EMPTY" and childObj.ootEmptyType == "LOD":
            ootProcessLOD(
                roomShape,
                dlEntry,
                sceneObj,
                childObj,
                transformMatrix,
                convertTextureData,
                LODHierarchyObject,
                boundingBox,
            )
        else:
            ootProcessMesh(
                roomShape,
                dlEntry,
                sceneObj,
                childObj,
                transformMatrix,
                convertTextureData,
                LODHierarchyObject,
                boundingBox,
            )


def ootProcessLOD(
    roomShape: RoomShape,
    dlEntry: RoomShapeDListsEntry,
    sceneObj,
    obj,
    transformMatrix,
    convertTextureData,
    LODHierarchyObject,
    boundingBox: BoundingBox,
):
    relativeTransform = transformMatrix @ sceneObj.matrix_world.inverted() @ obj.matrix_world
    translation, rotation, scale = relativeTransform.decompose()
    ootTranslation = ootConvertTranslation(translation)

    LODHierarchyObject = obj
    name = toAlnum(roomShape.model.name + "_" + obj.name + "_lod")
    opaqueLOD = roomShape.model.addLODGroup(name + "_opaque", ootTranslation, obj.f3d_lod_always_render_farthest)
    transparentLOD = roomShape.model.addLODGroup(
        name + "_transparent", ootTranslation, obj.f3d_lod_always_render_farthest
    )

    index = 0
    for childObj in obj.children:
        # This group will not be converted to C directly, but its display lists will be converted through the FLODGroup.
        childDLEntry = RoomShapeDListsEntry(f"{name}{str(index)}")
        index += 1

        if childObj.type == "EMPTY" and childObj.ootEmptyType == "LOD":
            ootProcessLOD(
                roomShape,
                childDLEntry,
                sceneObj,
                childObj,
                transformMatrix,
                convertTextureData,
                LODHierarchyObject,
                boundingBox,
            )
        else:
            ootProcessMesh(
                roomShape,
                childDLEntry,
                sceneObj,
                childObj,
                transformMatrix,
                convertTextureData,
                LODHierarchyObject,
                boundingBox,
            )

        # We handle case with no geometry, for the cases where we have "gaps" in the LOD hierarchy.
        # This can happen if a LOD does not use transparency while the levels above and below it does.
        childDLEntry.create_dls()
        childDLEntry.terminate_dls()

        # Add lod AFTER processing hierarchy, so that DLs will be built by then
        opaqueLOD.add_lod(childDLEntry.opaque, childObj.f3d_lod_z * bpy.context.scene.ootBlenderScale)
        transparentLOD.add_lod(childDLEntry.transparent, childObj.f3d_lod_z * bpy.context.scene.ootBlenderScale)

    opaqueLOD.create_data()
    transparentLOD.create_data()

    dlEntry.add_dl_call(opaqueLOD.draw, "Opaque")
    dlEntry.add_dl_call(transparentLOD.draw, "Transparent")
