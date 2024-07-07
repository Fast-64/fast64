from pprint import pprint
import addon_utils


def find_glTF2_addon():
    for mod in addon_utils.modules():
        if mod.__name__ == "io_scene_gltf2":
            return mod
    else:
        raise ValueError("glTF2 addon not found")


class GlTF2SubExtension:
    required: bool = False

    def post_init(self):
        pass

    def __init__(self, extension):
        self.extension = extension
        self.post_init()

    def print_verbose(self, content):
        if self.extension.verbose:
            pprint(content)

    def append_extension(self, gltf_prop, name: str, data: dict = None, required=False, skip_if_empty=True):
        if skip_if_empty and not data and data is not None:  # If none, assume it shouldn´t skip
            return
        self.print_verbose(f"Appending {name} extension")
        if data:
            self.print_verbose(data)
        if gltf_prop.extensions is None:
            gltf_prop.extensions = {}
        gltf_prop.extensions[name] = self.extension.Extension(
            name=name,
            extension=data if data else {},
            required=required if required else self.required,
        )

    def get_extension(self, gltf_prop, name: str):
        if gltf_prop.extensions is None:
            return None
        data = gltf_prop.extensions.get(name, None)
        if any(data):
            self.print_verbose(data)
        return data
