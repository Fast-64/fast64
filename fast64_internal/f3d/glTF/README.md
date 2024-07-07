## Extension Index:

- F3D (General F3D properties)
  - [F3D (FAST64_materials_f3d)](#FAST64_materials_f3d)
  - [F3D (FAST64_sampler_f3d)](#FAST64_sampler_f3d)
- [F3DEX1 (FAST64_materials_f3dex1)](#FAST64_materials_f3dex1)
- [F3DEX3 (FAST64_materials_f3dex3)](#FAST64_materials_f3dex3)
- [F3DEX and up (FAST64_mesh_f3d_new)](#FAST64_mesh_f3d_new)

---

<a id="FAST64_materials_f3d"></a>
# FAST64_materials_f3d

## Contributors

* [@Lilaa3](https://github.com/Lilaa3)

## Status

Draft

## Dependencies

Written against the glTF 2.0 spec.

## Overview

This extension implements a representation of fast64 material data, which itself is an abstraction of the F3D microcode, properties from other revisions are implemented in seperate extensions:

- [F3DEX1](#FAST64_materials_f3dex1)
- [F3DEX3](#FAST64_materials_f3dex3)

### JSON Schema

- [material.FAST64_materials_f3d.schema.json](schema/FAST64_materials_f3d.schema.json)

## Known Implementations

* No current implementations

## Resources

* [Latest N64 Documentation](https://ultra64.ca/files/documentation/online-manuals/man-v5-2/allman52/)

---
<a id="FAST64_sampler_f3d"></a>
# FAST64_sampler_f3d

## Contributors

* [@Lilaa3](https://github.com/Lilaa3)

## Status

Draft

## Dependencies

Written against the glTF 2.0 spec.

## Overview

This extension implements a representation of how individual textures are sampled on n64, including shift, mask, low and high values, clamp and mirror, format and reference information.

### JSON Schema

- [material.FAST64_materials_f3d.schema.json](schema/FAST64_materials_f3d.schema.json)

## Known Implementations

* No current implementations

## Resources

* TODO: Add more resources here
* [Texture Mapping Documentation](https://ultra64.ca/files/documentation/online-manuals/man/pro-man/pro13/index.html)

---

<a id="FAST64_materials_f3dex1"></a>
# FAST64_materials_f3dex1

## Contributors

* [@Lilaa3](https://github.com/Lilaa3)

## Status

Draft

## Dependencies

Written against the glTF 2.0 spec.

## Overview

This extension implements f3dex1 material features, which only differs in the inclusion of the G_CLIPPING geometry mode, it mostly exists for completeness as G_CLIPPING is on by default and is crucial for performance.

### JSON Schema

- [material.FAST64_materials_f3dex1.schema.json](schema/FAST64_materials_f3d.schema.json)

## Known Implementations

* No current implementations

## Resources

* [gSPSetGeometryMode Documentation](https://ultra64.ca/files/documentation/online-manuals/man-v5-2/allman52/n64man/gsp/gSPSetGeometryMode.htm)

---
<a id="FAST64_materials_f3dex3"></a>
# FAST64_materials_f3dex3

## Contributors

* [@Lilaa3](https://github.com/Lilaa3)

## Status

Draft

## Dependencies

Written against the glTF 2.0 spec.

## Overview

This extension implements F3DEX3 material features such as ambient occulsion, fresnel, attribute offsets and cel shading. F3DEX3 is based of F3DEX2 but does not include G_CLIPPING as an optional geometry mode, fast64 will never export both FAST64_materials_f3dex1 and FAST64_materials_f3dex3.

### JSON Schema

- [material.FAST64_materials_f3dex3.schema.json](schema/FAST64_materials_f3dex3.schema.json)

## Known Implementations

- No current implementations

## Resources

- [F3DEX3's Documentation](https://hackern64.github.io/F3DEX3/)

---
<a id="FAST64_mesh_f3d_new"></a>
# FAST64_mesh_f3d_new

## Contributors

* [@Lilaa3](https://github.com/Lilaa3)

## Status

Draft

## Dependencies

Written against the glTF 2.0 spec.

## Overview

This extension implements f3dex and up vertex based culling, which fast64 represents per mesh.

### JSON Schema

- [material.FAST64_mesh_f3d_new.schema.json](schema/FAST64_mesh_f3d_new.schema.json)

## Known Implementations

- No current implementations

## Resources

- [F3DEX3's Documentation](https://hackern64.github.io/F3DEX3/)