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
    if lMode == "0x01" or (lMode == "Custom" and not renderSettings.ootForceTimeOfDay):
        if renderSettings.ootLightIdx >= len(header.lightList):
            return
        l = header.lightList[renderSettings.ootLightIdx]
        renderSettings.ambientColor = tuple(c for c in l.ambient)
        col0, dir0 = ootGetBaseOrCustomLight(l, 0, False, False)
        renderSettings.lightColor = tuple(c for c in col0)
        renderSettings.lightDirection = tuple(d for d in dir0)
        # TODO: Implement light1 into shader nodes
        # col1, dir1 = ootGetBaseOrCustomLight(l, 1, False, False)
        # renderSettings.light1Color = tuple(c for c in col1)
        # renderSettings.light1Direction = tuple(d for d in dir1)
        renderSettings.fogPreviewColor = tuple(c for c in l.fogColor)
        renderSettings.fogPreviewPosition = (l.fogNear, l.fogFar)
    else:
        if header.skyboxLighting == "0x00":
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
        renderSettings.lightColor = col0a + (col0b - col0a) * fade
        # TODO: Implement light1 into shader nodes
        # col1a, _ = ootGetBaseOrCustomLight(la, 1, False, False)
        # col1b, _ = ootGetBaseOrCustomLight(lb, 1, False, False)
        # renderSettings.light1Color = col1a * fa + col1b * fb
        sint, cost = math.sin(math.tau * t / 24.0), math.cos(math.tau * t / 24.0)
        renderSettings.lightDirection = mathutils.Vector(
            (
                sint * 120.0 / 127.0,
                -cost * 120.0 / 127.0,
                -cost * 20.0 / 127.0,
            )
        ).normalized()
        # TODO: Implement light1 into shader nodes
        # renderSettings.light1Direction = -renderSettings.lightDirection
        renderSettings.fogColor = interpColors(la.fogColor, lb.fogColor, fade)
        renderSettings.fogPreviewPosition = (
            la.fogNear + int(float(lb.fogNear - la.fogNear) * fade),
            la.fogFar + int(float(lb.fogFar - la.fogFar) * fade),
        )


def update_lighting_space(renderSettings: "Fast64RenderSettings_Properties"):
    if renderSettings.useWorldSpaceLighting:
        bpy.data.node_groups["ShdCol_L"].nodes["GeometryNormal"].node_tree = bpy.data.node_groups[
            "GeometryNormal_WorldSpace"
        ]
    else:
        bpy.data.node_groups["ShdCol_L"].nodes["GeometryNormal"].node_tree = bpy.data.node_groups[
            "GeometryNormal_ViewSpace"
        ]


def update_scene_props_from_render_settings(
    context: bpy.types.Context,
    sceneOutputs: bpy.types.NodeGroupOutput,
    renderSettings: "Fast64RenderSettings_Properties",
):
    enableFog = int(renderSettings.enableFogPreview)
    sceneOutputs.inputs["FogEnable"].default_value = enableFog

    sceneOutputs.inputs["FogColor"].default_value = tuple(c for c in renderSettings.fogPreviewColor)
    sceneOutputs.inputs["FogNear"].default_value = renderSettings.fogPreviewPosition[0]
    sceneOutputs.inputs["FogFar"].default_value = renderSettings.fogPreviewPosition[1]

    sceneOutputs.inputs["F3D_NearClip"].default_value = float(renderSettings.clippingPlanes[0])
    sceneOutputs.inputs["F3D_FarClip"].default_value = float(renderSettings.clippingPlanes[1])

    sceneOutputs.inputs["ShadeColor"].default_value = tuple(c for c in renderSettings.lightColor)
    sceneOutputs.inputs["AmbientColor"].default_value = tuple(c for c in renderSettings.ambientColor)
    sceneOutputs.inputs["LightDirection"].default_value = tuple(
        d for d in (mathutils.Vector(renderSettings.lightDirection) @ transform_mtx_blender_to_n64())
    )

    update_lighting_space(renderSettings)

    sceneOutputs.inputs["Blender_Game_Scale"].default_value = float(get_blender_to_game_scale(context))


def on_update_render_preview_nodes(self, context: bpy.types.Context):
    sceneProps = bpy.data.node_groups.get("SceneProperties")
    if sceneProps == None:
        print("Could not locate SceneProperties!")
        return

    sceneOutputs: bpy.types.NodeGroupOutput = sceneProps.nodes["Group Output"]
    renderSettings: "Fast64RenderSettings_Properties" = context.scene.fast64.renderSettings
    update_scene_props_from_render_settings(context, sceneOutputs, renderSettings)


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

    on_update_render_preview_nodes(self, context)


def poll_sm64_area(self, object):
    return object.sm64_obj_type == "Area Root"


def poll_oot_scene(self, object):
    return object.ootEmptyType == "Scene"


def resync_scene_props():
    if "ShdCol_L" in bpy.data.node_groups and "GeometryNormal_WorldSpace" in bpy.data.node_groups:
        renderSettings: "Fast64RenderSettings_Properties" = bpy.context.scene.fast64.renderSettings
        # Lighting space needs to be updated due to the nodes being shared and reloaded
        update_lighting_space(renderSettings)


class Fast64RenderSettings_Properties(bpy.types.PropertyGroup):
    enableFogPreview: bpy.props.BoolProperty(name="Enable Fog Preview", default=True, update=on_update_render_settings)
    fogPreviewColor: bpy.props.FloatVectorProperty(
        name="Fog Color",
        subtype="COLOR",
        size=4,
        min=0,
        max=1,
        default=(1, 1, 1, 1),
        update=on_update_render_preview_nodes,
    )
    ambientColor: bpy.props.FloatVectorProperty(
        name="Ambient Light",
        subtype="COLOR",
        size=4,
        min=0,
        max=1,
        default=(0.5, 0.5, 0.5, 1),
        update=on_update_render_preview_nodes,
    )
    lightColor: bpy.props.FloatVectorProperty(
        name="Light Color",
        subtype="COLOR",
        size=4,
        min=0,
        max=1,
        default=(1, 1, 1, 1),
        update=on_update_render_preview_nodes,
    )
    lightDirection: bpy.props.FloatVectorProperty(
        name="Light Direction",
        subtype="DIRECTION",
        size=3,
        min=-1,
        max=1,
        default=mathutils.Vector((0.5, 0.5, 1)).normalized(),  # pre normalized
        update=on_update_render_preview_nodes,
    )
    useWorldSpaceLighting: bpy.props.BoolProperty(
        name="Use World Space Lighting", default=True, update=on_update_render_settings
    )
    # Fog Preview is int because values reflect F3D values
    fogPreviewPosition: bpy.props.IntVectorProperty(
        name="Fog Position", size=2, min=0, max=0x7FFFFFFF, default=(985, 1000), update=on_update_render_preview_nodes
    )
    # Clipping planes are float because values reflect F3D values
    clippingPlanes: bpy.props.FloatVectorProperty(
        name="Clipping Planes", size=2, min=0, default=(100, 30000), update=on_update_render_preview_nodes
    )
    useObjectRenderPreview: bpy.props.BoolProperty(
        name="Use Object Preview", default=True, update=on_update_render_settings
    )
    # SM64
    sm64Area: bpy.props.PointerProperty(
        name="Area Object", type=bpy.types.Object, update=on_update_sm64_render_settings, poll=poll_sm64_area
    )
    # OOT
    ootSceneObject: bpy.props.PointerProperty(
        name="Scene Object", type=bpy.types.Object, update=on_update_oot_render_settings, poll=poll_oot_scene
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
