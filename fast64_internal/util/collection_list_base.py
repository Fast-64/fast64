import bpy


class UnimplementedError(Exception):
    pass


def get_attr_from_dot_path(obj: object, path: str):
    for attribute in path.split("."):
        obj = getattr(obj, attribute)
    return obj


def get_collection_props_from_context(
    context: bpy.types.Context | object,
    base_path: tuple[str],  # path from context to the root of your prop, e.g. context.[scene.base_prop]
    collection_name: tuple[str],  # from base path, collection prop
    index_name: tuple[str],  # prop that tracks index
) -> tuple[object, bpy.types.Collection, int]:
    collection_base = context

    for i in range(0, len(collection_name)):
        if i > 0:
            collection_base = col_prop[index]

        collection_base = get_attr_from_dot_path(collection_base, base_path[i])
        col_prop = get_attr_from_dot_path(collection_base, collection_name[i])
        index = get_attr_from_dot_path(collection_base, index_name[i])

    return collection_base, col_prop, index


class CollectionOperator(bpy.types.Operator):
    bl_options = {"REGISTER", "UNDO", "PRESET"}

    base_path: str = None  # path from context to the root of your prop, e.g. context.[scene.base_prop]
    collection_name: tuple[str] = None  # from base path, collection prop
    index_name: tuple[str] = None  # prop that tracks index

    def get_collection(self) -> tuple[object, bpy.types.Collection, int]:
        if self.base_path is None:
            raise UnimplementedError("self.base_path not defined")
        if self.collection_name is None:
            raise UnimplementedError("self.collection_name not defined")
        if self.index_name is None:
            raise UnimplementedError("self.index_name not defined")

        return get_collection_props_from_context(bpy.context, self.base_path, self.collection_name, self.index_name)


class AddNewToCollection(CollectionOperator):
    bl_label = "Add an item to the list"

    @staticmethod
    def get_idname(base_list_name):
        return f"{base_list_name}.add_item"

    def execute(self, context):
        _, collection, _ = self.get_collection()
        collection.add()

        return {"FINISHED"}


class RemoveFromCollection(CollectionOperator):
    bl_label = "Remove an item in the list"

    @staticmethod
    def get_idname(base_list_name):
        return f"{base_list_name}.remove_item"

    @classmethod
    def poll(cls, context):
        # TODO: Remove if __init__ is successful
        raise Exception("classmethod `poll` not implemented: should poll the collection")

    def execute(self, context):
        collection_base, collection, index = self.get_collection()
        collection.remove(index)
        setattr(collection_base, self.index_name[-1], min(max(0, index - 1), len(collection)))

        return {"FINISHED"}


class MoveItemInCollection(CollectionOperator):
    """Move an item in the list."""

    bl_label = "Move an item in the list"

    direction: bpy.props.EnumProperty(
        items=(
            ("UP", "Up", ""),
            ("DOWN", "Down", ""),
        )
    )

    @staticmethod
    def get_idname(base_list_name):
        return f"{base_list_name}.move_item"

    def move_index(self):
        """Move index of an item render queue while clamping it."""
        collection_base, collection, index = self.get_collection()

        list_length = len(collection) - 1  # (index starts at 0)
        new_index = index + (-1 if self.direction == "UP" else 1)
        setattr(collection_base, self.index_name[-1], max(0, min(new_index, list_length)))

    def execute(self, context):
        _, collection, index = self.get_collection()

        neighbor = index + (-1 if self.direction == "UP" else 1)
        collection.move(neighbor, index)
        self.move_index()

        return {"FINISHED"}


class DrawList(bpy.types.UIList):
    """Demo UIList."""

    name = "List Name"  # User should override
    custom_icon = "OBJECT_DATAMODE"
    layout_type = "DEFAULT"

    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):

        # Make sure your code supports all 3 layout types
        if self.layout_type in {"DEFAULT", "COMPACT"}:
            if getattr(item, "draw", None):
                item.draw(layout, data, index)
            else:
                layout.label(text=item.name, icon=self.custom_icon)

        elif self.layout_type in {"GRID"}:
            layout.alignment = "CENTER"
            layout.label(text="", icon=self.custom_icon)


def get_collection_classes(
    # unique identifier for list root (can really be anything)
    base_list_name: str,
    # The following props are a list of tuples so you can have nested lists
    # path from context to the root of your prop, e.g. context.["scene.base_prop"]
    # You can supply dots in these paths to navigate through nested properties
    base_path: tuple[str],
    # from base_path, collection prop
    collection_name: tuple[str],
    # prop that tracks index
    index_name: tuple[str],
):
    """
    This function returns new classes that aid in creation of UI lists.
    Here is an example of how it would be called:

        (
            # first four are classes
            AddItemToNestedList,
            RemoveItemFromNestedList,
            MoveItemInNestedList,
            DrawNestedUIList,
            # last return value is the function you can call to draw your interactive list
            draw_custom_object_prop_list
        ) = get_collection_classes(
            "anyuniqueidentifier",
            ("object.fast64.sm64", "path.to_second_list"),
            ("first_list_prop", "second_list_prop"),
            ("first_list_prop_active_index", "second_list_prop_active_index")
        )

        What else you need to do:
            - Register the first four classes returned from this function.

            - Create a CollectionProperty, and an active index int property FOR that collection, e.g.:
                class My_Custom_Properties(bpy.types.PropertyGroup):
                    custom_props: bpy.props.CollectionProperty(type=CustomObjectExportProp, name="Custom Properties")
                    custom_props_active_index: bpy.props.IntProperty(default=0, name="Custom Props Active Index")

            - The CollectionProperty should point to a PropertyGroup for more customization. By default, the list
              UI will only display the .name of the property, but you can add a custom draw method to that class, e.g.:

                class CustomObjectExportProp(bpy.types.PropertyGroup):
                    name: bpy.props.StringProperty(name="Name")
                    value: bpy.props.StringProperty(name="Value")

                    def draw(self, layout: bpy.types.UILayout, _data: "CollectionPropsParentData", index: int):
                        row = layout.row(align=True).split(factor=0.15)
                        row.label(text=f"{index}:")
                        row.prop(self, 'value', text="")

            - Call the draw function from somewhere in your UI:
                draw_custom_object_prop_list(UILayout, context)

    """

    def get_this_collection(cls, context):
        _, collection, _ = get_collection_props_from_context(context, base_path, collection_name, index_name)
        return collection

    class col_add(AddNewToCollection):
        pass

    class col_remove(RemoveFromCollection):
        pass

    setattr(col_remove, "poll", classmethod(get_this_collection))

    class col_move(MoveItemInCollection):
        pass

    setattr(col_move, "poll", classmethod(get_this_collection))

    for cls in [col_add, col_remove, col_move]:
        setattr(cls, "bl_idname", cls.get_idname(base_list_name))
        setattr(cls, "base_path", base_path)
        setattr(cls, "collection_name", collection_name)
        setattr(cls, "index_name", index_name)

    class draw_item(DrawList):
        name = base_list_name
        bl_idname = f"draw{base_list_name}"

    def draw_list(
        layout: bpy.types.UILayout,
        context: bpy.types.Context,
    ):
        collection_base, _collection, _index = get_collection_props_from_context(
            context, base_path, collection_name, index_name
        )

        row = layout.row()
        row.template_list(
            draw_item.bl_idname, draw_item.name, collection_base, collection_name[-1], collection_base, index_name[-1]
        )

        column = row.column()
        addrm_box = column.box()
        addrm_box.emboss = "NORMAL"
        addrm_box.operator(col_add.bl_idname, text="", icon="ADD")
        addrm_box.operator(col_remove.bl_idname, text="", icon="REMOVE")

        mv_box = column.box()
        mv_box.emboss = "NORMAL"
        mv_box.operator(col_move.bl_idname, text="", icon="TRIA_UP").direction = "UP"
        mv_box.operator(col_move.bl_idname, text="", icon="TRIA_DOWN").direction = "DOWN"

    return col_add, col_remove, col_move, draw_item, draw_list
