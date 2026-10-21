"""Small retained canvas avatar; animation never modifies the session model."""
import math

BG = "#0D1522"
MINT = "#4EF0B5"
COLORS = {"working": MINT, "thinking": "#99a4ff", "idle": "#91a8b4",
          "sleeping": "#70859d", "waiting": "#f1cc84", "error": "#ff987e",
          "compacting": "#ba9ff5", "complete": MINT}
PIXELS = ("    bbbbbbbb    ", "  bbbbbbbbbbbb  ", " bbbbbbbbbbbbbb ",
          " bbbbbbbbbbbbbb ", " bbbbeebbeebbbb ", " bbbbeebbeebbbb ",
          " bbbbbbbbbbbbbb ", "  bbbbbbbbbbbb  ", "   bb bbbb bb   ",
          "   bb bb b bb   ", "  bbb bb b bbb  ")


def mix(first, second, amount):
    a = [int(first[i:i+2],16) for i in (1,3,5)]
    b = [int(second[i:i+2],16) for i in (1,3,5)]
    return "#"+"".join(f"{round(x+(y-x)*amount):02x}" for x,y in zip(a,b))


# Each pet has its own silhouette and palette; animation remains shared.
PETS = {
    "notchi": ("codumi", None, "#f0ba94", PIXELS),
    "cat": ("Gato", "#bdcbea", "#efa8c4", (
        "..bb........bb..", "..bab......bab..", "..baabbbbbbaab..", "..bbbbbbbbbbbb..",
        ".bbbbbbbbbbbbbb.", ".bbbbbbbbbbbbbb.", ".bbbeebbbbeebbb.", ".bbbeebbbbeebbb.",
        ".bbbbbbabbbbbbb.", "..bbbbaaabbbbb..", "...bbbbbbbbbb...", "...bbbbbbbbbb...",
        "..bbbbbbbbbbbb..", "..bbbbbbbbbbbb..", "...bbb....bbb...", "...bbb....bbb...")),
    "dog": ("Cachorro", "#d8af85", "#956e55", (
        "................", "..aaa......aaa..", ".aaaabbbbbbaaaa.", ".aaaabbbbbbaaaa.",
        ".aaabbbbbbbbaaa.", ".aaabbbbbbbbaaa.", ".aaabeebbeebaaa.", "..aabeebbeebaa..",
        "...bbbaaaabbb...", "...bbbaeeabbb...", "...bbbaaaabbb...", "....bbbbbbbb....",
        "...bbbbbbbbbb...", "...bbbbbbbbbb...", "...bbb....bbb...", "...aaa....aaa...")),
    "fox": ("Raposa", "#efa16b", "#fff0d8", (
        "..bb........bb..", "..bab......bab..", "..baab....baab..", "..bbbbbbbbbbbb..",
        ".bbbbbbbbbbbbbb.", ".bbbbbbbbbbbbbb.", ".bbbeebbbbeebbb.", "..bbeebbbbeebb..",
        "..aabbbbbbbaaa..", "...aaabbaaaaa...", "....aaaeeaaa....", ".....aaaaaa.....",
        "....bbbbbbbb....", "...bbbbbbbbbb...", "....bbb..bbb....", "....aaa..aaa....")),
    "rabbit": ("Coelho", "#e9e1ee", "#e9a4bf", (
        "...bb......bb...", "...bab....bab...", "...bab....bab...", "...bab....bab...",
        "...bbbbbbbbbb...", "..bbbbbbbbbbbb..", "..bbeebbbbeebb..", "..bbeebbbbeebb..",
        "..bbbbbaabbbbb..", "...bbbbaabbbb...", "....bbbbbbbb....", "....bbbbbbbb....",
        "...bbbbbbbbbb...", "...bbbbbbbbbb...", "..bbbb....bbbb..", "..aaaa....aaaa..")),
    "panda": ("Panda", "#e8eef3", "#526079", (
        "...aaa....aaa...", "..aaaaa..aaaaa..", "..aaabbbbbbaaa..", "...bbbbbbbbbb...",
        "..bbbbbbbbbbbb..", ".bbaaabbbbaaabb.", ".bbaeabbbbaeabb.", ".bbaeabbbbaeabb.",
        ".bbaaabbbbaaabb.", "..bbbbbaabbbbb..", "...bbbbbbbbbb...", "....aaaaaa......",
        "...aabbbbaa.....", "..aaabbbbaaa....", "...aaa..aaa.....", "...aaa..aaa.....")),
    "frog": ("Sapo", "#8fd99c", "#d6eeb5", (
        "................", "...bbbb..bbbb...", "..bbbbbbbbbbbb..", "..bbeebbbbeebb..",
        "..bbeebbbbeebb..", ".bbbbbbbbbbbbbb.", ".bbbbbbbbbbbbbb.", ".bbaaaaaaaaabbb.",
        "..baaeaaaeaabb..", "...aaaaaaaaaa...", "....bbbbbbbb....", "...bbbbbbbbbb...",
        "..bbbbbbbbbbbb..", ".bbbbbbbbbbbbbb.", "..bbb......bbb..", ".aaaa......aaaa.")),
    "owl": ("Coruja", "#bda8de", "#f0dabb", (
        "..bb........bb..", "..bbbbbbbbbbbb..", "..bbbbbbbbbbbb..", ".bbaaaabbaaabbb.",
        ".baaaaaaaaabbbb.", ".baaeaaaeaaabbb.", ".baaeaaaeaaabbb.", ".bbaaaaaaaaabbb.",
        "..bbbbaaabbbbb..", "..bbbbbabbbbbb..", "...bbbbbbbbbb...", "...babbbbbbab...",
        "...baabbbbaab...", "....bbbbbbbb....", ".....aa..aa.....", ".....aa..aa.....")),
    "robot": ("Rob\u00f4", "#9bdae8", "#4b7e99", (
        ".......aa.......", ".......aa.......", "...aaaaaaaaaa...", "..abbbbbbbbbba..",
        "..abbbbbbbbbba..", "..abbaabbaabba..", "..abbeabbeabba..", "..abbeabbeabba..",
        "..abbbbbbbbbba..", "..abbaaabbbbaa..", "...aaaaaaaaaa...", "....abbbbaa.....",
        "...aabbbbaaa....", "..aaabbbbaaaa...", "....aa..aa......", "...aaa..aaa.....")),
    "dragon": ("Drag\u00e3o", "#a6d6ab", "#c5a1e8", (
        "...aa......aa...", "..aabbbbbbbbaa..", "..abbbbbbbbbba..", ".bbbbbbbbbbbbbb.",
        ".bbbbbbbbbbbbbb.", ".bbbeebbbbeebbb.", ".bbbeebbbbeebbb.", "..bbbbbbbbbbbb..",
        "..aabbbbbbbaaa..", "...aaaabbaaaa...", "a...bbbbbbbb...a", "aa.bbbbbbbbbb.aa",
        ".aabbbbbbbbbbaa.", "..aabbbbbbbbaa..", "....bbb..bbb....", "....aaa..aaa....")),
}


def pet_palette(pet_id, state="idle", provider="Codex"):
    _, body, accent, _ = PETS[pet_id]
    body = body or ("#f0ba94" if provider=="Claude" else "#b8ebd7")
    if state=="sleeping":
        body,accent = mix(body,"#71899c",.4),mix(accent,"#71899c",.4)
    return {"b":body,"a":accent,"e":"#173143"}


def pet_preview(master, pet_id):
    import tkinter as tk
    image = tk.PhotoImage(master=master,width=32,height=32)
    palette = pet_palette(pet_id)
    pixels = PETS[pet_id][3]
    top = (32-len(pixels)*2)//2
    for row,line in enumerate(pixels):
        for col,pixel in enumerate(line):
            if pixel not in {" ","."}:
                image.put(palette[pixel],to=(col*2,top+row*2,col*2+2,top+row*2+2))
    return image


def exit_pose(progress, jump_height, sideways):
    phase = min(1,max(0,progress)/.65)
    hop = 4*phase*(1-phase)
    shrink = min(1,max(0,(progress-.7)/.3))
    return sideways*hop,-jump_height*hop,1-shrink*shrink*(3-2*shrink)


class PetAvatar:
    def __init__(self, canvas, pet_id="notchi"):
        self.canvas = c = canvas
        self.pet_id = pet_id if isinstance(pet_id,str) and pet_id in PETS else "notchi"
        self.state = "sleeping"
        self.changed = self.completed_until = self.pressed_until = 0
        self.color = COLORS["sleeping"]
        self.sprite_key = None
        self.configs = {}
        self.last_finger = None
        self.scale = 1
        self.bob = self.shake = 0
        self.hovered = False
        self.jump_until = 0
        self.pointer = (32,32)
        self.gaze = (0,0)
        self.gaze_time = None
        self.clicks = []
        self.reaction_started = None
        self.angle = 0
        self.sprite_coords = {}
        self.outer = c.create_oval(1,1,63,63,fill=BG,outline="#294354",width=1)
        self.inner = c.create_oval(5,5,59,59,fill="#172638",outline="#294354")
        self.arc = c.create_arc(2,2,62,62,start=0,extent=95,style="arc",outline=MINT,width=2,state="hidden")
        self.particles = [c.create_oval(0,0,1,1,fill=MINT,outline="",state="hidden") for _ in range(5)]
        self.spark = [c.create_line(48,13,48,19,fill=MINT,state="hidden"),
                      c.create_line(45,16,51,16,fill=MINT,state="hidden")]
        self.alert = c.create_oval(46,43,61,58,fill=BG,outline=MINT,state="hidden")
        self.symbol = c.create_text(53,50,text="",fill=MINT,font=("Segoe UI",8,"bold"))
        self.sleep = c.create_text(50,15,text="",fill="#839bb1",font=("Segoe UI",7))
        self.thought = c.create_text(49,18,text="",fill=COLORS["thinking"],font=("Segoe UI",9))
        self.keyboard = c.create_line(23,51,42,51,fill="#567582",state="hidden")
        self.finger = c.create_rectangle(26,48,30,50,fill=MINT,outline="",state="hidden")
        self.tears = [c.create_polygon(0,0,0,0,0,0,fill="#86d6ff",outline="",state="hidden") for _ in range(2)]
        self.sad_mouth = c.create_line(28,39,32,36,36,39,fill="#173143",width=1.5,smooth=True,state="hidden")

    def update(self, state, now):
        if state != self.state:
            self.state,self.changed = state,now

    def celebrate(self, now):
        self.completed_until = now+1.6

    def reacting(self, now):
        return self.reaction_started is not None and 0<=now-self.reaction_started<3.3

    def click(self, now):
        if self.reacting(now):
            return
        self.pressed_until = now+.2
        self.clicks = [t for t in self.clicks if 0<=now-t<=1.2]
        self.clicks.append(now)
        if len(self.clicks)>=4:
            self.reaction_started = now
            self.jump_until = self.completed_until = 0
            self.clicks.clear()

    def hover(self, inside, now):
        if inside and not self.hovered and not self.reacting(now):
            self.jump_until = now+.55
        self.hovered = inside

    def sprite(self, state, provider, blink):
        key = state,provider,blink,self.pet_id
        if self.sprite_key == key:
            return
        c = self.canvas
        c.delete("sprite")
        self.sprite_key = key
        self.scale,self.bob,self.shake = 1,0,0
        palette = pet_palette(self.pet_id,state,provider)
        pixels = PETS[self.pet_id][3]
        top = (64-len(pixels)*2)/2
        eye_top = next((row for row,line in enumerate(pixels) if "e" in line),-1)
        for row,line in enumerate(pixels):
            start = 0
            while start<len(line):
                pixel,end = line[start],start+1
                while end<len(line) and line[end]==pixel:
                    end+=1
                if pixel not in {" ","."}:
                    x,y = 16+start*2,top+row*2
                    eye = pixel=="e" and eye_top<=row<=eye_top+1
                    if eye:
                        # Fill the socket so moving eyes never expose the canvas beneath.
                        surround = line[start-1] if start and line[start-1] in {"a","b"} else "b"
                        c.create_polygon(x,y,x+(end-start)*2,y,x+(end-start)*2,y+2,x,y+2,
                                         fill=palette[surround],outline="",tags="sprite")
                    if not (eye and row==eye_top and blink):
                        c.create_polygon(x,y,x+(end-start)*2,y,x+(end-start)*2,y+2,x,y+2,
                                         fill=palette[pixel],outline="",tags=("sprite","eyes") if eye else "sprite")
                start=end
        if state=="error":
            c.create_polygon(30,35,34,35,34,39,30,39,fill="#173143",outline="",tags="sprite")
        self.sprite_coords = {item:tuple(c.coords(item)) for item in c.find_withtag("sprite")}
        c.tag_raise("eyes")

    def configure(self, item, **values):
        if self.configs.get(item)!=values:
            self.canvas.itemconfigure(item,**values)
            self.configs[item]=values

    def draw(self, now, provider="Codex", reduced=False):
        c = self.canvas
        reacting = self.reacting(now)
        elapsed = now-self.reaction_started if reacting else 0
        crying = reacting and 1.25<=elapsed<2.85
        state = "idle" if reacting else ("complete" if now<self.completed_until and self.state!="error" else self.state)
        self.color = COLORS[state] if reduced else mix(self.color,COLORS[state],.22)
        t = 0 if reduced else now
        active = state in {"working","thinking","compacting","complete"}
        pulse = .5+.5*math.sin(t*3) if active else 0
        self.configure(self.outer,outline=mix("#263c4c",self.color,.2+pulse*.2))
        blink = crying or state=="sleeping" or (not reduced and now%4.5<.15)
        self.sprite(state,provider,blink)
        scale = 1-(.07 if now<self.pressed_until and not reduced else 0)
        if state in {"idle","sleeping"}:
            scale+=.018*math.sin(t*1.6)
        bob = math.sin(t*10)*.7 if state=="working" else 0
        if state=="complete" and not reduced:
            bob = -abs(math.sin((self.completed_until-now)*7))*3
        if not reduced and 0<self.jump_until-now<=.55:
            phase = 1-(self.jump_until-now)/.55
            bob -= math.sin(math.pi*phase)*7
        shake = math.sin((now-self.changed)*36)*1.5 if state=="error" and now-self.changed<.55 and not reduced else 0
        angle = 0
        if reacting:
            if not reduced:
                fall = min(1,elapsed/.4) if elapsed<.7 else max(0,1-(elapsed-.7)/.55)
                fall = fall*fall*(3-2*fall)
                angle = fall*math.pi/2
                bob = fall*8
                if crying:
                    shake = math.sin(elapsed*24)*.6
            else:
                scale,bob,shake = 1,0,0
        self.scale,self.bob,self.shake,self.angle = scale,bob,shake,angle
        target = (max(-1.6,min(1.6,(self.pointer[0]-32)/100)),
                  max(-1.2,min(1.2,(self.pointer[1]-32)/100))) if state=="working" and not reduced else (0,0)
        dt = 0 if self.gaze_time is None else max(0,now-self.gaze_time)
        self.gaze_time = now
        ease = 1 if reduced else 1-math.exp(-12*dt)
        self.gaze = tuple(a+(b-a)*ease for a,b in zip(self.gaze,target))
        cosine,sine = math.cos(angle),math.sin(angle)
        eyes = set(c.find_withtag("eyes"))
        for item,points in self.sprite_coords.items():
            transformed = []
            for x,y in zip(points[::2],points[1::2]):
                if item in eyes:
                    x,y = x+self.gaze[0],y+self.gaze[1]
                x,y = (x-32)*scale,(y-32)*scale
                transformed.extend((32+x*cosine-y*sine+shake,32+x*sine+y*cosine+bob))
            c.coords(item,*transformed)
        eye_box = c.bbox("eyes") if crying else None
        for index,tear in enumerate(self.tears):
            self.configure(tear,state="normal" if crying else "hidden")
            if eye_box:
                x = eye_box[0]+2 if index==0 else eye_box[2]-2
                y = eye_box[3]+2+(0 if reduced else (elapsed*2+index*.5)%1*7)
                c.coords(tear,x,y-2,x-1.5,y+1,x,y+2,x+1.5,y+1)
                c.tag_raise(tear)
        self.configure(self.sad_mouth,state="normal" if crying else "hidden")
        if eye_box:
            y = eye_box[3]+7
            c.coords(self.sad_mouth,28,y+2,32,y-1,36,y+2)
            c.tag_raise(self.sad_mouth)
        self.configure(self.arc,state="normal" if active else "hidden",outline=self.color,
                         start=t*(40 if state=="thinking" else 95)%360,extent=215 if state=="complete" else 95)
        count = (5 if state=="complete" else 2) if active and not reduced else 0
        for i,item in enumerate(self.particles):
            if i<count:
                a = math.radians(t*(40 if state=="thinking" else 95)+i*360/count)
                x,y = 32+math.cos(a)*29,32+math.sin(a)*29
                r=1.5+(i%2)*.5
                c.coords(item,x-r,y-r,x+r,y+r)
                self.configure(item,state="normal",fill=self.color)
            else:
                self.configure(item,state="hidden")
        for item in self.spark:
            self.configure(item,state="normal" if state=="working" and not reduced and now%3<.3 else "hidden")
        typing = state=="working" and not reduced
        self.configure(self.keyboard,state="normal" if typing else "hidden")
        self.configure(self.finger,state="normal" if typing else "hidden")
        finger=int(t*10)%2
        if finger!=self.last_finger:
            c.coords(self.finger,26+finger*7,48,30+finger*7,50)
            self.last_finger=finger
        self.configure(self.alert,state="normal" if state in {"waiting","error"} else "hidden",outline=self.color)
        self.configure(self.symbol,text="!" if state=="error" else ("?" if state=="waiting" else ""),fill=self.color)
        self.configure(self.sleep,text=("z" if reduced or int(now/2)%2 else "zz") if state=="sleeping" else "")
        self.configure(self.thought,text="···" if state=="thinking" else "")


    def prepare_exit(self,provider):
        self.sprite("idle",provider,False)
        c = self.canvas
        c.itemconfigure("all",state="hidden")
        c.itemconfigure("sprite",state="normal")
        c.itemconfigure(self.outer,state="normal")
        c.itemconfigure(self.inner,state="normal")
        c.tag_raise("sprite")

    def draw_exit(self,progress,jump_height=72,sideways=0):
        c = self.canvas
        dx,dy,scale = exit_pose(progress,jump_height,sideways)
        for item,radius in ((self.outer,31),(self.inner,27)):
            r = radius*scale
            c.coords(item,120-r,120-r,120+r,120+r)
            c.itemconfigure(item,width=max(.1,scale))
        for item,points in self.sprite_coords.items():
            transformed = []
            for x,y in zip(points[::2],points[1::2]):
                transformed.extend((120+(x-32)*scale+dx,120+(y-32)*scale+dy))
            c.coords(item,*transformed)
