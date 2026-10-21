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


TONES=('direct','friendly','playful')


def session_hash(session):
    return hashlib.sha256(session.key.encode('utf-8')).hexdigest()


def attention_queue(sessions):
    return sorted((s for s in sessions if s.state in {'waiting','error'}),
                  key=lambda s:(s.state!='error',-s.updated))


class ProjectPreferences:
    def __init__(self,saved=None):
        self.values={}
        if isinstance(saved,dict):
            for identity,options in saved.items():
                if isinstance(identity,str) and len(identity)==64 and isinstance(options,dict):
                    clean={}
                    for field,value in options.items():
                        if self.valid(field,value): clean[field]=value
                    if clean: self.values[identity]=clean

    @staticmethod
    def valid(field,value):
        if not isinstance(field,str): return False
        from pet import PETS
        if field=='pet': return isinstance(value,str) and value in PETS
        if field=='tone': return isinstance(value,str) and value in TONES
        return field in {'edge','muted','alert.complete','alert.error','alert.waiting'} and type(value) is bool

    def get(self,session):
        return self.values.get(project_id(session),{}) if session else {}

    def set(self,session,field,value):
        if not session or (value is not None and not self.valid(field,value)): return False
        if field not in {'pet','tone','edge','muted','alert.complete','alert.error','alert.waiting'}: return False
        identity=project_id(session)
        options=dict(self.values.get(identity,{}))
        if value is None: options.pop(field,None)
        else: options[field]=value
        if options: self.values[identity]=options
        else: self.values.pop(identity,None)
        return True


class CompletionHistory:
    """Optional bounded metadata, never transcript paths or prompts."""
    def __init__(self,enabled=False,saved=None):
        self.enabled=enabled is True
        self.records=[]
        if self.enabled and isinstance(saved,list):
            for record in saved[-100:]:
                if not isinstance(record,dict): continue
                if (all(isinstance(record.get(k),str) and len(record[k])==64 for k in ('id','session','project'))
                    and isinstance(record.get('name'),str) and len(record['name'])<=80
                    and isinstance(record.get('provider'),str) and record['provider'] in {'Claude','Codex','Cursor'}
                    and type(record.get('time')) in (int,float) and 0<record['time']<=time.time()+60):
                    self.records.append({k:record[k] for k in ('id','session','project','name','provider','time')})
        self.prune()

    def prune(self):
        self.records=[r for r in self.records if 0<=time.time()-r['time']<30*86400][-100:]

    def add(self,session):
        if not self.enabled or not session.completed: return
        self.prune()
        identity=hashlib.sha256((session.key+'\0'+str(session.completed)).encode('utf-8')).hexdigest()
        if any(r['id']==identity for r in self.records): return
        self.records.append({'id':identity,'session':session_hash(session),'project':project_id(session),
                             'name':session.project[:80],'provider':session.provider,'time':session.completed})
        self.prune()

    def disable(self):
        self.enabled=False
        self.records.clear()
