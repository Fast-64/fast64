import bpy
import struct, re


def MetersToBlend(context, v):
    return v * 56.0 / context.scene.ootBlenderScale


def ActorHeightMeters(context, actor_id):
    if actor_id < 0:
        # Link
        return 1.7 if context.scene.zc_previewlinkage == "link_adult" else 1.3
    else:
        # Other actor
        return 1.5


"""From https://stackoverflow.com/questions/14431170/get-the-bits-of-a-float-in-python"""


def intBitsAsFloat(i):
    s = struct.pack(">l", i)
    return struct.unpack(">f", s)[0]


def floatBitsAsInt(f):
    s = struct.pack(">f", f)
    return struct.unpack(">l", s)[0]


"""From https://stackoverflow.com/questions/7085512/check-what-number-a-string-ends-with-in-python/7085715"""


def GetTrailingNumber(s):
    m = re.search(r"\d+$", s)
    return int(m.group()) if m else None


def GetObjectUniqueName(context, basename):
    num = GetTrailingNumber(basename)
    if num is None:
        num = 1
    while True:
        name = basename + ".{:03}".format(num)
        for o in context.scene.objects:
            if o.name == name:
                break
        else:
            return name
        num += 1


def CreateObject(context, name, data, select):
    obj = context.blend_data.objects.new(name=name, object_data=data)
    context.view_layer.active_layer_collection.collection.objects.link(obj)
    if select:
        obj.select_set(True)
        context.view_layer.objects.active = obj
    return obj
