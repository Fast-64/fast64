import bpy
import mathutils
import math
from .utility import *


def on_update_sm64_render_settings(self, context: bpy.types.Context):
    renderSettings: "Fast64RenderSettings_Properties" = context.scene.fast64.renderSettings
    if renderSettings.sm64Area and renderSettings.useObjectRenderPreview:
        area: bpy.types.Object = renderSettings.sm64Area
        renderSettings.fogPreviewColor = tuple(c for c in area.area_fog_color)
        renderSettings.fogPreviewPosition = tuple(round(p) for p in area.area_fog_position)
        renderSettings.clippingPlanes = tuple(float(p) for p in area.clipPlanes)


def on_update_oot_render_settings(self, context: bpy.types.Context):
    renderSettings: "Fast64RenderSettings_Properties" = context.scene.fast64.renderSettings
    if renderSettings.ootSceneObject is None or not renderSettings.useObjectRenderPreview:
        return
    header = ootGetSceneOrRoomHeader(
        renderSettings.ootSceneObject,
        renderSettings.ootSceneHeader,
        False,
    )
    if header is None:
        return
    lMode = header.skyboxLighting
    if lMode == "LIGHT_MODE_SETTINGS" or (lMode == "Custom" and not renderSettings.ootForceTimeOfDay):
        if renderSettings.ootLightIdx >= len(header.lightList):
            return
        l = header.lightList[renderSettings.ootLightIdx]
        renderSettings.ambientColor = tuple(c for c in l.ambient)
        col0, dir0 = ootGetBaseOrCustomLight(l, 0, False, False)
        renderSettings.light0Color = tuple(c for c in col0)
        renderSettings.light0Direction = tuple(d for d in dir0)
        col1, dir1 = ootGetBaseOrCustomLight(l, 1, False, False)
        renderSettings.light1Color = tuple(c for c in col1)
        renderSettings.light1Direction = tuple(d for d in dir1)
        renderSettings.fogPreviewColor = tuple(c for c in l.fogColor)
        renderSettings.fogPreviewPosition = (l.fogNear, 1000)  # fogFar is always 1000 in OoT
        renderSettings.clippingPlanes = (10.0, l.z_far)  # zNear seems to always be 10 in OoT
    else:
        if lMode == "LIGHT_MODE_TIME":
            tod = header.timeOfDayLights
            lights = [tod.dawn, tod.day, tod.dusk, tod.night]
        else:
            if renderSettings.ootLightIdx + 4 > len(header.lightList):
                return
            lights = header.lightList[renderSettings.ootLightIdx : renderSettings.ootLightIdx + 4]
        assert len(lights) == 4
        todTimes = [0.0, 4.0, 6.0, 8.0, 16.0, 17.0, 19.0, 24.0]
        todSets = [3, 3, 0, 1, 1, 2, 3, 3]
        t = renderSettings.ootTime
        for i in range(len(todTimes) - 1):
            assert t >= todTimes[i]
            if t < todTimes[i + 1]:
                la, lb = lights[todSets[i]], lights[todSets[i + 1]]
                fade = (t - todTimes[i]) / (todTimes[i + 1] - todTimes[i])
                break
        else:
            raise PluginError("OoT time of day out of range")

        def interpColors(cola, colb, fade):
            cola = mathutils.Vector(tuple(c for c in cola))
            colb = mathutils.Vector(tuple(c for c in colb))
            return cola + (colb - cola) * fade

        renderSettings.ambientColor = interpColors(la.ambient, lb.ambient, fade)
        col0a, _ = ootGetBaseOrCustomLight(la, 0, False, False)
        col0b, _ = ootGetBaseOrCustomLight(lb, 0, False, False)
        renderSettings.light0Color = col0a + (col0b - col0a) * fade
        col1a, _ = ootGetBaseOrCustomLight(la, 1, False, False)
        col1b, _ = ootGetBaseOrCustomLight(lb, 1, False, False)
        renderSettings.light1Color = col1a + (col1b - col1a) * fade
        sint, cost = math.sin(math.tau * t / 24.0), math.cos(math.tau * t / 24.0)
        renderSettings.light0Direction = mathutils.Vector(
            (
                sint * 120.0 / 127.0,
                cost * 20.0 / 127.0,
                -cost * 120.0 / 127.0,
            )
        ).normalized()
        renderSettings.light1Direction = -renderSettings.light0Direction
        renderSettings.fogPreviewColor = interpColors(la.fogColor, lb.fogColor, fade)
        renderSettings.fogPreviewPosition = (  # fogFar is always 1000 in OoT
            la.fogNear + int(float(lb.fogNear - la.fogNear) * fade),
            1000,
        )
        renderSettings.clippingPlanes = (  # zNear seems to always be 10 in OoT
            10.0,
            la.z_far + float(lb.z_far - la.z_far) * fade,
        )


def update_scene_props_from_rs_enableFogPreview(
    sceneOutputs: bpy.types.NodeGroupOutput, renderSettings: "Fast64RenderSettings_Properties"
):
    sceneOutputs.inputs["FogEnable"].default_value = int(renderSettings.enableFogPreview)


def update_scene_props_from_rs_fogPreviewColor(
    sceneOutputs: bpy.types.NodeGroupOutput, renderSettings: "Fast64RenderSettings_Properties"
):
    sceneOutputs.inputs["FogColor"].default_value = s_rgb_alpha_1_tuple(renderSettings.fogPreviewColor)


def update_scene_props_from_rs_clippingPlanes(
    sceneOutputs: bpy.types.NodeGroupOutput, renderSettings: "Fast64RenderSettings_Properties"
):
    sceneOutputs.inputs["F3D_NearClip"].default_value = float(renderSettings.clippingPlanes[0])
    sceneOutputs.inputs["F3D_FarClip"].default_value = float(renderSettings.clippingPlanes[1])


def update_scene_props_from_rs_fogPreviewPosition(
    sceneOutputs: bpy.types.NodeGroupOutput, renderSettings: "Fast64RenderSettings_Properties"
):
    sceneOutputs.inputs["FogNear"].default_value = renderSettings.fogPreviewPosition[0]
    sceneOutputs.inputs["FogFar"].default_value = renderSettings.fogPreviewPosition[1]


def update_scene_props_from_rs_ambientColor(
    sceneOutputs: bpy.types.NodeGroupOutput, renderSettings: "Fast64RenderSettings_Properties"
):
    sceneOutputs.inputs["AmbientColor"].default_value = s_rgb_alpha_1_tuple(renderSettings.ambientColor)


def update_scene_props_from_rs_light0Color(
    sceneOutputs: bpy.types.NodeGroupOutput, renderSettings: "Fast64RenderSettings_Properties"
):
    sceneOutputs.inputs["Light0Color"].default_value = s_rgb_alpha_1_tuple(renderSettings.light0Color)


def update_scene_props_from_rs_light0Direction(
    sceneOutputs: bpy.types.NodeGroupOutput, renderSettings: "Fast64RenderSettings_Properties"
):
    sceneOutputs.inputs["Light0Dir"].default_value = renderSettings.light0Direction


def update_scene_props_from_rs_light0SpecSize(
    sceneOutputs: bpy.types.NodeGroupOutput, renderSettings: "Fast64RenderSettings_Properties"
):
    sceneOutputs.inputs["Light0Size"].default_value = renderSettings.light0SpecSize


def update_scene_props_from_rs_light1Color(
    sceneOutputs: bpy.types.NodeGroupOutput, renderSettings: "Fast64RenderSettings_Properties"
):
    sceneOutputs.inputs["Light1Color"].default_value = s_rgb_alpha_1_tuple(renderSettings.light1Color)


def update_scene_props_from_rs_light1Direction(
    sceneOutputs: bpy.types.NodeGroupOutput, renderSettings: "Fast64RenderSettings_Properties"
):
    sceneOutputs.inputs["Light1Dir"].default_value = renderSettings.light1Direction


def update_scene_props_from_rs_light1SpecSize(
    sceneOutputs: bpy.types.NodeGroupOutput, renderSettings: "Fast64RenderSettings_Properties"
):
    sceneOutputs.inputs["Light1Size"].default_value = renderSettings.light1SpecSize


def update_scene_props_from_rs_useWorldSpaceLighting(renderSettings: "Fast64RenderSettings_Properties"):
    bpy.data.node_groups["GetSpecularNormal"].nodes["GeometryNormal"].node_tree = bpy.data.node_groups[
        "GeometryNormal_WorldSpace" if renderSettings.useWorldSpaceLighting else "GeometryNormal_ViewSpace"
    ]


def update_scene_props_from_render_settings(
    sceneOutputs: bpy.types.NodeGroupOutput,
    renderSettings: "Fast64RenderSettings_Properties",
):
    update_scene_props_from_rs_enableFogPreview(sceneOutputs, renderSettings)
    update_scene_props_from_rs_fogPreviewColor(sceneOutputs, renderSettings)
    update_scene_props_from_rs_clippingPlanes(sceneOutputs, renderSettings)
    update_scene_props_from_rs_fogPreviewPosition(sceneOutputs, renderSettings)
    update_scene_props_from_rs_ambientColor(sceneOutputs, renderSettings)
    update_scene_props_from_rs_light0Color(sceneOutputs, renderSettings)
    update_scene_props_from_rs_light0Direction(sceneOutputs, renderSettings)
    update_scene_props_from_rs_light0SpecSize(sceneOutputs, renderSettings)
    update_scene_props_from_rs_light1Color(sceneOutputs, renderSettings)
    update_scene_props_from_rs_light1Direction(sceneOutputs, renderSettings)
    update_scene_props_from_rs_light1SpecSize(sceneOutputs, renderSettings)
    update_scene_props_from_rs_useWorldSpaceLighting(renderSettings)

    # TODO use a callback on the scale props to set this value
    sceneOutputs.inputs["Blender_Game_Scale"].default_value = float(get_blender_to_game_scale(bpy.context))


def getSceneOutputs():
    sceneProps = bpy.data.node_groups.get("SceneProperties")
    if sceneProps == None:
        print("Could not locate SceneProperties!")
        return None

    sceneOutputs: bpy.types.NodeGroupOutput = sceneProps.nodes["Group Output"]
    return sceneOutputs


class ManualUpdatePreviewOperator(bpy.types.Operator):
    bl_idname = "view3d.fast64_manual_update_preview"
    bl_label = "Update Preview"
    bl_description = "Apply the F3D Render Settings to the view"

    def execute(self, context):
        sceneOutputs = getSceneOutputs()
        renderSettings = bpy.context.scene.fast64.renderSettings

        if sceneOutputs is None:
            return {"CANCELLED"}

        update_scene_props_from_render_settings(sceneOutputs, renderSettings)
        return {"FINISHED"}


def make_callback(update_scene_props_from_rs_func):
    def on_update_rs_func(self: "Fast64RenderSettings_Properties", context):
        if not self.enableAutoUpdatePreview:
            return
        sceneOutputs = getSceneOutputs()
        if sceneOutputs is not None:
            update_scene_props_from_rs_func(sceneOutputs, self)

    return on_update_rs_func


# These are all the callbacks that modify values in the scene properties node group
# Since modifying node values turns out to be very slow,
# we need one callback per prop in order to update the specific associated value.
on_update_rs_enableFogPreview = make_callback(update_scene_props_from_rs_enableFogPreview)
on_update_rs_fogPreviewColor = make_callback(update_scene_props_from_rs_fogPreviewColor)
on_update_rs_clippingPlanes = make_callback(update_scene_props_from_rs_clippingPlanes)
on_update_rs_fogPreviewPosition = make_callback(update_scene_props_from_rs_fogPreviewPosition)
on_update_rs_ambientColor = make_callback(update_scene_props_from_rs_ambientColor)
on_update_rs_light0Color = make_callback(update_scene_props_from_rs_light0Color)
on_update_rs_light0Direction = make_callback(update_scene_props_from_rs_light0Direction)
on_update_rs_light0SpecSize = make_callback(update_scene_props_from_rs_light0SpecSize)
on_update_rs_light1Color = make_callback(update_scene_props_from_rs_light1Color)
on_update_rs_light1Direction = make_callback(update_scene_props_from_rs_light1Direction)
on_update_rs_light1SpecSize = make_callback(update_scene_props_from_rs_light1SpecSize)
on_update_rs_useWorldSpaceLighting = make_callback(update_scene_props_from_rs_useWorldSpaceLighting)

del make_callback


def on_update_render_settings(self, context: bpy.types.Context):
    sceneProps = bpy.data.node_groups.get("SceneProperties")
    if sceneProps == None:
        print("Could not locate sceneProps!")
        return

    match context.scene.gameEditorMode:
        case "SM64":
            on_update_sm64_render_settings(self, context)
        case "OOT":
            on_update_oot_render_settings(self, context)
        case _:
            pass

    sceneOutputs = getSceneOutputs()
    if sceneOutputs is not None:
        update_scene_props_from_render_settings(sceneOutputs, self)


def poll_sm64_area(self, object):
    return object.sm64_obj_type == "Area Root"


def poll_oot_scene(self, object):
    return object.ootEmptyType == "Scene"


def resync_scene_props():
    if "GetSpecularNormal" in bpy.data.node_groups:
        # Lighting space needs to be updated due to the nodes being shared and reloaded
        update_scene_props_from_rs_useWorldSpaceLighting(bpy.context.scene.fast64.renderSettings)


def on_update_render_settings_enableAutoUpdatePreview(self, context):
    # Update on enabling but not disabling
    if self.enableAutoUpdatePreview:
        on_update_render_settings(self, context)


class Fast64RenderSettings_Properties(bpy.types.PropertyGroup):
    enableAutoUpdatePreview: bpy.props.BoolProperty(
        name="Auto Update Preview",
        description="If enabled, the view will update automatically when changing render settings",
        default=True,
        update=on_update_render_settings_enableAutoUpdatePreview,
    )
    enableFogPreview: bpy.props.BoolProperty(
        name="Enable Fog Preview",
        default=True,
        update=on_update_render_settings,
    )
    fogPreviewColor: bpy.props.FloatVectorProperty(
        name="Fog Color",
        subtype="COLOR",
        size=4,
        min=0,
        max=1,
        default=(1, 1, 1, 1),
        update=on_update_rs_fogPreviewColor,
    )
    ambientColor: bpy.props.FloatVectorProperty(
        name="Ambient Light",
        subtype="COLOR",
        size=4,
        min=0,
        max=1,
        default=(0.5, 0.5, 0.5, 1),
        update=on_update_rs_ambientColor,
    )
    light0Color: bpy.props.FloatVectorProperty(
        name="Light 0 Color",
        subtype="COLOR",
        size=4,
        min=0,
        max=1,
        default=(1, 1, 1, 1),
        update=on_update_rs_light0Color,
    )
    light0Direction: bpy.props.FloatVectorProperty(
        name="Light 0 Direction",
        subtype="DIRECTION",
        size=3,
        min=-1,
        max=1,
        default=mathutils.Vector((1.0, -1.0, 1.0)).normalized(),  # pre normalized
        update=on_update_rs_light0Direction,
    )
    light0SpecSize: bpy.props.IntProperty(
        name="Light 0 Specular Size",
        min=1,
        max=255,
        default=3,
        update=on_update_rs_light0SpecSize,
    )
    light1Color: bpy.props.FloatVectorProperty(
        name="Light 1 Color",
        subtype="COLOR",
        size=4,
        min=0,
        max=1,
        default=(0, 0, 0, 1),
        update=on_update_rs_light1Color,
    )
    light1Direction: bpy.props.FloatVectorProperty(
        name="Light 1 Direction",
        subtype="DIRECTION",
        size=3,
        min=-1,
        max=1,
        default=mathutils.Vector((-1.0, 1.0, -1.0)).normalized(),  # pre normalized
        update=on_update_rs_light1Direction,
    )
    light1SpecSize: bpy.props.IntProperty(
        name="Light 1 Specular Size",
        min=1,
        max=255,
        default=3,
        update=on_update_rs_light1SpecSize,
    )
    useWorldSpaceLighting: bpy.props.BoolProperty(
        name="Use World Space Lighting",
        default=True,
        update=on_update_render_settings,
    )
    # Fog Preview is int because values reflect F3D values
    fogPreviewPosition: bpy.props.IntVectorProperty(
        name="Fog Position",
        size=2,
        min=0,
        max=1000,
        default=(985, 1000),
        update=on_update_rs_fogPreviewPosition,
    )
    # Clipping planes are float because values reflect F3D values
    clippingPlanes: bpy.props.FloatVectorProperty(
        name="Clipping Planes",
        size=2,
        min=0,
        default=(100, 30000),
        update=on_update_rs_clippingPlanes,
    )
    useObjectRenderPreview: bpy.props.BoolProperty(
        name="Use Object Preview",
        default=True,
        update=on_update_render_settings,
    )
    # SM64
    sm64Area: bpy.props.PointerProperty(
        name="Area Object",
        type=bpy.types.Object,
        update=on_update_sm64_render_settings,
        poll=poll_sm64_area,
    )
    # OOT
    ootSceneObject: bpy.props.PointerProperty(
        name="Scene Object",
        type=bpy.types.Object,
        update=on_update_oot_render_settings,
        poll=poll_oot_scene,
    )
    ootSceneHeader: bpy.props.IntProperty(
        name="Header/Setup",
        description="Scene header / setup to use lighting data from",
        min=0,
        soft_max=10,
        default=0,
        update=on_update_oot_render_settings,
    )
    ootForceTimeOfDay: bpy.props.BoolProperty(
        name="Force Time of Day",
        description="Interpolate between four lights based on the time",
        default=False,
        update=on_update_oot_render_settings,
    )
    ootLightIdx: bpy.props.IntProperty(
        name="Light Index",
        min=0,
        soft_max=10,
        default=0,
        update=on_update_oot_render_settings,
    )
    ootTime: bpy.props.FloatProperty(
        name="Time of Day (Hours)",
        description="Time of day to emulate lighting conditions at, in hours",
        min=0.0,
        max=23.99,
        default=10.0,
        precision=2,
        subtype="TIME",
        unit="TIME",
        update=on_update_oot_render_settings,
    )
