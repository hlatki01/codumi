"""Speech notifications keep real actions and a shaped click-through silhouette."""
from pathlib import Path
import tempfile
import tkinter as tk
from unittest.mock import patch

from app import App
from i18n import LANGUAGE_NAMES
import desktop

with tempfile.TemporaryDirectory() as folder:
    app=App(demo=True,preferences_path=Path(folder)/'prefs.json')
    app.root.after_cancel(app.hover_id)
    try:
        app.reduced=True
        for language in LANGUAGE_NAMES:
            app.select_language(language)
            app.close_menu()
            app.hide_tray(immediate=True)
            for pet_y in (20,300,680):
                app.pet_x,app.pet_y=700,pet_y
                for kind in ('complete','error','waiting'):
                    app.toast_queue=[(kind,app.selected,'fictional-project-with-a-long-name')]
                    with patch.object(app,'work_area',return_value=(0,0,1024,768)):
                        app.show_next_notice()
                    app.root.update()
                    window=app.toast
                    assert window and window.winfo_ismapped()
                    x,y=window.winfo_x(),window.winfo_y()
                    width,height=window.winfo_width(),window.winfo_height()
                    assert 12<=x and x+width<=1012 and 12<=y and y+height<=756
                    body=next(w for w in window.winfo_children() if isinstance(w,tk.Button) and w.cget('text')!='×')
                    assert body.cget('text')==app.t('speech_'+kind,project='fictional-project-with-a-long-name')
                    assert body.winfo_height()>=body.winfo_reqheight(),(language,kind)
                    assert not desktop.contains(window,x,y)
                    assert not desktop.contains(window,x+width-1,y+height-1)
                    above=pet_y!=20
                    geometry=desktop.speech_placement(app.pet_x,pet_y,(0,0,1024,768),width,height)
                    assert geometry["above"]==above
                    if above:
                        assert y+height<pet_y and geometry["base"]<geometry["tip"]
                    tail_x=round(geometry["tip"]*.75+geometry["base"]*.25)
                    tail_y=height-3 if above else 3
                    assert desktop.contains(window,x+tail_x,y+tail_y),(language,above)
                    if kind=='complete':
                        body.invoke()
                        assert app.toast is None and app.tray.details
                        app.tray.details=False
                    else:
                        close=next(w for w in window.winfo_children() if isinstance(w,tk.Button) and w.cget('text')=='×')
                        close.invoke()
                        assert app.toast is None
        for area,pet in [((-1280,0,0,720),(-90,640)),((0,0,640,480),(15,20))]:
            p=desktop.speech_placement(*pet,area,300,104)
            assert area[0]+12<=p['x'] and p['x']+p['width']<=area[2]-12
            assert area[1]+12<=p['y'] and p['y']+p['height']<=area[3]-12
    finally: app.close(immediate=True)
print('Speech UI OK: six languages, three messages, top/bottom tails, monitor edges, hit regions, close and session action.')
