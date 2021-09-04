# Fast64

This requires Blender 2.82+.

Forked from [kurethedead/fast64 on BitBucket](https://bitbucket.org/kurethedead/fast64/src).

![alt-text](/images/mario_running.gif)

This is a Blender plugin that allows one to export F3D display lists. It also has the ability to export assets for Super Mario 64 and Ocarina of Time decompilation projects. It supports custom color combiners / geometry modes / etc. It is also possible to use exported C code in homebrew applications.

Make sure to save often, as this plugin is prone to crashing when creating materials / undoing material creation. This is a Blender issue.

<https://developer.blender.org/T70574>


![alt-text](/images/mat_inspector.png)


### Credits
Thanks to anonymous_moose, Cheezepin, Rovert, and especially InTheBeef for testing.
Thanks to InTheBeef for LowPolySkinnedMario.

### Table of Contents
1. [ Super Mario 64 ](/fast64_internal/sm64/README.md)
2. [ Ocarina Of Time ](/fast64_internal/oot/README.md)

### Installation
Download the repository as a zip file. In Blender, go to Edit -> Preferences -> Add-Ons and click the "Install" button to install the plugin from the zip file. Find the Fast64 addon in the addon list and enable it. If it does not show up, go to Edit -> Preferences -> Save&Load and make sure 'Auto Run Python Scripts' is enabled.

### Tool Locations
The tools can be found in the properties sidebar under the 'Fast64' tab (toggled by pressing N).
The F3D material inspector can be found in the properties editor under the material tab.

### F3D Materials
Any exported mesh must use an F3D Material, which can be added by the 'Create F3D Material' button in the material inspector window. You CANNOT use regular blender materials. If you have a model with Principled BSDF materials, you can use the Principled BSDF to F3D conversion operator to automatically convert them. The image in the "Base Color" slot will be set as texture 0, while the image in the "Subsurface Color" slot will be set as texture 1.

### Vertex Colors
To use vertex colors, select a vertex colored texture preset and add two vertex color layers to your mesh named 'Col' and 'Alpha'. The alpha layer will use the greyscale value of the vertex color to determine alpha.

### Large Texture Mode
In F3D material properties, you can enable "Large Texture Mode". This will let you use textures up to 1024x1024 as long as each triangle in the mesh has UVs that can fit within a single tile load. Fast64 will categorize triangles into shared tile loads and load the portion of the texture when necessary.

### Decomp vs Homebrew Compatibility
There may occur cases where code is formatted differently based on the code use case. In the tools panel under the Fast64 File Settings subheader, you can toggle homebrew compatibility.

### Converting To F3D v4 Materials
A new optimized shader graph was introduced to decrease processing times for material creation and exporting. If you have a project that still uses old materials, you may want to convert them to v4. To convert an old project, click the "Recreate F3D Materials As V4" operator near the top of the Fast64 tab in 3D view. This may take a while depending on the number of materials in the project. Then go to the outliner, change the display mode to "Orphan Data" (broken heart icon), then click "Purge" in the top right corner. Purge multiple times until all of the old node groups are gone.

### Fast64 Development
If you'd like to develop in VSCode, follow this tutorial to get proper autocomplete. Skip the linter for now, we'll need to make sure the entire project gets linted before enabling autosave linting because the changes will be massive.
https://b3d.interplanety.org/en/using-microsoft-visual-studio-code-as-external-ide-for-writing-blender-scripts-add-ons/
