bl_info = {
    "name": "Snapigon",
    "author": "PongBuster",
    "version": (1, 4),
    "blender": (2, 80, 0),
    "location": "View3D > Sidebar (N)",
    "description": "Draw polygon while snapping to nearby points of other strokes.",
    "warning": "",
    "doc_url": "",
    "category": "Grease Pencil",
}

import bpy
import mathutils
import operator
from bpy_extras import view3d_utils
from mathutils import Vector
from gpu_extras.presets import draw_circle_2d
from gpu_extras.batch import batch_for_shader
import gpu

startend_points = []

def s2lin(x): # convert srgb to linear
    a = 0.055
    if x <= 0.04045:
        y = x * (1.0 /12.92)
    else:
        y = pow ( (x + a) * (1.0 / (1 + a)), 2.4)
    return y

def to3d(context, pos2d): # helper function to convert 2d point to 3d
    return view3d_utils.region_2d_to_location_3d(context.region, context.space_data.region_3d, 
          pos2d, (0,0,0))
          
def to2d(context, pos3d): # helper function to convert 3d point to 2d
    return view3d_utils.location_3d_to_region_2d(context.region, context.space_data.region_3d, pos3d)
                
def init_startendpoints(context): # create array of start and end points of all visible strokes
    gp = context.active_object
    
    if gp.type != 'GPENCIL':
        return
    
    startend_points.clear()
    
    for lr in gp.data.layers:
        if lr.hide:
            continue
        for fr in lr.frames:
            if fr.frame_number == context.scene.frame_current:
                for s in fr.strokes:
                    if len(s.points) > 0:
                        #startend_points.append(s.points[0])
                        #startend_points.append(s.points[-1])
                        for p in s.points:
                            startend_points.append(p)

def draw_callback_px(self, context): # callback to draw polygon real time
    radius = 10
    col = (1, 0, 0, 1)

    lw = gpu.state.line_width_get()
    gpu.state.line_width_set(2.0)
        
    if self.selectedPoint:
        draw_circle_2d(self.drawPoint, col, radius)

    gpu.state.line_width_set(lw)
    
    pt = []
    
    if len(self.mouse_path) == 0:
        return
    
    for p in self.mouse_path:
        pt.append(to2d(context, p))
        
    if self.mouse_pos:
        pt.append(self.mouse_pos)
    
    shader = gpu.shader.from_builtin('UNIFORM_COLOR')
    gpu.state.blend_set('ALPHA')
    batch = batch_for_shader(shader, 'LINE_STRIP', {"pos": pt})
    
    gpu.state.line_width_set(4.0)
    shader.uniform_float("color", (0.0, 0.0, 0.0, 1.0))
    batch.draw(shader)
    
    gpu.state.line_width_set(2.0)
    shader.uniform_float("color", (0.7, 0.7, 0.7, 0.5))
    batch.draw(shader)
    
    for p in self.mouse_path:
        draw_circle_2d(to2d(context, p), (0.3, 0.3, 0.3, 1), 2)


class snapigonOperator(bpy.types.Operator):
    """Draw polygon with snapping to nearby points of other strokes.
Left click to draw polygon. SPACE/ENTER/MIDDLEMOUSE to add as new stroke.
SHIFT to disable snapping.
CTRL to restrict to horizontal/vertical lines.
Right click/ESC to finish.

Brush color is used as the FILL color, secondary_color is used as the STROKE color.
"""

    bl_idname = "quicktools.snapigon"
    bl_label = "Snapigon"
    bl_options = {'REGISTER', 'UNDO' }
    
    @classmethod
    def poll(self, context):
        return (context.active_object and context.active_object.type == 'GPENCIL')
    
    def modal(self, context, event):
        global startend_points
        
        if event.type == 'MIDDLEMOUSE' and event.shift:
            self.mouse_pos = None
            return {'PASS_THROUGH'}
        
        if event.type == 'WHEELUPMOUSE' or event.type == 'WHEELDOWNMOUSE':
            return {'PASS_THROUGH'}

        context.area.tag_redraw()

        self.mouse_pos = (event.mouse_region_x, event.mouse_region_y)

        if event.ctrl and len(self.mouse_path) > 0:
            p2d = to2d(context, self.mouse_path[-1])
            delta = Vector(p2d) - Vector(self.mouse_pos)
            a = delta.angle((1,0)) * 180 / 3.14159 - 90
            if abs(a) > 45:
                self.mouse_pos = (event.mouse_region_x, p2d[1])
            elif abs(a) <= 45:
                self.mouse_pos = (p2d[0], event.mouse_region_y)
            
        if event.type == "MOUSEMOVE":
            self.selectedPoint = None
            
#            if event.shift: return {'RUNNING_MODAL'}
        
            if len(self.mouse_path) > 2:
                p2d = to2d(context, self.mouse_path[0])
                delta = Vector(p2d) - Vector(self.mouse_pos)
                if delta.length < self.pixels:
                    self.selectedPoint = context, self.mouse_path[0]
                    self.drawPoint = p2d
                    self.close = True

            if self.close:
                context.window.cursor_modal_set("DOT")
            else:
                for p in startend_points:
                    p3d = (p.co[0], p.co[1], p.co[2])
                    p2d = to2d(context, p3d)
                    delta = Vector(self.mouse_pos) - Vector(p2d)
                    
                    if delta.length < self.pixels:
                        self.selectedPoint = p3d
                        self.drawPoint = p2d
                        context.window.cursor_modal_set("PAINT_CROSS")
                        
                        if event.shift: 
                            if self.mouse_path.count(self.selectedPoint) == 0:
                                self.mouse_path.append(self.selectedPoint)
                            
                        break
                    
                if self.selectedPoint == None:
                    context.window.cursor_modal_set("CROSSHAIR")
                    self.close = False
                    
        elif event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            if self.close:
                self.xyz(context)
            else:
                if self.selectedPoint:
                    self.mouse_path.append(self.selectedPoint)
                else:
                    pos = to3d(context, self.mouse_pos)
                    self.mouse_path.append(pos)
            
        elif event.type in {'SPACE', 'ENTER', 'MIDDLEMOUSE'} and event.value == 'RELEASE':
            self.xyz(context)        
            return {'RUNNING_MODAL'}

        elif event.type in {'RIGHTMOUSE', 'ESC'}:
            context.window.cursor_modal_restore()
            bpy.types.SpaceView3D.draw_handler_remove(self._handle, 'WINDOW')
            context.area.tag_redraw()
            return {'FINISHED'}

        return {'RUNNING_MODAL'}
    
    def xyz(self, context):
        global startend_points
        
        C = context

        matIndex = C.active_object.active_material_index
        lineWidth = C.tool_settings.gpencil_paint.brush.size

        clr = C.tool_settings.gpencil_paint.brush.secondary_color
        vertexColor = (s2lin(clr.r), s2lin(clr.g), s2lin(clr.b), 1)
        
        clr = C.tool_settings.gpencil_paint.brush.color 
        fillColor = (s2lin(clr.r), s2lin(clr.g), s2lin(clr.b), 1)
        
        gp = C.active_object
        layer = gp.data.layers[gp.data.layers.active_index]
        
        for frame in layer.frames:
            if frame.frame_number == C.scene.frame_current:
                newStroke = frame.strokes.new()
                newStroke.line_width = lineWidth
                newStroke.material_index = matIndex
                newStroke.vertex_color_fill = fillColor                        
                newStroke.points.add( len(self.mouse_path) )
                for idx, pt in enumerate(self.mouse_path):
                    newStroke.points[idx].co = pt
                    newStroke.points[idx].vertex_color = vertexColor
                newStroke.use_cyclic = self.close
                newStroke.uv_scale = 1

        init_startendpoints(context)
        self.mouse_path.clear()
        self.selectedPoint = None
        self.drawPoint = None
        self.close = False
        
        bpy.ops.ed.undo_push(message = 'Added snapigon')
        
        context.area.tag_redraw()

    def execute(self, context):
        self.mouse_path = []
        self.mouse_path.clear()
        self.pixels = 8
        self.close = False

        init_startendpoints(context)

        if context.area.type == 'VIEW_3D':
            self._handle = bpy.types.SpaceView3D.draw_handler_add(draw_callback_px, (self, context), 'WINDOW', 'POST_PIXEL')                    
            context.window_manager.modal_handler_add(self)
            context.window.cursor_modal_set("CROSSHAIR")
            return {'RUNNING_MODAL'}
        else:
            self.report({'WARNING'}, "View3D not found, cannot run operator")
            return {'CANCELLED'}            
    
""" class PGP_PT_sidebarSnapigonPanel(bpy.types.Panel):
    bl_label = "Snapigon"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Grease Pencil"

    def draw(self, context):
        layout = self.layout
        row = layout.row()
        row.operator('quicktools.snapigon', text = "Snapigon" ) """
