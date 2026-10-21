"""Floating pet and hover tray. The transcript reader remains independent of UI."""
from __future__ import annotations
import argparse
import ctypes
import json
import logging
import queue
import sys
import tempfile
import threading
import time
from pathlib import Path
import tkinter as tk
from tkinter import messagebox, ttk

import desktop
import terminal
from pet import PetAvatar, PETS, COLORS, MINT, mix, pet_preview
from sessions import Monitor, Session
from companion import Activity, HOTKEYS, project_id
from i18n import APP_NAME, Translator, LANGUAGE_NAMES

BG = "#0D1522"
CARD = "#172638"
BORDER = "#294154"
TEXT = "#edf4fc"
MUTED = "#8ca5be"
KEY = "#ff00ff"


def compact_tokens(count):
    if count>=1_000_000:
        return f"{count//100_000/10:.1f}".rstrip("0").rstrip(".")+"M"
    if count>=1_000:
        return f"{count//100/10:.1f}".rstrip("0").rstrip(".")+"K"
    return str(count)


def load_preferences(path):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def rounded(canvas, x, y, right, bottom, radius=16, fill=BG, outline=""):
    points = [x+radius,y, right-radius,y, right,y, right,y+radius,
              right,bottom-radius, right,bottom, right-radius,bottom,
              x+radius,bottom, x,bottom, x,bottom-radius, x,y+radius,x,y]
    return canvas.create_polygon(points, smooth=True, splinesteps=24,
                                 fill=fill, outline=outline, width=1)


def overlay_window(window, topmost):
    window.withdraw()
    window.configure(bg=KEY)
    window.overrideredirect(True)
    if desktop.WINDOWS:
        window.attributes("-transparentcolor", KEY)
    desktop.prepare(window, topmost)


class Tooltip:
    def __init__(self, widget, text, app):
        self.widget, self.text, self.app = widget, text, app
        self.timer = self.tip = None
        widget.bind("<Enter>", self.enter, add="+")
        widget.bind("<Leave>", self.hide, add="+")
        widget.bind("<Destroy>", self.hide, add="+")

    def enter(self, _):
        self.hide()
        self.timer = self.widget.after(650, self.show)

    def show(self):
        self.timer = None
        if self.app.menu_open or self.app.closed:
            return
        self.tip = tk.Toplevel(self.app.root)
        overlay_window(self.tip, self.app.topmost)
        label = tk.Label(self.tip, text=self.text, bg="#22344a", fg=TEXT, font=("Segoe UI", 9),
                         padx=10, pady=7, wraplength=240, justify="left")
        label.pack()
        self.tip.update_idletasks()
        area = self.app.work_area()
        width, height = label.winfo_reqwidth(), label.winfo_reqheight()
        x = max(area[0]+8, min(self.widget.winfo_rootx(), area[2]-width-8))
        y = min(self.widget.winfo_rooty()+self.widget.winfo_height()+4, area[3]-height-8)
        self.tip.deiconify()
        desktop.place(self.tip, x, y, width, height)

    def hide(self, _=None):
        if self.timer:
            self.widget.after_cancel(self.timer)
            self.timer = None
        if self.tip:
            self.tip.destroy()
            self.tip = None


class HoverTray:
    def __init__(self, app):
        self.app = app
        self.t = app.t
        self.window = tk.Toplevel(app.root)
        self.window.title(APP_NAME+" — "+self.t("tray_title"))
        overlay_window(self.window, app.topmost)
        self.canvas = tk.Canvas(self.window, bg=KEY, highlightthickness=0)
        self.canvas.place(x=0, y=0, relwidth=1, relheight=1)
        self.details = False
        self.placement = None
        self.rows = {}
        self.keys = []
        self.hovered = None
        self.hover_amounts = {}
        self.filter_active = False
        self.menu_button = self.button("···", app.open_menu, size=16)
        self.close_button = self.button("×", app.close, color=MUTED, size=15)
        Tooltip(self.close_button, self.t("close_tip"), app)
        self.filter_button = self.button(self.t("all")+"  →", self.toggle_filter, MINT, 10)
        self.activity_button = self.button(self.t("activity")+"  →", app.toggle_details, MINT, 9)
        Tooltip(self.menu_button, self.t("menu_tip"), app)
        Tooltip(self.filter_button, self.t("filter_tip"), app)
        Tooltip(self.activity_button, self.t("activity_tip"), app)
        self.session_canvas = tk.Canvas(self.window, bg=BG, highlightthickness=0)
        style = ttk.Style(self.window)
        style.theme_use("clam")
        style.layout("codumi.Vertical.TScrollbar", [
            ("Vertical.Scrollbar.trough", {"sticky": "ns", "children": [
                ("Vertical.Scrollbar.thumb", {"expand": True, "sticky": "nswe"})]})])
        style.configure("codumi.Vertical.TScrollbar", background="#354c63", troughcolor=BG,
                        bordercolor=BG, lightcolor="#354c63", darkcolor="#354c63", arrowsize=0)
        self.scrollbar = ttk.Scrollbar(self.window, command=self.session_canvas.yview,
                                       orient="vertical", style="codumi.Vertical.TScrollbar")
        self.session_canvas.configure(yscrollcommand=self.on_scroll)
        self.session_frame = tk.Frame(self.session_canvas, bg=BG)
        self.session_window = self.session_canvas.create_window(0, 0, anchor="nw", window=self.session_frame)
        self.session_frame.bind("<Configure>", lambda _: self.session_canvas.configure(
            scrollregion=self.session_canvas.bbox("all")))
        self.session_canvas.bind("<MouseWheel>", self.scroll)
        self.empty = tk.Label(self.window, bg=BG, fg=MUTED, justify="left",
                              font=("Segoe UI", 10), anchor="nw")
        self.detail_frame = tk.Frame(self.window, bg=BG)
        self.meta = tk.Label(self.detail_frame, bg=BG, fg=MINT, font=("Segoe UI", 9), anchor="w")
        self.meta.pack(fill="x", pady=(0, 6))
        self.detail_actions=tk.Frame(self.detail_frame,bg=BG)
        self.detail_actions.pack(fill="x",pady=(0,4))
        self.pin_button=tk.Button(self.detail_actions,command=app.toggle_favorite,bg=BG,fg=MINT,
                                  activebackground=CARD,activeforeground=TEXT,relief="flat",
                                  font=("Segoe UI",9),cursor="hand2")
        self.pin_button.pack(side="right")
        self.terminal_button = tk.Button(self.detail_actions,text=self.t("focus_terminal"),
                                         command=app.focus_selected_terminal,bg=CARD,fg=MINT,
                                         activebackground=BORDER,activeforeground=TEXT,relief="flat",
                                         bd=0,padx=8,pady=3,font=("Segoe UI",9),cursor="hand2",takefocus=True)
        self.terminal_button.pack(side="left")
        self.choose_terminal_button = tk.Button(self.detail_frame,text=self.t("choose_terminal"),
                                               command=app.open_terminal_picker,bg=BG,fg=MINT,
                                               activebackground=CARD,activeforeground=TEXT,relief="flat",
                                               bd=0,padx=8,pady=2,font=("Segoe UI",9),cursor="hand2",takefocus=True)
        self.choose_terminal_button.pack(anchor="w",pady=(0,4))
        self.terminal_notice = tk.Label(self.detail_frame,bg=BG,fg=MUTED,justify="left",
                                        anchor="w",font=("Segoe UI",8),wraplength=280)
        self.terminal_notice.pack(fill="x",pady=(0,4))
        tk.Label(self.detail_frame, text=self.t("last_prompt"), bg=BG, fg=MUTED,
                 font=("Segoe UI", 8, "bold"), anchor="w").pack(fill="x", pady=(0, 7))
        self.prompt_label = tk.Label(self.detail_frame, bg=BG, fg=TEXT, justify="left",
                                     anchor="nw", font=("Segoe UI", 10), wraplength=292)
        self.prompt_label.pack(fill="x")
        tk.Label(self.detail_frame, text=self.t("recent_activity"), bg=BG, fg=MUTED,
                 anchor="w", font=("Segoe UI", 8, "bold")).pack(fill="x", pady=(15, 7))
        self.feed_label = tk.Label(self.detail_frame, bg=BG, fg=MUTED, justify="left",
                                   anchor="nw", font=("Segoe UI", 9), wraplength=292)
        self.feed_label.pack(fill="x")
        self.window.bind("<Escape>", lambda _: app.dismiss_tray())
        self.window.bind("<Control-q>", lambda _: app.close())
        self.window.bind("<FocusOut>", lambda _: app.root.after_idle(app.check_keyboard_focus))
        self.window.protocol("WM_DELETE_WINDOW", app.dismiss_tray)

        self.settings_frame = tk.Frame(self.window, bg=BG, padx=8, pady=5)
        self.settings_buttons = {}
        for key, label, command in [
            ("back", "←  "+self.t("back_sessions"), app.close_menu),
            ("pets", self.t("choose_pet"), app.open_pet_picker),
            ("language", self.t("language"), app.open_language_picker),
            ("companion", self.t("companion_settings"), app.open_companion_settings),
            ("sound", self.t("sound"), app.toggle_sound),
            ("topmost", self.t("topmost"), app.toggle_topmost),
            ("focus", self.t("keyboard"), app.focus_panel),
            ("dock", self.t("dock"), app.dock_right),
            ("quit", self.t("quit"), app.close),
        ]:
            button = tk.Button(self.settings_frame, text=label, command=command, anchor="w",
                               bg=BG, fg=COLORS["error"] if key=="quit" else TEXT,
                               activebackground=CARD, activeforeground=TEXT, relief="flat",
                               bd=0, padx=8, pady=2, highlightthickness=1,
                               highlightbackground=BG, highlightcolor=MINT,
                               font=("Segoe UI",10), cursor="hand2", takefocus=True)
            button.pack(fill="x", pady=1)
            self.settings_buttons[key] = button

        self.pet_frame = tk.Frame(self.window,bg=BG,padx=8,pady=5)
        self.pet_previews = {}
        self.pet_buttons = {}
        self.pet_back = tk.Button(self.pet_frame,text="←  "+self.t("back")+"  ·  "+self.t("choose_pet"),
                                  command=app.open_menu,bg=BG,fg=TEXT,activebackground=CARD,
                                  activeforeground=TEXT,relief="flat",bd=0,pady=4,
                                  highlightthickness=1,highlightbackground=BG,highlightcolor=MINT,
                                  anchor="w",font=("Segoe UI",9),cursor="hand2",takefocus=True)
        self.pet_back.grid(row=0,column=0,columnspan=2,sticky="ew",pady=(0,4))
        for index,pet_id in enumerate(PETS):
            preview = pet_preview(self.window,pet_id)
            self.pet_previews[pet_id] = preview
            button = tk.Button(self.pet_frame,text=" "+self.t.pet_name(pet_id),image=preview,compound="left",
                               command=lambda choice=pet_id:app.select_pet(choice),
                               bg=BG,fg=TEXT,activebackground=CARD,activeforeground=MINT,
                               relief="flat",bd=0,padx=4,pady=1,font=("Segoe UI",9),
                               highlightthickness=1,highlightbackground=BG,highlightcolor=MINT,
                               anchor="w",cursor="hand2",takefocus=True)
            button.grid(row=1+index//2,column=index%2,sticky="ew",padx=2,pady=1)
            self.pet_buttons[pet_id] = button
        for column in range(2):
            self.pet_frame.columnconfigure(column,weight=1,uniform="pets")

        self.language_frame = tk.Frame(self.window,bg=BG,padx=8,pady=5)
        self.language_buttons = {}
        for code,label in [("back","←  "+self.t("back")+"  ·  "+self.t("language")),
                           ("auto",self.t("automatic")),*LANGUAGE_NAMES.items()]:
            button = tk.Button(self.language_frame,text=label,anchor="w",
                               command=app.open_menu if code=="back" else lambda choice=code:app.select_language(choice),
                               bg=BG,fg=TEXT,activebackground=CARD,activeforeground=MINT,
                               relief="flat",bd=0,padx=8,pady=2,font=("Segoe UI",10),
                               highlightthickness=1,highlightbackground=BG,highlightcolor=MINT,
                               cursor="hand2",takefocus=True)
            button.pack(fill="x",pady=1)
            self.language_buttons[code] = button

        self.companion_frame=tk.Canvas(self.window,bg=BG,highlightthickness=0)
        self.companion_content=tk.Frame(self.companion_frame,bg=BG,padx=8,pady=5)
        self.companion_window=self.companion_frame.create_window(0,0,anchor="nw",window=self.companion_content)
        self.companion_scroll=ttk.Scrollbar(self.companion_frame,orient="vertical",command=self.companion_frame.yview,style="codumi.Vertical.TScrollbar")
        self.companion_frame.configure(yscrollcommand=self.companion_scroll.set)
        self.companion_scroll.place(relx=1,x=-6,y=0,width=6,relheight=1)
        self.companion_content.bind("<Configure>",lambda _:self.companion_frame.configure(scrollregion=self.companion_frame.bbox("all")))
        self.companion_frame.bind("<Configure>",lambda e:self.companion_frame.itemconfigure(self.companion_window,width=e.width-10))
        self.companion_buttons={}
        for key,command in [("back",app.close_menu),("focus",app.toggle_focus),
                            ("complete",lambda:app.toggle_alert("complete")),
                            ("error",lambda:app.toggle_alert("error")),
                            ("waiting",lambda:app.toggle_alert("waiting")),("hotkey",app.cycle_hotkey)]:
            button=tk.Button(self.companion_content,command=command,bg=BG,fg=TEXT,
                             activebackground=CARD,activeforeground=MINT,relief="flat",anchor="w",
                             font=("Segoe UI",9),padx=6,pady=4,cursor="hand2")
            button.pack(fill="x",pady=1)
            self.companion_buttons[key]=button
        self.hotkey_notice=tk.Label(self.companion_content,bg=BG,fg=COLORS["waiting"],
                                   wraplength=270,justify="left",font=("Segoe UI",8))
        self.hotkey_notice.pack(fill="x")
        self.summary=tk.Label(self.companion_content,bg=BG,fg=MUTED,justify="left",anchor="nw",
                              wraplength=270,font=("Segoe UI",9))
        self.summary.pack(fill="x",pady=(12,0))
        def scroll_companion(event):
            self.companion_frame.yview_scroll(-int(event.delta/120),"units")
            return "break"
        for widget in [self.companion_frame,self.companion_content,self.summary,self.hotkey_notice,*self.companion_buttons.values()]:
            widget.bind("<MouseWheel>",scroll_companion)
        def reveal(button):
            self.companion_frame.update_idletasks()
            top=self.companion_frame.canvasy(0)
            if button.winfo_y()<top or button.winfo_y()+button.winfo_height()>top+self.companion_frame.winfo_height():
                self.companion_frame.yview_moveto(button.winfo_y()/max(1,self.companion_content.winfo_height()))
        for button in self.companion_buttons.values():
            button.bind("<FocusIn>",lambda _,b=button:reveal(b))

        self.terminal_frame = tk.Frame(self.window,bg=BG,padx=8,pady=5)
        tk.Button(self.terminal_frame,text="←  "+self.t("back"),command=app.close_menu,
                  bg=BG,fg=TEXT,activebackground=CARD,activeforeground=MINT,relief="flat",
                  font=("Segoe UI",10),cursor="hand2").pack(anchor="w")
        tk.Label(self.terminal_frame,text=self.t("choose_terminal_tip"),bg=BG,fg=MUTED,
                 wraplength=270,justify="left",font=("Segoe UI",9)).pack(fill="x",pady=6)
        self.bind_terminal_button = tk.Button(self.terminal_frame,text=self.t("confirm_terminal"),
                                              command=app.bind_terminal,bg=CARD,fg=MINT,
                                              activebackground=BORDER,activeforeground=TEXT,
                                              relief="flat",font=("Segoe UI",10),cursor="hand2")
        self.bind_terminal_button.pack(side="bottom",fill="x",pady=(6,0))
        holder=tk.Frame(self.terminal_frame,bg=BG)
        holder.pack(fill="both",expand=True)
        self.terminal_list=tk.Listbox(holder,bg=BG,fg=TEXT,selectbackground=CARD,
                                      selectforeground=MINT,relief="flat",bd=0,highlightthickness=1,
                                      highlightbackground=BORDER,font=("Segoe UI",9),exportselection=False)
        scroll=ttk.Scrollbar(holder,orient="vertical",command=self.terminal_list.yview,
                             style="codumi.Vertical.TScrollbar")
        self.terminal_list.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right",fill="y")
        self.terminal_list.pack(fill="both",expand=True)
        self.terminal_list.bind("<Return>",lambda _:app.bind_terminal())

    def button(self, text, command, color=TEXT, size=10):
        return tk.Button(self.window, text=text, command=command, bg=BG, fg=color,
                         activebackground=CARD, activeforeground=MINT, relief="flat", bd=0,
                         highlightthickness=1, highlightbackground=BG, highlightcolor=MINT,
                         cursor="hand2", font=("Segoe UI", size), takefocus=True)

    def filtered_sessions(self):
        items = self.app.sessions
        if self.filter_active:
            items = [s for s in items if s.display_state() not in {"idle", "sleeping"}]
        rank = {"working": 0, "thinking": 1, "waiting": 2, "error": 3, "compacting": 4, "idle": 5, "sleeping": 6}
        return sorted(items, key=lambda s: (project_id(s) not in self.app.favorites,rank.get(s.display_state(), 5), -s.updated))

    def layout(self):
        p = self.placement
        w, h = p["width"], p["height"]
        origin = 0 if p["side"] == "left" else 12
        card_width = w - 12
        self.menu_button.place(x=origin+card_width-82, y=22, width=30, height=30)
        self.close_button.place(x=origin+card_width-45, y=22, width=27, height=30)
        self.filter_button.place(x=origin+card_width-105, y=92, width=85, height=28)
        self.activity_button.configure(text=self.t("collapse")+"  ←" if self.details else self.t("activity")+"  →")
        self.activity_button.place(x=origin+card_width-119, y=h-46, width=100, height=28)
        list_height = min(222, h - 198)
        self.session_canvas.place(x=origin+20, y=136, width=card_width-49, height=list_height)
        self.session_canvas.itemconfigure(self.session_window, width=card_width-49)
        self.scrollbar.place(x=origin+card_width-26, y=136, width=6, height=list_height)
        if self.details:
            self.detail_frame.place(x=origin+24, y=380, width=card_width-48, height=max(0, h-446))
            self.prompt_label.configure(wraplength=card_width-48)
            self.feed_label.configure(wraplength=card_width-48)
        else:
            self.detail_frame.place_forget()
        desktop.shape(self.window, w, h, p["connector"], p["side"])
        if self.app.menu_open:
            self.filter_button.place_forget()
            self.activity_button.place_forget()
            self.settings_frame.place_forget()
            self.companion_frame.place_forget()
            self.pet_frame.place_forget()
            self.language_frame.place_forget()
            self.terminal_frame.place_forget()
            frame = (self.companion_frame if self.app.companion_open else
                     self.terminal_frame if self.app.terminal_picker_open else
                     self.pet_frame if self.app.pet_picker_open else
                     self.language_frame if self.app.language_picker_open else self.settings_frame)
            frame.place(x=origin+20,y=91,width=card_width-40,height=h-168)
            tk.Misc.lift(frame)
        else:
            self.settings_frame.place_forget()
            self.companion_frame.place_forget()
            self.pet_frame.place_forget()
            self.language_frame.place_forget()
            self.terminal_frame.place_forget()
        self.render()

    def on_scroll(self, first, last):
        self.scrollbar.set(first,last)
        if float(first)<=0 and float(last)>=1:
            self.scrollbar.place_forget()
        elif self.placement:
            p=self.placement
            origin=0 if p["side"]=="left" else 12
            self.scrollbar.place(x=origin+p["width"]-38,y=136,width=6,height=min(222,p["height"]-198))

    def render(self):
        if not self.placement:
            return
        c, p = self.canvas, self.placement
        w, h = p["width"], p["height"]
        origin = 0 if p["side"] == "left" else 12
        end = w-12 if p["side"] == "left" else w
        c.delete("all")
        rounded(c, origin+2, 3, end-1, h-1, 16, "#060d17")
        rounded(c, origin, 0, end-3, h-4, 16, BG, BORDER)
        y = p["connector"]
        points = [end-2,y-12,w,y,end-2,y+12] if p["side"] == "left" else [12,y-12,0,y,12,y+12]
        c.create_polygon(points, fill="#173840", outline=BORDER)
        rounded(c, origin+22, 23, origin+56, 60, 9, "#193237", "#284850")
        c.create_text(origin+39, 41, text="c", fill=MINT, font=("Segoe UI", 20, "bold"))
        c.create_text(origin+70, 34, text=APP_NAME, fill=TEXT, anchor="w", font=("Segoe UI", 16, "bold"))
        c.create_oval(origin+153,30,origin+159,36,fill=MINT,outline="")
        c.create_text(origin+70, 57, text=self.t("tagline"), fill=MUTED, anchor="w", font=("Segoe UI", 9))
        c.create_line(origin+23, 80, end-23, 80, fill=BORDER)
        c.create_text(origin+24, 106, text=self.t("settings") if self.app.menu_open else self.t("recent_sessions"), anchor="w", fill=MUTED, font=("Segoe UI", 9))
        if not self.app.menu_open:
            c.create_text(origin+24,123,text=self.t("pet_session_note"),anchor="w",
                          fill=MUTED,font=("Segoe UI",8))
        c.create_line(origin+23, h-62, end-23, h-62, fill=BORDER)
        active = sum(s.display_state() not in {"idle", "sleeping"} for s in self.app.sessions)
        resting = len(self.app.sessions)-active
        for i, bar in enumerate([6, 12, 9]):
            c.create_rectangle(origin+25+i*5, h-29-bar, origin+28+i*5, h-29, fill="#6b97b2", outline="")
        c.create_text(origin+47, h-35, text=self.t("counts",active=active,resting=resting).replace(" · ","\n"),
                       anchor="w", fill=MUTED, font=("Segoe UI", 8))
        if self.app.warning:
            c.create_text(origin+24, h-74, text=self.t("read_notice"),
                           anchor="w", fill=COLORS["error"], font=("Segoe UI", 8))

    def refresh(self):
        self.companion_buttons["back"].configure(text="←  "+self.t("back"))
        self.companion_buttons["focus"].configure(text=self.t("focus_end") if self.app.focus_until>time.time() else self.t("focus_start"))
        for kind in ("complete","error","waiting"):
            self.companion_buttons[kind].configure(text=self.t("alert_"+kind)+" · "+self.t("enabled" if self.app.alerts[kind] else "disabled"))
        self.companion_buttons["hotkey"].configure(text=self.t("hotkey_choice",name=self.t("disabled") if self.app.hotkey_name=="Off" else self.app.hotkey_name)+"  ↻")
        self.hotkey_notice.configure(text=self.t("hotkey_unavailable") if self.app.hotkey_failed else "")
        self.summary.configure(text=self.app.usage_summary())
        name = self.t("automatic") if self.app.language=="auto" else LANGUAGE_NAMES[self.app.language]
        self.settings_buttons["language"].configure(text=self.t("language_choice",name=name)+"  →")
        for code,button in self.language_buttons.items():
            selected = code==self.app.language
            button.configure(bg=CARD if selected else BG,fg=MINT if selected else TEXT,
                             highlightbackground=MINT if selected else BG)
        self.settings_buttons["pets"].configure(text=self.t("pet_choice",name=self.t.pet_name(self.app.pet.pet_id))+"  →")
        for pet_id,button in self.pet_buttons.items():
            selected = pet_id==self.app.pet.pet_id
            button.configure(bg=CARD if selected else BG,fg=MINT if selected else TEXT,
                             highlightbackground=MINT if selected else BG)
        self.settings_buttons["sound"].configure(text=self.t("sound_off") if self.app.sound else self.t("sound_on"))
        self.settings_buttons["topmost"].configure(text=self.t("topmost_off") if self.app.topmost else self.t("topmost_on"))
        visible = self.filtered_sessions()
        if self.app.selected not in [s.key for s in visible]:
            self.app.selected = visible[0].key if visible else None
        keys = [s.key for s in visible]
        if keys != self.keys:
            for child in self.session_frame.winfo_children():
                child.destroy()
            self.rows, self.hover_amounts = {}, {}
            self.keys = keys
            self.hovered = None
            for s in visible:
                row = tk.Frame(self.session_frame, bg=BG)
                row.pack(fill="x", pady=(0, 7))
                marker = tk.Frame(row, bg=COLORS[s.display_state()], width=3)
                marker.pack(side="left", fill="y", padx=(0, 2), pady=6)
                indicator = tk.Canvas(row, width=24, height=49, bg=BG, highlightthickness=0)
                indicator.pack(side="right")
                button = tk.Button(row, anchor="w", justify="left", relief="flat", bd=0, padx=12,
                                   pady=6, bg=BG, fg=TEXT, activebackground=CARD, activeforeground=TEXT,
                                   highlightthickness=1, highlightbackground=BG, highlightcolor=MINT,
                                   font=("Segoe UI", 10), cursor="hand2",
                                   command=lambda key=s.key: self.app.select_session(key))
                button.pack(side="left", fill="x", expand=True)
                button.bind("<Button-3>", lambda _, key=s.key:self.app.toggle_favorite(key))
                button.bind("<MouseWheel>", self.scroll)
                button.bind("<Enter>", lambda _, key=s.key: setattr(self, "hovered", key))
                button.bind("<Leave>", lambda _: setattr(self, "hovered", None))
                Tooltip(button, self.t("session_tip",project=self.app.project_name(s),provider=s.provider), self.app)
                self.rows[s.key] = (button, marker, indicator)
        for s in visible:
            button, marker, _ = self.rows[s.key]
            state = s.display_state()
            usage = ("≥" if s.tokens_partial else "")+compact_tokens(s.tokens)
            suffix = "  ·  "+self.t("tokens_short",count=usage) if s.tokens else ""
            button.configure(text=f"{'★ ' if project_id(s) in self.app.favorites else ''}{self.app.project_name(s)[:26]}\n{s.provider}  ·  {self.t.state(state)}{suffix}",
                             wraplength=max(100,(self.placement["width"] if self.placement else 364)-114),
                             fg=MUTED if state in {"idle", "sleeping"} else TEXT)
            marker.configure(bg=COLORS[state])
        p = self.placement
        if visible:
            self.empty.place_forget()
        elif p:
            self.empty.configure(text=self.t("no_active") if self.filter_active
                                 else self.t("no_sessions"))
            self.empty.place(x=(24 if p["side"] == "left" else 36), y=150, width=p["width"]-60, height=90)
        session = self.app.current_session()
        self.pin_button.configure(text=self.t("unfavorite" if session and project_id(session) in self.app.favorites else "favorite"))
        self.terminal_button.configure(text=self.t("focus_cursor" if session and session.provider=="Cursor" else "focus_terminal"))
        self.choose_terminal_button.configure(text=self.t("choose_window" if session and session.provider=="Cursor" else "choose_terminal"))
        self.terminal_button.configure(state="normal" if session and self.app.terminal_pending is None else "disabled")
        self.terminal_notice.configure(text=self.t(self.app.terminal_status) if self.app.terminal_status else "")
        duration = max(0, int(time.time() - session.started)) if session else 0
        self.meta.configure(text=(self.t("duration",time=f"{duration//3600:02d}:{duration//60%60:02d}:{duration%60:02d}")
                            + (" · "+("≥" if session.tokens_partial else "")+self.t("tokens",count=session.tokens) if session.tokens else "")) if session else self.t("no_selection"))
        self.prompt_label.configure(text=session.prompt[:120] if session and session.prompt else self.t("no_prompt"))
        self.feed_label.configure(text=self.t.warning(self.app.warning) or "\n".join(
            f"{time.strftime('%H:%M',time.localtime(t))}   {self.t.event(label)[:32]}" for t,label in list(session.events)[-3:])
            if session else (self.t.warning(self.app.warning) or self.t("waiting_activity")))
        self.render()

    def animate(self, now, reduced):
        sessions = {s.key: s for s in self.app.sessions}
        top = self.session_canvas.canvasy(0)
        bottom = top + self.session_canvas.winfo_height()
        for key, (button, _, indicator) in self.rows.items():
            row_y = button.master.winfo_y()
            if row_y + button.winfo_height() < top or row_y > bottom:
                continue
            target = 1 if self.hovered == key else 0
            previous = self.hover_amounts.get(key, 0)
            amount = target if reduced else previous + (target-previous)*.25
            self.hover_amounts[key] = amount
            base = CARD if key == self.app.selected else BG
            color = mix(base, "#203448", amount)
            if button.cget("bg") != color:
                button.configure(bg=color, highlightbackground=BORDER if key==self.app.selected else color)
                indicator.configure(bg=color)
            indicator.delete("all")
            state = sessions[key].display_state()
            if state in {"working", "thinking", "compacting"}:
                indicator.create_oval(3,17,19,33, outline="#294252", width=2)
                indicator.create_arc(3,17,19,33, start=0 if reduced else now*110%360,
                                     extent=120, style="arc", outline=COLORS[state], width=2)
            else:
                indicator.create_text(11,25,text="z" if state=="sleeping" else ("!" if state=="error" else "·"),
                                       fill=COLORS[state],font=("Segoe UI",11))

    def toggle_filter(self):
        self.filter_active = not self.filter_active
        self.filter_button.configure(text=self.t("active")+"  →" if self.filter_active else self.t("all")+"  →")
        self.app.refresh_now()

    def scroll(self, event):
        self.session_canvas.yview_scroll(-int(event.delta/120), "units")
        return "break"


class App:
    def __init__(self, demo=False, preferences_path=None):
        self.preferences_path = preferences_path or Path(__file__).with_name("preferences.json")
        self.preferences = load_preferences(self.preferences_path)
        choice = self.preferences.get("language","auto")
        self.language = choice if isinstance(choice,str) and choice in {"auto",*LANGUAGE_NAMES} else "auto"
        self.t = Translator(None if self.language=="auto" else self.language)
        self.topmost = self.preferences.get("topmost", True) is not False
        self.demo=demo
        favorites=self.preferences.get("favorites",[])
        self.favorites={v for v in favorites if isinstance(v,str) and len(v)==64} if isinstance(favorites,list) else set()
        self.restored_selection=self.preferences.get("selected")
        if not isinstance(self.restored_selection,str): self.restored_selection=None
        alerts=self.preferences.get("alerts",{})
        self.alerts={k:alerts.get(k,True) is not False for k in ("complete","error","waiting")} if isinstance(alerts,dict) else dict.fromkeys(("complete","error","waiting"),True)
        focus=self.preferences.get("focus_until",0)
        self.focus_until=focus if type(focus) in (int,float) and time.time()<focus<time.time()+86400 else 0
        self.activity=Activity(self.preferences.get("activity"))
        profiles=self.preferences.get("window_profiles",{})
        self.window_profiles=profiles if isinstance(profiles,dict) else {}
        self.companion_open=False
        self.toast=None
        self.toast_timer=None
        self.toast_queue=[]
        self.hotkey=desktop.GlobalHotkey()
        self.hotkey_name=self.preferences.get("hotkey","Ctrl+Alt+N")
        if self.hotkey_name not in HOTKEYS: self.hotkey_name="Ctrl+Alt+N"
        self.hotkey_failed=False
        if not demo: self.hotkey_failed=not self.hotkey.set(self.hotkey_name)
        self.last_preferences=None
        self.sound = self.preferences.get("sound") is True
        self.root = tk.Tk()
        self.root.title(APP_NAME+" — "+self.t("tagline"))
        overlay_window(self.root, self.topmost)
        self.canvas = tk.Canvas(self.root, width=64, height=64, bg=KEY, highlightthickness=0, cursor="hand2")
        self.canvas.pack()
        self.pet_tooltip=Tooltip(self.canvas,"",self)
        self.pet = PetAvatar(self.canvas,self.preferences.get("pet_kind","notchi"))
        self.completion_star=self.canvas.create_text(52,13,text="★",fill=MINT,font=("Segoe UI",12),state="hidden",tags="completion_badge")
        self.other_dot=self.canvas.create_oval(44,44,54,54,fill=MINT,outline=BG,state="hidden",tags="other_activity")
        self.other_count=self.canvas.create_text(49,49,text="",fill=BG,font=("Segoe UI",7,"bold"),state="hidden",tags="other_activity")
        self.sessions, self.selected, self.warning = [], None, ""
        self.stopping = threading.Event()
        self.updates = queue.Queue(maxsize=1)
        self.terminal_results = queue.Queue()
        self.terminal_pending = self.terminal_requested = None
        self.terminal_bindings = {}
        self.terminal_choices = []
        self.terminal_picker_open = False
        self.terminal_status = ""
        self.closed = self.menu_open = self.keyboard_mode = self.tray_visible = False
        self.exit_finished = False
        self.exit_id = None
        self.pet_picker_open = self.language_picker_open = False
        self.drag = None
        self.moved = self.drag_suppressed = False
        self.suppress_until = self.leave_at = None
        self.spring = desktop.Spring()
        self.last_tray_frame = None
        self.reduced = desktop.reduced_motion()
        self.last_animation = self.last_motion_check = time.monotonic()
        self.completions = {}
        self.tray = HoverTray(self)
        self.canvas.bind("<ButtonPress-1>", self.press)
        self.canvas.bind("<B1-Motion>", self.move)
        self.canvas.bind("<ButtonRelease-1>", self.release)
        self.canvas.bind("<Button-3>", lambda _: self.open_menu())
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.bind("<Escape>", lambda _: self.dismiss_tray())
        self.root.bind("<Control-q>", lambda _: self.close())
        area = self.work_area()
        saved = self.preferences.get("pet")
        if isinstance(saved, list) and len(saved)==2 and all(type(v) is int for v in saved):
            x, y = saved
        elif type(self.preferences.get("right")) is int and type(self.preferences.get("top")) is int:
            x, y = self.preferences["right"]-64, self.preferences["top"]
        else:
            x, y = area[2]-88, area[1]+(area[3]-area[1]-64)//2
        area = desktop.work_area(self.root, x+32, y+32)
        self.pet_x, self.pet_y = desktop.clamp_pet(x, y, area)
        desktop.place(self.root, self.pet_x, self.pet_y, 64, 64)
        desktop.shape(self.root,64,64)
        if demo:
            now = time.time()
            self.sessions = [Session("demo-claude","Claude","D:/Projects/orbit","working",started=now-940),
                             Session("demo-codex","Codex","D:/Projects/atlas","sleeping",updated=now-600),
                             Session("demo-idle","Claude","D:/Projects/aurora","sleeping",updated=now-700)]
            self.sessions[0].prompt = "Build the floating companion and improve the session tray."
            self.sessions[0].events.extend([(now-22,"Prompt received"),(now-9,"Updating the interface")])
        self.root.deiconify()
        desktop.place(self.root, self.pet_x, self.pet_y, 64, 64)
        self.refresh()
        self.animate()
        self.poll_hover()
        if not demo:
            threading.Thread(target=self.watch,daemon=True,name="transcript-reader").start()

    def work_area(self):
        return desktop.work_area(self.root, getattr(self,"pet_x",None), getattr(self,"pet_y",None))

    def position_tray(self):
        p = desktop.tray_placement(self.pet_x,self.pet_y,self.work_area(),self.tray.details or self.menu_open)
        if (p["pet_x"],p["pet_y"]) != (self.pet_x,self.pet_y):
            self.pet_x,self.pet_y = p["pet_x"],p["pet_y"]
            desktop.place(self.root,self.pet_x,self.pet_y,64,64)
            self.save_preferences()
        self.tray.placement = p
        desktop.place(self.tray.window,p["x"],p["y"],p["width"],p["height"])
        self.tray.layout()
        self.tray.refresh()

    def show_tray(self, focus=False):
        if self.drag or self.closed:
            return
        self.leave_at = None
        if not self.tray_visible:
            self.position_tray()
            self.tray.window.attributes("-alpha",1 if self.reduced else 0)
            self.tray.window.deiconify()
            p = self.tray.placement
            offset = 0 if self.reduced else (24 if p["side"] == "left" else -24)
            desktop.place(self.tray.window,p["x"]+offset,p["y"],p["width"],p["height"])
            self.tray_visible = True
            self.last_tray_frame = None
        self.spring.target = 1
        if focus:
            self.keyboard_mode = True
            desktop.prepare(self.tray.window,self.topmost,no_activate=False)
            self.tray.window.focus_force()
            self.tray.filter_button.focus_set()

    def dismiss_tray(self):
        self.drag_suppressed = True
        self.hide_tray()

    def hide_tray(self, immediate=False):
        self.keyboard_mode = False
        self.spring.target = 0
        self.leave_at = None
        if immediate:
            self.spring.value = self.spring.velocity = 0
            self.tray.window.withdraw()
            self.tray_visible = False
            self.close_menu()
        desktop.prepare(self.tray.window,self.topmost)
        for row in self.tray.rows.values():
            # Pending tooltips are owned by their widgets and close on leave.
            row[0].event_generate("<Leave>")

    def update_hover(self, x, y, now):
        self.pet.pointer = (x-self.pet_x,y-self.pet_y)
        over_pet = desktop.circle_contains(self.pet_x,self.pet_y,x,y)
        self.pet.hover(over_pet and not self.drag and not self.drag_suppressed,now)
        if self.drag:
            return
        inside = over_pet
        if self.tray_visible:
            inside = inside or desktop.contains(self.tray.window,x,y)
        if self.drag_suppressed:
            if not inside:
                self.drag_suppressed = False
            return
        if self.suppress_until and now < self.suppress_until:
            return
        if self.keyboard_mode:
            return
        if inside:
            self.show_tray()
        elif self.spring.target:
            if self.leave_at is None:
                self.leave_at = now
            elif now-self.leave_at >= .250:
                self.hide_tray()

    def poll_hover(self):
        if self.closed:
            return
        now = time.monotonic()
        self.check_terminal_result()
        if self.hotkey.pressed():
            if self.tray_visible: self.dismiss_tray()
            else:
                self.drag_suppressed=False
                self.show_tray()
                self.leave_at=None
                self.suppress_until=time.monotonic()+1.2
        if now-self.last_motion_check > 3:
            self.reduced = desktop.reduced_motion()
            self.last_motion_check = now
        x,y = self.root.winfo_pointerxy()
        self.update_hover(x,y,now)
        self.hover_id = self.root.after(40,self.poll_hover)

    def animate(self):
        now = time.monotonic()
        moving = self.spring.step(now-self.last_animation,self.reduced)
        self.last_animation = now
        session = self.current_session()
        state = session.display_state() if session else "sleeping"
        self.pet.update(state,now)
        focused=self.focus_until>time.time()
        self.pet.draw(now,session.provider if session else "Codex",self.reduced or focused)
        self.canvas.itemconfigure(self.completion_star,state="normal" if self.activity.badge else "hidden")
        self.canvas.tag_raise(self.completion_star)
        others=sum(s.key!=self.selected and s.display_state() in {"working","thinking","compacting"} for s in self.sessions)
        visible=bool(session and session.display_state() in {"idle","sleeping"} and others)
        self.canvas.itemconfigure(self.other_dot,state="normal" if visible else "hidden")
        self.canvas.itemconfigure(self.other_count,state="normal" if visible else "hidden",text=str(others))
        self.canvas.tag_raise("other_activity")
        if self.tray_visible:
            p = self.tray.placement
            alpha = max(0,min(1,self.spring.value))
            offset = (1-self.spring.value)*24*(1 if p["side"]=="left" else -1)
            frame = (round(p["x"]+offset),p["y"],p["width"],p["height"],round(alpha,3))
            if frame != self.last_tray_frame:
                desktop.place(self.tray.window,*frame[:4])
                self.tray.window.attributes("-alpha",alpha)
                self.last_tray_frame = frame
            self.tray.animate(now,self.reduced)
            if not moving and not self.spring.target:
                self.tray.window.withdraw()
                self.tray_visible = False
                self.close_menu()
        active = (state in {"working","thinking","compacting"} or now < self.pet.completed_until or now < self.pet.jump_until or self.pet.reacting(now)
                  or (state == "error" and now-self.pet.changed < .6))
        interval = 16 if moving else (250 if self.reduced or focused else (33 if active else 120))
        self.animation_id = self.root.after(interval,self.animate)

    def watch(self):
        monitor = Monitor()
        while not self.stopping.is_set():
            try:
                result = monitor.poll(),monitor.warning
            except Exception:
                logging.exception("Falha ao ler sessões")
                result = None,self.t("read_error")
            try:
                self.updates.get_nowait()
            except queue.Empty:
                pass
            self.updates.put_nowait(result)
            self.stopping.wait(1)

    def refresh(self):
        try:
            sessions,self.warning = self.updates.get_nowait()
            if sessions is not None:
                self.sessions = sessions
        except queue.Empty:
            pass
        if self.restored_selection and self.sessions:
            if any(session.key==self.restored_selection for session in self.sessions): self.selected=self.restored_selection
            self.restored_selection=None
        self.activity.update(self.sessions)
        pending,self.activity.ready=self.activity.ready,[]
        for kind,key,project in pending:
            if self.alerts.get(kind) and self.focus_until<=time.time():
                self.toast_queue.append((kind,key,project))
        if self.focus_until and self.focus_until<=time.time(): self.focus_until=0
        self.show_next_notice()
        self.tray.refresh()
        session=self.current_session()
        tip=(self.project_name(session)+" · "+session.provider+" · "+self.t.state(session.display_state())) if session else self.t("no_selection")
        others=sum(s.key!=self.selected and s.display_state() in {"working","thinking","compacting"} for s in self.sessions)
        if others: tip+="\n"+self.t("other_working",count=others)
        if self.focus_until>time.time(): tip+="\n"+self.t("focus_remaining",minutes=max(1,int((self.focus_until-time.time())/60)+1))
        if self.activity.badge: tip+="\n"+self.t("completion_tip")
        self.pet_tooltip.text=tip
        self.save_preferences()
        now = time.monotonic()
        for session in self.sessions:
            completed = session.completed
            previous = self.completions.get(session.key,completed)
            if completed > previous and time.time()-completed < 8:
                if session.key == self.selected:
                    self.pet.celebrate(now)
                if self.sound and self.focus_until<=time.time():
                    self.root.bell()
            self.completions[session.key] = completed
        self.completions = {s.key:self.completions[s.key] for s in self.sessions}
        session = self.current_session()
        self.root.title(APP_NAME+" ● "+(self.t.state(session.display_state())+" · "+self.project_name(session) if session else self.t.state("sleeping")))
        self.refresh_id = self.root.after(1000,self.refresh)

    def project_name(self,session):
        return session.project if session.cwd or session.project_hint else self.t("local_session")

    def current_session(self):
        return next((s for s in self.sessions if s.key==self.selected),None)

    def refresh_now(self):
        self.root.after_cancel(self.refresh_id)
        self.refresh()

    def select_session(self,key):
        if not any(s.key==key for s in self.sessions):
            return
        details = key!=self.selected or not self.tray.details
        self.selected = key
        self.restored_selection=None
        if self.activity.badge and self.activity.badge[0]==key: self.activity.badge=None
        self.terminal_pending = self.terminal_requested = None
        self.terminal_status = ""
        self.close_menu()
        self.tray.details = details
        self.position_tray()
        self.show_tray()
        self.refresh_now()

    def focus_selected_terminal(self):
        session = self.current_session()
        if not session:
            return
        self.terminal_requested = session.key
        target = self.terminal_bindings.get(session.key)
        if not target:
            target=terminal.restore_window(self.window_profiles.get(project_id(session)))
        if target and terminal.valid_target(target):
            self.terminal_pending = None
            if terminal.focus_terminal(target):
                self.terminal_status = ""
                self.hide_tray(immediate=True)
            else:
                self.terminal_status = "terminal_denied"
                self.tray.details = True
                self.position_tray()
            self.tray.refresh()
            return
        self.terminal_bindings.pop(session.key,None)
        if session.provider=="Cursor":
            self.open_terminal_picker()
            return
        if self.terminal_pending is not None:
            return
        self.terminal_pending = session.key
        self.terminal_status = "terminal_finding"
        self.tray.refresh()
        def resolve():
            try:
                target = terminal.find_terminal(session.provider,session.key)
            except (OSError,ValueError):
                target = None
            self.terminal_results.put((session.key,target))
        threading.Thread(target=resolve,daemon=True,name="terminal-lookup").start()

    def check_terminal_result(self):
        try:
            key,target = self.terminal_results.get_nowait()
        except queue.Empty:
            return
        if self.terminal_pending!=key:
            return
        self.terminal_pending = None
        if key!=self.selected or key!=self.terminal_requested:
            self.terminal_status = ""
            if self.terminal_requested==self.selected:
                self.focus_selected_terminal()
            return
        if target:
            self.terminal_bindings[key] = target
        if target and terminal.focus_terminal(target):
            self.terminal_status = ""
            self.hide_tray(immediate=True)
        else:
            self.terminal_status = "terminal_denied" if target else "terminal_missing"
            self.tray.details = True
            self.position_tray()
        self.tray.refresh()

    def open_terminal_picker(self):
        if not self.current_session():
            return
        self.terminal_pending = self.terminal_requested = None
        self.terminal_choices = terminal.available_terminals()
        self.menu_open = self.terminal_picker_open = True
        self.pet_picker_open = self.language_picker_open = self.companion_open = False
        self.position_tray()
        self.tray.terminal_list.delete(0,"end")
        for title,_ in self.terminal_choices:
            self.tray.terminal_list.insert("end",title)
        if self.terminal_choices:
            self.tray.terminal_list.selection_set(0)
        else:
            self.tray.terminal_list.insert("end",self.t("terminal_missing"))
        self.tray.bind_terminal_button.configure(state="normal" if self.terminal_choices else "disabled")
        self.show_tray()
        self.tray.layout()

    def bind_terminal(self):
        selection = self.tray.terminal_list.curselection()
        session = self.current_session()
        if not selection or not session or selection[0]>=len(self.terminal_choices):
            return
        target=self.terminal_choices[selection[0]][1]
        if not terminal.valid_target(target):
            self.terminal_status="terminal_missing"
            self.close_menu()
            self.tray.refresh()
            return
        self.terminal_bindings[session.key] = target
        profile=terminal.window_profile(target)
        if profile: self.window_profiles[project_id(session)]=profile
        self.save_preferences()
        self.terminal_pending = None
        self.terminal_requested = session.key
        self.close_menu()
        self.focus_selected_terminal()

    def toggle_details(self):
        self.close_menu()
        self.tray.details = not self.tray.details
        self.position_tray()
        self.show_tray()

    def press(self,event):
        self.pet.jump_until = 0
        self.drag = event.x_root,event.y_root,self.pet_x,self.pet_y
        self.moved = False

    def move(self,event):
        if self.drag:
            px,py,x,y = self.drag
            dx,dy = event.x_root-px,event.y_root-py
            if abs(dx)+abs(dy)>4:
                if not self.moved:
                    self.dismiss_notice()
                    self.hide_tray(immediate=True)
                self.moved = True
                area = desktop.work_area(self.root,event.x_root,event.y_root)
                self.pet_x,self.pet_y = desktop.clamp_pet(x+dx,y+dy,area)
                desktop.place(self.root,self.pet_x,self.pet_y,64,64)

    def release(self,_=None):
        self.drag = None
        if self.moved:
            self.drag_suppressed = True
            self.suppress_until = time.monotonic()+.3
            self.save_preferences()
        else:
            if self.activity.badge:
                x,y=self.root.winfo_pointerxy()
                if x-self.pet_x>=43 and y-self.pet_y<=23:
                    key=self.activity.badge[0]
                    self.select_session(key)
                    return
            self.pet.click(time.monotonic())
            self.show_tray()

    def check_keyboard_focus(self):
        if self.closed or not self.keyboard_mode:
            return
        focused = self.root.focus_displayof()
        if not focused or focused.winfo_toplevel() != self.tray.window:
            self.keyboard_mode = False
            desktop.prepare(self.tray.window,self.topmost)

    def open_menu(self):
        if self.pet_picker_open or self.language_picker_open or self.terminal_picker_open or self.companion_open:
            self.pet_picker_open = self.language_picker_open = self.terminal_picker_open = self.companion_open = False
            self.tray.layout()
            return
        if self.menu_open:
            self.close_menu()
            return
        self.show_tray()
        self.menu_open = True
        self.position_tray()
        self.tray.layout()
        self.tray.refresh()

    def open_pet_picker(self):
        self.show_tray()
        self.menu_open = self.pet_picker_open = True
        self.language_picker_open = self.terminal_picker_open = self.companion_open = False
        self.position_tray()
        self.tray.layout()
        self.tray.refresh()

    def open_language_picker(self):
        self.show_tray()
        self.menu_open = self.language_picker_open = True
        self.pet_picker_open = self.terminal_picker_open = self.companion_open = False
        self.position_tray()
        self.tray.layout()
        self.tray.refresh()

    def select_language(self,language):
        if not isinstance(language,str) or language not in {"auto",*LANGUAGE_NAMES}:
            return False
        if language==self.language:
            return True
        self.dismiss_notice()
        self.toast_queue.clear()
        self.language = language
        self.t = Translator(None if language=="auto" else language)
        self.root.title(APP_NAME+" — "+self.t("tagline"))
        details,focus = self.tray.details,self.keyboard_mode
        self.tray.window.destroy()
        self.tray_visible = False
        self.tray = HoverTray(self)
        self.tray.details = details
        self.last_tray_frame = None
        self.position_tray()
        self.show_tray(focus=focus)
        if focus:
            self.tray.language_buttons[language].focus_set()
        self.save_preferences()
        return True

    def select_pet(self,pet_id):
        if not isinstance(pet_id,str) or pet_id not in PETS:
            return False
        self.pet.pet_id = pet_id
        session = self.current_session()
        self.pet.draw(time.monotonic(),session.provider if session else "Codex",self.reduced)
        self.save_preferences()
        self.tray.refresh()
        return True

    def close_menu(self):
        self.menu_open = self.pet_picker_open = self.language_picker_open = self.terminal_picker_open = self.companion_open = False
        self.tray.companion_frame.place_forget()
        self.tray.terminal_frame.place_forget()
        self.tray.language_frame.place_forget()
        self.tray.settings_frame.place_forget()
        self.tray.pet_frame.place_forget()
        if self.tray.placement:
            self.position_tray()

    def focus_panel(self):
        self.close_menu()
        self.show_tray(focus=True)

    def toggle_sound(self):
        self.sound = not self.sound
        self.save_preferences()
        self.tray.refresh()

    def toggle_topmost(self):
        self.topmost = not self.topmost
        desktop.prepare(self.root,self.topmost)
        desktop.prepare(self.tray.window,self.topmost,not self.keyboard_mode)
        self.save_preferences()
        self.tray.refresh()

    def dock_right(self):
        area = self.work_area()
        self.pet_x,self.pet_y = area[2]-88,area[1]+(area[3]-area[1]-64)//2
        desktop.place(self.root,self.pet_x,self.pet_y,64,64)
        if self.tray_visible:
            self.position_tray()
        self.save_preferences()

    def toggle_favorite(self,key=None):
        session=next((s for s in self.sessions if s.key==(key or self.selected)),None)
        if not session: return
        identity=project_id(session)
        if identity in self.favorites: self.favorites.remove(identity)
        else: self.favorites.add(identity)
        self.save_preferences()
        self.tray.refresh()

    def open_companion_settings(self):
        self.menu_open=self.companion_open=True
        self.pet_picker_open=self.language_picker_open=self.terminal_picker_open=False
        self.show_tray()
        self.position_tray()
        self.tray.refresh()

    def toggle_focus(self):
        self.focus_until=0 if self.focus_until>time.time() else time.time()+25*60
        self.toast_queue.clear()
        self.dismiss_notice()
        self.save_preferences()
        self.tray.refresh()

    def toggle_alert(self,kind):
        if kind not in self.alerts: return
        self.alerts[kind]=not self.alerts[kind]
        self.save_preferences()
        self.tray.refresh()

    def cycle_hotkey(self):
        self.hotkey_name=HOTKEYS[(HOTKEYS.index(self.hotkey_name)+1)%len(HOTKEYS)]
        self.hotkey_failed=not self.hotkey.set(self.hotkey_name)
        self.save_preferences()
        self.tray.refresh()

    def usage_summary(self):
        session=self.current_session()
        totals=self.activity.today()
        def breakdown(values,key):
            if not any(values): return self.t("usage_unknown")
            return self.t(key,**dict(zip(("input","output","write","read"),(compact_tokens(v) for v in values))))
        count=("≥" if session and session.tokens_partial else "")+compact_tokens(session.tokens) if session and session.tokens else self.t("usage_unknown")
        return (self.t("summary_title")+"\n\n"+self.t("summary_session",count=count)+"\n"+
                (breakdown(session.usage,"usage_breakdown") if session else self.t("usage_unknown"))+"\n\n"+
                self.t("summary_today",count=compact_tokens(totals[0]))+"\n"+
                breakdown(totals[1:],"usage_daily_breakdown")+"\n\n"+self.t("summary_note"))

    def dismiss_notice(self):
        if self.toast_timer:
            self.root.after_cancel(self.toast_timer)
            self.toast_timer=None
        if self.toast:
            self.toast.destroy()
            self.toast=None

    def show_next_notice(self):
        if self.toast or not self.toast_queue or self.closed: return
        if self.focus_until>time.time():
            self.toast_queue.clear()
            return
        self.toast_queue=self.toast_queue[-16:]
        kind,key,project=self.toast_queue.pop(0)
        if not self.alerts.get(kind): return
        window=self.toast=tk.Toplevel(self.root)
        overlay_window(window,True)
        area=self.work_area()
        width=min(300,area[2]-area[0]-24)
        def open_session():
            self.dismiss_notice()
            self.select_session(key)
        canvas=tk.Canvas(window,bg=KEY,highlightthickness=0)
        canvas.place(x=0,y=0,relwidth=1,relheight=1)
        body=tk.Button(window,text=self.t("speech_"+kind,project=project[:40]),command=open_session,
                       bg=BG,fg=TEXT,activebackground=BG,activeforeground=MINT,
                       anchor="nw",justify="left",relief="flat",bd=0,padx=0,pady=0,
                       font=("Segoe UI",10),wraplength=width-52,cursor="hand2")
        body.update_idletasks()
        height=max(92,body.winfo_reqheight()+54)+12
        p=desktop.speech_placement(self.pet_x,self.pet_y,area,width,height)
        top,bottom=(0,height-12) if p["above"] else (12,height)
        edge=bottom-2 if p["above"] else top+2
        point=height-1 if p["above"] else 1
        canvas.create_polygon(p["base"]-9,edge,p["tip"],point,p["base"]+9,edge,
                              fill=BG,outline=BORDER,width=1)
        rounded(canvas,1,top+1,width-1,bottom-1,16,BG,BORDER)
        join=bottom-1 if p["above"] else top+1
        canvas.create_line(p["base"]-7,join,p["base"]+7,join,fill=BG,width=2)
        canvas.create_oval(17,top+17,22,top+22,fill=MINT,outline="")
        canvas.create_text(29,top+20,text=self.t.pet_name(self.pet.pet_id),anchor="w",fill=MINT,
                           font=("Segoe UI",9,"bold"))
        body.place(x=17,y=top+36,width=width-51,height=height-12-48)
        tk.Button(window,text="×",command=self.dismiss_notice,bg=BG,fg=MUTED,
                  activebackground=BG,activeforeground=TEXT,relief="flat",bd=0,
                  font=("Segoe UI",11),cursor="hand2").place(x=width-35,y=top+10,width=23,height=24)
        window.deiconify()
        desktop.place(window,p["x"],p["y"],width,height)
        desktop.speech_shape(window,width,height,p["tip"],p["above"],p["base"])
        self.toast_timer=self.root.after(5000,self.dismiss_notice)

    def save_preferences(self):
        data = {"pet":[self.pet_x,self.pet_y],"sound":self.sound,"topmost":self.topmost,"pet_kind":self.pet.pet_id,"language":self.language,
                "favorites":sorted(self.favorites),"selected":self.selected or self.restored_selection,
                "alerts":self.alerts,"focus_until":self.focus_until,"hotkey":self.hotkey_name,
                "window_profiles":self.window_profiles,"activity":self.activity.days}
        serialized=json.dumps(data)
        if serialized==self.last_preferences: return
        temporary = self.preferences_path.with_suffix(".tmp")
        try:
            temporary.write_text(serialized,encoding="utf-8")
            temporary.replace(self.preferences_path)
            self.last_preferences=serialized
        except OSError:
            logging.warning("Não foi possível salvar as preferências.")

    def close(self, immediate=False):
        if self.closed:
            if immediate and not self.exit_finished:
                self.finish_close()
            return
        self.closed = True
        self.hotkey.close()
        self.pet_tooltip.hide()
        self.dismiss_notice()
        self.toast_queue.clear()
        self.save_preferences()
        self.stopping.set()
        for timer in (self.refresh_id,self.hover_id,self.animation_id):
            self.root.after_cancel(timer)
        self.tray.window.destroy()
        self.tray_visible = False
        self.root.unbind("<Escape>")
        for binding in ("<ButtonPress-1>","<B1-Motion>","<ButtonRelease-1>","<Button-3>"):
            self.canvas.unbind(binding)
        if immediate or self.reduced:
            self.finish_close()
            return
        try:
            self.exit_started = time.monotonic()
            area = self.work_area()
            self.exit_height = min(72,max(0,self.pet_y-area[1]+12))
            self.exit_sideways = (64 if self.pet_x+32<(area[0]+area[2])/2 else -64) if self.exit_height<60 else 0
            self.canvas.configure(width=240,height=176)
            desktop.place(self.root,self.pet_x-88,self.pet_y-88,240,176)
            desktop.exit_overlay(self.root)
            session = self.current_session()
            self.pet.prepare_exit(session.provider if session else "Codex")
            self.exit_frame()
        except (tk.TclError,OSError):
            logging.exception("Unable to animate exit")
            self.finish_close()

    def exit_frame(self):
        self.exit_id = None
        try:
            progress = (time.monotonic()-self.exit_started)/1.25
            if progress>=1:
                self.finish_close()
                return
            self.pet.draw_exit(progress,self.exit_height,self.exit_sideways)
            self.exit_id = self.root.after(16,self.exit_frame)
        except (tk.TclError,OSError):
            logging.exception("Unable to finish exit animation")
            self.finish_close()

    def finish_close(self):
        if self.exit_finished:
            return
        self.exit_finished = True
        if self.exit_id is not None:
            self.root.after_cancel(self.exit_id)
            self.exit_id = None
        self.root.destroy()


def main():
    parser = argparse.ArgumentParser(description=APP_NAME+" — "+Translator()("tagline"))
    parser.add_argument("--demo",action="store_true",help=Translator()("demo_help"))
    parser.add_argument("--smoke-test",action="store_true",help=argparse.SUPPRESS)
    args = parser.parse_args()
    logging.basicConfig(filename=Path(__file__).with_name("codumi.log"),encoding="utf-8",level=logging.WARNING)
    mutex = None
    if desktop.WINDOWS and not args.smoke_test:
        kernel = ctypes.windll.kernel32
        kernel.CreateMutexW.argtypes = [ctypes.c_void_p,ctypes.c_bool,ctypes.c_wchar_p]
        kernel.CreateMutexW.restype = ctypes.c_void_p
        # Keep the legacy mutex to avoid duplicate instances during the rename.
        mutex = kernel.CreateMutexW(None,False,"Local\\NotchiWindowsCompanion")
        if not mutex:
            raise ctypes.WinError()
        if kernel.GetLastError()==183:
            kernel.CloseHandle.argtypes = [ctypes.c_void_p]
            kernel.CloseHandle(mutex)
            return
    if desktop.WINDOWS:
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except (AttributeError,OSError):
            pass
    test_preferences = tempfile.TemporaryDirectory() if args.smoke_test else None
    try:
        app = App(args.demo,Path(test_preferences.name)/"preferences.json" if test_preferences else None)
        if args.smoke_test:
            app.root.after(120,app.show_tray)
            app.root.after(450,app.toggle_details)
            app.root.after(700,app.hide_tray)
            app.root.after(1000,app.close)
        app.root.mainloop()
    finally:
        if test_preferences:
            test_preferences.cleanup()
        if mutex:
            kernel.CloseHandle.argtypes = [ctypes.c_void_p]
            kernel.CloseHandle(mutex)


if __name__=="__main__":
    try:
        main()
    except Exception as exc:
        logging.exception("codumi failed to start")
        messagebox.showerror(APP_NAME,Translator()("startup_error",error=exc))
        sys.exit(1)
