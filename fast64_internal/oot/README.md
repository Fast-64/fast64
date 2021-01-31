# Ocarina Of Time

### Getting Started
1. In the 3D view properties sidebar, go to the Fast64 tab -> Fast64 Global Properties and set "Game" to OOT.
2. Switch to the OOT tab. Set your decomp path to the path of your repository on disk.
3. Click "Add Scene" to create a basic scene.
4. Choose the scene to replace. Some scenes have some hardcoded things that will cause them to break, so choose something like "spot01".
5. Click "Export Scene" to export it.
6. Compile and run the game.

### Scene Overview
In Blender, the "empty" object type is used to define different types of OOT data. 
For scenes, there must be a specific parenting hierarchy:

![](https://bitbucket.org/kurethedead/fast64/raw/master/images/oot_scene_hierarchy.png)

This means that any geometry/actors/etc. not parented to the scene hierarchy will NOT be included in the export.
Note that geometry/actors/etc. do not have to be directly parented to the room empty, as long as its in a descendant's hierachy somewhere.

Properties for empties/meshes can be found in the Blender object properties window.
![](https://bitbucket.org/kurethedead/fast64/raw/master/images/oot_object_properties.png)

To export a scene, the "Scene Object" must be set in the "OOT Scene Exporter" section in the tool properties sidebar. When you click "Add Scene" this is set automatically.

### Actors Variables
Actor variables can be found at https://wiki.cloudmodding.com/oot/Actor_List_(Variables).

### Exits
The debug menu scene select can be found at sScenes in src/overlays/gamestates/ovl_select/z_select.c.
The last field of a SceneSelectEntry is the index into gEntranceTable (found in src/code/z_scene_table.c).
All exits are basically an index into this table. Due to the way it works it makes it difficult to add/remove entries without breaking everything. For now the user will have to manually manage this table. For more info check out https://wiki.cloudmodding.com/oot/Entrance_Table.

### Scene Draw Configuration And Dynamic Material Properties
The scene object has a property called "Draw Config." This is an index into sSceneDrawHandlers in src/code/z_scene_table.c.
Each function in this table will load certain Gfx commands such as scrolling textures or setting color registers into the beginning of a RAM segment using gsSPSegment(). In Blender, in the material properties window you can choose which commands are called at the beginning of the material drawing.

![](https://bitbucket.org/kurethedead/fast64/raw/master/images/oot_dynamic_material.png)

Note that there are different segments loaded between the OPA (opaque) and XLU (transparent) draw layers.
Additionally, for functions like Gfx_TexScroll(), the x,y inputs are pre-shifted by <<2. For example, a % 128 means a repeat of the texture every 32 pixels.

### Collision
Collision properties are found underneath the material properties. Water boxes and collision properties will have references the properties "Camera", "Lighting", and "Exit", which reference the indices of the scene cameras, scene light list, and scene exit list respectively. If you want separate visual/collision geometry, you can set per mesh object "Ignore Collision" or "Ignore Render" in object inspector window.