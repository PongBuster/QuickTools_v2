bl_info = {
    "name": "Stroke Hardness",
    "author": "pongbuster",
    "version": (1, 0),
    "blender": (2, 80, 0),
    "location": "View3D > Sidebar (N)",
    "description": "Adjust hardness of selected strokes.",
    "warning": "",
    "doc_url": "",
    "category": "Grease Pencil",
}

import bpy

class hardnessOperator(bpy.types.Operator):
    """Middle mouse to adjust selected strokes' hardness.
Hold CTRL to adjust selected points' pressure(radius) instead.
Hold SHIFT to adjust selected points' strength instead.
Left click to apply"""
    
    bl_idname = "stroke.hardness"
    bl_label = "Stroke Hardness"
    bl_options = {'REGISTER', 'UNDO'}
    selected_points = []
    
    @classmethod
    def poll(self, context):
        return (context.mode == 'SCULPT_GPENCIL' or context.mode == 'EDIT_GPENCIL')
    
    def get_selected_points(self, context):
        gp = context.active_object.data
        return [p
            for lr in gp.layers
                if not lr.lock and not lr.hide  # Respect layer locking and visibility
                    for fr in ([fr for fr in lr.frames if fr.select or fr == lr.active_frame] if gp.use_multiedit else [lr.active_frame])    #Respect multiframe editing settings
                        for s in fr.strokes
                            if s.select
                                for p in s.points
                                    if p.select]

    def modal(self, context, event):
        if event.type == "WHEELUPMOUSE" or event.type == "WHEELDOWNMOUSE":
            incr = -0.01 if event.type == "WHEELDOWNMOUSE" else 0.01

            if event.shift:
                incr *= 2
                for p in self.selected_points:
                    p.strength += incr
                if p: context.area.header_text_set("Strength: %.4f" % p.strength)
            elif event.ctrl:
                for p in self.selected_points:
                    p.pressure += incr * 100
                if p: context.area.header_text_set("Pressure: %.4f" % p.pressure)
            else:
                gp =  context.active_object.data
                for lr in gp.layers:
                    if not lr.lock and not lr.hide:
                        frame_list = [fr for fr in lr.frames if fr.select] if gp.use_multiedit else [lr.active_frame]
                        for fr in frame_list:
                            for s in fr.strokes:
                                if s.select:
                                    s.hardness += incr
                                    context.area.header_text_set("Hardness: %.4f" % s.hardness)
                    
        elif event.type == "LEFTMOUSE":
            context.area.header_text_set(None)
            context.window.cursor_modal_restore()
            return {'FINISHED'}
        
        return {'RUNNING_MODAL'}    

    def execute(self, context):
        self.selected_points = self.get_selected_points(context)    
        context.window.cursor_modal_set("SCROLL_Y")
        context.window_manager.modal_handler_add(self)
        
        return {'RUNNING_MODAL'}
    
    def cancel(self, context):
        context.area.header_text_set(None)
        context.window.cursor_modal_restore()
