bl_info = {
    "name": "Geometry Fill",
    "author": "PongBuster",
    "version": (1, 4),
    "blender": (2, 80, 0),
    "location": "View3D > Sidebar (N)",
    "description": "Grease Pencil Geometry Fill",
    "warning": "",
    "doc_url": "",
    "category": "Grease Pencil",
}

import bpy
import math
import mathutils

from mathutils import Vector
from bpy_extras import view3d_utils

# mm = bpy.data.texts['gp_GeometryFill.py'].as_module()

PREC = 4

def s2lin(x): # convert srgb to linear
    a = 0.055
    if x <= 0.04045:
        y = x * (1.0 /12.92)
    else:
        y = pow ( (x + a) * (1.0 / (1 + a)), 2.4)
    return y

def createStroke(points):
    C = bpy.context

    matIndex = C.active_object.active_material_index
    lineWidth = C.tool_settings.gpencil_paint.brush.size

    clr = C.tool_settings.gpencil_paint.brush.color
    vertexColor = (0,0,0,1)
    
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
            newStroke.points.add( len(points ) )
            for idx, pt in enumerate(points):
                newStroke.points[idx].co = (pt[0], 0, pt[1])
                newStroke.points[idx].vertex_color = vertexColor
            newStroke.use_cyclic = True
            newStroke.uv_scale = 1

    bpy.ops.ed.undo_push(message = 'Added GeometryFill')

def isvclose(v1, v2):
    return (v2 - v1).length < 0.0001

def pointInPoly(x,y,poly):
    inside = False
    p1x, p1y = poly[0]
    n = len(poly)
    for i in range(n+1):
        p2x, p2y = poly[i % n]
        if y > min(p1y, p2y):
            if y <= max(p1y, p2y):
                if x <= max(p1x, p2x):
                    if p1y != p2y:
                        xinters = (y-p1y) * (p2x-p1x)/(p2y-p1y)+p1x
                    if p1x == p2x or x <= xinters:
                        inside = not inside
        p1x, p1y = p2x, p2y
    return inside

def getIntersections(edges, edge):
    intersections = []
    for edge1 in edges:
        if edge1 == edge:
            continue
        ix = mathutils.geometry.intersect_line_line_2d(edge1[0], edge1[1], edge[0], edge[1])
        if ix:
            ix = (round(ix[0], PREC), round(ix[1], PREC) )
            start_point = Vector(edge[0])
            d = (start_point - Vector(ix)).length
            intersections.append( (d, ix) )
    intersections.sort()
    return intersections

def getConnectedEdges(edges, pt):
    ret = []
    for edge in edges:
        if edge[0] == pt or (edge[1] == pt):
            ret.append(edge)
    return ret

def fillPoly(context, clicked_spot):
    print("-------------- START --------------")

    gp = bpy.context.active_object

    PREC = 4

    rawedges = []
    polyedges = []
                
    # create list of raw edge data from Grease Pencil strokes        
    for layer in gp.data.layers: 
        for stroke in layer.active_frame.strokes:
            pts = [ ( round(v.co[0], PREC), round(v.co[2], PREC) ) for v in stroke.points]
            for pt1, pt2 in zip(pts, pts[1:]):
                if rawedges.count( (pt1, pt2) ) > 0 or rawedges.count( (pt2, pt1) ) > 0:
                    continue # don't add duplicate edges
                rawedges.append( (pt1, pt2) )
            if stroke.use_cyclic and pt2 != pts[0]:
                rawedges.append( (pt2, pts[0]) )

    # calculate edge intersections of raw edge data and create list of individual unique edges
    for edge in rawedges:
        intersections = getIntersections(rawedges, edge)
        if len(intersections) == 0: # no shared point?
            continue
        elif len(intersections) == 1:
            polyedges.append(edge)
        else:
            pt = edge[0]
            for ix in intersections:
                if ix[1] == pt or ix[1] == (pt[1], pt[0]):
                    continue
                newedge = ( pt, (ix[1][0], ix[1][1]) )
                if polyedges.count( newedge) == 0 and polyedges.count( (newedge[1], newedge[0]) ) == 0:
                    polyedges.append( newedge )
                pt = ( ix[1][0], ix[1][1] )

    # remove duplicate edges if they exist
    polyedges = list(dict.fromkeys(polyedges))

    up_ray = ( (clicked_spot[0], clicked_spot[1]), (clicked_spot[0], 9999) )

    closest_edges = []

    for edge in polyedges:
        ix = mathutils.geometry.intersect_line_line_2d(edge[0], edge[1], up_ray[0], up_ray[1])
        if ix:
            closest_edges.append( [ (ix - Vector(clicked_spot)).length, edge ] ) 

    closest_edges.sort()

    for closest_edge in closest_edges:
        print("Closest edge:" , closest_edge)
        ev = Vector(closest_edge[1][1]) - Vector(closest_edge[1][0])
        cv = Vector(closest_edge[1][1]) - Vector(clicked_spot) 
        
        clockwise = ev.cross(cv) >= 0
        print("clockwise: ", clockwise)
        
        closed_poly = [ closest_edge[1][0] ]
        
        active_edge = closest_edge[1]

        while(1):
            connected_edges = getConnectedEdges(polyedges, active_edge[1])
            
            if len(connected_edges) == 0:
                break
            
            sorted = []
            
            for edge in connected_edges:
                if edge == active_edge or (edge[1], edge[0]) == active_edge:
                    continue
                if edge[1] == active_edge[1]: edge = ( edge[1], edge[0] )
                v1 = Vector(active_edge[1]) - Vector(active_edge[0])
                v2 = Vector(active_edge[1]) - Vector(edge[1])
                cross = v1.cross(v2)
                angle = math.degrees(v1.angle(v2))
                if clockwise:
                    if cross < 0: angle = 360 - angle
                else:
                    if cross >= 0: angle = 360 - angle
                sorted.append( [ angle, edge ] )
            
            sorted.sort()
            
            active_edge = sorted[0][1]
            
            closed_poly.append(active_edge[0])

            if active_edge[1] == closed_poly[0]:
                break
            
            if len(closed_poly) == 9999:
                print("Break limit reached")
                break

        if pointInPoly(clicked_spot[0], clicked_spot[1], closed_poly):
            createStroke(closed_poly)
            break
            
    print("-------------- END --------------")

#fillPoly(bpy.context, (0,0) )

class gp_GeometryFillOperator(bpy.types.Operator):
    """Grease Pencil Geometry Fill"""
    bl_idname = "quicktools.geometry_fill"
    bl_label = "Grease Pencil Geometry Fill"

    @classmethod
    def poll(self, context):
        if not context.active_object: return False
        return (context.active_object.type == 'GPENCIL')

    def modal(self, context, event):
        if event.type  == 'LEFTMOUSE':
            pt = view3d_utils.region_2d_to_location_3d(context.region, context.space_data.region_3d, 
                (event.mouse_region_x, event.mouse_region_y), (0,0,0))
            print("Clicked: ", pt)
            fillPoly(bpy.context, (pt[0], pt[2]) )
            context.window.cursor_modal_restore()
            return {'FINISHED'}
        elif event.type in {'RIGHTMOUSE', 'ESC'}:
            context.window.cursor_modal_restore()
            return {'CANCELLED'}
            
        return {'RUNNING_MODAL'}

    def invoke(self, context, event):
        if context.area.type == 'VIEW_3D' and context.active_object.type == 'GPENCIL':
            context.window.cursor_modal_set("PAINT_BRUSH")
            context.window_manager.modal_handler_add(self)
            return {'RUNNING_MODAL'}
        else:
            self.report({'WARNING'}, "View3D not found, cannot run operator")
            return {'CANCELLED'}

"""        
class VIEW3D_PT_FillPolyPanel(bpy.types.Panel):
    bl_label = "Geometry Fill"
    bl_space_type = "VIEW_3D"
    bl_region_type = "UI"
    bl_category = "Grease Pencil"

    def draw(self, context):
        layout = self.layout
        row = layout.row()
        row.operator(gp_GeometryFillOperator.bl_idname, text = gpGeometryFillOperator.bl_label )

# Class list to register
_classes = [
    gp_GeometryFillOperator,
#    VIEW3D_PT_FillPolyPanel
]

def register():
    for cls in _classes:
        bpy.utils.register_class(cls)
    
def unregister():
    for cls in _classes:
        bpy.utils.unregister_class(cls)
        
if __name__ == "__main__":
    register()
"""