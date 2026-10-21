"""Native proof for hover jumps and cursor-tracking eyes on every sprite."""
from pathlib import Path
import tempfile
from types import SimpleNamespace

from app import App
from pet import PETS


def eye_position(app):
    c=app.canvas
    eyes=c.find_withtag("eyes")
    assert eyes
    anchor=next(item for item in c.find_withtag("sprite") if "eyes" not in c.gettags(item))
    ax,ay,*_=c.coords(anchor)
    boxes=[c.coords(item) for item in eyes]
    return (sum(sum(b[::2])/(len(b)//2) for b in boxes)/len(boxes)-ax,
            sum(sum(b[1::2])/(len(b)//2) for b in boxes)/len(boxes)-ay)


with tempfile.TemporaryDirectory() as folder:
    app=App(demo=True,preferences_path=Path(folder)/"preferences.json")
    app.root.after_cancel(app.hover_id)
    try:
        pet=app.pet
        pet.completed_until=0
        pet.update("idle",20)
        app.update_hover(-10000,-10000,20)
        app.update_hover(app.pet_x+32,app.pet_y+32,20.1)
        until=pet.jump_until
        assert abs(until-20.65)<1e-9
        pet.draw(20.375)
        assert -7.01<pet.bob<-6.99
        app.update_hover(app.pet_x+34,app.pet_y+30,20.4)
        assert pet.jump_until==until,"hover must not loop or restart the jump"
        pet.draw(20.8)
        assert pet.bob==0
        app.update_hover(-10000,-10000,20.9)
        app.update_hover(app.pet_x+32,app.pet_y+32,21)
        assert abs(pet.jump_until-21.55)<1e-9
        app.press(SimpleNamespace(x_root=app.pet_x+32,y_root=app.pet_y+32))
        app.update_hover(app.pet_x+32,app.pet_y+32,21.1)
        assert pet.jump_until==0,"drag must cancel hover animation"
        app.drag=None

        for pet_id in PETS:
            pet.pet_id=pet_id
            pet.update("working",99)
            pet.pointer=(1032,1032)
            pet.draw(100)
            pet.draw(100.3)
            right=eye_position(app)
            ids=app.canvas.find_withtag("sprite")
            pet.pointer=(-1000,-1000)
            pet.draw(100.8)
            left=eye_position(app)
            assert right[0]-left[0]>2.8,(pet_id,right,left)
            assert right[1]-left[1]>2,(pet_id,right,left)
            assert ids==app.canvas.find_withtag("sprite"),"tracking must retain canvas objects"
            assert abs(pet.gaze[0])<=1.6 and abs(pet.gaze[1])<=1.2
            pet.hover(False,101)
            pet.hover(True,101.1)
            pet.draw(101.3,reduced=True)
            assert pet.gaze==(0,0) and pet.bob==0
            static={item:app.canvas.coords(item) for item in app.canvas.find_all()}
            pet.pointer=(999,999)
            pet.draw(102,reduced=True)
            assert static=={item:app.canvas.coords(item) for item in app.canvas.find_all()}
            pet.update("sleeping",103)
            pet.draw(103)
            pet.draw(104)
            assert abs(pet.gaze[0])<.001 and abs(pet.gaze[1])<.001
    finally:
        app.close(immediate=True)
print("Pet motion OK: one jump per hover, drag cancellation, all ten pets track both axes, retained items, reduced motion and resting eyes")
