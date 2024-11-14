bl_info = {
    "name": "PaintInsideColor",
    "author": "PongBuster",
    "version": (1, 0),
    "blender": (2, 80, 0),
    "location": "View3D > Sidebar (N)",
    "description": "Draw polygon in region color.",
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
from math import copysign
import gpu

startend_points = []

def s2lin(x): # convert srgb to linear
    a = 0.1
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

def cmp(clr1, clr2):
    delta = 0.06
    return abs(clr1[0] - clr2[0]) < delta and abs(clr1[1] - clr2[1]) < delta and abs(clr1[2] - clr2[2]) < delta

def convert_mouse_region_to_view(context, region_x, region_y):
    region = context.region.view2d
    ui_scale = context.preferences.system.ui_scale
    x, y = region.region_to_view(region_x, region_y)
    return x / ui_scale, y / ui_scale

def getPixel(X, Y):
    fb = gpu.state.active_framebuffer_get()
    screen_buffer = fb.read_color(X, Y, 1, 1, 3, 0, 'FLOAT')

    rgb_as_list = screen_buffer.to_list()[0]

    R = rgb_as_list[0][0]
    G = rgb_as_list[0][1]
    B = rgb_as_list[0][2]

    return R, G, B

def draw_callback_px(self, context): # callback to draw polygon real time
    
    # 50% alpha, 2 pixel width line
    shader = gpu.shader.from_builtin('UNIFORM_COLOR')
    gpu.state.blend_set('ALPHA')
    gpu.state.line_width_set(2.0)

#    if self.will_close:
#        draw_circle_2d( self.mousePath[0], (1, 0, 0, 1), 10)

    batch = batch_for_shader(shader, 'LINE_STRIP', {"pos": self.mousePath})
    shader.uniform_float("color", (1.0, 0.0, 0.0, 1.0))
    batch.draw(shader)

    batch = batch_for_shader(shader, 'LINE_STRIP', {"pos": self.tracePath})
    shader.uniform_float("color", (1.0, 0.8, 1.0, 1.0))
    batch.draw(shader)
    
    # restore opengl defaults
    gpu.state.line_width_set(1.0)
    gpu.state.blend_set('NONE')


class PaintInsideColorOperator(bpy.types.Operator):
    """Draw polygon with on screen color.
Left click to draw polygon. SPACE/ENTER/MIDDLEMOUSE to add as new stroke.
Right click/ESC to finish.

Brush color is used as the FILL color, secondary_color is used as the STROKE color.
"""

    bl_idname = "quicktools.paintinsidecolor"
    bl_label = "PaintInsideColor"
    bl_options = {'REGISTER', 'UNDO' }
    
    maskColor = None
    mousePath = []
    tracePath = []
    will_close = close = False
    mousePressed = False
    state = 0
    
    @classmethod
    def poll(self, context):
        return (context.mode == 'PAINT_GPENCIL')

    def xyz(self, context):
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
                newStroke.points.add( len(self.mousePath) )
                for idx, pt in enumerate(self.mousePath):
                    newStroke.points[idx].co = to3d(context, pt)
                    newStroke.points[idx].vertex_color = vertexColor
                newStroke.use_cyclic = self.close
                newStroke.uv_scale = 1

        self.mousePath.clear()
        
        bpy.ops.ed.undo_push(message = 'Added PaintInsideColor')
        
        context.area.tag_redraw()

    
    def getImgPixel(self, X, Y):
        context = bpy.context
        offset = int(self.width * (Y + context.area.y) * 4 + (X + context.area.x) * 4)
        
        if offset + 3 >= len(self.pixelBuffer) or offset < 0:
            print("ERROR: " + str(X) + ", " + str(Y) + " out of bounds")
            return 0, 0, 0
        
        R, G, B = self.pixelBuffer[offset:offset + 3]
        
        return R, G, B
    
    def onEdge(self, dx, dy, maskColor):
        for y in range(3):
            for x in range(3):
                clr = self.getImgPixel(dx + x - 1, dy + y - 1)
                if not cmp(clr, maskColor):
                    return True
        return False
        
    
    def modal(self, context, event):
        context.area.tag_redraw()
        
        if self.state == 0: # TAKE BLENDER INTERFACE SCREENSHOT
            
            self.viewport_info = gpu.state.viewport_get()
            self.width = self.viewport_info[2]
            self.height = self.viewport_info[3]
            self.framebuffer = gpu.state.active_framebuffer_get()

            self.pixelBuffer = self.framebuffer.read_color(0, 0, self.width, self.height, 4, 0, 'FLOAT')
            self.pixelBuffer.dimensions = self.width * self.height * 4

            self.framebuffer_image = bpy.data.images.new("color_buffer_copy" , 32, 32, float_buffer=True)
            self.framebuffer_image.scale(self.width, self.height)
            self.framebuffer_image.pixels.foreach_set(self.pixelBuffer)
            self.framebuffer_image.save(filepath="c:\\tmp\\x.png")
            
            self.state = 1
            
        else: # PROCESS NORMALLY
            
            if event.type == 'LEFTMOUSE':
                if event.value == 'PRESS':
                    self.mousePressed = True
                    
                    if self.maskColor == None:
                        self.maskColor = self.getImgPixel(event.mouse_region_x, event.mouse_region_y)
                        self.mousePath.append((event.mouse_region_x, event.mouse_region_y))
                else:
                    self.mousePressed = False
                    
            elif event.type == 'MOUSEMOVE':
                
                if self.mousePressed:
                    clr = self.getImgPixel(event.mouse_region_x, event.mouse_region_y)
                    
                    hdrtxt = "X: {} Y: {} Match: {}".format(event.mouse_region_x, event.mouse_region_y, cmp(clr, self.maskColor))
                    context.area.header_text_set( hdrtxt )
                    
                    if cmp(clr, self.maskColor):
                        self.mousePath.append((event.mouse_region_x, event.mouse_region_y))
                    else:
                        lastPoint = self.mousePath[-1:][0] 
                        vectorToMouse = Vector( (event.mouse_region_x - lastPoint[0], event.mouse_region_y - lastPoint[1]) )
                        
                        vtmn = vectorToMouse.normalized()
                        
                        nextPoint = (lastPoint[0] + vtmn.x, lastPoint[1]+ vtmn.y)
                        nextPointColor = self.getImgPixel(nextPoint[0], nextPoint[1])
                        if cmp(nextPointColor, self.maskColor) and self.onEdge(nextPoint[0], nextPoint[1], self.maskColor):
                            self.mousePath.append((nextPoint[0], nextPoint[1]))
                        else:
                            nextPoint = (lastPoint[0] + vtmn.x, lastPoint[1])
                            nextPointColor = self.getImgPixel(nextPoint[0], nextPoint[1])
                            if cmp(nextPointColor, self.maskColor) and self.onEdge(nextPoint[0], nextPoint[1], self.maskColor):
                                self.mousePath.append((nextPoint[0], nextPoint[1]))
                            else:
                                nextPoint = (lastPoint[0], lastPoint[1] + vtmn.y)
                                nextPointColor = self.getImgPixel(nextPoint[0], nextPoint[1])
                                if cmp(nextPointColor, self.maskColor) and self.onEdge(nextPoint[0], nextPoint[1], self.maskColor):
                                    self.mousePath.append((nextPoint[0], nextPoint[1]))

                        
#                        for i in range(int(vectorToMouse.length)):
#                            pt = vectorToMouse.normalized() * i
#                            
#                            nextPoint = Vector(lastPoint) + pt
#                            
##                            if cmp(self.getImgPixel(nextPoint.x, nextPoint.y), self.maskColor):
##                                self.mousePath.append((nextPoint.x, nextPoint.y))
#                            
#                            nextPointColor = self.getImgPixel(nextPoint.x, nextPoint.y)
#                            
#                            if cmp(nextPointColor, self.maskColor):
#                                if self.onEdge(nextPoint.x, nextPoint.y, self.maskColor):
#                                    self.mousePath.append((nextPoint.x, nextPoint.y))
#                                    lastPoint = self.mousePath[-1:][0] 
#                            elif self.onEdge(lastPoint[0] + pt[0], lastPoint[1], self.maskColor):
#                                self.mousePath.append((lastPoint[0] + pt[0], lastPoint[1]))
#                            elif self.onEdge(lastPoint[0], lastPoint[1] + pt[1], self.maskColor):
#                                self.mousePath.append((lastPoint[0], lastPoint[1] + pt[1]))
                            
                        
                    
            elif event.type in {'SPACE', 'ENTER', 'MIDDLEMOUSE'} and event.value == 'RELEASE':
                self.xyz(context)        
                return {'RUNNING_MODAL'}

            elif event.type in {'RIGHTMOUSE', 'ESC'}:
                context.window.cursor_modal_restore()
                context.area.header_text_set(None)
                bpy.types.SpaceView3D.draw_handler_remove(self._handle, 'WINDOW')
                context.area.tag_redraw()
                del(self.pixelBuffer)
                return {'FINISHED'}

        return {'RUNNING_MODAL'}
    
    def execute(self, context):
        self.mousePath = []
        self.tracePath = []
        self.maskColor = None

        if context.area.type == 'VIEW_3D':
            self._handle = bpy.types.SpaceView3D.draw_handler_add(draw_callback_px, (self, context), 'WINDOW', 'POST_PIXEL')                    
            context.window_manager.modal_handler_add(self)
            context.window.cursor_modal_set("PAINT_BRUSH")
            
            return {'RUNNING_MODAL'}
        else:
            self.report({'WARNING'}, "View3D not found, cannot run operator")
            return {'CANCELLED'}            
    
""" class PGP_PT_sidebarPaintInsideColorPanel(bpy.types.Panel):
    bl_label = "PaintInsideColor"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Grease Pencil"

    def draw(self, context):
        layout = self.layout
        row = layout.row()
        row.operator('stroke.PaintInsideColor', text = "PaintInsideColor" ) 
"""

# Register and add to the "view" menu (required to also use F3 search "Modal Draw Operator" for quick access).
#def register():
#    bpy.utils.register_class(PaintInsideColorOperator)

#def unregister():
#    bpy.utils.unregister_class(PaintInsideColorOperator)

if __name__ == "__main__":
#    bpy.utils.unregister_class(PaintInsideColorOperator)
    bpy.utils.register_class(PaintInsideColorOperator)
#    register()

