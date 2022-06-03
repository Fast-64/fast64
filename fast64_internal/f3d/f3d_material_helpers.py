import bpy

class F3DMaterial_UpdateLock:
    material: bpy.types.Material = None

    def __init__(self, material: bpy.types.Material):
        self.material = material
        if self.mat_is_locked():
            # Disallow access to locked materials
            self.material = None
        
    def __enter__(self):
        if self.mat_is_locked():
            return None

        self.lock_material()
        return self.material
    
    def __exit__(self, exc_type, exc_value, traceback):
        self.unlock_material()
        if exc_value:
            print("\nExecution type:", exc_type)
            print("\nExecution value:", exc_value)
            print("\nTraceback:", traceback)
    
    def mat_is_locked(self):
        return getattr(self.material, 'f3d_update_flag', True) or not getattr(self.material, 'is_f3d', False)
    
    def lock_material(self):
        if hasattr(self.material, 'f3d_update_flag'):
            self.material.f3d_update_flag = True
    
    def unlock_material(self):
        if hasattr(self.material, 'f3d_update_flag'):
            self.material.f3d_update_flag = False
