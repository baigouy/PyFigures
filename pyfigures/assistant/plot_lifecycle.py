"""Own only figures belonging to this scene or created by its transaction."""
from contextlib import contextmanager
from functools import wraps
import matplotlib.pyplot as plt
from matplotlib.figure import Figure
from matplotlib._pylab_helpers import Gcf

def scene_figures(window):
    found=set();seen=set()
    def visit(obj):
        if id(obj) in seen:return
        seen.add(id(obj))
        image=getattr(obj,'img',None)
        if isinstance(image,Figure):found.add(image)
        for key in ('content','annotations'):
            values=getattr(obj,key,None)
            if isinstance(values,(list,tuple)):
                for child in values:visit(child)
    try:
        for obj in window.paint.EZFIG_panel.shapes_to_draw:visit(obj)
    except (AttributeError,RuntimeError):pass
    return found

def managed_figures():
    return {manager.canvas.figure for manager in Gcf.get_all_fig_managers()}

@contextmanager
def figure_scope(window=None):
    before=managed_figures();owned=scene_figures(window)
    try:yield
    finally:
        active=scene_figures(window)
        # Never close somebody else's pre-existing analysis window.
        for figure in (owned|(managed_figures()-before))-active:
            plt.close(figure)

def scene_transaction(fn):
    @wraps(fn)
    def wrapped(self,*args,**kwargs):
        window=getattr(self,'window',None)
        if callable(window):window=self
        if window is None:window=self
        with figure_scope(window):return fn(self,*args,**kwargs)
    return wrapped

def close_scene_figures(window):
    for figure in scene_figures(window):plt.close(figure)
