import re

import bpy
import sys

# import path
from bpy.path import abspath

"""
A script that can be run in blender to import all skeletons and animations 
(if there's only one skeleton) in a file from OOT or MM

Usage:
blender --background --python-exit-code 1 --python make_skeletons.py -- <path to decomp> <input file> <output blend file> <object name> ["1" to import animations too]

Example:
blender --background --python-exit-code 1 --python make_skeletons.py -- ~/git/mm ~/git/mm/assets/objects/object_dnj/object_dnj.c deku_butler.blend object_dnj 1 
"""
args = sys.argv[(sys.argv.index("--") + 1) :]

decompPath = args[0]
inFile = args[1]
outFile = args[2]
objectName = args[3]
importAnimations = len(args) > 4 and args[4] == "1"

# objectName = path.basename(path.dirname(inFile))
print(f"decomp path {decompPath}")
print(f"inFile {inFile}")
print(f"outFile {outFile}")
print(f"object name {objectName}")

# delete the default cube
if bpy.context.view_layer.objects.active.name == "Cube":
    bpy.ops.object.delete()


with open(inFile, "r") as file:
    code = file.read()

# Identify all skeleton headers in the input file
skeletonNames = list(
    m.group("name") for m in re.finditer(r"(Flex)?SkeletonHeader\s*(?P<name>[A-Za-z0-9\_]+)\s*=", code)
)

# Setup Fast64 settings
bpy.context.scene.gameEditorMode = "OOT"
bpy.context.scene.ootDecompPath = abspath(decompPath)
bpy.context.scene.fast64.oot.animImportSettings.folderName = objectName

# These aren't used by the script, but we may as well set them to reasonable values
# in case someone is going to work out of the output blend file
bpy.context.scene.fast64.oot.skeletonExportSettings.folder = objectName
bpy.context.scene.fast64.oot.animExportSettings.folderName = objectName
bpy.context.scene.fast64.oot.DLExportSettings.folder = objectName
bpy.context.scene.fast64.oot.collisionExportSettings.folder = objectName

# Import all skeletons from the file
errs = []
for skeletonName in skeletonNames:
    imp = bpy.context.scene.fast64.oot.skeletonImportSettings
    imp.name = skeletonName  # e.g. gDekuButlerSkel
    imp.folder = objectName  # e.g. object_dnj
    # TODO: maybe try to identify an appropriate overlay, or allow it as an argument
    imp.actorOverlayName = ""  # e.g. ovl_En_Dno

    res = bpy.ops.object.oot_import_skeleton()
    if "CANCELLED" in res:
        errs.append(f"Failed to import skeleton {skeletonName}")

# Import animations if there's only one skeleton and animation import was anbled
if len(skeletonNames) == 1 and importAnimations:
    animationNames = list(m.group("name") for m in re.finditer(r"AnimationHeader\s*(?P<name>[A-Za-z0-9\_]+)\s*=", code))

    # select the armature
    bpy.context.view_layer.objects.active = bpy.context.view_layer.objects[skeletonNames[0]]

    # import each animation
    for animationName in animationNames:
        bpy.context.scene.fast64.oot.animImportSettings.animName = animationName
        res = bpy.ops.object.oot_import_anim()
        if "CANCELLED" in res:
            errs.append(f"Failed to import animation {animationName}")

if len(errs) > 0:
    raise RuntimeError(f"Errors running skeleton import: {errs}")

# Set viewport shading to show textures
for area in bpy.context.screen.areas:
    if area.type == "VIEW_3D":
        for space in area.spaces:
            if space.type == "VIEW_3D":
                space.shading.type = "MATERIAL"

# Save the file if anything was imported
if len(skeletonNames) > 0:
    bpy.ops.wm.save_mainfile(filepath=outFile)
