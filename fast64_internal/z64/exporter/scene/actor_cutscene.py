from dataclasses import dataclass
from bpy.types import Object
from mathutils import Matrix
from typing import Optional
from ....utility import CData, PluginError, exportColor, scaleToU8, indent
from ...utility import getObjectList
from ...actor_cutscene.properties import Z64_ActorCutsceneProperty, Z64_ActorCutscene
from ..utility import Utility
from ..collision.camera import BgCamInformations, CameraInfo


class ActorCutscene:
    def __init__(
        self, scene_obj: Object, transform: Matrix, props: Z64_ActorCutscene, name: str, index: int, obj: Object
    ):
        self.name = name
        self.priority: int = props.priority
        self.length: int = props.length
        self.index = index
        self.cam_info: Optional[CameraInfo] = None

        if obj.ootEmptyType == "Actor":
            obj.ootActorProperty.actor_cs_index = index

        if props.cs_cam_id == "Custom":
            self.cs_cam_id: str = props.cs_cam_id_custom
        elif props.cs_cam_id == "Camera":
            if props.cs_cam_obj is None:
                raise PluginError("ERROR: The Actor Cutscene Camera object is unset!")

            cam_props = props.cs_cam_obj.ootCameraPositionProperty
            self.cs_cam_id: str = f"{cam_props.index}"

            # since it's literally the same thing we can just use `BgCamInformations`
            self.cam_info = BgCamInformations.get_camera_info(scene_obj, props.cs_cam_obj, transform, None)
            self.cam_info.arrayIndex = cam_props.index * 3
        else:
            self.cs_cam_id: str = props.cs_cam_id

        self.script_index: int = props.script_index
        self.additional_cs_id: int = props.additional_cs_id
        self.end_sfx: str = Utility.getPropValue(props, "end_sfx", "end_sfx_custom")
        self.custom_value: str = props.custom_value
        self.hud_visibility: str = Utility.getPropValue(props, "hud_visibility", "hud_visibility_custom")
        self.end_cam: str = Utility.getPropValue(props, "end_cam", "end_cam_custom")
        self.letterbox_size: int = props.letterbox_size

        if self.script_index != -1 and self.cs_cam_id not in {"CS_CAM_ID_NONE", "-1"}:
            print(
                "WARNING: this actor cutscene entry won't use the camera cutscene since the script takes the priority."
            )

    def cutscene_entry_to_c(self):
        values = [
            self.priority,
            self.length,
            self.cs_cam_id,
            self.script_index,
            self.additional_cs_id,
            self.end_sfx,
            self.custom_value,
            self.hud_visibility,
            self.end_cam,
            self.letterbox_size,
        ]

        return "{ " + ", ".join(f"{value}" for value in values) + " }"


@dataclass
class SceneActorCutscene:
    """This class hosts actor cutscene data"""

    name: str
    cam_info_array_name: str
    cam_data_array_name: str
    header_index: int
    entries: list[ActorCutscene]

    @staticmethod
    def get_entries(name: str, scene_obj: Object, transform: Matrix, header_index: int, empty_type: str, start: int):
        entries: list[ActorCutscene] = []
        obj_list = getObjectList(scene_obj.children_recursive, "EMPTY", empty_type)
        processed = []

        for obj in obj_list:
            if empty_type == "Actor":
                header_settings = obj.ootActorProperty.headerSettings
            else:
                header_settings = obj.z64_actor_cs_property.header_settings

            for i, item in enumerate(obj.z64_actor_cs_property.entries, start):
                if Utility.isCurrentHeaderValid(header_settings, header_index):
                    new_entry = ActorCutscene(scene_obj, transform, item, name, i, obj)

                    if new_entry.cs_cam_id not in {"Custom", "Camera", "CS_CAM_ID_NONE"}:
                        if new_entry.cs_cam_id not in processed:
                            entries.append(new_entry)
                            processed.append(new_entry.cs_cam_id)
                        else:
                            raise PluginError(f"ERROR: reapeated actor cutscene camera id {repr(new_entry.cs_cam_id)}")

            start += i

        return entries

    @staticmethod
    def new(name: str, scene_obj: Object, transform: Matrix, header_index: int):
        entries = SceneActorCutscene.get_entries(name, scene_obj, transform, header_index, "Actor Cutscene", 0)
        entries.extend(SceneActorCutscene.get_entries(name, scene_obj, transform, header_index, "Actor", len(entries)))

        # validate camera indices
        last_cam_index = -1
        for entry in entries:
            if entry.cam_info is not None:
                if entry.cam_info.camIndex > last_cam_index:
                    last_cam_index = entry.cam_info.camIndex
                else:
                    raise PluginError("ERROR: the actor cs camera indices are not consecutives!")

        return SceneActorCutscene(name, f"{name}CameraInfo", f"{name}CameraData", header_index, entries)

    def is_cs_cam_used(self):
        for entry in self.entries:
            if entry.cam_info is not None:
                return True
        return False

    def get_cs_cam_list_length(self):
        length = 0
        for entry in self.entries:
            if entry.cam_info is not None:
                length += 1
        return length

    def get_cmds(self):
        """Returns the actor cutscene commands"""

        commands = [
            f"SCENE_CMD_ACTOR_CUTSCENE_LIST({len(self.entries)}, {self.name}List)",
        ]

        if self.is_cs_cam_used():
            commands.append(
                f"SCENE_CMD_ACTOR_CUTSCENE_CAM_LIST({self.get_cs_cam_list_length()}, {self.cam_info_array_name})"
            )

        return indent + f",\n{indent}".join(commands) + ",\n"

    def cam_data_to_c(self):
        """Returns the camera data positions array"""

        data = CData()
        array_name = f"Vec3s {self.cam_data_array_name}[]"

        # .h
        data.header = f"extern {array_name};\n"

        # .c
        data.source = array_name + " = {\n"

        for entry in self.entries:
            if entry.cam_info is not None:
                data.source += entry.cam_info.data.getEntryC() + "\n"

        data.source = data.source[:-1]  # remove extra newline
        data.source += "};\n\n"

        return data

    def cam_info_to_c(self):
        """Returns the array containing the informations of each cameras"""

        data = CData()
        array_name = f"ActorCsCamInfo {self.cam_info_array_name}[]"

        # .h
        data.header = f"extern {array_name};\n"

        # .c
        data.source = (
            (array_name + " = {\n")
            + "".join(
                entry.cam_info.getInfoEntryC(self.cam_data_array_name)
                for i, entry in enumerate(self.entries)
                if entry.cam_info is not None
            )
            + "};\n\n"
        )

        return data

    def to_c(self):
        data = CData()
        array_name = f"CutsceneEntry {self.name}List[]"

        if self.is_cs_cam_used():
            data.append(self.cam_data_to_c())
            data.append(self.cam_info_to_c())

        # .h
        data.header += f"extern {array_name};\n"

        # .c
        data.source += (
            (array_name + " = {\n")
            + (
                ",\n".join(
                    indent + f"/* {i:02} */ " + entry.cutscene_entry_to_c() for i, entry in enumerate(self.entries)
                )
            )
            + "\n};\n\n"
        )

        return data
