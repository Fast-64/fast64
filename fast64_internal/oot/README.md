# Ocarina Of Time

### Getting Started
1. In the 3D view properties sidebar, go to the Fast64 tab -> Fast64 Global Properties and set "Game" to OOT.
2. Set "F3D Version" to F3DEX2.
3. Switch to the OOT tab. Set your decomp path to the path of your repository on disk.
4. Click "Add Scene" to create a basic scene.
5. Choose the scene to replace. Some scenes have some hardcoded things that will cause them to break, so choose something like "spot01".
6. Click "Export Scene" to export it.
7. Compile and run the game. This was tested for commit 20c1f4e.

### Scene Overview
In Blender, the "empty" object type is used to define different types of OOT data, including scenes and rooms.
For scenes, there must be a specific parenting hierarchy:

![](/images/oot_scene_hierarchy.png)

This means that any geometry/actors/etc. not parented to the scene hierarchy will NOT be included in the export.
Note that geometry/actors/etc. do not have to be directly parented to the room empty, as long as its in a descendant's hierachy somewhere.

Properties for empties/meshes can be found in the Blender object properties window.
![](/images/oot_object_properties.png)

To export a scene, the "Scene Object" must be set in the "OOT Scene Exporter" section in the tool properties sidebar. When you click "Add Scene" this is set automatically.

### Actors
To add actors to a scene, create a new Empty and parent it to a Room. Then in the Object Properties panel select "Actor" as the Object Type. Use the "Select Actor ID" button to choose an actor, and then set the Actor Parameter value as desired (see the list of Actor Variables below). Finally, all actors you are using must be added to the parent Room's object dependencies, otherwise they will not load into the room at all. To do this select the Room that your actor is parented to, select the "Objects" tab in its Object Properties window, and click "Add Item". Then "Search Object ID" to find the actor object you need. For example, if adding a Deku Baba actor (EN_DEKUBABA) you need to add the "Dekubaba" object to the Room's object dependencies.

#### Actor Variables
Actor variables can be found at https://wiki.cloudmodding.com/oot/Actor_List_(Variables).

### Exits
The debug menu scene select can be found at sScenes in src/overlays/gamestates/ovl_select/z_select.c.
The last field of a SceneSelectEntry is the index into gEntranceTable (found in src/code/z_scene_table.c).
All exits are basically an index into this table. Due to the way it works it makes it difficult to add/remove entries without breaking everything. For now the user will have to manually manage this table. For more info check out https://wiki.cloudmodding.com/oot/Entrance_Table.

### Scene Draw Configuration And Dynamic Material Properties
The scene object has a property called "Draw Config." This is an index into sSceneDrawHandlers in src/code/z_scene_table.c.
Each function in this table will load certain Gfx commands such as scrolling textures or setting color registers into the beginning of a RAM segment using gsSPSegment(). In Blender, in the material properties window you can choose which commands are called at the beginning of the material drawing.

![](/images/oot_dynamic_material.png)

Note that there are different segments loaded between the OPA (opaque) and XLU (transparent) draw layers.
Additionally, for functions like Gfx_TexScroll(), the x,y inputs are pre-shifted by <<2. For example, a % 128 means a repeat of the texture every 32 pixels.

### Collision
Collision properties are found underneath the material properties. Water boxes and collision properties will have references the properties "Camera", "Lighting", and "Exit", which reference the indices of the scene cameras, scene light list, and scene exit list respectively. If you want separate visual/collision geometry, you can set per mesh object "Ignore Collision" or "Ignore Render" in object inspector window.

### Skeletons And Animations
For bones, there are 3 bone types: Default, Custom DL, and Ignore. This can be set in the bone properties window.
Default is a regular deformation bone. Ignore will not be handled by the exporter/importer. Custom DL lets you define the name of a DL that you want a bone to draw instead of drawing geometry from the armature. There is also an option for billboarding the specific geometry associated with the bone.

The armature properties window also has the option to set a LOD armature. This armature must have the same bone structure as your current armature.

To export a skeletal mesh, select an armature and then click "Export" for the armature exporter. Make sure there is only one bone without a parent (the root bone), as the exporter will choose the first parentless bone as the start bone of the armature.

To import a skeletal mesh, just click "Import" for the armature importer. You may encounter a couple issues:

![](/images/oot_imported_gerudo_textured.png)
![](/images/oot_imported_gerudo_solid.png)


1. Eye/face textures are black: Texture pointers which are set dynamically will not be imported. Instead, the name of the pointer will be used instead of the actual data.
2. Certain colors are white/different: Some graphical effects are achieved through dynamic Gfx commands, such as tinting white textures. These effects will not be imported.
3. Strange imported normals: Due to the behaviour of rotating vertices on a skinned triangle that differs between Blender and the N64, normals may look strange. Note that these normals will look correct if re exported back into the game (assuming the rest pose is not changed).

Note that rest pose rotations are zeroed out on export, so you can modify the rest pose of imported armature while still preserving its structure. You can do this by using the "Apply As Rest Pose" operator under the Fast64 tab. Note that imported animations however still require the imported rest pose to work correctly.

There may also be an issue where some meshes import completely black due to the assumption that the F3D cycle mode is set to 2-Cycle, when it should really be 1-Cycle. Try changing the cycle type to 1-Cycle in cases where a dynamic texture pointer is not expected.

To import an animation, select the armature the animation belongs to then click "Import" on the animation importer.
To export an animation, select an armature and click "Export", which will export the active animation of the armature.
