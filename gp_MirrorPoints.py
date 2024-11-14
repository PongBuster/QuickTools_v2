import bpy
import gpu
from bpy_extras import view3d_utils
from mathutils import Vector
from bpy.props import IntProperty, FloatProperty, BoolProperty, EnumProperty

def get_selected_points(context):
    if context.active_object.type != 'GPENCIL':
        return []
    gp = context.active_object.data
    return [p
        for lr in gp.layers
            if not lr.lock and not lr.hide  #Respect layer locking and visibility
                for fr in ([fr for fr in lr.frames if fr.select or fr == lr.active_frame] if gp.use_multiedit else [lr.active_frame])    #Respect multiframe editing settings
                    for s in fr.strokes
                        if s.select
                            for p in s.points
                                if p.select]


class mirrorOperator(bpy.types.Operator):
    arg: bpy.props.StringProperty()
    
    bl_idname = "quicktools.mirror"
    bl_label = "Mirror Selection"
    bl_options = {'REGISTER', 'UNDO'}
    
    mirror : IntProperty(default=0)
    
    shift_key = False

    @classmethod
    def description(cls, context, properties):
        if properties.mirror == 1:
            txt = "Mirror vertically.\nShift to duplicate selection first."
        else:
            txt = "Mirror horizontally.\nShift to duplicate selection first."
        
        return txt

    @classmethod
    def poll(self, context):
        return (context.mode == 'SCULPT_GPENCIL' or context.mode == 'EDIT_GPENCIL')
    
    def invoke(self, context, event):
        self.shift_key = event.shift
        return self.execute(context)

    def execute(self, context):
        prev_mode = context.mode
        bpy.ops.object.mode_set(mode='EDIT_GPENCIL')
        if self.shift_key:
            bpy.ops.gpencil.duplicate_move()
            
        if self.mirror == 0:
            bpy.ops.transform.mirror(orient_type='GLOBAL',
                orient_matrix=((1, 0, 0), (0, 1, 0), (0, 0, 1)),
                orient_matrix_type='GLOBAL',
                constraint_axis=(True, False, False))
        else:
            bpy.ops.transform.mirror(orient_type='GLOBAL',
                orient_matrix=((1, 0, 0), (0, 1, 0), (0, 0, 1)),
                orient_matrix_type='GLOBAL',
                constraint_axis=(False, False, True))
        bpy.ops.object.mode_set(mode=prev_mode)
            
        return {'FINISHED'}
