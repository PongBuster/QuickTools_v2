bl_info = {
    "name": "Cut Stroke",
    "author": "pongbuster",
    "version": (1, 1),
    "blender": (2, 90, 0),
    "location": "View3D > Sidebar (N)",
    "description": "Cuts visible strokes on active layer.",
    "warning": "",
    "doc_url": "",
    "category": "Grease Pencil",
}

import bpy
import blf
import gpu
from gpu_extras.batch import batch_for_shader
from bpy_extras import view3d_utils
from mathutils import Vector
import mathutils

def draw_callback_px(self, context):
    
    if self.first:
        lines = []
        lines.append(self.first)
        lines.append(self.mousepos)
        # 50% alpha, 2 pixel width line
        shader = gpu.shader.from_builtin('UNIFORM_COLOR')
        gpu.state.blend_set('ALPHA')
        gpu.state.line_width_set(2.0)
        batch = batch_for_shader(shader, 'LINE_STRIP', {"pos": lines})
        shader.uniform_float("color", (0.0, 0.0, 0.0, 0.5))
        batch.draw(shader)

        # restore opengl defaults
        gpu.state.line_width_set(1.0)
        gpu.state.blend_set('NONE')


class CutStrokeOperator(bpy.types.Operator):
    """Cut visible strokes on the active layer"""
    bl_idname = "view3d.cutstroke_operator"
    bl_label = "Cut strokes Operator"

    @classmethod
    def poll(self, context):
        return (context.mode == 'SCULPT_GPENCIL' or context.mode == 'EDIT_GPENCIL')

    def modal(self, context, event):
        context.area.tag_redraw()
        
        if event.type in {'RIGHTMOUSE', 'ESC'}:
            context.window.cursor_modal_restore()
            bpy.types.SpaceView3D.draw_handler_remove(self._handle, 'WINDOW')
            return {'FINISHED'}
            
        elif event.type == 'MOUSEMOVE':
            self.mousepos = (event.mouse_region_x, event.mouse_region_y)

        elif event.type == 'LEFTMOUSE':
            if self.first == None:
                self.first = (event.mouse_region_x, event.mouse_region_y)
                return {'RUNNING_MODAL'}

            self.last = (event.mouse_region_x, event.mouse_region_y)
            
            area = context.area
            space = area.spaces[0]
            
            for region in area.regions:
                if region.type == 'WINDOW':
                    break
                
            pt1 = view3d_utils.region_2d_to_location_3d(context.region, context.space_data.region_3d, 
                (self.first[0], self.first[1]), (0,0,0))
            pt2 = view3d_utils.region_2d_to_location_3d(context.region, context.space_data.region_3d, 
                (self.last[0], self.last[1]), (0,0,0))
                
            lineA_p1 = Vector((pt1[0], pt1[2]))
            lineA_p2 = Vector((pt2[0], pt2[2]))
                
            gp = context.active_object    
            
            strokes = [s for lr in gp.data.layers for s in lr.active_frame.strokes]
            
            for stroke in strokes:
                cnt = len(stroke.points)
                if cnt <= 1: continue
            
                x = list(range(cnt if stroke.use_cyclic else cnt - 1, 0, -1))
                
                for idx in range(len(x)):
                    p1_idx = x[idx] % cnt
                    p2_idx = x[idx] - 1
                    
                    lineB_p1 = Vector((stroke.points[p1_idx].co[0], stroke.points[p1_idx].co[2]))
                    lineB_p2 = Vector((stroke.points[p2_idx].co[0], stroke.points[p2_idx].co[2]))

                    intersect_point = mathutils.geometry.intersect_line_line_2d(lineA_p1, lineA_p2, lineB_p1, lineB_p2)
                    
                    pdx = x[idx]
                    
                    if intersect_point:
                        
                        stroke.points.add(1)
                    
                        for i in range( len(stroke.points) - 1, pdx, -1):
                            stroke.points[i].uv_rotation = stroke.points[i - 1].uv_rotation
                            stroke.points[i].uv_fill = stroke.points[i - 1].uv_fill
                            stroke.points[i].uv_factor = stroke.points[i - 1].uv_factor
                            
                            stroke.points[i].pressure = stroke.points[i - 1].pressure
                            stroke.points[i].strength = stroke.points[i - 1].strength
                            stroke.points[i].vertex_color = stroke.points[i - 1].vertex_color
                            
                            stroke.points[i].co[0] = stroke.points[i - 1].co[0]
                            stroke.points[i].co[1] = stroke.points[i - 1].co[1]
                            stroke.points[i].co[2] = stroke.points[i - 1].co[2]
                            stroke.points[i].select = stroke.points[i - 1].select
                        
                        stroke.points[pdx].pressure = stroke.points[pdx].pressure
                        stroke.points[pdx].strength = stroke.points[pdx].strength
                        stroke.points[pdx].vertex_color = stroke.points[pdx].vertex_color
                        stroke.points[pdx].uv_rotation = stroke.points[pdx].uv_rotation
                        stroke.points[pdx].uv_fill = stroke.points[pdx].uv_fill
                        stroke.points[pdx].uv_factor = stroke.points[pdx].uv_factor
                        
                        stroke.points[pdx].co[0] = intersect_point.x
                        stroke.points[pdx].co[1] = 0
                        stroke.points[pdx].co[2] = intersect_point.y
                        stroke.points[pdx].select = True

                                            
            self.first = None
            
        return {'RUNNING_MODAL'}

    def invoke(self, context, event):
        if context.area.type == 'VIEW_3D' and context.active_object.type == 'GPENCIL':
            # the arguments we pass the the callback
            args = (self, context)
            # Add the region OpenGL drawing callback
            # draw in view space with 'POST_VIEW' and 'PRE_VIEW'
            self._handle = bpy.types.SpaceView3D.draw_handler_add(draw_callback_px, args, 'WINDOW', 'POST_PIXEL')
            context.window.cursor_modal_set("KNIFE")

            self.first = None
            self.mousepos = None

            context.window_manager.modal_handler_add(self)
            return {'RUNNING_MODAL'}
        else:
            self.report({'WARNING'}, "View3D not found, cannot run operator")
            return {'CANCELLED'}

if __name__ == "__main__":
    bpy.utils.register_class(CutStrokeOperator)