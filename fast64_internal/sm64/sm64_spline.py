import bpy
from bpy.utils import register_class, unregister_class
from ..utility import PluginError, CData, toAlnum, prop_split


enumSplineTypes = [
    ("Trajectory", "Trajectory", "Exports to Trajectory[]. Used for movement"),
    ("Cutscene", "Cutscene", "Exports to CutsceneSplinePoint[]. Used for cutscenes"),
    ("Vector", "Vector", "Exports to Vec4s[]. Used for the jumbo star keyframes"),
]


class SM64Spline:
    def __init__(self, name, splineType):
        self.name = toAlnum(name)
        self.splineType = splineType
        self.points = []
        self.speeds = []

    def to_c(self):
        data = CData()
        if self.splineType == "Trajectory":
            data.header = "extern const Trajectory " + self.name + "[];\n"
            data.source += "const Trajectory " + self.name + "[] = {\n"
            for index in range(len(self.points)):
                point = self.points[index]
                data.source += (
                    "\tTRAJECTORY_POS( "
                    + str(index)
                    + ", "
                    + str(int(round(point[0])))
                    + ", "
                    + str(int(round(point[1])))
                    + ", "
                    + str(int(round(point[2])))
                    + "),\n"
                )
            data.source += "\tTRAJECTORY_END(),\n};\n"
            return data
        elif self.splineType == "Cutscene":
            data.header = "extern struct CutsceneSplinePoint " + self.name + "[];\n"
            data.source += "struct CutsceneSplinePoint " + self.name + "[] = {\n"
            for index in range(len(self.points)):
                point = self.points[index]
                if index == len(self.points) - 1:
                    splineIndex = -1  # last keyframe
                else:
                    splineIndex = index
                data.source += (
                    "\t{ "
                    + str(splineIndex)
                    + ", "
                    + str(int(round(self.speeds[index])))
                    + ", { "
                    + str(int(round(point[0])))
                    + ", "
                    + str(int(round(point[1])))
                    + ", "
                    + str(int(round(point[2])))
                    + " }},\n"
                )
            data.source += "};\n"
            return data
        elif self.splineType == "Vector":
            data.header = "extern const Vec4s " + self.name + "[];\n"
            data.source += "const Vec4s " + self.name + "[] = {\n"
            for index in range(len(self.points)):
                point = self.points[index]
                if index >= len(self.points) - 3:
                    speed = 0  # last 3 points of spline
                else:
                    speed = self.speeds[index]
                data.source += (
                    "\t{ "
                    + str(int(round(speed)))
                    + ", "
                    + str(int(round(point[0])))
                    + ", "
                    + str(int(round(point[1])))
                    + ", "
                    + str(int(round(point[2])))
                    + " },\n"
                )
            data.source += "};\n"
            return data
        else:
            raise PluginError("Invalid SM64 spline type: " + self.splineType)


def convertSplineObject(name, obj, transform):
    sm64_spline = SM64Spline(name, obj.data.sm64_spline_type)

    spline = obj.data.splines[0]
    for point in spline.points:
        position = transform @ point.co
        sm64_spline.points.append(position)
        sm64_spline.speeds.append(int(round(point.radius)))

    return sm64_spline


def onSplineTypeSet(self, context):
    if self.sm64_spline_type == "Trajectory":
        self.splines.active.order_u = 1
    else:
        self.splines.active.order_u = 4


class SM64_ExportSpline(bpy.types.Operator):
    bl_idname = "object.sm64_export_spline"
    bl_label = "Export Spline"
    bl_options = {"REGISTER", "UNDO"}

    def execute(self, context):
        context.object.sm64_special_enum = self.sm64_special_enum
        bpy.context.region.tag_redraw()
        self.report({"INFO"}, "Selected: " + self.sm64_special_enum)
        return {"FINISHED"}


class SM64SplinePanel(bpy.types.Panel):
    bl_label = "Spline Inspector"
    bl_idname = "OBJECT_PT_SM64_Spline_Inspector"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_context = "object"
    bl_options = {"HIDE_HEADER"}

    @classmethod
    def poll(cls, context):
        return context.scene.gameEditorMode == "SM64" and (
            context.object is not None and type(context.object.data) == bpy.types.Curve
        )

    def draw(self, context):
        box = self.layout.box()
        box.box().label(text="SM64 Spline Inspector")
        curve = context.object.data
        if curve.splines[0].type != "NURBS":
            box.label(text="Only NURBS curves are compatible.")
        else:
            prop_split(box, curve, "sm64_spline_type", "Spline Type")
            if curve.sm64_spline_type == "Cutscene" or curve.sm64_spline_type == "Vector":
                pointIndex = 0
                for point in curve.splines.active.points:
                    if point.select:
                        prop_split(box.box(), point, "radius", "Point " + str(pointIndex) + " Speed")
                    pointIndex += 1


def assertCurveValid(obj):
    curve = obj.data
    if not isinstance(curve, bpy.types.Curve) or curve.splines[0].type != "NURBS":
        # Curve was likely not intended to be exported
        return False
    if len(curve.splines) != 1:
        # Curve was intended to be exported but has multiple disconnected segments
        raise PluginError("Exported curves should have only one single segment, found " + str(len(curve.splines)))
    return True


sm64_spline_classes = (SM64_ExportSpline,)


sm64_spline_panel_classes = (SM64SplinePanel,)


def sm64_spline_panel_register():
    for cls in sm64_spline_panel_classes:
        register_class(cls)


def sm64_spline_panel_unregister():
    for cls in sm64_spline_panel_classes:
        unregister_class(cls)


def sm64_spline_register():
    for cls in sm64_spline_classes:
        register_class(cls)

    bpy.types.Curve.sm64_spline_type = bpy.props.EnumProperty(
        name="Type", items=enumSplineTypes, update=onSplineTypeSet
    )


def sm64_spline_unregister():
    del bpy.types.Curve.sm64_spline_type

    for cls in reversed(sm64_spline_classes):
        unregister_class(cls)
