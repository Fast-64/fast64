from pprint import pprint
import addon_utils


def find_glTF2_addon():
    for mod in addon_utils.modules():
        if mod.__name__ == "io_scene_gltf2":
            return mod
    else:
        raise ValueError("glTF2 addon not found")


class GlTF2SubExtension:
    extension_name: str = None
    required: bool = False

    def post_init(self):
        pass

    def __init__(self, extension):
        self.extension = extension
        self.post_init()

    def print_verbose(self, content):
        if self.extension.verbose:
            pprint(content)

    def append_gltf2_extension(self, gltf_prop, data: dict, extension_name=None, required=False):
        self.print_verbose(f"Appending {self.extension_name} extension: {data}")
        if gltf_prop.extensions is None:
            gltf_prop.extensions = {}
        extension_name = extension_name if extension_name else self.extension_name
        gltf_prop.extensions[extension_name] = self.extension.Extension(
            name=extension_name,
            extension=data,
            required=required if required else self.required,
        )

    def get_gltf2_extension(self, gltf_prop, extension_name=None):
        if gltf_prop.extensions is None:
            return None
        extension_name = extension_name if extension_name else self.extension_name
        data = gltf_prop.extensions.get(extension_name, None)
        if any(data):
            self.print_verbose(data)
        return data
