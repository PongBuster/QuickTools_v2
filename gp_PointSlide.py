bl_info = {
    "name": "Point Slide",
    "author": "pongbuster",
    "version": (1, 0),
    "blender": (2, 90, 0),
    "location": "View3D > Sidebar (N)",
    "description": "Slides selected points along their normals.",
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

def to2d(context, pos3d): # helper function to convert 3d point to 2d
    return view3d_utils.location_3d_to_region_2d(context.region, context.space_data.region_3d, pos3d)

def draw_callback_px(self, context):

    font_id = 0  # XXX, need to find out how best to get this.
    
    normals = []
    lines = []
    
    delta_2d = to2d( context, Vector((self.delta, 0, 0)) )
    delta_2d.x -= self.origin_2d.x
    
    shader = gpu.shader.from_builtin('UNIFORM_COLOR')
    gpu.state.blend_set('ALPHA')
    gpu.state.line_width_set(2.0)
    
    for pt in self.points_normals:
        if pt[0] == "":
            # 50% alpha, 2 pixel width line
            batch = batch_for_shader(shader, 'LINES', {"pos": normals})
            shader.uniform_float("color", (1.0, 0.0, 0.0, 0.5))
            batch.draw(shader)

            batch = batch_for_shader(shader, 'LINE_STRIP', {"pos": lines})
            shader.uniform_float("color", (0.0, 1.0, 0.0, 0.5))
            batch.draw(shader)

            normals.clear()
            lines.clear()

            continue
        
        p2d = to2d(context, pt[0].co)
        pn = pt[1]
        pn = pn.normalized()
        normals.append( (p2d[0], p2d[1]) )
        normals.append( (p2d[0] + pn[0] * 50, p2d[1] + pn[2] * 50) )

        lines.append( p2d + pn.xz * delta_2d.x)

    if len(lines) > 0:
        # 50% alpha, 2 pixel width line
        batch = batch_for_shader(shader, 'LINES', {"pos": normals})
        shader.uniform_float("color", (1.0, 0.0, 0.0, 0.5))
        batch.draw(shader)

        batch = batch_for_shader(shader, 'LINE_STRIP', {"pos": lines})
        shader.uniform_float("color", (0.0, 1.0, 0.0, 0.5))
        batch.draw(shader)

    normals.clear()
    lines.clear()

    # draw some text
#    blf.position(font_id, 15, 30, 0)
#    blf.size(font_id, 20.0)
#    blf.draw(font_id, "Delta: " + str(self.delta))
#    blf.position(font_id, 5, 80, 0)
#    blf.draw(font_id, "Delta_2d: " + str(delta_2d.x))

    # restore opengl defaults
    gpu.state.line_width_set(1.0)
    gpu.state.blend_set('NONE')


class PointSlideOperator(bpy.types.Operator):
    """Slide selected points along point normals."""
    bl_idname = "object.pointslide_operator"
    bl_label = "Point Slide Operator"
    bl_options = {"REGISTER", "UNDO"}

    delta = 0    
    point_normals = []

    @classmethod
    def poll(self, context):
        return (context.mode == 'SCULPT_GPENCIL' or context.mode == 'EDIT_GPENCIL')

    def modal(self, context, event):
        context.area.tag_redraw()

        if event.type == 'MOUSEMOVE':
            self.delta += (event.mouse_x - event.mouse_prev_x) * 0.001
            
        if event.type == 'LEFTMOUSE':
            bpy.types.SpaceView3D.draw_handler_remove(self._handle, 'WINDOW')
            
            for point_normal in self.points_normals:
                if point_normal[0] == "":
                    continue
                pn = point_normal[1]
                pn = pn.normalized() * self.delta
                point = point_normal[0]
                point.co[0] += pn.x
                point.co[2] += pn.z
        
            return {'FINISHED'}

        elif event.type in {'RIGHTMOUSE', 'ESC'}:
            bpy.types.SpaceView3D.draw_handler_remove(self._handle, 'WINDOW')
            return {'CANCELLED'}

        return {'RUNNING_MODAL'}
    
    def updateNormals(self, context):
        gp = context.active_object

        self.points_normals = []

        for layer in gp.data.layers:
            for stroke in layer.active_frame.strokes:
                all = True
                for point in stroke.points:
                    if point.select == False:
                        all = False
                        break
                num_points = len(stroke.points)
                isegment = True
                for idx, point in enumerate(stroke.points):
                    point1 = stroke.points[ (idx - 1) % num_points ]
                    point2 = stroke.points[idx]
                    point3 = stroke.points[(idx + 1) % num_points]

                    vPoint1 = Vector(point1.co)
                    vPoint2 = Vector(point2.co)
                    vPoint3 = Vector(point3.co)

                    if stroke.use_cyclic == False or all == False:
                        if idx == 0:
                            vPoint1 = vPoint2
                        if idx == num_points - 1:
                            vPoint3 = vPoint2
                    
#                    if idx == 0: # and not stroke.use_cyclic:
#                         point_normal = (vPoint3 - vPoint2).cross((0, 1, 0))
#                    elif idx == num_points - 1: # and not stroke.use_cyclic:
#                         point_normal = (vPoint2 - vPoint1).cross((0, 1, 0))
#                    else:
                    n1 = (vPoint2 - vPoint1).cross((0,1,0))
                    n2 = (vPoint2 - vPoint3).cross((0,1,0))
                    point_normal =  n1 + (n1 - n2 ) / 2

                    if point.select:
                        if not isegment and len(self.points_normals) > 0:
                            self.points_normals.append(("", ""))
                            print("new segment")
                        self.points_normals.append((point, point_normal))
                        isegment = True
                    else:
                        isegment = False
                self.points_normals.append(("", ""))
            
        for n in self.point_normals:
            print(n)

    def invoke(self, context, event):
        if context.area.type == 'VIEW_3D':

            self.origin_2d = to2d(context, Vector((0,0,0)))
            self.updateNormals(context)

            # the arguments we pass the the callback
            args = (self, context)
            # Add the region OpenGL drawing callback
            # draw in view space with 'POST_VIEW' and 'PRE_VIEW'
            self._handle = bpy.types.SpaceView3D.draw_handler_add(draw_callback_px, args, 'WINDOW', 'POST_PIXEL')
            
            context.window_manager.modal_handler_add(self)
            return {'RUNNING_MODAL'}
        else:
            self.report({'WARNING'}, "View3D not found, cannot run operator")
            return {'CANCELLED'}


if __name__ == "__main__":
    bpy.utils.register_class(PointSlideOperator)
