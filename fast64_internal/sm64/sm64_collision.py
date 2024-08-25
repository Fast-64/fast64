import bpy, shutil, os, math, mathutils
from bpy.utils import register_class, unregister_class
from io import BytesIO
from .sm64_constants import (
    level_enums,
    level_pointers,
    enumLevelNames,
    insertableBinaryTypes,
    defaultExtendSegment4,
)
from .sm64_utility import export_rom_checks
from .sm64_objects import SM64_Area, start_process_sm64_objects
from .sm64_level_parser import parseLevelAtPointer
from .sm64_rom_tweaks import ExtendBank0x04
from ..panels import SM64_Panel

from ..utility import (
    PluginError,
    CData,
    toAlnum,
    raisePluginError,
    encodeSegmentedAddr,
    get64bitAlignedAddr,
    prop_split,
    getExportDir,
    writeIfNotFound,
    deleteIfFound,
    duplicateHierarchy,
    cleanupDuplicatedObjects,
    writeInsertableFile,
    applyRotation,
    getPathAndLevel,
    applyBasicTweaks,
    tempName,
    bytesToHex,
    applyRotation,
    customExportWarning,
    decompFolderMessage,
    makeWriteInfoBox,
    writeBoxExportType,
    enumExportHeaderType,
)


class CollisionVertex:
    def __init__(self, position):
        self.position = position

    def to_binary(self):
        data = bytearray(0)
        if len(self.position) > 3:
            raise PluginError("Vertex position should not be " + str(len(self.position) + " fields long."))
        for field in self.position:
            data.extend(int(round(field)).to_bytes(2, "big", signed=True))
        return data

    def to_c(self):
        return (
            "COL_VERTEX("
            + str(int(round(self.position[0])))
            + ", "
            + str(int(round(self.position[1])))
            + ", "
            + str(int(round(self.position[2])))
            + "),\n"
        )


class CollisionTriangle:
    def __init__(self, indices, specialParam, room):
        self.indices = indices
        self.specialParam = specialParam
        self.room = room

    def to_binary(self):
        data = bytearray(0)
        if len(self.indices) > 3:
            raise PluginError("Triangle indices should not be " + str(len(self.indices) + " fields long."))
        for index in self.indices:
            data.extend(int(round(index)).to_bytes(2, "big", signed=False))
        if self.specialParam is not None:
            data.extend(int(self.specialParam, 16).to_bytes(2, "big", signed=False))
        return data

    def to_c(self):
        if self.specialParam is None:
            return (
                "COL_TRI("
                + str(int(round(self.indices[0])))
                + ", "
                + str(int(round(self.indices[1])))
                + ", "
                + str(int(round(self.indices[2])))
                + "),\n"
            )
        else:
            return (
                "COL_TRI_SPECIAL("
                + str(int(round(self.indices[0])))
                + ", "
                + str(int(round(self.indices[1])))
                + ", "
                + str(int(round(self.indices[2])))
                + ", "
                + str(self.specialParam)
                + "),\n"
            )


class Collision:
    def __init__(self, name):
        self.name = name
        self.startAddress = 0
        self.vertices = []
        # dict of collision type : triangle list
        self.triangles = {}
        self.specials = []
        self.water_boxes = []

    def set_addr(self, startAddress):
        startAddress = get64bitAlignedAddr(startAddress)
        self.startAddress = startAddress
        print("Collision " + self.name + ": " + str(startAddress) + ", " + str(self.size()))
        return startAddress, startAddress + self.size()

    def save_binary(self, romfile):
        romfile.seek(self.startAddress)
        romfile.write(self.to_binary())

    def size(self):
        return len(self.to_binary())

    def to_c(self):
        data = CData()
        data.header = "extern const Collision " + self.name + "[];\n"
        data.source = "const Collision " + self.name + "[] = {\n"
        data.source += "\tCOL_INIT(),\n"
        data.source += "\tCOL_VERTEX_INIT(" + str(len(self.vertices)) + "),\n"
        for vertex in self.vertices:
            data.source += "\t" + vertex.to_c()
        for collisionType, triangles in self.triangles.items():
            data.source += "\tCOL_TRI_INIT(" + collisionType + ", " + str(len(triangles)) + "),\n"
            for triangle in triangles:
                data.source += "\t" + triangle.to_c()
        data.source += "\tCOL_TRI_STOP(),\n"
        if len(self.specials) > 0:
            data.source += "\tCOL_SPECIAL_INIT(" + str(len(self.specials)) + "),\n"
            for special in self.specials:
                data.source += "\t" + special.to_c()
        if len(self.water_boxes) > 0:
            data.source += "\tCOL_WATER_BOX_INIT(" + str(len(self.water_boxes)) + "),\n"
            for waterBox in self.water_boxes:
                data.source += "\t" + waterBox.to_c()
        data.source += "\tCOL_END()\n" + "};\n"
        return data

    def rooms_name(self):
        return self.name + "_rooms"

    def to_c_rooms(self):
        data = CData()
        data.header = "extern const u8 " + self.rooms_name() + "[];\n"
        data.source = "const u8 " + self.rooms_name() + "[] = {\n\t"
        newlineCount = 0
        for (
            collisionType,
            triangles,
        ) in self.triangles.items():
            for triangle in triangles:
                data.source += str(triangle.room) + ", "
                newlineCount += 1
                if newlineCount >= 8:
                    newlineCount = 0
                    data.source += "\n\t"
        data.source += "\n};\n"
        return data

    def to_binary(self):
        colTypeDef = CollisionTypeDefinition()
        data = bytearray([0x00, 0x40])
        data += len(self.vertices).to_bytes(2, "big")
        for vertex in self.vertices:
            data += vertex.to_binary()
        for collisionType, triangles in self.triangles.items():
            data += getattr(colTypeDef, collisionType).to_bytes(2, "big")
            data += len(triangles).to_bytes(2, "big")
            for triangle in triangles:
                data += triangle.to_binary()
        data += bytearray([0x00, 0x41])
        if len(self.specials) > 0:
            data += bytearray([0x00, 0x43])
            data += len(self.specials).to_bytes(2, "big")
            for special in self.specials:
                data += special.to_binary()
        if len(self.water_boxes) > 0:
            data += bytearray([0x00, 0x44])
            data += len(self.water_boxes).to_bytes(2, "big")
            for waterBox in self.water_boxes:
                data += waterBox.to_binary()
        data += bytearray([0x00, 0x42])
        return data


class SM64CollisionPanel(bpy.types.Panel):
    bl_label = "Collision Inspector"
    bl_idname = "MATERIAL_PT_SM64_Collision_Inspector"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "material"
    bl_options = {"HIDE_HEADER"}

    @classmethod
    def poll(cls, context):
        return context.scene.gameEditorMode == "SM64" and context.material is not None

    def paramInfo(self, layout):
        box = layout.box()
        box.label(text="Parameter is two bytes.")
        box.label(text="First byte is an index into an array of speed values.")
        box.label(text="(See: sMovingSandSpeeds, sWaterCurrentSpeeds)")
        box.label(text="Second byte is a rotation value.")

    def draw(self, context):
        box = self.layout.box()
        # box.label(text = 'Collision Inspector')
        material = context.material
        if not material.collision_all_options:
            prop_split(box, material, "collision_type_simple", "SM64 Collision Type")
            if material.collision_type_simple == "Custom":
                prop_split(box, material, "collision_custom", "Collision Value")
            # if material.collision_type_simple in specialSurfaces:
            # 	prop_split(box, material, 'collision_param', 'Parameter')
            # 	self.paramInfo(box)
        else:
            prop_split(box, material, "collision_type", "SM64 Collision Type All")
            if material.collision_type == "Custom":
                prop_split(box, material, "collision_custom", "Collision Value")
            # if material.collision_type in specialSurfaces:
            # 	prop_split(box, material, 'collision_param', 'Parameter')
            # 	self.paramInfo(box)

        split = box.split(factor=0.5)
        split.label(text="")
        split.prop(material, "collision_all_options")

        box.prop(material, "use_collision_param")
        if material.use_collision_param:
            prop_split(box, material, "collision_param", "Parameter")
            self.paramInfo(box)

        # infoBox = box.box()
        # infoBox.label(text = \
        # 	'For special params, make a vert color layer named "Collision."')
        # infoBox.label(text = 'The red value 0-1 will be converted to 0-65535.')


"""
class SM64ObjectPanel(bpy.types.Panel):
	bl_label = "Object Inspector"
	bl_idname = "SM64_Object_Inspector"
	bl_space_type = 'PROPERTIES'
	bl_region_type = 'WINDOW'
	bl_context = "object"
	bl_options = {'HIDE_HEADER'}

	@classmethod
	def poll(cls, context):
		return (context.object is not None)

	def draw(self, context):
		box = self.layout.box()
		box.label(text = 'SM64 Object Inspector')
		obj = context.object
		prop_split(box, obj, 'sm64_obj_type', 'Special Preset')
		if obj.sm64_obj_type == 'Special':
			prop_split(box, obj, 'sm64_special_preset', 'Special Preset')
		elif obj.sm64_obj_type == 'Water Box':
			prop_split(box, obj, 'sm64_water_box', 'Water Box Type')
"""


def exportCollisionBinary(obj, transformMatrix, romfile, startAddress, endAddress, includeSpecials, includeChildren):
    collision = exportCollisionCommon(obj, transformMatrix, includeSpecials, includeChildren, obj.name, None)
    start, end = collision.set_addr(startAddress)
    if end > endAddress:
        raise PluginError("Size too big: Data ends at " + hex(end) + ", which is larger than the specified range.")
    collision.save_binary(romfile)
    return start, end


def exportCollisionC(
    obj,
    transformMatrix,
    dirPath,
    includeSpecials,
    includeChildren,
    name,
    customExport,
    writeRoomsFile,
    headerType,
    groupName,
    levelName,
):
    dirPath, texDir = getExportDir(customExport, dirPath, headerType, levelName, "", name)

    name = toAlnum(name)
    colDirPath = os.path.join(dirPath, toAlnum(name))

    if not os.path.exists(colDirPath):
        os.mkdir(colDirPath)

    colPath = os.path.join(colDirPath, "collision.inc.c")

    fileObj = open(colPath, "w", newline="\n")
    collision = exportCollisionCommon(obj, transformMatrix, includeSpecials, includeChildren, name, None)
    collisionC = collision.to_c()
    fileObj.write(collisionC.source)
    fileObj.close()

    cDefine = collisionC.header
    if writeRoomsFile:
        roomsData = collision.to_c_rooms()
        cDefine += roomsData.header
        roomsPath = os.path.join(colDirPath, "rooms.inc.c")
        roomsFile = open(roomsPath, "w", newline="\n")
        roomsFile.write(roomsData.source)
        roomsFile.close()

    headerPath = os.path.join(colDirPath, "collision_header.h")
    cDefFile = open(headerPath, "w", newline="\n")
    cDefFile.write(cDefine)
    cDefFile.close()

    if headerType == "Actor":
        # Write to group files
        if groupName == "" or groupName is None:
            raise PluginError("Actor header type chosen but group name not provided.")

        groupPathC = os.path.join(dirPath, groupName + ".c")
        groupPathH = os.path.join(dirPath, groupName + ".h")

        writeIfNotFound(groupPathC, '\n#include "' + name + '/collision.inc.c"', "")
        if writeRoomsFile:
            writeIfNotFound(groupPathC, '\n#include "' + name + '/rooms.inc.c"', "")
        else:
            deleteIfFound(groupPathC, '\n#include "' + name + '/rooms.inc.c"')
        writeIfNotFound(groupPathH, '\n#include "' + name + '/collision_header.h"', "\n#endif")

    elif headerType == "Level":
        groupPathC = os.path.join(dirPath, "leveldata.c")
        groupPathH = os.path.join(dirPath, "header.h")

        writeIfNotFound(groupPathC, '\n#include "levels/' + levelName + "/" + name + '/collision.inc.c"', "")
        if writeRoomsFile:
            writeIfNotFound(groupPathC, '\n#include "levels/' + levelName + "/" + name + '/rooms.inc.c"', "")
        else:
            deleteIfFound(groupPathC, '\n#include "levels/' + levelName + "/" + name + '/rooms.inc.c"')
        writeIfNotFound(groupPathH, '\n#include "levels/' + levelName + "/" + name + '/collision_header.h"', "\n#endif")

    return cDefine


def exportCollisionInsertableBinary(obj, transformMatrix, filepath, includeSpecials, includeChildren):
    collision = exportCollisionCommon(obj, transformMatrix, includeSpecials, includeChildren, obj.name, None)
    start, end = collision.set_addr(0)
    if end > 0xFFFFFF:
        raise PluginError("Size too big: Data ends at " + hex(end) + ", which is larger than the specified range.")

    bytesIO = BytesIO()
    collision.save_binary(bytesIO)
    data = bytesIO.getvalue()[start:]
    bytesIO.close()

    writeInsertableFile(filepath, insertableBinaryTypes["Collision"], [], collision.startAddress, data)

    return data


def exportCollisionCommon(obj, transformMatrix, includeSpecials, includeChildren, name, areaIndex):
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)

    # dict of collisionType : faces
    collisionDict = {}
    # addCollisionTriangles(obj, collisionDict, includeChildren, transformMatrix, areaIndex)
    tempObj, allObjs = duplicateHierarchy(obj, None, True, areaIndex)
    try:
        addCollisionTriangles(tempObj, collisionDict, includeChildren, transformMatrix, areaIndex)
        if not collisionDict:
            raise PluginError("No collision data to export")
        cleanupDuplicatedObjects(allObjs)
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
    except Exception as e:
        cleanupDuplicatedObjects(allObjs)
        obj.select_set(True)
        bpy.context.view_layer.objects.active = obj
        raise Exception(str(e))

    collision = Collision(toAlnum(name) + "_collision")
    for collisionType, faces in collisionDict.items():
        collision.triangles[collisionType] = []
        for faceVerts, specialParam, room in faces:
            indices = []
            for roundedPosition in faceVerts:
                index = collisionVertIndex(roundedPosition, collision.vertices)
                if index is None:
                    collision.vertices.append(CollisionVertex(roundedPosition))
                    indices.append(len(collision.vertices) - 1)
                else:
                    indices.append(index)
            collision.triangles[collisionType].append(CollisionTriangle(indices, specialParam, room))
    if includeSpecials:
        area = SM64_Area(areaIndex, "", "", "", None, None, [], name, None)
        # This assumes that only levels will export with included specials,
        # And that the collision exporter never will.
        start_process_sm64_objects(obj, area, transformMatrix, True)
        collision.specials = area.specials
        collision.water_boxes = area.water_boxes

    return collision


def addCollisionTriangles(obj, collisionDict, includeChildren, transformMatrix, areaIndex):
    if obj.type == "MESH" and not obj.ignore_collision:
        if len(obj.data.materials) == 0:
            raise PluginError(obj.name + " must have a material associated with it.")
        obj.data.calc_loop_triangles()
        for face in obj.data.loop_triangles:
            material = obj.material_slots[face.material_index].material
            colType = material.collision_type if material.collision_all_options else material.collision_type_simple
            if colType == "Custom":
                colType = material.collision_custom
            specialParam = material.collision_param if material.use_collision_param else None

            (x1, y1, z1) = roundPosition(transformMatrix @ obj.data.vertices[face.vertices[0]].co)
            (x2, y2, z2) = roundPosition(transformMatrix @ obj.data.vertices[face.vertices[1]].co)
            (x3, y3, z3) = roundPosition(transformMatrix @ obj.data.vertices[face.vertices[2]].co)

            nx = (y2 - y1) * (z3 - z2) - (z2 - z1) * (y3 - y2)
            ny = (z2 - z1) * (x3 - x2) - (x2 - x1) * (z3 - z2)
            nz = (x2 - x1) * (y3 - y2) - (y2 - y1) * (x3 - x2)
            magSqr = nx * nx + ny * ny + nz * nz

            if magSqr <= 0:
                print("Ignore denormalized triangle.")
                continue

            if colType not in collisionDict:
                collisionDict[colType] = []
            collisionDict[colType].append((((x1, y1, z1), (x2, y2, z2), (x3, y3, z3)), specialParam, obj.room_num))

    if includeChildren:
        for child in obj.children:
            addCollisionTriangles(
                child, collisionDict, includeChildren, transformMatrix @ child.matrix_local, areaIndex
            )


def roundPosition(position):
    return (int(round(position[0])), int(round(position[1])), int(round(position[2])))


def collisionVertIndex(vert, vertArray):
    for i in range(len(vertArray)):
        colVert = vertArray[i]
        if colVert.position == vert:
            return i
    return None


class SM64_ExportCollision(bpy.types.Operator):
    # set bl_ properties
    bl_idname = "object.sm64_export_collision"
    bl_label = "Export Collision"
    bl_options = {"REGISTER", "UNDO"}

    export_obj: bpy.props.StringProperty()

    def execute(self, context):
        romfileOutput = None
        tempROM = None
        props = context.scene.fast64.sm64.combined_export
        try:
            obj = None
            if context.mode != "OBJECT":
                raise PluginError("Operator can only be used in object mode.")
            obj = bpy.data.objects.get(self.export_obj, None) or context.active_object
            self.export_obj = ""
            scale_value = context.scene.fast64.sm64.blender_to_sm64_scale
            final_transform = mathutils.Matrix.Diagonal(
                mathutils.Vector((scale_value, scale_value, scale_value))
            ).to_4x4()
        except Exception as e:
            raisePluginError(self, e)
            return {"CANCELLED"}

        try:
            applyRotation([obj], math.radians(90), "X")
            if context.scene.fast64.sm64.export_type == "C":
                export_path, level_name = getPathAndLevel(
                    props.is_actor_custom_export,
                    props.actor_custom_path,
                    props.export_level_name,
                    props.level_name,
                )
                if not props.is_actor_custom_export:
                    applyBasicTweaks(export_path)
                exportCollisionC(
                    obj,
                    final_transform,
                    export_path,
                    False,
                    props.include_children,
                    props.obj_name_col,
                    props.is_actor_custom_export,
                    props.export_rooms,
                    props.export_header_type,
                    props.actor_group_name,
                    level_name,
                )
                self.report({"INFO"}, "Success!")
            elif context.scene.fast64.sm64.export_type == "Insertable Binary":
                exportCollisionInsertableBinary(
                    obj,
                    final_transform,
                    bpy.path.abspath(context.scene.colInsertableBinaryPath),
                    False,
                    context.scene.colIncludeChildren,
                )
                self.report({"INFO"}, "Success! Collision at " + context.scene.colInsertableBinaryPath)
            else:
                tempROM = tempName(context.scene.fast64.sm64.output_rom)
                export_rom_checks(bpy.path.abspath(context.scene.fast64.sm64.export_rom))
                romfileExport = open(bpy.path.abspath(context.scene.fast64.sm64.export_rom), "rb")
                shutil.copy(bpy.path.abspath(context.scene.fast64.sm64.export_rom), bpy.path.abspath(tempROM))
                romfileExport.close()
                romfileOutput = open(bpy.path.abspath(tempROM), "rb+")

                levelParsed = parseLevelAtPointer(romfileOutput, level_pointers[context.scene.colExportLevel])
                segmentData = levelParsed.segmentData

                if context.scene.fast64.sm64.extend_bank_4:
                    ExtendBank0x04(romfileOutput, segmentData, defaultExtendSegment4)

                addrRange = exportCollisionBinary(
                    obj,
                    final_transform,
                    romfileOutput,
                    int(context.scene.colStartAddr, 16),
                    int(context.scene.colEndAddr, 16),
                    False,
                    context.scene.colIncludeChildren,
                )

                segAddress = encodeSegmentedAddr(addrRange[0], segmentData)
                if context.scene.set_addr_0x2A:
                    romfileOutput.seek(int(context.scene.addr_0x2A, 16) + 4)
                    romfileOutput.write(segAddress)
                segPointer = bytesToHex(segAddress)

                romfileOutput.close()

                if os.path.exists(bpy.path.abspath(context.scene.fast64.sm64.output_rom)):
                    os.remove(bpy.path.abspath(context.scene.fast64.sm64.output_rom))
                os.rename(bpy.path.abspath(tempROM), bpy.path.abspath(context.scene.fast64.sm64.output_rom))

                self.report(
                    {"INFO"},
                    "Success! Collision at ("
                    + hex(addrRange[0])
                    + ", "
                    + hex(addrRange[1])
                    + ") (Seg. "
                    + segPointer
                    + ").",
                )

            applyRotation([obj], math.radians(-90), "X")
            return {"FINISHED"}  # must return a set

        except Exception as e:
            if context.mode != "OBJECT":
                bpy.ops.object.mode_set(mode="OBJECT")

            applyRotation([obj], math.radians(-90), "X")

            if context.scene.fast64.sm64.export_type == "Binary":
                if romfileOutput is not None:
                    romfileOutput.close()
                if tempROM is not None and os.path.exists(bpy.path.abspath(tempROM)):
                    os.remove(bpy.path.abspath(tempROM))
            obj.select_set(True)
            context.view_layer.objects.active = obj
            raisePluginError(self, e)
            return {"CANCELLED"}  # must return a set


class SM64_ExportCollisionPanel(SM64_Panel):
    bl_idname = "SM64_PT_export_collision"
    bl_label = "SM64 Collision Exporter"
    goal = "Object/Actor/Anim"
    binary_only = True

    # called every frame
    def draw(self, context):
        col = self.layout.column()
        propsColE = col.operator(SM64_ExportCollision.bl_idname)

        col.prop(context.scene, "colIncludeChildren")
        if context.scene.fast64.sm64.export_type == "Insertable Binary":
            col.prop(context.scene, "colInsertableBinaryPath")
        else:
            prop_split(col, context.scene, "colStartAddr", "Start Address")
            prop_split(col, context.scene, "colEndAddr", "End Address")
            prop_split(col, context.scene, "colExportLevel", "Level Used By Collision")
            col.prop(context.scene, "set_addr_0x2A")
            if context.scene.set_addr_0x2A:
                prop_split(col, context.scene, "addr_0x2A", "0x2A Behaviour Command Address")


sm64_col_classes = (SM64_ExportCollision,)

sm64_col_panel_classes = (
    SM64CollisionPanel,
    SM64_ExportCollisionPanel,
)


def sm64_col_panel_register():
    for cls in sm64_col_panel_classes:
        register_class(cls)


def sm64_col_panel_unregister():
    for cls in sm64_col_panel_classes:
        unregister_class(cls)


def sm64_col_register():
    for cls in sm64_col_classes:
        register_class(cls)

    # Collision
    bpy.types.Scene.colExportLevel = bpy.props.EnumProperty(
        items=level_enums, name="Level Used By Collision", default="WF"
    )
    bpy.types.Scene.addr_0x2A = bpy.props.StringProperty(name="0x2A Behaviour Command Address", default="21A9CC")
    bpy.types.Scene.set_addr_0x2A = bpy.props.BoolProperty(name="Overwrite 0x2A Behaviour Command")
    bpy.types.Scene.colStartAddr = bpy.props.StringProperty(name="Start Address", default="11D8930")
    bpy.types.Scene.colEndAddr = bpy.props.StringProperty(name="Start Address", default="11FFF00")
    bpy.types.Scene.colIncludeChildren = bpy.props.BoolProperty(name="Include child objects", default=True)
    bpy.types.Scene.colInsertableBinaryPath = bpy.props.StringProperty(name="Filepath", subtype="FILE_PATH")

    bpy.types.Material.collision_type = bpy.props.EnumProperty(
        name="Collision Type", items=enumCollisionType, default="SURFACE_DEFAULT"
    )
    bpy.types.Material.collision_type_simple = bpy.props.EnumProperty(
        name="Collision Type", items=enumCollisionTypeSimple, default="SURFACE_DEFAULT"
    )
    bpy.types.Material.collision_custom = bpy.props.StringProperty(name="Collision Value", default="SURFACE_DEFAULT")
    bpy.types.Material.collision_all_options = bpy.props.BoolProperty(name="Show All Options")
    bpy.types.Material.use_collision_param = bpy.props.BoolProperty(name="Use Collision Parameter")
    bpy.types.Material.collision_param = bpy.props.StringProperty(name="Parameter", default="0x0000")
    bpy.types.Object.sm64_water_box = bpy.props.EnumProperty(
        name="SM64 Water Box", items=enumWaterBoxType, default="Water"
    )
    bpy.types.Object.sm64_special_preset = bpy.props.EnumProperty(
        name="SM64 Special", items=enumSpecialType, default="special_yellow_coin"
    )
    bpy.types.Object.room_num = bpy.props.IntProperty(name="Room", default=0, min=0)


def sm64_col_unregister():
    # Collision
    del bpy.types.Scene.colExportLevel
    del bpy.types.Scene.addr_0x2A
    del bpy.types.Scene.set_addr_0x2A
    del bpy.types.Scene.colStartAddr
    del bpy.types.Scene.colEndAddr
    del bpy.types.Scene.colInsertableBinaryPath

    del bpy.types.Material.collision_type
    del bpy.types.Material.collision_type_simple
    del bpy.types.Material.collision_all_options
    del bpy.types.Material.collision_param
    del bpy.types.Material.collision_custom

    del bpy.types.Object.sm64_water_box
    del bpy.types.Object.sm64_special_preset

    del bpy.types.Object.room_num

    for cls in reversed(sm64_col_classes):
        unregister_class(cls)


enumWaterBoxType = [("Water", "Water", "Water"), ("Toxic Haze", "Toxic Haze", "Toxic Haze")]

specialSurfaces = [
    "SURFACE_0004",
    "SURFACE_FLOWING_WATER",
    "SURFACE_DEEP_MOVING_QUICKSAND",
    "SURFACE_SHALLOW_MOVING_QUICKSAND",
    "SURFACE_MOVING_QUICKSAND",
    "SURFACE_HORIZONTAL_WIND",
    "SURFACE_INSTANT_MOVING_QUICKSAND",
]


class CollisionTypeDefinition:
    def __init__(self):
        self.SURFACE_DEFAULT = 0x0000
        self.SURFACE_BURNING = 0x0001
        self.SURFACE_0004 = 0x0004
        self.SURFACE_HANGABLE = 0x0005
        self.SURFACE_SLOW = 0x0009
        self.SURFACE_DEATH_PLANE = 0x000A
        self.SURFACE_CLOSE_CAMERA = 0x000B
        self.SURFACE_WATER = 0x000D
        self.SURFACE_FLOWING_WATER = 0x000E
        self.SURFACE_INTANGIBLE = 0x0012
        self.SURFACE_VERY_SLIPPERY = 0x0013
        self.SURFACE_SLIPPERY = 0x0014
        self.SURFACE_NOT_SLIPPERY = 0x0015
        self.SURFACE_TTM_VINES = 0x0016
        self.SURFACE_MGR_MUSIC = 0x001A
        self.SURFACE_INSTANT_WARP_1B = 0x001B
        self.SURFACE_INSTANT_WARP_1C = 0x001C
        self.SURFACE_INSTANT_WARP_1D = 0x001D
        self.SURFACE_INSTANT_WARP_1E = 0x001E
        self.SURFACE_SHALLOW_QUICKSAND = 0x0021
        self.SURFACE_DEEP_QUICKSAND = 0x0022
        self.SURFACE_INSTANT_QUICKSAND = 0x0023
        self.SURFACE_DEEP_MOVING_QUICKSAND = 0x0024
        self.SURFACE_SHALLOW_MOVING_QUICKSAND = 0x0025
        self.SURFACE_QUICKSAND = 0x0026
        self.SURFACE_MOVING_QUICKSAND = 0x0027
        self.SURFACE_WALL_MISC = 0x0028
        self.SURFACE_NOISE_DEFAULT = 0x0029
        self.SURFACE_NOISE_SLIPPERY = 0x002A
        self.SURFACE_HORIZONTAL_WIND = 0x002C
        self.SURFACE_INSTANT_MOVING_QUICKSAND = 0x002D
        self.SURFACE_ICE = 0x002E
        self.SURFACE_LOOK_UP_WARP = 0x002F
        self.SURFACE_HARD = 0x0030
        self.SURFACE_WARP = 0x0032
        self.SURFACE_TIMER_START = 0x0033
        self.SURFACE_TIMER_END = 0x0034
        self.SURFACE_HARD_SLIPPERY = 0x0035
        self.SURFACE_HARD_VERY_SLIPPERY = 0x0036
        self.SURFACE_HARD_NOT_SLIPPERY = 0x0037
        self.SURFACE_VERTICAL_WIND = 0x0038
        self.SURFACE_BOSS_FIGHT_CAMERA = 0x0065
        self.SURFACE_CAMERA_FREE_ROAM = 0x0066
        self.SURFACE_THI3_WALLKICK = 0x0068
        self.SURFACE_CAMERA_PLATFORM = 0x0069
        self.SURFACE_CAMERA_MIDDLE = 0x006E
        self.SURFACE_CAMERA_ROTATE_RIGHT = 0x006F
        self.SURFACE_CAMERA_ROTATE_LEFT = 0x0070
        self.SURFACE_CAMERA_BOUNDARY = 0x0072
        self.SURFACE_NOISE_VERY_SLIPPERY_73 = 0x0073
        self.SURFACE_NOISE_VERY_SLIPPERY_74 = 0x0074
        self.SURFACE_NOISE_VERY_SLIPPERY = 0x0075
        self.SURFACE_NO_CAM_COLLISION = 0x0076
        self.SURFACE_NO_CAM_COLLISION_77 = 0x0077
        self.SURFACE_NO_CAM_COL_VERY_SLIPPERY = 0x0078
        self.SURFACE_NO_CAM_COL_SLIPPERY = 0x0079
        self.SURFACE_SWITCH = 0x007A
        self.SURFACE_VANISH_CAP_WALLS = 0x007B
        self.SURFACE_PAINTING_WOBBLE_A6 = 0x00A6
        self.SURFACE_PAINTING_WOBBLE_A7 = 0x00A7
        self.SURFACE_PAINTING_WOBBLE_A8 = 0x00A8
        self.SURFACE_PAINTING_WOBBLE_A9 = 0x00A9
        self.SURFACE_PAINTING_WOBBLE_AA = 0x00AA
        self.SURFACE_PAINTING_WOBBLE_AB = 0x00AB
        self.SURFACE_PAINTING_WOBBLE_AC = 0x00AC
        self.SURFACE_PAINTING_WOBBLE_AD = 0x00AD
        self.SURFACE_PAINTING_WOBBLE_AE = 0x00AE
        self.SURFACE_PAINTING_WOBBLE_AF = 0x00AF
        self.SURFACE_PAINTING_WOBBLE_B0 = 0x00B0
        self.SURFACE_PAINTING_WOBBLE_B1 = 0x00B1
        self.SURFACE_PAINTING_WOBBLE_B2 = 0x00B2
        self.SURFACE_PAINTING_WOBBLE_B3 = 0x00B3
        self.SURFACE_PAINTING_WOBBLE_B4 = 0x00B4
        self.SURFACE_PAINTING_WOBBLE_B5 = 0x00B5
        self.SURFACE_PAINTING_WOBBLE_B6 = 0x00B6
        self.SURFACE_PAINTING_WOBBLE_B7 = 0x00B7
        self.SURFACE_PAINTING_WOBBLE_B8 = 0x00B8
        self.SURFACE_PAINTING_WOBBLE_B9 = 0x00B9
        self.SURFACE_PAINTING_WOBBLE_BA = 0x00BA
        self.SURFACE_PAINTING_WOBBLE_BB = 0x00BB
        self.SURFACE_PAINTING_WOBBLE_BC = 0x00BC
        self.SURFACE_PAINTING_WOBBLE_BD = 0x00BD
        self.SURFACE_PAINTING_WOBBLE_BE = 0x00BE
        self.SURFACE_PAINTING_WOBBLE_BF = 0x00BF
        self.SURFACE_PAINTING_WOBBLE_C0 = 0x00C0
        self.SURFACE_PAINTING_WOBBLE_C1 = 0x00C1
        self.SURFACE_PAINTING_WOBBLE_C2 = 0x00C2
        self.SURFACE_PAINTING_WOBBLE_C3 = 0x00C3
        self.SURFACE_PAINTING_WOBBLE_C4 = 0x00C4
        self.SURFACE_PAINTING_WOBBLE_C5 = 0x00C5
        self.SURFACE_PAINTING_WOBBLE_C6 = 0x00C6
        self.SURFACE_PAINTING_WOBBLE_C7 = 0x00C7
        self.SURFACE_PAINTING_WOBBLE_C8 = 0x00C8
        self.SURFACE_PAINTING_WOBBLE_C9 = 0x00C9
        self.SURFACE_PAINTING_WOBBLE_CA = 0x00CA
        self.SURFACE_PAINTING_WOBBLE_CB = 0x00CB
        self.SURFACE_PAINTING_WOBBLE_CC = 0x00CC
        self.SURFACE_PAINTING_WOBBLE_CD = 0x00CD
        self.SURFACE_PAINTING_WOBBLE_CE = 0x00CE
        self.SURFACE_PAINTING_WOBBLE_CF = 0x00CF
        self.SURFACE_PAINTING_WOBBLE_D0 = 0x00D0
        self.SURFACE_PAINTING_WOBBLE_D1 = 0x00D1
        self.SURFACE_PAINTING_WOBBLE_D2 = 0x00D2
        self.SURFACE_PAINTING_WARP_D3 = 0x00D3
        self.SURFACE_PAINTING_WARP_D4 = 0x00D4
        self.SURFACE_PAINTING_WARP_D5 = 0x00D5
        self.SURFACE_PAINTING_WARP_D6 = 0x00D6
        self.SURFACE_PAINTING_WARP_D7 = 0x00D7
        self.SURFACE_PAINTING_WARP_D8 = 0x00D8
        self.SURFACE_PAINTING_WARP_D9 = 0x00D9
        self.SURFACE_PAINTING_WARP_DA = 0x00DA
        self.SURFACE_PAINTING_WARP_DB = 0x00DB
        self.SURFACE_PAINTING_WARP_DC = 0x00DC
        self.SURFACE_PAINTING_WARP_DD = 0x00DD
        self.SURFACE_PAINTING_WARP_DE = 0x00DE
        self.SURFACE_PAINTING_WARP_DF = 0x00DF
        self.SURFACE_PAINTING_WARP_E0 = 0x00E0
        self.SURFACE_PAINTING_WARP_E1 = 0x00E1
        self.SURFACE_PAINTING_WARP_E2 = 0x00E2
        self.SURFACE_PAINTING_WARP_E3 = 0x00E3
        self.SURFACE_PAINTING_WARP_E4 = 0x00E4
        self.SURFACE_PAINTING_WARP_E5 = 0x00E5
        self.SURFACE_PAINTING_WARP_E6 = 0x00E6
        self.SURFACE_PAINTING_WARP_E7 = 0x00E7
        self.SURFACE_PAINTING_WARP_E8 = 0x00E8
        self.SURFACE_PAINTING_WARP_E9 = 0x00E9
        self.SURFACE_PAINTING_WARP_EA = 0x00EA
        self.SURFACE_PAINTING_WARP_EB = 0x00EB
        self.SURFACE_PAINTING_WARP_EC = 0x00EC
        self.SURFACE_PAINTING_WARP_ED = 0x00ED
        self.SURFACE_PAINTING_WARP_EE = 0x00EE
        self.SURFACE_PAINTING_WARP_EF = 0x00EF
        self.SURFACE_PAINTING_WARP_F0 = 0x00F0
        self.SURFACE_PAINTING_WARP_F1 = 0x00F1
        self.SURFACE_PAINTING_WARP_F2 = 0x00F2
        self.SURFACE_PAINTING_WARP_F3 = 0x00F3
        self.SURFACE_TTC_PAINTING_1 = 0x00F4
        self.SURFACE_TTC_PAINTING_2 = 0x00F5
        self.SURFACE_TTC_PAINTING_3 = 0x00F6
        self.SURFACE_PAINTING_WARP_F7 = 0x00F7
        self.SURFACE_PAINTING_WARP_F8 = 0x00F8
        self.SURFACE_PAINTING_WARP_F9 = 0x00F9
        self.SURFACE_PAINTING_WARP_FA = 0x00FA
        self.SURFACE_PAINTING_WARP_FB = 0x00FB
        self.SURFACE_PAINTING_WARP_FC = 0x00FC
        self.SURFACE_WOBBLING_WARP = 0x00FD
        self.SURFACE_TRAPDOOR = 0x00FF

        self.SURFACE_CLASS_DEFAULT = 0x0000
        self.SURFACE_CLASS_VERY_SLIPPERY = 0x0013
        self.SURFACE_CLASS_SLIPPERY = 0x0014
        self.SURFACE_CLASS_NOT_SLIPPERY = 0x0015

        self.SURFACE_FLAG_DYNAMIC = 1 << 0
        self.SURFACE_FLAG_NO_CAM_COLLISION = 1 << 1
        self.SURFACE_FLAG_X_PROJECTION = 1 << 3

        self.TERRAIN_LOAD_VERTICES = 0x0040
        self.TERRAIN_LOAD_CONTINUE = 0x0041
        self.TERRAIN_LOAD_END = 0x0042
        self.TERRAIN_LOAD_OBJECTS = 0x0043
        self.TERRAIN_LOAD_ENVIRONMENT = 0x0044

        self.TERRAIN_GRASS = 0x0000
        self.TERRAIN_STONE = 0x0001
        self.TERRAIN_SNOW = 0x0002
        self.TERRAIN_SAND = 0x0003
        self.TERRAIN_SPOOKY = 0x0004
        self.TERRAIN_WATER = 0x0005
        self.TERRAIN_SLIDE = 0x0006
        self.TERRAIN_MASK = 0x0007

    def SURFACE_IS_QUICKSAND(self, cmd):
        return cmd >= 0x21 and cmd <= 0x28

    def SURFACE_IS_NOT_HARD(self, cmd):
        return cmd != self.SURFACE_HARD and not (cmd >= 0x35 and cmd <= 0x37)

    def SURFACE_IS_PAINTING_WARP(self, cmd):
        return cmd >= 0xD3 and cmd < 0xFD

    def TERRAIN_LOAD_IS_SURFACE_TYPE_LOW(self, cmd):
        return cmd < 0x40

    def TERRAIN_LOAD_IS_SURFACE_TYPE_HIGH(self, cmd):
        return cmd >= 0x65


enumSpecialType = [
    ("special_null_start", "Null Start", "Null Start"),
    ("special_yellow_coin", "Yellow Coin", "Yellow Coin"),
    ("special_yellow_coin_2", "Yellow Coin 2", "Yellow Coin 2"),
    ("special_unknown_3", "Unknown 3", "Unknown 3"),
    ("special_boo", "Boo", "Boo"),
    ("special_unknown_5", "Unknown 5", "Unknown 5"),
    ("special_lll_moving_octagonal_mesh_platform", "LLL Moving Octagonal Platform", "LLL Moving Octagonal Platform"),
    ("special_snow_ball", "Snow Ball", "Snow Ball"),
    ("special_lll_drawbridge_spawner", "LLL Drawbridge Spawner", "LLL Drawbridge Spawner"),
    ("special_empty_9", "Empty 9", "Empty 9"),
    (
        "special_lll_rotating_block_with_fire_bars",
        "LLL Rotating Block With Fire Bars",
        "LLL Rotating Block With Fire Bars",
    ),
    ("special_lll_floating_wood_bridge", "LLL Floating Wood Bridge", "LLL Floating Wood Bridge"),
    ("special_tumbling_platform", "Tumbling Platform", "Tumbling Platform"),
    ("special_lll_rotating_hexagonal_ring", "LLL Rotating Hexagonal Ring", "LLL Rotating Hexagonal Ring"),
    (
        "special_lll_sinking_rectangular_platform",
        "LLL Sinking Rectangular Platform",
        "LLL Sinking Rectangular Platform",
    ),
    ("special_lll_sinking_square_platforms", "LLL Sinking Square Platforms", "LLL Sinking Square Platforms"),
    ("special_lll_tilting_square_platform", "LLL Tilting Square Platform", "LLL Tilting Square Platform"),
    ("special_lll_bowser_puzzle", "LLL Bowser Puzzle", "LLL Bowser Puzzle"),
    ("special_mr_i", "Mr. I", "Mr. I"),
    ("special_small_bully", "Small Bully", "Small Bully"),
    ("special_big_bully", "Big Bully", "Big Bully"),
    ("special_empty_21", "Empty 21", "Empty 21"),
    ("special_empty_22", "Empty 22", "Empty 22"),
    ("special_empty_23", "Empty 23", "Empty 23"),
    ("special_empty_24", "Empty 24", "Empty 24"),
    ("special_empty_25", "Empty 25", "Empty 25"),
    ("special_moving_blue_coin", "Moving Blue Coin", "Moving Blue Coin"),
    ("special_jrb_chest", "JRB Chest", "JRB Chest"),
    ("special_water_ring", "Water Ring", "Water Ring"),
    ("special_mine", "Mine", "Mine"),
    ("special_empty_30", "Empty 30", "Empty 30"),
    ("special_empty_31", "Empty 31", "Empty 31"),
    ("special_butterfly", "Butterfly", "Butterfly"),
    ("special_bowser", "Bowser", "Bowser"),
    ("special_wf_rotating_wooden_platform", "WF Rotating Wooden Platform", "WF Rotating Wooden Platform"),
    ("special_small_bomp", "Small Bomp", "Small Bomp"),
    ("special_wf_sliding_platform", "WF Sliding Platform", "WF Sliding Platform"),
    ("special_tower_platform_group", "Tower Platform Group", "Tower Platform Group"),
    ("special_rotating_counter_clockwise", "Rotating Counter Clockwise", "Rotating Counter Clockwise"),
    ("special_wf_tumbling_bridge", "WF Tumbling Bridge", "WF Tumbling Bridge"),
    ("special_large_bomp", "Large Bomp", "Large Bomp"),
    ("special_level_geo_03", "Level Geo 03", "Level Geo 03"),
    ("special_level_geo_04", "Level Geo 04", "Level Geo 04"),
    ("special_level_geo_05", "Level Geo 05", "Level Geo 05"),
    ("special_level_geo_06", "Level Geo 06", "Level Geo 06"),
    ("special_level_geo_07", "Level Geo 07", "Level Geo 07"),
    ("special_level_geo_08", "Level Geo 08", "Level Geo 08"),
    ("special_level_geo_09", "Level Geo 09", "Level Geo 09"),
    ("special_level_geo_0A", "Level Geo 0A", "Level Geo 0A"),
    ("special_level_geo_0B", "Level Geo 0B", "Level Geo 0B"),
    ("special_level_geo_0C", "Level Geo 0C", "Level Geo 0C"),
    ("special_level_geo_0D", "Level Geo 0D", "Level Geo 0D"),
    ("special_level_geo_0E", "Level Geo 0E", "Level Geo 0E"),
    ("special_level_geo_0F", "Level Geo 0F", "Level Geo 0F"),
    ("special_level_geo_10", "Level Geo 10", "Level Geo 10"),
    ("special_level_geo_11", "Level Geo 11", "Level Geo 11"),
    ("special_level_geo_12", "Level Geo 12", "Level Geo 12"),
    ("special_level_geo_13", "Level Geo 13", "Level Geo 13"),
    ("special_level_geo_14", "Level Geo 14", "Level Geo 14"),
    ("special_level_geo_15", "Level Geo 15", "Level Geo 15"),
    ("special_level_geo_16", "Level Geo 16", "Level Geo 16"),
    ("special_bubble_tree", "bubble_tree", "bubble_tree"),
    ("special_spiky_tree", "Spiky Tree", "Spiky Tree"),
    ("special_snow_tree", "Snow Tree", "Snow Tree"),
    ("special_unknown_tree", "Unknown Tree", "Unknown Tree"),
    ("special_palm_tree", "Palm Tree", "Palm Tree"),
    ("special_wooden_door", "Wooden Door", "Wooden Door"),
    ("special_haunted_door", "Haunted Door", "Haunted Door"),
    ("special_unknown_door", "Unknown Door", "Unknown Door"),
    ("special_metal_door", "Metal Door", "Metal Door"),
    ("special_hmc_door", "HMC Door", "HMC Door"),
    ("special_unknown2_door", "Unknown 2 Door", "Unknown 2 Door"),
    ("special_wooden_door_warp", "Wooden Door Warp", "Wooden Door Warp"),
    ("special_unknown1_door_warp", "Unknown 1 Door Warp", "Unknown 1 Door Warp"),
    ("special_metal_door_warp", "Metal Door Warp", "Metal Door Warp"),
    ("special_unknown2_door_warp", "Unknown 2 Door Warp", "Unknown 2 Door Warp"),
    ("special_unknown3_door_warp", "Unknown 3 Door Warp", "Unknown 3 Door Warp"),
    ("special_castle_door_warp", "Castle Door Warp", "Castle Door Warp"),
    ("special_castle_door", "Castle Door", "Castle Door"),
    ("special_0stars_door", "0 Stars Door", "0 Stars Door"),
    ("special_1star_door", "1 Star Door", "1 Star Door"),
    ("special_3star_door", "3 Star Door", "3 Star Door"),
    ("special_key_door", "Key Door", "Key Door"),
    ("special_null_end", "Null End", "Null End"),
]

enumObjectType = [
    ("None", "None", "None"),
    ("Special", "Special", "Special"),
    ("Water Box", "Water Box", "Water Box"),
]

enumCollisionTypeSimple = [
    ("SURFACE_DEFAULT", "Default", "Default"),
    ("SURFACE_BURNING", "Burning", "Burning"),
    ("SURFACE_HANGABLE", "Hangable", "Hangable"),
    ("SURFACE_SLOW", "Slow", "Slow"),
    ("SURFACE_DEATH_PLANE", "Death Plane", "Death Plane"),
    ("SURFACE_WATER", "Water", "Water"),
    ("SURFACE_FLOWING_WATER", "Flowing Water", "Flowing Water"),
    ("SURFACE_INTANGIBLE", "Intangible", "Intangible"),
    ("SURFACE_VERY_SLIPPERY", "Very Slippery", "Very Slippery"),
    ("SURFACE_SLIPPERY", "Slippery", "Slippery"),
    ("SURFACE_NOT_SLIPPERY", "Not Slippery", "Not Slippery"),
    ("SURFACE_TTM_VINES", "Vines", "Vines"),
    ("SURFACE_SHALLOW_QUICKSAND", "Shallow Quicksand", "Shallow Quicksand"),
    ("SURFACE_DEEP_QUICKSAND", "Deep Quicksand", "Deep Quicksand"),
    ("SURFACE_INSTANT_QUICKSAND", "Instant Quicksand", "Instant Quicksand"),
    ("SURFACE_DEEP_MOVING_QUICKSAND", "Deep Moving Quicksand", "Deep Moving Quicksand"),
    ("SURFACE_SHALLOW_MOVING_QUICKSAND", "Shallow Moving Quicksand", "Shallow Moving Quicksand"),
    ("SURFACE_QUICKSAND", "Quicksand", "Quicksand"),
    ("SURFACE_MOVING_QUICKSAND", "Moving Quicksand", "Moving Quicksand"),
    ("SURFACE_WALL_MISC", "Wall Misc", "Wall Misc"),
    ("SURFACE_NOISE_DEFAULT", "Noise Default", "Noise Default"),
    ("SURFACE_NOISE_SLIPPERY", "Noise Slippery", "Noise Slippery"),
    ("SURFACE_HORIZONTAL_WIND", "Horizontal Wind", "Horizontal Wind"),
    ("SURFACE_INSTANT_MOVING_QUICKSAND", "Instant Moving Quicksand", "Instant Moving Quicksand"),
    ("SURFACE_ICE", "Ice", "Ice"),
    ("SURFACE_HARD", "Hard", "Hard"),
    ("SURFACE_HARD_SLIPPERY", "Hard Slippery", "Hard Slippery"),
    ("SURFACE_HARD_VERY_SLIPPERY", "Hard Very Slippery", "Hard Very Slippery"),
    ("SURFACE_HARD_NOT_SLIPPERY", "Hard Not Slippery", "Hard Not Slippery"),
    ("SURFACE_VERTICAL_WIND", "Vertical Wind", "Vertical Wind"),
    ("SURFACE_SWITCH", "Switch", "Switch"),
    ("SURFACE_VANISH_CAP_WALLS", "Vanish Cap Walls", "Vanish Cap Walls"),
    ("Custom", "Custom", "Custom"),
]

enumCollisionType = [
    ("SURFACE_DEFAULT", "Default", "Default"),
    ("SURFACE_BURNING", "Burning", "Burning"),
    ("SURFACE_0004", "0004", "0004"),
    ("SURFACE_HANGABLE", "Hangable", "Hangable"),
    ("SURFACE_SLOW", "Slow", "Slow"),
    ("SURFACE_DEATH_PLANE", "Death Plane", "Death Plane"),
    ("SURFACE_CLOSE_CAMERA", "Close Camera", "Close Camera"),
    ("SURFACE_WATER", "Water", "Water"),
    ("SURFACE_FLOWING_WATER", "Flowing Water", "Flowing Water"),
    ("SURFACE_INTANGIBLE", "Intangible", "Intangible"),
    ("SURFACE_VERY_SLIPPERY", "Very Slippery", "Very Slippery"),
    ("SURFACE_SLIPPERY", "Slippery", "Slippery"),
    ("SURFACE_NOT_SLIPPERY", "Not Slippery", "Not Slippery"),
    ("SURFACE_TTM_VINES", "Vines", "Vines"),
    ("SURFACE_MGR_MUSIC", "Music", "Music"),
    ("SURFACE_INSTANT_WARP_1B", "Instant Warp 1B", "Instant Warp 1B"),
    ("SURFACE_INSTANT_WARP_1C", "Instant Warp 1C", "Instant Warp 1C"),
    ("SURFACE_INSTANT_WARP_1D", "Instant Warp 1D", "Instant Warp 1D"),
    ("SURFACE_INSTANT_WARP_1E", "Instant Warp 1E", "Instant Warp 1E"),
    ("SURFACE_SHALLOW_QUICKSAND", "Shallow Quicksand", "Shallow Quicksand"),
    ("SURFACE_DEEP_QUICKSAND", "Deep Quicksand", "Deep Quicksand"),
    ("SURFACE_INSTANT_QUICKSAND", "Instant Quicksand", "Instant Quicksand"),
    ("SURFACE_DEEP_MOVING_QUICKSAND", "Deep Moving Quicksand", "Deep Moving Quicksand"),
    ("SURFACE_SHALLOW_MOVING_QUICKSAND", "Shallow Moving Quicksand", "Shallow Moving Quicksand"),
    ("SURFACE_QUICKSAND", "Quicksand", "Quicksand"),
    ("SURFACE_MOVING_QUICKSAND", "Moving Quicksand", "Moving Quicksand"),
    ("SURFACE_WALL_MISC", "Wall Misc", "Wall Misc"),
    ("SURFACE_NOISE_DEFAULT", "Noise Default", "Noise Default"),
    ("SURFACE_NOISE_SLIPPERY", "Noise Slippery", "Noise Slippery"),
    ("SURFACE_HORIZONTAL_WIND", "Horizontal Wind", "Horizontal Wind"),
    ("SURFACE_INSTANT_MOVING_QUICKSAND", "Instant Moving Quicksand", "Instant Moving Quicksand"),
    ("SURFACE_ICE", "Ice", "Ice"),
    ("SURFACE_LOOK_UP_WARP", "Look Up Warp", "Look Up Warp"),
    ("SURFACE_HARD", "Hard", "Hard"),
    ("SURFACE_WARP", "Warp", "Warp"),
    ("SURFACE_TIMER_START", "Timer Start", "Timer Start"),
    ("SURFACE_TIMER_END", "Timer End", "Timer End"),
    ("SURFACE_HARD_SLIPPERY", "Hard Slippery", "Hard Slippery"),
    ("SURFACE_HARD_VERY_SLIPPERY", "Hard Very Slippery", "Hard Very Slippery"),
    ("SURFACE_HARD_NOT_SLIPPERY", "Hard Not Slippery", "Hard Not Slippery"),
    ("SURFACE_VERTICAL_WIND", "Vertical Wind", "Vertical Wind"),
    ("SURFACE_BOSS_FIGHT_CAMERA", "Boss Fight Camera", "Boss Fight Camera"),
    ("SURFACE_CAMERA_FREE_ROAM", "Camera Free Roam", "Camera Free Roam"),
    ("SURFACE_THI3_WALLKICK", "Wallkick", "Wallkick"),
    ("SURFACE_CAMERA_PLATFORM", "Camera Platform", "Camera Platform"),
    ("SURFACE_CAMERA_MIDDLE", "Camera Middle", "Camera Middle"),
    ("SURFACE_CAMERA_ROTATE_RIGHT", "Camera Rotate Right", "Camera Rotate Right"),
    ("SURFACE_CAMERA_ROTATE_LEFT", "Camera Rotate Left", "Camera Rotate Left"),
    ("SURFACE_CAMERA_BOUNDARY", "Camera Boundary", "Camera Boundary"),
    ("SURFACE_NOISE_VERY_SLIPPERY_73", "Noise Very Slippery 73", "Noise Very Slippery 73"),
    ("SURFACE_NOISE_VERY_SLIPPERY_74", "Noise Very Slippery 74", "Noise Very Slippery 74"),
    ("SURFACE_NOISE_VERY_SLIPPERY", "Noise Very Slippery", "Noise Very Slippery"),
    ("SURFACE_NO_CAM_COLLISION", "No Cam Collision", "No Cam Collision"),
    ("SURFACE_NO_CAM_COLLISION_77", "No Cam Collision 77", "No Cam Collision 77"),
    ("SURFACE_NO_CAM_COL_VERY_SLIPPERY", "No Cam Collision Very Slippery", "No Cam Collision Very Slippery"),
    ("SURFACE_NO_CAM_COL_SLIPPERY", "No Cam Collision Slippery", "No Cam Collision Slippery"),
    ("SURFACE_SWITCH", "Switch", "Switch"),
    ("SURFACE_VANISH_CAP_WALLS", "Vanish Cap Walls", "Vanish Cap Walls"),
    ("SURFACE_PAINTING_WOBBLE_A6", "Painting Wobble A6", "Painting Wobble A6"),
    ("SURFACE_PAINTING_WOBBLE_A7", "Painting Wobble A7", "Painting Wobble A7"),
    ("SURFACE_PAINTING_WOBBLE_A8", "Painting Wobble A8", "Painting Wobble A8"),
    ("SURFACE_PAINTING_WOBBLE_A9", "Painting Wobble A9", "Painting Wobble A9"),
    ("SURFACE_PAINTING_WOBBLE_AA", "Painting Wobble AA", "Painting Wobble AA"),
    ("SURFACE_PAINTING_WOBBLE_AB", "Painting Wobble AB", "Painting Wobble AB"),
    ("SURFACE_PAINTING_WOBBLE_AC", "Painting Wobble AC", "Painting Wobble AC"),
    ("SURFACE_PAINTING_WOBBLE_AD", "Painting Wobble AD", "Painting Wobble AD"),
    ("SURFACE_PAINTING_WOBBLE_AE", "Painting Wobble AE", "Painting Wobble AE"),
    ("SURFACE_PAINTING_WOBBLE_AF", "Painting Wobble AF", "Painting Wobble AF"),
    ("SURFACE_PAINTING_WOBBLE_B0", "Painting Wobble B0", "Painting Wobble B0"),
    ("SURFACE_PAINTING_WOBBLE_B1", "Painting Wobble B1", "Painting Wobble B1"),
    ("SURFACE_PAINTING_WOBBLE_B2", "Painting Wobble B2", "Painting Wobble B2"),
    ("SURFACE_PAINTING_WOBBLE_B3", "Painting Wobble B3", "Painting Wobble B3"),
    ("SURFACE_PAINTING_WOBBLE_B4", "Painting Wobble B4", "Painting Wobble B4"),
    ("SURFACE_PAINTING_WOBBLE_B5", "Painting Wobble B5", "Painting Wobble B5"),
    ("SURFACE_PAINTING_WOBBLE_B6", "Painting Wobble B6", "Painting Wobble B6"),
    ("SURFACE_PAINTING_WOBBLE_B7", "Painting Wobble B7", "Painting Wobble B7"),
    ("SURFACE_PAINTING_WOBBLE_B8", "Painting Wobble B8", "Painting Wobble B8"),
    ("SURFACE_PAINTING_WOBBLE_B9", "Painting Wobble B9", "Painting Wobble B9"),
    ("SURFACE_PAINTING_WOBBLE_BA", "Painting Wobble BA", "Painting Wobble BA"),
    ("SURFACE_PAINTING_WOBBLE_BB", "Painting Wobble BB", "Painting Wobble BB"),
    ("SURFACE_PAINTING_WOBBLE_BC", "Painting Wobble BC", "Painting Wobble BC"),
    ("SURFACE_PAINTING_WOBBLE_BD", "Painting Wobble BD", "Painting Wobble BD"),
    ("SURFACE_PAINTING_WOBBLE_BE", "Painting Wobble BE", "Painting Wobble BE"),
    ("SURFACE_PAINTING_WOBBLE_BF", "Painting Wobble BF", "Painting Wobble BF"),
    ("SURFACE_PAINTING_WOBBLE_C0", "Painting Wobble C0", "Painting Wobble C0"),
    ("SURFACE_PAINTING_WOBBLE_C1", "Painting Wobble C1", "Painting Wobble C1"),
    ("SURFACE_PAINTING_WOBBLE_C2", "Painting Wobble C2", "Painting Wobble C2"),
    ("SURFACE_PAINTING_WOBBLE_C3", "Painting Wobble C3", "Painting Wobble C3"),
    ("SURFACE_PAINTING_WOBBLE_C4", "Painting Wobble C4", "Painting Wobble C4"),
    ("SURFACE_PAINTING_WOBBLE_C5", "Painting Wobble C5", "Painting Wobble C5"),
    ("SURFACE_PAINTING_WOBBLE_C6", "Painting Wobble C6", "Painting Wobble C6"),
    ("SURFACE_PAINTING_WOBBLE_C7", "Painting Wobble C7", "Painting Wobble C7"),
    ("SURFACE_PAINTING_WOBBLE_C8", "Painting Wobble C8", "Painting Wobble C8"),
    ("SURFACE_PAINTING_WOBBLE_C9", "Painting Wobble C9", "Painting Wobble C9"),
    ("SURFACE_PAINTING_WOBBLE_CA", "Painting Wobble CA", "Painting Wobble CA"),
    ("SURFACE_PAINTING_WOBBLE_CB", "Painting Wobble CB", "Painting Wobble CB"),
    ("SURFACE_PAINTING_WOBBLE_CC", "Painting Wobble CC", "Painting Wobble CC"),
    ("SURFACE_PAINTING_WOBBLE_CD", "Painting Wobble CD", "Painting Wobble CD"),
    ("SURFACE_PAINTING_WOBBLE_CE", "Painting Wobble CE", "Painting Wobble CE"),
    ("SURFACE_PAINTING_WOBBLE_CF", "Painting Wobble CF", "Painting Wobble CF"),
    ("SURFACE_PAINTING_WOBBLE_D0", "Painting Wobble D0", "Painting Wobble D0"),
    ("SURFACE_PAINTING_WOBBLE_D1", "Painting Wobble D1", "Painting Wobble D1"),
    ("SURFACE_PAINTING_WOBBLE_D2", "Painting Wobble D2", "Painting Wobble D2"),
    ("SURFACE_PAINTING_WARP_D3", "Painting Warp D3", "Painting Warp D3"),
    ("SURFACE_PAINTING_WARP_D4", "Painting Warp D4", "Painting Warp D4"),
    ("SURFACE_PAINTING_WARP_D5", "Painting Warp D5", "Painting Warp D5"),
    ("SURFACE_PAINTING_WARP_D6", "Painting Warp D6", "Painting Warp D6"),
    ("SURFACE_PAINTING_WARP_D7", "Painting Warp D7", "Painting Warp D7"),
    ("SURFACE_PAINTING_WARP_D8", "Painting Warp D8", "Painting Warp D8"),
    ("SURFACE_PAINTING_WARP_D9", "Painting Warp D9", "Painting Warp D9"),
    ("SURFACE_PAINTING_WARP_DA", "Painting Warp DA", "Painting Warp DA"),
    ("SURFACE_PAINTING_WARP_DB", "Painting Warp DB", "Painting Warp DB"),
    ("SURFACE_PAINTING_WARP_DC", "Painting Warp DC", "Painting Warp DC"),
    ("SURFACE_PAINTING_WARP_DD", "Painting Warp DD", "Painting Warp DD"),
    ("SURFACE_PAINTING_WARP_DE", "Painting Warp DE", "Painting Warp DE"),
    ("SURFACE_PAINTING_WARP_DF", "Painting Warp DF", "Painting Warp DF"),
    ("SURFACE_PAINTING_WARP_E0", "Painting Warp E0", "Painting Warp E0"),
    ("SURFACE_PAINTING_WARP_E1", "Painting Warp E1", "Painting Warp E1"),
    ("SURFACE_PAINTING_WARP_E2", "Painting Warp E2", "Painting Warp E2"),
    ("SURFACE_PAINTING_WARP_E3", "Painting Warp E3", "Painting Warp E3"),
    ("SURFACE_PAINTING_WARP_E4", "Painting Warp E4", "Painting Warp E4"),
    ("SURFACE_PAINTING_WARP_E5", "Painting Warp E5", "Painting Warp E5"),
    ("SURFACE_PAINTING_WARP_E6", "Painting Warp E6", "Painting Warp E6"),
    ("SURFACE_PAINTING_WARP_E7", "Painting Warp E7", "Painting Warp E7"),
    ("SURFACE_PAINTING_WARP_E8", "Painting Warp E8", "Painting Warp E8"),
    ("SURFACE_PAINTING_WARP_E9", "Painting Warp E9", "Painting Warp E9"),
    ("SURFACE_PAINTING_WARP_EA", "Painting Warp EA", "Painting Warp EA"),
    ("SURFACE_PAINTING_WARP_EB", "Painting Warp EB", "Painting Warp EB"),
    ("SURFACE_PAINTING_WARP_EC", "Painting Warp EC", "Painting Warp EC"),
    ("SURFACE_PAINTING_WARP_ED", "Painting Warp ED", "Painting Warp ED"),
    ("SURFACE_PAINTING_WARP_EE", "Painting Warp EE", "Painting Warp EE"),
    ("SURFACE_PAINTING_WARP_EF", "Painting Warp EF", "Painting Warp EF"),
    ("SURFACE_PAINTING_WARP_F0", "Painting Warp F0", "Painting Warp F0"),
    ("SURFACE_PAINTING_WARP_F1", "Painting Warp F1", "Painting Warp F1"),
    ("SURFACE_PAINTING_WARP_F2", "Painting Warp F2", "Painting Warp F2"),
    ("SURFACE_PAINTING_WARP_F3", "Painting Warp F3", "Painting Warp F3"),
    ("SURFACE_TTC_PAINTING_1", "TTC Painting 1", "TTC Painting 1"),
    ("SURFACE_TTC_PAINTING_2", "TTC Painting 2", "TTC Painting 2"),
    ("SURFACE_TTC_PAINTING_3", "TTC Painting 3", "TTC Painting 3"),
    ("SURFACE_PAINTING_WARP_F7", "Painting Warp F7", "Painting Warp F7"),
    ("SURFACE_PAINTING_WARP_F8", "Painting Warp F8", "Painting Warp F8"),
    ("SURFACE_PAINTING_WARP_F9", "Painting Warp F9", "Painting Warp F9"),
    ("SURFACE_PAINTING_WARP_FA", "Painting Warp FA", "Painting Warp FA"),
    ("SURFACE_PAINTING_WARP_FB", "Painting Warp FB", "Painting Warp FB"),
    ("SURFACE_PAINTING_WARP_FC", "Painting Warp FC", "Painting Warp FC"),
    ("SURFACE_WOBBLING_WARP", "Wobbling Warp", "Wobbling Warp"),
    ("SURFACE_TRAPDOOR", "Trapdoor", "Trapdoor"),
    ("Custom", "Custom", "Custom"),
]

enumPaintingCollisionType = [
    ("SURFACE_PAINTING_WOBBLE_A6", "Painting Wobble A6", "Painting Wobble A6"),
    ("SURFACE_PAINTING_WOBBLE_A7", "Painting Wobble A7", "Painting Wobble A7"),
    ("SURFACE_PAINTING_WOBBLE_A8", "Painting Wobble A8", "Painting Wobble A8"),
    ("SURFACE_PAINTING_WOBBLE_A9", "Painting Wobble A9", "Painting Wobble A9"),
    ("SURFACE_PAINTING_WOBBLE_AA", "Painting Wobble AA", "Painting Wobble AA"),
    ("SURFACE_PAINTING_WOBBLE_AB", "Painting Wobble AB", "Painting Wobble AB"),
    ("SURFACE_PAINTING_WOBBLE_AC", "Painting Wobble AC", "Painting Wobble AC"),
    ("SURFACE_PAINTING_WOBBLE_AD", "Painting Wobble AD", "Painting Wobble AD"),
    ("SURFACE_PAINTING_WOBBLE_AE", "Painting Wobble AE", "Painting Wobble AE"),
    ("SURFACE_PAINTING_WOBBLE_AF", "Painting Wobble AF", "Painting Wobble AF"),
    ("SURFACE_PAINTING_WOBBLE_B0", "Painting Wobble B0", "Painting Wobble B0"),
    ("SURFACE_PAINTING_WOBBLE_B1", "Painting Wobble B1", "Painting Wobble B1"),
    ("SURFACE_PAINTING_WOBBLE_B2", "Painting Wobble B2", "Painting Wobble B2"),
    ("SURFACE_PAINTING_WOBBLE_B3", "Painting Wobble B3", "Painting Wobble B3"),
    ("SURFACE_PAINTING_WOBBLE_B4", "Painting Wobble B4", "Painting Wobble B4"),
    ("SURFACE_PAINTING_WOBBLE_B5", "Painting Wobble B5", "Painting Wobble B5"),
    ("SURFACE_PAINTING_WOBBLE_B6", "Painting Wobble B6", "Painting Wobble B6"),
    ("SURFACE_PAINTING_WOBBLE_B7", "Painting Wobble B7", "Painting Wobble B7"),
    ("SURFACE_PAINTING_WOBBLE_B8", "Painting Wobble B8", "Painting Wobble B8"),
    ("SURFACE_PAINTING_WOBBLE_B9", "Painting Wobble B9", "Painting Wobble B9"),
    ("SURFACE_PAINTING_WOBBLE_BA", "Painting Wobble BA", "Painting Wobble BA"),
    ("SURFACE_PAINTING_WOBBLE_BB", "Painting Wobble BB", "Painting Wobble BB"),
    ("SURFACE_PAINTING_WOBBLE_BC", "Painting Wobble BC", "Painting Wobble BC"),
    ("SURFACE_PAINTING_WOBBLE_BD", "Painting Wobble BD", "Painting Wobble BD"),
    ("SURFACE_PAINTING_WOBBLE_BE", "Painting Wobble BE", "Painting Wobble BE"),
    ("SURFACE_PAINTING_WOBBLE_BF", "Painting Wobble BF", "Painting Wobble BF"),
    ("SURFACE_PAINTING_WOBBLE_C0", "Painting Wobble C0", "Painting Wobble C0"),
    ("SURFACE_PAINTING_WOBBLE_C1", "Painting Wobble C1", "Painting Wobble C1"),
    ("SURFACE_PAINTING_WOBBLE_C2", "Painting Wobble C2", "Painting Wobble C2"),
    ("SURFACE_PAINTING_WOBBLE_C3", "Painting Wobble C3", "Painting Wobble C3"),
    ("SURFACE_PAINTING_WOBBLE_C4", "Painting Wobble C4", "Painting Wobble C4"),
    ("SURFACE_PAINTING_WOBBLE_C5", "Painting Wobble C5", "Painting Wobble C5"),
    ("SURFACE_PAINTING_WOBBLE_C6", "Painting Wobble C6", "Painting Wobble C6"),
    ("SURFACE_PAINTING_WOBBLE_C7", "Painting Wobble C7", "Painting Wobble C7"),
    ("SURFACE_PAINTING_WOBBLE_C8", "Painting Wobble C8", "Painting Wobble C8"),
    ("SURFACE_PAINTING_WOBBLE_C9", "Painting Wobble C9", "Painting Wobble C9"),
    ("SURFACE_PAINTING_WOBBLE_CA", "Painting Wobble CA", "Painting Wobble CA"),
    ("SURFACE_PAINTING_WOBBLE_CB", "Painting Wobble CB", "Painting Wobble CB"),
    ("SURFACE_PAINTING_WOBBLE_CC", "Painting Wobble CC", "Painting Wobble CC"),
    ("SURFACE_PAINTING_WOBBLE_CD", "Painting Wobble CD", "Painting Wobble CD"),
    ("SURFACE_PAINTING_WOBBLE_CE", "Painting Wobble CE", "Painting Wobble CE"),
    ("SURFACE_PAINTING_WOBBLE_CF", "Painting Wobble CF", "Painting Wobble CF"),
    ("SURFACE_PAINTING_WOBBLE_D0", "Painting Wobble D0", "Painting Wobble D0"),
    ("SURFACE_PAINTING_WOBBLE_D1", "Painting Wobble D1", "Painting Wobble D1"),
    ("SURFACE_PAINTING_WOBBLE_D2", "Painting Wobble D2", "Painting Wobble D2"),
    ("SURFACE_PAINTING_WARP_D3", "Painting Warp D3", "Painting Warp D3"),
    ("SURFACE_PAINTING_WARP_D4", "Painting Warp D4", "Painting Warp D4"),
    ("SURFACE_PAINTING_WARP_D5", "Painting Warp D5", "Painting Warp D5"),
    ("SURFACE_PAINTING_WARP_D6", "Painting Warp D6", "Painting Warp D6"),
    ("SURFACE_PAINTING_WARP_D7", "Painting Warp D7", "Painting Warp D7"),
    ("SURFACE_PAINTING_WARP_D8", "Painting Warp D8", "Painting Warp D8"),
    ("SURFACE_PAINTING_WARP_D9", "Painting Warp D9", "Painting Warp D9"),
    ("SURFACE_PAINTING_WARP_DA", "Painting Warp DA", "Painting Warp DA"),
    ("SURFACE_PAINTING_WARP_DB", "Painting Warp DB", "Painting Warp DB"),
    ("SURFACE_PAINTING_WARP_DC", "Painting Warp DC", "Painting Warp DC"),
    ("SURFACE_PAINTING_WARP_DD", "Painting Warp DD", "Painting Warp DD"),
    ("SURFACE_PAINTING_WARP_DE", "Painting Warp DE", "Painting Warp DE"),
    ("SURFACE_PAINTING_WARP_DF", "Painting Warp DF", "Painting Warp DF"),
    ("SURFACE_PAINTING_WARP_E0", "Painting Warp E0", "Painting Warp E0"),
    ("SURFACE_PAINTING_WARP_E1", "Painting Warp E1", "Painting Warp E1"),
    ("SURFACE_PAINTING_WARP_E2", "Painting Warp E2", "Painting Warp E2"),
    ("SURFACE_PAINTING_WARP_E3", "Painting Warp E3", "Painting Warp E3"),
    ("SURFACE_PAINTING_WARP_E4", "Painting Warp E4", "Painting Warp E4"),
    ("SURFACE_PAINTING_WARP_E5", "Painting Warp E5", "Painting Warp E5"),
    ("SURFACE_PAINTING_WARP_E6", "Painting Warp E6", "Painting Warp E6"),
    ("SURFACE_PAINTING_WARP_E7", "Painting Warp E7", "Painting Warp E7"),
    ("SURFACE_PAINTING_WARP_E8", "Painting Warp E8", "Painting Warp E8"),
    ("SURFACE_PAINTING_WARP_E9", "Painting Warp E9", "Painting Warp E9"),
    ("SURFACE_PAINTING_WARP_EA", "Painting Warp EA", "Painting Warp EA"),
    ("SURFACE_PAINTING_WARP_EB", "Painting Warp EB", "Painting Warp EB"),
    ("SURFACE_PAINTING_WARP_EC", "Painting Warp EC", "Painting Warp EC"),
    ("SURFACE_PAINTING_WARP_ED", "Painting Warp ED", "Painting Warp ED"),
    ("SURFACE_PAINTING_WARP_EE", "Painting Warp EE", "Painting Warp EE"),
    ("SURFACE_PAINTING_WARP_EF", "Painting Warp EF", "Painting Warp EF"),
    ("SURFACE_PAINTING_WARP_F0", "Painting Warp F0", "Painting Warp F0"),
    ("SURFACE_PAINTING_WARP_F1", "Painting Warp F1", "Painting Warp F1"),
    ("SURFACE_PAINTING_WARP_F2", "Painting Warp F2", "Painting Warp F2"),
    ("SURFACE_PAINTING_WARP_F3", "Painting Warp F3", "Painting Warp F3"),
    ("SURFACE_TTC_PAINTING_1", "TTC Painting 1", "TTC Painting 1"),
    ("SURFACE_TTC_PAINTING_2", "TTC Painting 2", "TTC Painting 2"),
    ("SURFACE_TTC_PAINTING_3", "TTC Painting 3", "TTC Painting 3"),
    ("SURFACE_PAINTING_WARP_F7", "Painting Warp F7", "Painting Warp F7"),
    ("SURFACE_PAINTING_WARP_F8", "Painting Warp F8", "Painting Warp F8"),
    ("SURFACE_PAINTING_WARP_F9", "Painting Warp F9", "Painting Warp F9"),
    ("SURFACE_PAINTING_WARP_FA", "Painting Warp FA", "Painting Warp FA"),
    ("SURFACE_PAINTING_WARP_FB", "Painting Warp FB", "Painting Warp FB"),
    ("SURFACE_PAINTING_WARP_FC", "Painting Warp FC", "Painting Warp FC"),
]

enumUnusedCollisionType = [
    ("SURFACE_0004", "0004", "0004"),
]
