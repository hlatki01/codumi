"""GitHub release checks and opt-in verified staging; never overwrite a running app."""
from pathlib import Path, PurePosixPath
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tempfile
import urllib.request
import zipfile

REPOSITORY='https://github.com/hlatki01/codumi'
API='https://api.github.com/repos/hlatki01/codumi/releases/latest'
MAX_ARCHIVE=200*1024*1024
MAX_EXPANDED=512*1024*1024


def version_tuple(value):
    if not isinstance(value,str) or not re.fullmatch(r'v?\d{1,4}\.\d{1,4}\.\d{1,4}',value):
        raise ValueError('Invalid release version')
    return tuple(int(n) for n in value.lstrip('v').split('.'))


class ReleaseRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        from urllib.parse import urlparse
        target=urlparse(newurl)
        if target.username or target.password or target.port not in (None,443) or target.scheme!='https' or target.hostname not in {'github.com','api.github.com','release-assets.githubusercontent.com','objects.githubusercontent.com'}:
            raise ValueError('Untrusted update redirect')
        return super().redirect_request(req,fp,code,msg,headers,newurl)


def fetch(url,limit,destination=None):
    request=urllib.request.Request(url,headers={'User-Agent':'codumi-updater','Accept':'application/vnd.github+json' if url==API else 'application/octet-stream'})
    opener=urllib.request.build_opener(ReleaseRedirect())
    total=0
    with opener.open(request,timeout=15) as response:
        with Path(destination).open('xb') if destination else tempfile.TemporaryFile() as output:
            while True:
                data=response.read(65536)
                if not data: break
                total+=len(data)
                if total>limit: raise ValueError('Update response exceeds size limit')
                output.write(data)
            if not destination:
                output.seek(0)
                return output.read()
    return total


def parse_release(data,current):
    if not isinstance(data,dict) or data.get('draft') or data.get('prerelease'): raise ValueError('Not a stable release')
    tag=data.get('tag_name')
    version=version_tuple(tag)
    if version<=version_tuple(current): return None
    tag='v'+'.'.join(map(str,version))
    filename=f'codumi-{tag}-windows-x64.zip'
    assets=data.get('assets')
    if not isinstance(assets,list): raise ValueError('Release assets missing')
    urls={}
    for name in (filename,'SHA256SUMS.txt'):
        expected=f'{REPOSITORY}/releases/download/{tag}/{name}'
        matches=[a for a in assets if isinstance(a,dict) and a.get('name')==name and a.get('browser_download_url')==expected]
        if len(matches)!=1: raise ValueError('Expected release asset missing or ambiguous')
        size=matches[0].get('size')
        if type(size) is not int or not 0<size<=(MAX_ARCHIVE if name==filename else 65536): raise ValueError('Invalid asset size')
        urls[name]=expected
    notes=data.get('body','')
    return {'version':tag,'filename':filename,'archive_url':urls[filename],
            'checksum_url':urls['SHA256SUMS.txt'],'url':f'{REPOSITORY}/releases/tag/{tag}',
            'notes':notes[:32000] if isinstance(notes,str) else ''}


def check_latest(current):
    return parse_release(json.loads(fetch(API,512*1024)),current)


def checksum(text,filename):
    matches=[]
    for line in text.splitlines():
        match=re.fullmatch(r'([0-9a-fA-F]{64})\s+\*?([^\s]+)',line.strip())
        if match and match[2]==filename: matches.append(match[1].lower())
    if len(matches)!=1: raise ValueError('Checksum missing or ambiguous')
    return matches[0]


def digest(path):
    with Path(path).open('rb') as handle:
        result=hashlib.sha256()
        for chunk in iter(lambda:handle.read(65536),b''): result.update(chunk)
    return result.hexdigest()


def archive_members(bundle):
    members=bundle.infolist()
    if not 0<len(members)<=20000 or sum(m.file_size for m in members)>MAX_EXPANDED: raise ValueError('Archive size limit')
    seen=set()
    required={'codumi-Windows/codumi.exe','codumi-Windows/app.py','codumi-Windows/runtime/pythonw.exe'}
    reserved={'CON','PRN','AUX','NUL',*[f'{p}{i}' for p in ('COM','LPT') for i in range(1,10)]}
    for member in members:
        name=member.filename.rstrip('/')
        parts=PurePosixPath(name).parts
        if (member.orig_filename!=member.filename or any(p in {'.','..',''} for p in name.split('/')) or not parts or parts[0]!='codumi-Windows' or '\\' in name or name.startswith('/')
            or any(p in {'.','..'} or p.endswith((' ','.')) or ':' in p or any(ord(c)<32 for c in p)
                   or p.split('.')[0].upper() in reserved for p in parts)
            or member.flag_bits&1 or stat.S_ISLNK(member.external_attr>>16)
            or member.file_size>128*1024*1024 or name.casefold() in seen):
            raise ValueError('Unsafe archive member')
        seen.add(name.casefold())
        if parts[-1].casefold() in {'preferences.json','codumi.log','.env'}: raise ValueError('Personal data in update archive')
        required.discard(name)
    if required: raise ValueError('Incomplete portable archive')
    return members


def update_base(install):
    install=Path(install).resolve()
    if install.name=='codumi-Windows' and install.parent.parent.name=='updates': return install.parent.parent
    return install/'updates'


def stage_release(info,install):
    install=Path(install).resolve()
    base=update_base(install)
    base.mkdir(exist_ok=True)
    if base.is_symlink() or base.resolve()!=base: raise ValueError('Unsafe update directory')
    # Revalidate all remote URLs even if the caller retained the release object.
    tag=info['version']; version_tuple(tag)
    expected=f'codumi-{tag}-windows-x64.zip'
    if info['filename']!=expected or info['archive_url']!=f'{REPOSITORY}/releases/download/{tag}/{expected}' or info['checksum_url']!=f'{REPOSITORY}/releases/download/{tag}/SHA256SUMS.txt': raise ValueError('Untrusted release URLs')
    folder=Path(tempfile.mkdtemp(prefix=tag+'-',dir=base)).resolve()
    try:
        wanted=checksum(fetch(info['checksum_url'],65536).decode('ascii'),expected)
        archive=folder/expected
        fetch(info['archive_url'],MAX_ARCHIVE,archive)
        if digest(archive)!=wanted: raise ValueError('Checksum mismatch')
        with zipfile.ZipFile(archive) as bundle:
            members=archive_members(bundle)
            for member in members:
                target=folder.joinpath(*PurePosixPath(member.filename).parts)
                if member.is_dir(): target.mkdir(parents=True,exist_ok=True); continue
                target.parent.mkdir(parents=True,exist_ok=True)
                with bundle.open(member) as source,target.open('xb') as output:
                    shutil.copyfileobj(source,output,65536)
        return {'root':folder/'codumi-Windows','archive':archive,'digest':wanted,'version':tag}
    except BaseException:
        if folder.resolve().parent==base.resolve() and not folder.is_symlink(): shutil.rmtree(folder)
        raise


def verify_stage(staged):
    root=Path(staged['root']).resolve()
    archive=Path(staged['archive']).resolve()
    if root.parent!=archive.parent or root.name!='codumi-Windows' or digest(archive)!=staged['digest']: raise ValueError('Update staging changed')
    with zipfile.ZipFile(archive) as bundle:
        members=archive_members(bundle)
        expected_paths={root.parent.joinpath(*PurePosixPath(m.filename).parts) for m in members if not m.is_dir()}
        paths=list(root.rglob('*'))
        if any(p.is_symlink() or p.resolve()!=p for p in paths): raise ValueError('Staged path redirected')
        actual_paths={p for p in paths if not p.is_dir()}
        if expected_paths!=actual_paths: raise ValueError('Unexpected staged files')
        for member in members:
            if member.is_dir(): continue
            path=root.parent.joinpath(*PurePosixPath(member.filename).parts)
            if path.is_symlink() or path.resolve()!=path or not path.is_file(): raise ValueError('Staged path changed')
            with bundle.open(member) as stream:
                expected=hashlib.sha256()
                for chunk in iter(lambda:stream.read(65536),b''): expected.update(chunk)
            if digest(path)!=expected.hexdigest(): raise ValueError('Staged file changed')
    return root


def copy_preferences(install,target):
    install=Path(install).resolve();target=Path(target).resolve()
    if target.parent.parent!=update_base(install) or target==install or target.name!='codumi-Windows' or not (target/'codumi.exe').is_file(): raise ValueError('Invalid update target')
    source=install/'preferences.json'
    if source.exists():
        if source.stat().st_size>2*1024*1024: raise ValueError('Preferences exceed limit')
        data=source.read_bytes()
        if not isinstance(json.loads(data),dict): raise ValueError('Invalid preferences')
        temporary=target/'preferences.tmp'
        temporary.write_bytes(data)
        temporary.replace(target/'preferences.json')
    return target/'codumi.exe'


def apply_update(install,target,pid,started):
    import ctypes
    import terminal
    if terminal.process_start(pid)==started and started:
        handle=terminal.kernel.OpenProcess(0x100000,False,pid)
        if not handle: raise OSError('Cannot wait for previous instance')
        try:
            terminal.kernel.WaitForSingleObject.argtypes=[ctypes.c_void_p,ctypes.c_ulong]
            if terminal.kernel.WaitForSingleObject(handle,60000)!=0: raise OSError('Previous instance is still running')
        finally: terminal.kernel.CloseHandle(handle)
    launcher=copy_preferences(install,target)
    process=subprocess.Popen([str(launcher)],cwd=launcher.parent,creationflags=subprocess.CREATE_NO_WINDOW)
    try:
        if process.wait(timeout=3)!=0: raise OSError('New version exited during startup')
    except subprocess.TimeoutExpired: pass


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser()
    parser.add_argument('--apply',nargs=4,metavar=('INSTALL','TARGET','PID','STARTED'))
    parser.add_argument('--language',default='en')
    args=parser.parse_args()
    if args.apply:
        try: apply_update(args.apply[0],args.apply[1],int(args.apply[2]),int(args.apply[3]))
        except Exception:
            from i18n import Translator
            text=Translator(args.language)('update_install_failed')
            import ctypes
            ctypes.windll.user32.MessageBoxW(None,text,'codumi',0x10)
            raise
