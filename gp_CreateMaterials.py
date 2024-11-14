import bpy

def cmp(clr1, clr2):
    delta = 0.03
    return abs(clr1[0] - clr2[0]) < delta and abs(clr1[1] - clr2[1]) < delta and abs(clr1[2] - clr2[2]) < delta

class createMaterialsFromStrokes(bpy.types.Operator):
    bl_idname = "quicktools.create_materials"
    bl_label = "Create Materials"
    bl_options = {'REGISTER', 'UNDO'}
    
    def execute(self, context):
        gp = context.active_object
        
        for layer in gp.data.layers:
            for frame in layer.frames:
                for stroke in frame.strokes:
                    if len(stroke.points) == 0 : continue
                
                    mat_index = stroke.material_index
                    vertex_color = vertex_color_fill = None
                    if gp.data.materials[mat_index].grease_pencil.show_fill:
                        vertex_color_fill = stroke.vertex_color_fill
                    if gp.data.materials[mat_index].grease_pencil.show_stroke:
                        vertex_color = stroke.points[0].vertex_color     

                    # skip strokes drawn with material color
                    if (vertex_color_fill and stroke.vertex_color_fill[3] == 0) and \
                        (vertex_color and stroke.points[0].vertex_color[3] == 0):
                        continue

                    bFound = False
                    
                    for idx in range(0, len(gp.data.materials)):
                        mat = gp.data.materials[idx].grease_pencil
                        
                        mc = [ mat.color[0], mat.color[1], mat.color[2] ]
                        mf = [ mat.fill_color[0], mat.fill_color[1], mat.fill_color[2] ]

                        if vertex_color and not vertex_color_fill:
                            sc = [ vertex_color[0], vertex_color[1], vertex_color[2] ]
                            if mat.show_stroke and not mat.show_fill and cmp(sc, mc):
                                stroke.material_index = idx
                                bFound = True
                                break
                                
                        if vertex_color_fill and not vertex_color:
                            sf = [ vertex_color_fill[0], vertex_color_fill[1], vertex_color_fill[2]]
                            if mat.show_fill and not mat.show_stroke and cmp(sf, mf):
                                stroke.material_index = idx
                                bFound = True
                                break
                            
                        if vertex_color and vertex_color_fill:
                            sc = [ vertex_color[0], vertex_color[1], vertex_color[2] ]
                            sf = [ vertex_color_fill[0], vertex_color_fill[1], vertex_color_fill[2]]
                            if mat.show_stroke and mat.show_fill and cmp(sc, mc) and cmp(sf, mf):
                                stroke.material_index = idx
                                bFound = True
                                break
                                    
                    if bFound == False:
                        # create new material    
                        gp_mat = bpy.data.materials.new("COLOR" + str( len(gp.data.materials) + 1) )

                        if not gp_mat.is_grease_pencil:
                            bpy.data.materials.create_gpencil_data(gp_mat)
                            if vertex_color:
                                gp_mat.grease_pencil.color = (vertex_color[0], vertex_color[1], vertex_color[2], 1)
                                gp_mat.grease_pencil.show_stroke=True
                            else:
                                gp_mat.grease_pencil.show_stroke=False
                            
                            if vertex_color_fill:
                                gp_mat.grease_pencil.fill_color = (vertex_color_fill[0], vertex_color_fill[1], vertex_color_fill[2], 1) 
                                gp_mat.grease_pencil.show_fill=True
                            else:
                                gp_mat.grease_pencil.show_fill=False

                        gp.data.materials.append(gp_mat)
                        stroke.material_index = len(gp.data.materials) - 1
                        stroke.vertex_color_fill[3] = 0
                        stroke.points[0].vertex_color[3] = 0
                        
        return {'FINISHED'}

def create_materials_menu_func(self, context):
    self.layout.operator(createMaterialsFromStrokes.bl_idname, text="Create Materials")

def register():
    cls = bpy.types.VIEW3D_MT_paint_gpencil
    omenu = next(iter([f for f in cls._dyn_ui_initialize() if f.__name__ == create_materials_menu_func.__name__]),None)
    if not omenu:
        cls.append(create_materials_menu_func)
                        