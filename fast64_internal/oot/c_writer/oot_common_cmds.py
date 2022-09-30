# Common Commands
def cmdAltHeaders(altHeaderName: str):
    """Returns the alternate scene layer command"""
    return f"SCENE_CMD_ALTERNATE_HEADER_LIST({altHeaderName})"


def cmdEndMarker():
    """Returns the end marker command, common to scenes and rooms"""
    # ``SCENE_CMD_END`` defines the end of scene commands
    return "SCENE_CMD_END(),\n"
