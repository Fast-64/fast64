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

    def post_init(self):
        pass

    def __init__(self, extension):
        self.extension = extension
        self.post_init()

    def print_verbose(self, content):
        if self.extension.verbose:
            pprint(content)

    def append_gltf2_extension(self, gltf_prop, data: dict):
        if not any(data):
            return
        self.print_verbose(data)

        if gltf_prop.extensions is None:
            gltf_prop.extensions = {}
        gltf_prop.extensions[self.extension_name] = self.extension.Extension(
            name=self.extension_name,
            extension=data,
            required=False,
        )

    def get_gltf2_extension(self, gltf_prop):
        if gltf_prop.extensions is None:
            return None
        data = gltf_prop.extensions.get(self.extension_name, None)
        if any(data):
            self.print_verbose(data)
        return data
