
# Fast64

This requires Blender 2.81.

![alt-text](https://bitbucket.org/kurethedead/fast64/raw/master/images/mario_running.gif)

This is a Blender plugin that allows one to export display lists, geolayouts, and animations to Super Mario 64, either directly into a ROM or to C code. It supports custom color combiners / geometry modes, and different geolayout node types. 

Make sure to save often, as this plugin is prone to crashing when creating materials / undoing material creation. This is a Blender issue.

<https://developer.blender.org/T70574>

<https://developer.blender.org/T68406>


![alt-text](https://bitbucket.org/kurethedead/fast64/raw/master/images/mat_inspector.png)

![alt-text](https://bitbucket.org/kurethedead/fast64/raw/master/images/bone_inspector.png)

### Features (import means import into Blender)  
-   Geolayout import/export 
-   Display List import/export 
-   Animation import/export
-   Collision export
-   Skinned mesh support
-   Custom normals

### Restrictions
-   No YUV textures supported.
-   When importing display lists / geolayouts from SM64 to Blender, only the mesh is imported (no material)

### Credits
Thanks to anonymous_moose, Cheezepin, Rovert, and especially InTheBeef for testing.

# Instructions
### Installation
Unzip and drag the entire folder into your blender addons folder (usually at C:\Program Files\Blender Foundation\Blender\2.80\scripts\addons). Note that you must drag the ENTIRE folder, not just the 'fast64_internal' folder. Then in Blender, go to Edit -> Preferences -> Add-Ons and find/check the 'Fast64' plugin. If it does not show up, go to Edit -> Preferences -> Save&Load and make sure 'Auto Run Python Scripts' is enabled.

### Tool Locations
The tools can be found in the properties sidebar under the 'Tools' tab (toggled by pressing N).
The F3D material inspector can be found in the properties editor under the material tab.
The geolayout inspector can be found in the properties editor under the bone tab in Pose Mode.
The RDP default settings can be found in the properties editor under the world tab.

### ROM File Settings
When importing from a ROM, the plugin will import from the ROM at filepath 'Import ROM', When exporting to a ROM, the plugin will make a copy of the file at 'Export ROM', modify it, and save the file to 'Output ROM'. The ROM must be expanded.

### Where Can I Export To?
By default, when exporting to ROM, the plugin will copy the contents of bank 4 to the range (0x11A35B8 - 0x11FFF00). This will leave you with free space to export assets to range (0x11D8930 - 0x11FFF00).

### Vertex Colors
To use vertex colors, select the "Vertex Colored Texture" preset and add two vertex color layers to your mesh named 'Col' and 'Alpha'. The alpha layer will use the greyscale value of the vertex color to determine alpha.

### F3D Materials
Any exported meshes must have an F3D Material, which can be added by the 'Create F3D Material' button in the material inspector window.

### RDP State Optimization
A material will not set every single geometry mode / other mode option. Instead, each property will be checked against the default settings located in the world tab in the properties sidebar. If the values are the same, then the code to change it is not added. 

### Geolayouts
There are many different geolayout node types. In Blender, each node type is represented by a bone group. Imported geolayouts will already have these bone groups, but if you want to add them to your own armature use the 'Add Bone Groups' operator in the SM64 Armature Tools header. All regular bones (aka 0x13 commands) and 0x15 command bones are placed on armature layer 0. All other geolayout commands are placed on layer 1. Metarig generated bones are placed on layers 3 and 4 (see 'Animating Existing Geolayouts'). If you change a bone's geolayout command type and it dissapears, it might have been moved to a different layer. Make sure to go to the armature properties editor and set both layers 0 and 1 to be visible. Geolayout command types can be editted in the properties editor under the bone tab in pose mode.

### Exporting Geolayouts and Skinned Meshes
The N64 supports binary skinning, meaning each vertex will be influenced by one bone only. When skinning an exported geolayout, do NOT use automatic skinning, as this results in a smooth weight falloff. Instead, when weight painting set the weight to either 1 or 0, and set the brush Falloff to square. Skinning can only occur between an immediate parent and a child deform bone, not between siblings / across ancestors.

### Replacing Existing SM64 Geolayout Geometry
SM64 geolayouts are often in strange rest poses, which makes it hard to modify their geometry. It often helps to import an animation belonging to that geolayout to see what the idle pose of a geolayout should be. Once you know, you can rotate the bones of the armature in pose mode to a usable position and then use the 'Apply as Rest Pose' operator under the SM64 Armature Tools header. Skin your new mesh to that armature, then rotate the bones back to the original position and use 'Apply as Rest Pose' again. You can now export the geolayout to SM64 and it will be able to use existing animations.

### Importing An Animation To Blender
To import an animation to blender, select an armature for the animation to be exported to, and press 'Import animation'. Note that the armature's root 0x13 (i.e. regular) bone must be named 'root'. Animations can be found by looking at behaviour scripts where 27 and 28 commands are.

### Exporting Mario Animations
Mario animations use a DMA table, which contains 8 byte entries of (offset from table start, animation size). Documentation about this table is here:
https://dudaw.webs.com/sm64docs/sm64_marios_animation_table.txt
Basically, Mario's DMA table starts at 0x4EC000. There is an 8 byte header, and then the animation entries afterward. Thus the 'climb up ledge' DMA entry is at 0x4EC008. The first 8 bytes at that address indicate the offset from 0x4EC000 at which the actual animation exists. Using this table you can find animations you want to overwrite.

### Animating Existing Geolayouts
Often times it is hard to rig an existing SM64 geolayout, as there are many intermediate non-deform bones and bones don't point to their children. To make this easier you can use the 'Create Animatable Metarig' operator in the SM64 Armature Tools header. This will generate a metarig which can be used with IK. The metarig bones will be placed on armature layers 3 and 4.

### Exporting Geolayouts to C
When you export in C, there will be 3 paths. Geo Filepath is for geolayout data. DL Filepath is for f3d data. Definitions Filepath is for extern definitions of objects.
To replace a model in decomp, replace its geo.inc.c and model.inc.c contents with the geolayout file and the dl file respectively. Use the contents of the define file to replace existing defines in one of the group header files (ex. mario is in group0.h). Make sure that the name of your geolayout is the same the name of the geolayout you're replacing.

### Switch Statements
To add a switch mesh node, duplicate your switch bone and move it off to the side. Set the bone geolayout command to be Switch Option. Any nodes in this switch option must be children of this bone. Add any other bones to this bone. Add your switch geometry into your existing mesh in the correct position and skin it.

### Common Issues
Inivisible Mesh : Bone is not set to deform, or geometry is skinned to more than one bone.

Game crashes: Invalid function address for switch/function/held object bones.
