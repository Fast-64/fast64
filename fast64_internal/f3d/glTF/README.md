## Extension Index:

- [N64 Material (FAST64_materials_n64](#FAST64_materials_n64)
- [N64 Sampler (FAST64_sampler_n64)](#FAST64_sampler_n64)
- F3D
  - [F3D Material Properties (FAST64_materials_f3d)](#FAST64_materials_f3d)
  - [F3D Mesh Properties (FAST64_mesh_f3d)](#FAST64_mesh_f3d)
  - Revisions
    - [F3DLX Material Properties (FAST64_materials_f3dlx)](#FAST64_materials_f3dlx)
    - [F3DEX3 Material Properties (FAST64_materials_f3dex3)](#FAST64_materials_f3dex3)
    - [F3DEX and up Mesh Properties (FAST64_mesh_f3d_new)](#FAST64_mesh_f3d_new)

---

<h1 id="FAST64_materials_n64">FAST64_materials_n64</h1>

## Contributors

* [@Lilaa3](https://github.com/Lilaa3)

## Status

Draft

## Dependencies

Written against the glTF 2.0 spec.

## Overview

This extension implements a representation of the n64's basic rendering properties present in fast64 materials, properties in individual microcodes are implemented in seperate extensions:

- [F3D](#FAST64_materials_f3d)
  - [F3DLX](#FAST64_materials_f3dlx)
  - [F3DEX3](#FAST64_materials_f3dex3)

### JSON Schema

- [material.FAST64_materials_n64.schema.json](schema/FAST64_materials_n64.schema.json)

## Known Implementations

* No current implementations

## Resources

* [RDP Command Documentation](https://n64brew.dev/wiki/Reality_Display_Processor/Commands)

---

<h1 id="FAST64_sampler_n64">FAST64_sampler_n64</h1>

## Contributors

* [@Lilaa3](https://github.com/Lilaa3)

## Status

Draft

## Dependencies

Written against the glTF 2.0 spec.

## Overview

This extension implements a representation of how individual textures are sampled on n64, including shift, mask, low and high values, clamp and mirror, format and reference information.

### JSON Schema

- [material.FAST64_sampler_n64.schema.json](schema/FAST64_sampler_n64.schema.json)

## Known Implementations

* No current implementations

## Resources

* [Texture Mapping Documentation](https://ultra64.ca/files/documentation/online-manuals/man/pro-man/pro13/index.html)
* [Load Tile RDP Command Documentation](https://n64brew.dev/wiki/Reality_Display_Processor/Commands#0x35_-_Set_Tile)

---

<h1 id="FAST64_materials_f3d">FAST64_materials_f3d</h1>

## Contributors

* [@Lilaa3](https://github.com/Lilaa3)

## Status

Draft

## Dependencies

Extension of [FAST64_materials_n64](#FAST64_materials_n64)

## Overview

This extension implements an abstraction of F3D material features, properties from other revisions are implemented in seperate extensions:

- [F3DLX](#FAST64_materials_f3dlx)
- [F3DEX3](#FAST64_materials_f3dex3)

### JSON Schema

- [material.FAST64_materials_f3d.schema.json](schema/FAST64_materials_f3d.schema.json)

## Known Implementations

* No current implementations

## Resources

* [Latest N64 Documentation](https://ultra64.ca/files/documentation/online-manuals/man-v5-2/allman52/)

---

<h1 id="FAST64_mesh_f3d">FAST64_mesh_f3d</h1>

## Contributors

* [@Lilaa3](https://github.com/Lilaa3)

## Status

Draft

## Dependencies

Written against the glTF 2.0 spec.

## Overview

This extension implements a representation of fast64 mesh data, currently only contains one property from post F3DLX microcodes, which is implemented in a seperate extension:

- [F3DEX and up](#FAST64_mesh_f3d_new)

### JSON Schema

- [material.FAST64_mesh_f3d.schema.json](schema/FAST64_mesh_f3d.schema.json)

## Known Implementations

* No current implementations

---

<h1 id="FAST64_materials_f3dlx">FAST64_materials_f3dlx</h1>

## Contributors

* [@Lilaa3](https://github.com/Lilaa3)

## Status

Draft

## Dependencies

Extension of [FAST64_materials_f3d](#FAST64_materials_f3d)

## Overview

This extension implements F3DLX material features, which only differs in the inclusion of the G_CLIPPING geometry mode, it mostly exists for completeness as G_CLIPPING is on by default and is crucial for performance.

### JSON Schema

- [material.FAST64_materials_f3dlx.schema.json](schema/FAST64_materials_f3dlx.schema.json)

## Known Implementations

* No current implementations

## Resources

* [gSPSetGeometryMode Documentation](https://ultra64.ca/files/documentation/online-manuals/man-v5-2/allman52/n64man/gsp/gSPSetGeometryMode.htm)

---

<h1 id="FAST64_materials_f3dex3">FAST64_materials_f3dex3</h1>

## Contributors

* [@Lilaa3](https://github.com/Lilaa3)

## Status

Draft

## Dependencies

Extension of [FAST64_materials_f3d](#FAST64_materials_f3d)

## Overview

This extension implements F3DEX3 material features such as ambient occulsion, fresnel, attribute offsets and cel shading. F3DEX3 is based of F3DEX2 but does not include G_CLIPPING as an optional geometry mode, fast64 will never export both FAST64_materials_f3dlx and FAST64_materials_f3dex3.

### JSON Schema

- [material.FAST64_materials_f3dex3.schema.json](schema/FAST64_materials_f3dex3.schema.json)

## Known Implementations

- No current implementations

## Resources

- [F3DEX3's Documentation](https://hackern64.github.io/F3DEX3/)

---

<h1 id="FAST64_mesh_f3d_new">FAST64_mesh_f3d_new</h1>

## Contributors

* [@Lilaa3](https://github.com/Lilaa3)

## Status

Draft

## Dependencies

Extension of [FAST64_mesh_f3d](#FAST64_mesh_f3d)

## Overview

This extension implements f3dex and up vertex based culling, which fast64 represents per mesh.

### JSON Schema

- [material.FAST64_mesh_f3d_new.schema.json](schema/FAST64_mesh_f3d_new.schema.json)

## Known Implementations

- No current implementations

## Resources

- [gSPCullDisplayList Documentation](https://ultra64.ca/files/documentation/online-manuals/man-v5-2/allman52/n64man/gsp/gSPCullDisplayList.htm)