bl_info = {
    "name": "Select Points",
    "author": "pongbuster",
    "version": (1, 0),
    "blender": (2, 90, 0),
    "location": "View3D > Sidebar (N)",
    "description": "Select Points on select strokes.",
    "warning": "",
    "doc_url": "",
    "category": "Grease Pencil",
}

import bpy
import blf
import gpu
from bpy_extras import view3d_utils
from mathutils import Vector
import mathutils

class SelectPointsOperator2(bpy.types.Operator):
    """Select points on selected strokes"""
    bl_idname = "quicktools2.selectpoints"
    bl_label = "Select Points"

    @classmethod
    def poll(self, context):
        if not context.active_object: return False
        return (context.active_object.type == 'GPENCIL')

    def execute(self, context):
        gp = context.active_object
        
        for layer in gp.data.layers:
            for stroke in layer.active_frame.strokes:
                for point in stroke.points:
                    print(point.select)
        return {'FINISHED'}
    
    def invoke(self, context, event):
        return execute(self, context)                    
            
