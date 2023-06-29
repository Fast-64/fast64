from .Common import MetersToBlend, CreateObject
from .CamData import GetCSFakeEnd
from .ActionData import IsActionList, CreateOrInitPreview


def InitCS(context, cs_object):
    # Add or move camera
    camo = None
    nocam = True
    for o in context.blend_data.objects:
        if o.type != "CAMERA":
            continue
        nocam = False
        if o.parent is not None and o.parent != cs_object:
            continue
        camo = o
        break
    if nocam:
        cam = context.blend_data.cameras.new("Camera")
        camo = CreateObject(context, "Camera", cam, False)
        print("Created new camera")
    if camo is not None:
        camo.parent = cs_object
        camo.data.display_size = MetersToBlend(context, 0.25)
        camo.data.passepartout_alpha = 0.95
        camo.data.clip_start = MetersToBlend(context, 1e-3)
        camo.data.clip_end = MetersToBlend(context, 200.0)
    # Preview actions
    for o in context.blend_data.objects:
        if IsActionList(o):
            CreateOrInitPreview(context, o.parent, o.zc_alist.actor_id, False)
    # Other setup
    context.scene.frame_start = 0
    context.scene.frame_end = max(GetCSFakeEnd(context, cs_object), context.scene.frame_end)
    context.scene.render.fps = 20
    context.scene.render.resolution_x = 320
    context.scene.render.resolution_y = 240
