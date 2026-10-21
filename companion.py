"""Local companion state: observed usage, deduplicated events, and project identity."""
from datetime import datetime
import hashlib
import time

HOTKEYS=("Off","Ctrl+Alt+N","Ctrl+Shift+F12","Ctrl+Alt+Space")


def project_id(session):
    path=(session.cwd or session.project_hint or session.key).replace('\\','/').rstrip('/').casefold()
    return hashlib.sha256((session.provider+'\0'+path).encode('utf-8')).hexdigest()


def counter(value):
    return value if type(value) is int and 0<=value<2**63 else 0


class Activity:
    def __init__(self,saved=None):
        saved=saved if isinstance(saved,dict) else {}
        self.days={}
        for day,values in list(saved.items())[-31:]:
            if isinstance(day,str) and len(day)==10 and isinstance(values,list) and len(values)==5:
                self.days[day]=[counter(v) for v in values]
        self.previous={}
        self.events={}
        self.ready=[]
        self.badge=None

    def update(self,sessions,now=None):
        now=time.time() if now is None else now
        day=datetime.fromtimestamp(now).strftime('%Y-%m-%d')
        self.days={k:v for k,v in self.days.items() if 0<=(datetime.fromtimestamp(now).date()-self._date(k)).days<31}
        for session in sessions:
            values=(session.tokens,*session.usage)
            previous=self.previous.get(session.key)
            # Historical discovery/backfill is a baseline, not usage performed today.
            if previous and not session.tokens_partial and not previous[2] and previous[1]==day:
                increments=[max(0,b-a) for a,b in zip(previous[0],values)]
                if any(increments):
                    totals=self.days.setdefault(day,[0]*5)
                    self.days[day]=[a+b for a,b in zip(totals,increments)]
            self.previous[session.key]=(values,day,session.tokens_partial)
            signature=(session.state,session.updated,session.completed)
            last=self.events.get(session.key)
            if last is not None and signature!=last and 0<=now-session.updated<30:
                kind=('complete' if session.completed>last[2] else
                      session.state if session.state in {'error','waiting'} and session.state!=last[0] else None)
                if kind:
                    self.ready.append((kind,session.key,session.project))
                    if kind=='complete': self.badge=(session.key,now+60)
            self.events[session.key]=signature
        live={s.key for s in sessions}
        self.previous={k:v for k,v in self.previous.items() if k in live}
        self.events={k:v for k,v in self.events.items() if k in live}
        if self.badge and (self.badge[0] not in live or self.badge[1]<now): self.badge=None

    @staticmethod
    def _date(value):
        try: return datetime.strptime(value,'%Y-%m-%d').date()
        except ValueError: return datetime.min.date()

    def today(self):
        return self.days.get(datetime.now().strftime('%Y-%m-%d'),[0]*5)
