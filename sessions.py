"""Read-only adapters for local agent transcripts. No credentials or network."""
from __future__ import annotations

import json
import os
import re
from urllib.parse import urlparse, unquote
import time
from collections import deque
from dataclasses import dataclass, field, replace
from datetime import datetime
from pathlib import Path, PureWindowsPath

LIMIT = 1024 * 1024
STATES = {
    "thinking": "Pensando", "idle": "Disponível", "working": "Trabalhando", "waiting": "Aguardando você",
    "compacting": "Organizando contexto", "sleeping": "Descansando", "error": "Erro",
}


def timestamp(value, fallback):
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).timestamp()
    except (ValueError, TypeError, AttributeError, OSError, OverflowError):
        return fallback


def text_content(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(b.get("text", "") for b in content
                        if isinstance(b, dict) and isinstance(b.get("text"), str))
    return ""


@dataclass
class Session:
    key: str
    provider: str
    cwd: str = ""
    state: str = "idle"
    started: float = field(default_factory=time.time)
    updated: float = field(default_factory=time.time)
    tool: str = ""
    prompt: str = ""
    tokens: int = 0
    completed: float = 0.0
    events: deque = field(default_factory=lambda: deque(maxlen=6))
    project_hint: str = ""
    usage: tuple = (0,0,0,0)
    tokens_partial: bool = False
    _claude_usage: dict = field(default_factory=dict,repr=False,compare=False)

    @property
    def project(self):
        return PureWindowsPath(self.cwd).name if self.cwd else (self.project_hint or "Sessão local")

    def display_state(self, now=None):
        age = (time.time() if now is None else now) - self.updated
        # shortcut: logs cannot prove a process is still alive; age out silent sessions.
        return "sleeping" if age > 300 else self.state

    def apply(self, record, fallback):
        if not isinstance(record, dict):
            return
        if self.provider=="Cursor":
            record=dict(record)
            if "type" not in record:
                record["type"]=record.get("role")
        kind = record.get("type")
        body = record.get("payload")
        body = body if isinstance(body, dict) else {}
        when = timestamp(record.get("timestamp"), fallback)
        state, label = None, ""
        cwd = record.get("cwd") or body.get("cwd")
        if isinstance(cwd, str):
            self.cwd = cwd
        if self.provider == "Codex":
            event = body.get("type")
            if kind == "session_meta":
                self.started = when
            elif kind == "event_msg":
                if event in {"task_started", "turn_started", "user_message"}:
                    state, label = "working", "Novo pedido"
                    if event == "user_message":
                        self.prompt = str(body.get("message", ""))[:240]
                elif event in {"task_complete", "task_completed", "turn_complete", "turn_aborted"}:
                    state, label = "idle", "Turno interrompido" if event == "turn_aborted" else "Turno concluído"
                elif event in {"context_compacted", "context_compaction"}:
                    state, label = "compacting", "Contexto compactado"
                elif event == "token_count":
                    info = body.get("info")
                    usage = info.get("total_token_usage") if isinstance(info, dict) else None
                    self.set_tokens(usage)
                elif event in {"approval_request", "request_user_input"}:
                    state, label = "waiting", "Aguardando resposta"
            elif kind == "token_usage_record":
                self.set_tokens(body.get("thread_token_usage"))
            elif kind == "response_item":
                if event in {"function_call", "custom_tool_call", "local_shell_call"}:
                    self.tool = str(body.get("name", "Ferramenta"))[:80]
                    state = "waiting" if "request_user_input" in self.tool else "working"
                    label = self.tool
                elif event == "reasoning":
                    state, label = "thinking", "Pensando"
                elif event == "message" and body.get("role") == "assistant":
                    state = "idle" if body.get("phase") == "final_answer" else "working"
                    label = "Resposta concluída" if state == "idle" else "Respondendo"
        elif self.provider=="Cursor" and kind in {"result","tool_call","thinking"}:
            if kind=="result":
                state,label=("error","Ferramenta retornou erro") if record.get("is_error") else ("idle","Resposta concluída")
                self.set_tokens(record.get("usage"))
            elif kind=="thinking":
                state,label="thinking","Pensando"
            else:
                tool=record.get("tool_call")
                if isinstance(tool,dict):
                    self.tool=str(next(iter(tool),"Ferramenta"))[:80]
                state,label="working",self.tool or "Respondendo"
        else:
            message = record.get("message")
            message = message if isinstance(message, dict) else {}
            blocks = message.get("content", [])
            if kind == "user":
                state, label = "working", "Novo pedido"
                if isinstance(blocks, list) and any(isinstance(b, dict) and b.get("type") == "tool_result" for b in blocks):
                    label = "Resultado de ferramenta"
                    if any(isinstance(b, dict) and b.get("is_error") for b in blocks):
                        state, label = "error", "Ferramenta retornou erro"
                else:
                    self.prompt = text_content(blocks)[:240]
            elif kind == "assistant":
                self.add_claude_tokens(record)
                state, label = "working", "Respondendo"
                tools = [b for b in blocks if isinstance(b, dict) and b.get("type") == "tool_use"] if isinstance(blocks, list) else []
                if tools:
                    self.tool = str(tools[-1].get("name", "Ferramenta"))[:80]
                    state = "waiting" if self.tool == "AskUserQuestion" else "working"
                    label = self.tool
                elif message.get("stop_reason") in {"end_turn", "stop_sequence"}:
                    state, label = "idle", "Resposta concluída"
                elif isinstance(blocks, list) and any(isinstance(b, dict) and b.get("type") == "thinking" for b in blocks):
                    state, label = "thinking", "Pensando"
            elif kind == "system" and record.get("subtype") == "compact_boundary":
                state, label = "compacting", "Contexto compactado"
        if state:
            if state == "idle" and self.state != "idle" and label in {"Resposta concluída", "Turno concluído"}:
                self.completed = max(self.completed, when)
            self.state = state
            self.updated = when
            self.events.append((when, label))
            if state == "idle":
                self.tool = ""

    def set_tokens(self, usage):
        total = usage.get("total_tokens") if isinstance(usage, dict) else None
        if type(total) is int and 0<=total<2**63:
            self.tokens = max(self.tokens, total)
        if isinstance(usage,dict):
            fields=("input_tokens","output_tokens","cache_creation_input_tokens","cached_input_tokens")
            values=tuple(usage.get(key,0) for key in fields)
            self.usage=tuple(max(a,b) if type(b) is int and 0<=b<2**63 else a for a,b in zip(self.usage,values))

    def add_claude_tokens(self, record):
        if not isinstance(record,dict) or record.get("type",record.get("role"))!="assistant":
            return
        message=record.get("message")
        if not isinstance(message,dict) or not isinstance(message.get("usage"),dict):
            return
        identity=message.get("id") or record.get("uuid")
        if not isinstance(identity,str) or not 0<len(identity)<=256:
            return
        usage=message["usage"]
        fields=("input_tokens","output_tokens","cache_creation_input_tokens","cache_read_input_tokens")
        previous=self._claude_usage.get(identity,(0,0,0,0))
        current=tuple(max(old,value) if type(value) is int and 0<=value<2**63 else old
                      for old,value in zip(previous,(usage.get(key,0) for key in fields)))
        self.tokens+=sum(current)-sum(previous)
        self.usage=tuple(a+b-old for a,b,old in zip(self.usage,current,previous))
        self._claude_usage[identity]=current


def read_lines(path,offset,skip):
    """Read at most one bounded chunk and commit only complete lines."""
    with path.open("rb") as handle:
        handle.seek(offset)
        data=handle.read(LIMIT)
    if not data:
        return [],offset,skip
    end=data.rfind(b"\n")
    if end<0:
        return ([],offset+len(data),True) if len(data)==LIMIT else ([],offset,skip)
    lines=data[:end].split(b"\n")
    if skip:
        lines=lines[1:]
    return lines,offset+end+1,False


class Tail:
    """Only commit complete JSONL lines; bound work and memory per poll."""
    def __init__(self, path, provider):
        self.path = path
        stat = path.stat()
        self.identity = (stat.st_dev, stat.st_ino)
        self.offset = max(0, stat.st_size - LIMIT)
        self.skip = self.offset > 0
        self.session = Session(str(path), provider, started=stat.st_mtime, updated=stat.st_mtime)
        if provider=="Cursor" and "agent-transcripts" in path.parts:
            index=path.parts.index("agent-transcripts")
            self.session.project_hint=path.parts[index-1] if index else "Cursor"
        self.usage_offset,self.usage_skip=0,False
        self.usage_target=self.offset if provider in {"Claude","Cursor"} else 0
        self.session.tokens_partial=self.usage_target>0
        with path.open("rb") as handle:
            first = handle.readline(65536)
        try:
            self.session.apply(json.loads(first), stat.st_mtime)
        except (ValueError, UnicodeDecodeError, TypeError, RecursionError):
            pass

    def poll(self):
        stat = self.path.stat()
        if stat.st_size < self.offset or self.identity != (stat.st_dev, stat.st_ino):
            self.__init__(self.path, self.session.provider)
        lines,self.offset,self.skip=read_lines(self.path,self.offset,self.skip)
        for line in lines:
            try:
                self.session.apply(json.loads(line), stat.st_mtime)
            except (ValueError, UnicodeDecodeError, TypeError, RecursionError):
                continue
        if self.session.tokens_partial:
            lines,self.usage_offset,self.usage_skip=read_lines(self.path,self.usage_offset,self.usage_skip)
            for line in lines:
                try:
                    self.session.add_claude_tokens(json.loads(line))
                except (ValueError, UnicodeDecodeError, TypeError, RecursionError):
                    continue
            self.session.tokens_partial=self.usage_offset<self.usage_target


class Monitor:
    def __init__(self, home=None):
        home = Path.home() if home is None else Path(home)
        self.cursor_workspaces={}
        storage=home/"AppData/Roaming/Cursor/User/workspaceStorage"
        try:
            for index,path in enumerate(storage.glob("*/workspace.json")):
                if index>=256: break
                if path.is_symlink() or path.stat().st_size>65536: continue
                try:
                    data=json.loads(path.read_text(encoding="utf-8"))
                    uri=data.get("folder") if isinstance(data,dict) else None
                    if not isinstance(uri,str) or len(uri)>4096: continue
                    parsed=urlparse(uri)
                    if parsed.scheme!="file" or parsed.netloc: continue
                    cwd=unquote(parsed.path)
                    if re.match(r"^/[A-Za-z]:/",cwd): cwd=cwd[1:]
                    encoded=re.sub(r"[^A-Za-z0-9]+","-",cwd).strip("-").casefold()
                    self.cursor_workspaces[encoded]="" if encoded in self.cursor_workspaces and self.cursor_workspaces[encoded].casefold()!=cwd.casefold() else cwd
                except (ValueError,OSError,RecursionError): continue
        except OSError: pass
        self.roots = [(Path(os.environ.get("CODEX_HOME", home / ".codex")) / "sessions", "Codex"),
                      (Path(os.environ.get("CLAUDE_CONFIG_DIR", home / ".claude")) / "projects", "Claude"),
                      (home / ".cursor" / "projects", "Cursor")]
        self.tails = {}
        self.scanned = 0
        self.warning = ""

    def poll(self):
        now = time.time()
        warnings = []
        if now - self.scanned >= 10:
            candidates = []
            for root, provider in self.roots:
                try:
                    for path in root.rglob("*.jsonl"):
                        if path.is_symlink() or "subagents" in path.parts or (provider=="Cursor" and "agent-transcripts" not in path.parts):
                            continue
                        modified = path.stat().st_mtime
                        if now - modified < 86400:
                            candidates.append((modified, str(path), path, provider))
                except OSError as exc:
                    warnings.append(f"Não foi possível ler {provider}: {exc.strerror}")
            selected = sorted(candidates, reverse=True)[:48]
            keep = {item[2] for item in selected}
            self.tails = {p: t for p, t in self.tails.items() if p in keep}
            for _, _, path, provider in selected:
                if path not in self.tails:
                    try:
                        self.tails[path] = Tail(path, provider)
                        session=self.tails[path].session
                        if provider=="Cursor" and not session.cwd:
                            session.cwd=self.cursor_workspaces.get(session.project_hint.casefold(),"")
                    except OSError:
                        warnings.append("Uma sessão está temporariamente inacessível.")
            self.scanned = now
        for tail in list(self.tails.values()):
            try:
                tail.poll()
            except OSError:
                warnings.append("Uma sessão está temporariamente inacessível.")
        self.warning = " ".join(dict.fromkeys(warnings))
        return sorted((replace(t.session, events=deque(t.session.events, maxlen=6),_claude_usage=t.session._claude_usage.copy())
                       for t in self.tails.values()), key=lambda s: s.updated, reverse=True)
