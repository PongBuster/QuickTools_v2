import bpy
import gpu
from bpy_extras import view3d_utils
from mathutils import Vector
from bpy.props import IntProperty, FloatProperty, BoolProperty, EnumProperty

def to3d(context, pos2d): # helper function to convert 2d point to 3d
    return view3d_utils.region_2d_to_location_3d(context.region, context.space_data.region_3d, 
          pos2d, (0,0,0))
          
def to2d(context, pos3d): # helper function to convert 3d point to 2d
    return view3d_utils.location_3d_to_region_2d(context.region, context.space_data.region_3d, pos3d)

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


class alignOperator(bpy.types.Operator):
    arg: bpy.props.IntProperty()
    bl_idname = "quicktools.align_points"
    bl_label = "Align Selection"
    bl_options = {'REGISTER', 'UNDO'}
    
    selectedPoint = None
    selected_points = []
    align : IntProperty(default=0)

    @classmethod
    def description(cls, context, properties):
        match properties.align:
            case 1:
                return "Align selected points horizontally to clicked selected point.\nSHIFT to keep relative offsets"
            case 2: 
                return "Align selected points vertically to clicked selected point.\nSHIFT to keep relative offsets"
            
        return "Converge selected points to clicked selected point.\nSHIFT to keep relative offsets"

    @classmethod
    def poll(self, context):
        return (context.mode == 'SCULPT_GPENCIL' or context.mode == 'EDIT_GPENCIL')
    
    def modal(self, context, event):
        
        self.shift_key = event.shift
        
        if event.type == "MOUSEMOVE":
            pos = view3d_utils.region_2d_to_location_3d(context.region, context.space_data.region_3d, 
                (event.mouse_region_x, event.mouse_region_y), (0,0,0))

            self.selectedPoint = None
            gp = context.active_object.data
            
            for lr in gp.layers:
                if not lr.lock and not lr.hide:  #Respect layer locking and visibility
                    for fr in ([fr for fr in lr.frames if fr.select or fr == lr.active_frame] if gp.use_multiedit else [lr.active_frame]):    #Respect multiframe editing settings
                        for s in fr.strokes:
                                for p in s.points:
                                    v = Vector((pos[0] - p.co[0], 0, pos[2] - p.co[2]))
                                    if v.length < 0.04:
                                        self.selectedPoint = p
                                        break
                                                        

            if self.selectedPoint:
               context.window.cursor_modal_set("CROSSHAIR")
            else:
                context.window.cursor_modal_set("PAINT_CROSS")

        elif event.type == "LEFTMOUSE":
            context.window.cursor_modal_restore()
            context.window.cursor_modal_restore()

            if self.selectedPoint:
                if self.shift_key:
                    vOffset = Vector((99999, 0, 99999))
                    for p in self.selected_points:
                        if p == self.selectedPoint: continue
                        if self.align == 1:
                            v = Vector((self.selectedPoint.co[0] - p.co[0], 0, 0))
                        elif self.align == 2:
                            v = Vector((0, 0, self.selectedPoint.co[2] - p.co[2]))
                        else:
                            v = Vector((self.selectedPoint.co[0] - p.co[0], 0, self.selectedPoint.co[2] - p.co[2]))
                        if v.length < vOffset.length:
                            vOffset = v

                for p in self.selected_points:
                    if p == self.selectedPoint: continue
                    if self.align == 0 or self.align == 1:
                        p.co[0] = self.selectedPoint.co[0] if not self.shift_key else p.co[0] + vOffset.x
                    if self.align == 0 or self.align == 2:
                        p.co[2] = self.selectedPoint.co[2] if not self.shift_key else p.co[2] + vOffset.z
                    
                return {'FINISHED'}
            return {'CANCELLED'}
            
        elif event.type in {'RIGHTMOUSE', 'ESC'}:
            context.window.cursor_modal_restore()

            return {'CANCELLED'}
        
        return {'RUNNING_MODAL'}    
    
    def execute(self, context):
        self.selected_points = get_selected_points(context)
        context.window.cursor_modal_set("PAINT_CROSS")
        context.window_manager.modal_handler_add(self)
        
        return {'RUNNING_MODAL'}

    def invoke(self, context, event):
        self.shift_key = event.shift
        return self.execute(context)                

class pointAlignMenu(bpy.types.Menu):
    bl_label = "Align"
    bl_idname = "GPENCIL_MT_point_align_menu"

    def draw(self, context):
        self.layout.operator(alignOperator.bl_idname, text="Horizontal").align=1
        self.layout.operator(alignOperator.bl_idname, text="Vertical").align=2
        self.layout.separator()
        self.layout.operator(alignOperator.bl_idname, text="Converge").align=0
    
    
def align_menu_func(self, context):
    self.layout.menu(pointAlignMenu.bl_idname)

def register():
    cls = bpy.types.VIEW3D_MT_edit_gpencil_point
    omenu = next(iter([f for f in cls._dyn_ui_initialize() if f.__name__ == align_menu_func.__name__]),None)
    if not omenu:
        cls.append(align_menu_func)
        
#    bpy.types.VIEW3D_MT_edit_gpencil_point.append(align_menu_func)
