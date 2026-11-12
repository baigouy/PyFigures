"""Read-only prototype canvas context. Never changes normal mouse handling."""
from qtpy.QtCore import QObject, QEvent, Qt
import time

def geometry(panel):
    rect = panel.getRect(all=True)
    width, height = panel.get_raw_size()
    return dict(scene_bounds=dict(x=rect.x(), y=rect.y(), width=rect.width(), height=rect.height()),
                source_size=dict(width=width, height=height),
                rotation_degrees=getattr(panel, 'theta', 0) or 0,
                crop=dict(left=getattr(panel, 'crop_left', 0) or 0, top=getattr(panel, 'crop_top', 0) or 0,
                          right=getattr(panel, 'crop_right', 0) or 0, bottom=getattr(panel, 'crop_bottom', 0) or 0))

class PointerContext(QObject):
    def __init__(self, session):
        super().__init__(session.window)
        self.session = session
        self.canvas = session.window.paint.EZFIG_panel
        self.last = None
        self.panel = None
        self.signature = None
        self.canvas.installEventFilter(self)

    def eventFilter(self, obj, event):
        if event.type() == QEvent.Type.MouseButtonPress and event.button() in (Qt.MouseButton.LeftButton, Qt.MouseButton.RightButton):
            self.capture(event.position())
        return False

    def capture(self, position):
        from .partner_gui import panels
        zoom = float(self.canvas.scale)
        point = position / zoom
        hits = [(gp, ix, p) for gp, ix, p in panels(self.canvas.shapes_to_draw) if p.getRect(all=True).contains(point)]
        self.panel = None
        self.last = dict(timestamp=time.time(), widget_position=[position.x(), position.y()],
                         scene_position=[point.x(), point.y()], canvas_zoom=zoom, valid=False)
        if len(hits) != 1:
            self.last['reason'] = 'Click is outside panels or overlaps multiple panels'
            return
        gp, ix, p = hits[0]
        data = geometry(p)
        self.panel, self.signature = p, data
        self.last.update(panel_id='/'.join(map(str, (*gp, ix))), group_path=list(gp), image_index=ix,
                         geometry=data, panel_position=[point.x()-data['scene_bounds']['x'], point.y()-data['scene_bounds']['y']])
        if data['source_size']['width'] <= 0 or data['source_size']['height'] <= 0:
            self.last['reason'] = 'Raw pixel conversion not verified: missing source size'
            return
        if data['rotation_degrees']:
            # a rotated panel: measured on a real paint ("add an arrowhead where I clicked" on
            # the rotated panel I could not be placed, 2026-11-12)
            from pyfigures.zoom_geometry import scene_to_image_point
            pixel = scene_to_image_point(p, (point.x(), point.y()))
            if pixel is None:
                self.last['reason'] = 'The click is on the rotated panel but outside its image (a corner of the frame)'
                return
            self.last.update(valid=True, image_position=[pixel[0], pixel[1]],
                             coordinate_system='raw image pixels, origin top left (rotation measured)')
            return
        x, y = self.last['panel_position']
        self.last.update(valid=True, image_position=[x*float(p.scale)+data['crop']['left'],
                                                     y*float(p.scale)+data['crop']['top']],
                         coordinate_system='raw image pixels, origin top left')

    def snapshot(self):
        if self.last is None:
            return None
        from .partner_gui import panels
        live = [(gp, ix, p) for gp, ix, p in panels(self.canvas.shapes_to_draw) if p is self.panel]
        result = dict(self.last)
        if self.panel is not None and (len(live) != 1 or geometry(self.panel) != self.signature or
            '/'.join(map(str, (*live[0][0], live[0][1]))) != result['panel_id']):
            result.update(valid=False, reason='Panel changed since click; click again')
            result.pop('image_position', None)
        return result
