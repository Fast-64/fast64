from .classes import CFileExport


def ExportCFile(context, filename, use_floats, use_tabs, use_cscmd):
    ex = CFileExport(context, use_floats, use_tabs, use_cscmd)
    return ex.ExportCFile(filename)
