bl_info = {
    "name": "Grease Pencil Text",
    "author": "pongbuster",
    "version": (1, 2),
    "blender": (2, 90, 0),
    "location": "View3D > Sidebar (N)",
    "description": "Add text strokes to Grease Pencil layer.",
    "warning": "",
    "doc_url": "",
    "category": "Grease Pencil",
}

import os
import bpy
import blf
import gpu
import json
from gpu_extras.batch import batch_for_shader
from bpy_extras import view3d_utils

inputData = None

def draw_callback_px(self, context):
    
    redraw = False

    if context.scene.gptext_xpos != self._xoff:
        self._xoff = context.scene.gptext_xpos
        redraw = True
    
    if context.scene.gptext_ypos != self._yoff:
        self._yoff = context.scene.gptext_ypos
        redraw = True

    if context.scene.gptext_cx != self._cx:
        self._cx = context.scene.gptext_cx
        redraw = True
    
    if context.scene.gptext_cy != self._cy:
        self._cy = context.scene.gptext_cy
        redraw = True

    if context.scene.gptext_size != self._size:
        self._size = context.scene.gptext_size
        redraw = True

    if context.scene.align != self._align:
        self._align = context.scene.align
        redraw = True

    if context.scene.gptext != self._text:
        self._text = context.scene.gptext
        redraw = True

    if redraw == True:
        self._strokes = self.buildString(context)
        redraw = False
        
    area = context.area
    space = area.spaces[0]
    
    for region in area.regions:
        if region.type == 'WINDOW':
            break

    shader = gpu.shader.from_builtin('UNIFORM_COLOR')
    gpu.state.blend_set('ALPHA')

    lineWidth = int(context.scene.gptext_thickness / 7)
    gpu.state.line_width_set( lineWidth )
    
    clr = context.tool_settings.gpencil_paint.brush.color
    clr = (s2lin(clr.r), s2lin(clr.g), s2lin(clr.b), 1)
    shader.uniform_float("color", clr)

    for stroke in self._strokes:
        stroke2d = []
        for point in stroke:
            p = view3d_utils.location_3d_to_region_2d(region, space.region_3d, (point[0],0,point[1]))
            stroke2d.append(p)
        batch = batch_for_shader(shader, 'LINE_STRIP', {"pos": stroke2d})
        batch.draw(shader)    
        
    # restore opengl defaults
    gpu.state.line_width_set(1.0)
    gpu.state.blend_set('NONE')
        
def s2lin(x): # convert srgb to linear
    a = 0.055
    if x <= 0.04045:
        y = x * (1.0 /12.92)
    else:
        y = pow ( (x + a) * (1.0 / (1 + a)), 2.4)
    return y

class GPTEXT_OT_DrawTextOperator(bpy.types.Operator):
    """
"""
    bl_label = "Add text strokeks to layer"
    bl_idname = "object.drawtext_operator"
    bl_options = {'REGISTER', 'UNDO_GROUPED'}
    
    _handle = None
    _last_text_drawn = ""
    
    _cx = 0
    _cy = 0
    _xoff = 0
    _yoff = 0
    _size = 0
    _align = 0
    _text = ""

    def getMinMax(self, ch):
        ch_min = 999
        ch_max = -999       
        
        data = charData.get(ch)

        if data == None:
            return ch_min, ch_max

        for ss in data:
            if len(ss) < 2:
                continue
            if isinstance(ss[0], float):
                ch_min = min(ch_min, ss[0])
                ch_max = max(ch_max, ss[0])
            else:
                for pp in ss:
                    ch_min = min(ch_min, pp[0])
                    ch_max = max(ch_max, pp[0])
                
        return ch_min, ch_max

    def getStringWidth(self, string, spacing, defaultWidth):
        width = 0
        for ch in string:
            ch_min, ch_max = self.getMinMax(ch)
            if ch_max != -999:
                if width > 0: width += spacing
                width += abs(ch_max - ch_min)
            else:
                width += defaultWidth - spacing
                
        return width
    
    def buildString(self, context):
        
        stringStrokes = []
        
        xoff = context.scene.gptext_xpos
        yoff = context.scene.gptext_ypos
        scale = context.scene.gptext_size * 0.1
        spacing = context.scene.gptext_cx
        defaultWidth = 1.7
        
        lines = context.scene.gptext.split("\\n")

        for string in lines:
            xoff = context.scene.gptext_xpos
            stringWidth = self.getStringWidth(string, spacing, defaultWidth)

            if context.scene.align == '1':
                xoff -= stringWidth / 2 * scale
            elif context.scene.align == '2':
                xoff -= stringWidth * scale
            
            offset = 0
            
            for idx,ch in enumerate(string):
                ch_min, ch_max = self.getMinMax(ch)
                if ch_max != -999:
                    if idx > 0: offset += spacing
                    strokePoints = []
                    data = charData.get(ch)
                    for stroke in data:
                        if len(stroke) < 2: continue
                        if isinstance(stroke[0], float):
                            px = xoff + (stroke[0] + offset - ch_min) * scale
                            py = yoff + stroke[1] * scale
                            strokePoints.append( (px, py) )
                        else:
                            for point in stroke:
                                if len(point) == 2:
                                    px = xoff + (point[0] + offset - ch_min) * scale
                                    py = yoff + point[1] * scale
                                    strokePoints.append( (px, py) )
                                    
                            stringStrokes.append(strokePoints)
                            strokePoints = []            
                    if len(strokePoints) > 1:
                        stringStrokes.append(strokePoints)
                    offset += abs(ch_max - ch_min)
                else:
                    offset += defaultWidth - spacing
                    
            yoff -= context.scene.gptext_cy * scale
                    
        return stringStrokes
    
    def invoke(self, context, event):
        global charData
        
        # I will eventually enumerate json stroke files in script directory to allow picking
        jsonFile = os.path.join(bpy.utils.script_path_user(), 'addons', 'comical_gptext.json')
        if not os.path.exists(jsonFile):
            print("Missing: " + jsonFile)
            return {'CANCELLED'}
        
        inputData = open(jsonFile, "rt")
        
        charData = json.load(inputData)
        self._strokes = self.buildString(context)
        context.area.tag_redraw()
        x = context.area.x + int(context.area.width / 2)
        y = context.area.y
        context.window.cursor_warp(x,y + 120);
        self._handle = bpy.types.SpaceView3D.draw_handler_add(draw_callback_px, (self, context), 'WINDOW', 'POST_PIXEL')
        return context.window_manager.invoke_props_dialog(self)

    def draw(self, context):
        row = self.layout.row()
        row.prop(context.scene, 'gptext_xpos')
        row.prop(context.scene, 'gptext_ypos')
        row = self.layout.row()
        row.prop(context.scene, 'gptext_cx')
        row.prop(context.scene, 'gptext_cy')
        row = self.layout.row()
        row.prop(context.scene, 'gptext_size')    
        row.prop(context.scene, 'gptext_thickness')
        row = self.layout.row()
        row.prop(context.scene, 'align', expand=True)
        row.prop(context.scene, 'gptext')
        
    def cancel(self, context):
        if self._handle:
            bpy.types.SpaceView3D.draw_handler_remove(self._handle, 'WINDOW')
            self._handle = None
        self.report({'INFO'}, "Cancelled")
        context.area.tag_redraw()
        return None
        
    def execute(self, context):
        if self._handle:
            bpy.types.SpaceView3D.draw_handler_remove(self._handle, 'WINDOW')
            self._handle = None
            
        matIndex = 0
        vertexColor = context.tool_settings.gpencil_paint.brush.color
        fillColor = (1,0,0,1)
        lineWidth = int(context.scene.gptext_thickness)
        
        gp = bpy.context.active_object
        layer = gp.data.layers[gp.data.layers.active_index]
        
        frame = None
        for frame in layer.frames:
            if frame.frame_number == context.scene.frame_current:
                break

        if frame == None or frame.frame_number != context.scene.frame_current:
            self.report({'ERROR'}, "No keyframe added at current frame")
            return {'FINISHED'}        
            
        for stroke in self._strokes:
            newStroke = frame.strokes.new()
            newStroke.line_width = lineWidth
            newStroke.material_index = matIndex
            newStroke.vertex_color_fill = fillColor
            for point in stroke:
                newStroke.points.add( 1 )
                newStroke.points[-1].co = ( point[0], 0, point[1] )
                newStroke.points[-1].vertex_color = (s2lin(vertexColor.r),
                    s2lin(vertexColor.g), s2lin(vertexColor.b), 1)
                    
        #self.report({'INFO'}, "Done")
        return {'FINISHED'}        



classes = [
    GPTEXT_OT_DrawTextOperator
]

def register():
    bpy.types.Scene.gptext = bpy.props.StringProperty ( name = "", description = "User text",  default = "Lorem ipsum dolor sit amet,\\nconsectetur adipiscing elit" )
    bpy.types.Scene.gptext_xpos = bpy.props.FloatProperty( name="X", description="X position", default=0.0)
    bpy.types.Scene.gptext_ypos = bpy.props.FloatProperty( name="Y", description="Y position", default=0.0)

    bpy.types.Scene.gptext_cx = bpy.props.FloatProperty( name="CX", description="Character spacing", default=1)
    bpy.types.Scene.gptext_cy = bpy.props.FloatProperty( name="CY", description="Line spacing", default=5)

    bpy.types.Scene.gptext_size = bpy.props.FloatProperty( name="Size", description="Size", default=1)
    bpy.types.Scene.gptext_thickness = bpy.props.IntProperty( name="Thickness", description="Thickness", default=40)

    enum_items = (('0','','','ANCHOR_LEFT',0),('1','','','ANCHOR_CENTER',1),('2','','','ANCHOR_RIGHT',2))
    bpy.types.Scene.align = bpy.props.EnumProperty(items = enum_items, default=1)

#    for cls in classes:
#        bpy.utils.register_class(cls)

#def unregister():
#    for cls in reversed(classes):
#        bpy.utils.unregister_class(cls)

#if __name__ == "__main__":
#    register()