from pprint import pprint
class GlTF2SubExtension:
    extension_name: str = None

    def post_init(self):
        pass

    def __init__(self, extension):
        self.extension = extension
        self.post_init()

    def append_gltf2_extension(self, gltf_prop, data: dict):
        if not any(data):
            return
        if self.extension.verbose:
            pprint(data)

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
        if self.extension.verbose and data is not None:
            pprint(data)
        return data
