"""Trust boundaries for optional downloads and non-destructive update staging."""
import hashlib
import io
import json
import tempfile
from pathlib import Path
import stat
import unittest
from unittest.mock import patch
import zipfile

import updater


def package(extra=None):
    buffer=io.BytesIO()
    with zipfile.ZipFile(buffer,'w',zipfile.ZIP_DEFLATED) as z:
        for name in ('codumi.exe','app.py','runtime/pythonw.exe'):
            z.writestr('codumi-Windows/'+name,b'fictional fixture')
        for name,contents in (extra or {}).items():
            entry=zipfile.ZipInfo()
            entry.filename=entry.orig_filename=name
            z.writestr(entry,contents)
    return buffer.getvalue()


def release():
    tag='v0.3.1'
    names=['codumi-v0.3.1-windows-x64.zip','SHA256SUMS.txt']
    return {'tag_name':tag,'body':'Fictional release notes','assets':[
        {'name':name,'size':100,'browser_download_url':f'{updater.REPOSITORY}/releases/download/{tag}/{name}'} for name in names]}


class UpdaterTests(unittest.TestCase):
    def test_stable_versions_and_official_asset_urls(self):
        data=release()
        result=updater.parse_release(data,'0.3.0')
        self.assertEqual(result['version'],'v0.3.1')
        self.assertIsNone(updater.parse_release(data,'0.3.1'))
        self.assertIsNone(updater.parse_release(data,'0.4.0'))
        data['assets'][0]['browser_download_url']='https://example.com/installer.exe'
        with self.assertRaises(ValueError): updater.parse_release(data,'0.3.0')
        for bad in ('v1.2','v1.2.3-rc1','../v1.2.3','v10000.0.0',[],None):
            with self.assertRaises(ValueError): updater.version_tuple(bad)

    def test_missing_duplicate_or_prerelease_assets_are_rejected(self):
        for mutate in (lambda d:d.update(prerelease=True),lambda d:d.update(assets=[]),
                       lambda d:d['assets'].append(dict(d['assets'][0])),
                       lambda d:d['assets'][0].update(size=True)):
            data=release();mutate(data)
            with self.assertRaises(ValueError): updater.parse_release(data,'0.3.0')

    def test_checksum_is_exact_and_unique(self):
        digest='a'*64;name='portable.zip'
        self.assertEqual(updater.checksum(digest+'  '+name,name),digest)
        self.assertEqual(updater.checksum(digest+' *'+name,name),digest)
        for text in ('garbage',digest+' other.zip',(digest+' '+name+'\n')*2):
            with self.assertRaises(ValueError): updater.checksum(text,name)

    def test_archive_rejects_paths_links_duplicates_and_personal_files(self):
        names=['../outside','codumi-Windows/../../outside','/codumi-Windows/outside',
               'codumi-Windows/C:/outside','codumi-Windows/a\\b','codumi-Windows/CON.txt',
               'codumi-Windows/folder./file','codumi-Windows/preferences.json',
               'codumi-Windows/APP.PY']
        for name in names:
            with self.subTest(name=name),zipfile.ZipFile(io.BytesIO(package({name:b'x'}))) as z:
                with self.assertRaises(ValueError): updater.archive_members(z)
        data=io.BytesIO(package())
        with zipfile.ZipFile(data,'a') as z:
            link=zipfile.ZipInfo('codumi-Windows/link')
            link.external_attr=(stat.S_IFLNK|0o777)<<16
            z.writestr(link,b'outside')
        with zipfile.ZipFile(data) as z:
            with self.assertRaises(ValueError): updater.archive_members(z)

    def test_stage_verify_and_preserve_preferences_without_network(self):
        data=package();wanted=hashlib.sha256(data).hexdigest()
        info=updater.parse_release(release(),'0.3.0')
        def fetch(url,limit,destination=None):
            if destination: Path(destination).write_bytes(data);return len(data)
            return (wanted+'  '+info['filename']).encode()
        with tempfile.TemporaryDirectory() as folder,patch('updater.fetch',side_effect=fetch):
            source=Path(folder)
            original=b'{"language":"pt","pet_kind":"fox","projects":{}}'
            (source/'preferences.json').write_bytes(original)
            staged=updater.stage_release(info,source)
            self.assertEqual(updater.verify_stage(staged),staged['root'])
            self.assertEqual((source/'preferences.json').read_bytes(),original)
            executable=updater.copy_preferences(source,staged['root'])
            self.assertTrue(executable.is_file())
            self.assertEqual((staged['root']/'preferences.json').read_bytes(),original)
            with self.assertRaises(ValueError): updater.copy_preferences(source,source)

    def test_failed_checksum_leaves_current_installation_untouched(self):
        info=updater.parse_release(release(),'0.3.0')
        def fetch(url,limit,destination=None):
            if destination: Path(destination).write_bytes(package());return 10
            return ('0'*64+'  '+info['filename']).encode()
        with tempfile.TemporaryDirectory() as folder,patch('updater.fetch',side_effect=fetch):
            root=Path(folder);(root/'app.py').write_text('original')
            with self.assertRaises(ValueError): updater.stage_release(info,root)
            self.assertEqual((root/'app.py').read_text(),'original')
            self.assertEqual(list((root/'updates').iterdir()),[])

    def test_staged_tampering_and_added_files_are_rejected(self):
        data=package();wanted=hashlib.sha256(data).hexdigest()
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);archive=root/'portable.zip';archive.write_bytes(data)
            with zipfile.ZipFile(archive) as z: z.extractall(root)
            staged={'root':root/'codumi-Windows','archive':archive,'digest':wanted}
            updater.verify_stage(staged)
            extra=staged['root']/'sitecustomize.py';extra.write_text('unexpected')
            with self.assertRaises(ValueError): updater.verify_stage(staged)
            extra.unlink()
            (staged['root']/'app.py').write_text('changed')
            with self.assertRaises(ValueError): updater.verify_stage(staged)

    def test_repeated_updates_reuse_the_same_updates_area(self):
        data=package();wanted=hashlib.sha256(data).hexdigest()
        info=updater.parse_release(release(),'0.3.0')
        def fetch(url,limit,destination=None):
            if destination: Path(destination).write_bytes(data);return len(data)
            return (wanted+'  '+info['filename']).encode()
        with tempfile.TemporaryDirectory() as folder,patch('updater.fetch',side_effect=fetch):
            source=Path(folder)
            (source/'preferences.json').write_text('{"language":"pt"}')
            first=updater.stage_release(info,source)
            updater.copy_preferences(source,first['root'])
            second=updater.stage_release(info,first['root'])
            self.assertEqual(first['root'].parent.parent,second['root'].parent.parent)
            updater.copy_preferences(first['root'],second['root'])
            self.assertEqual((second['root']/'preferences.json').read_text(),'{"language":"pt"}')

    def test_failed_parent_wait_does_not_copy_or_launch(self):
        import terminal
        with patch('terminal.process_start',return_value=123),patch.object(terminal.kernel,'OpenProcess',return_value=42),\
             patch.object(terminal.kernel,'WaitForSingleObject',return_value=258),patch.object(terminal.kernel,'CloseHandle') as close,\
             patch('updater.copy_preferences') as copy,patch('updater.subprocess.Popen') as launch:
            with self.assertRaises(OSError): updater.apply_update('source','target',100,123)
            copy.assert_not_called();launch.assert_not_called();close.assert_called_once_with(42)

    def test_response_size_is_bounded(self):
        from unittest.mock import MagicMock
        opener=MagicMock()
        response=opener.open.return_value.__enter__.return_value
        response.read.side_effect=[b'x'*11,b'']
        with patch('updater.urllib.request.build_opener',return_value=opener):
            with self.assertRaises(ValueError): updater.fetch(updater.API,10)

    def test_network_redirects_cannot_leave_trusted_https_hosts(self):
        handler=updater.ReleaseRedirect()
        request=updater.urllib.request.Request(updater.API)
        for url in ('http://github.com/file','https://evil.example/file','file:///tmp/file','https://github.com:444/file'):
            with self.assertRaises(ValueError): handler.redirect_request(request,None,302,'',{},url)

    def test_update_api_is_fixed_and_bounded(self):
        with patch('updater.fetch',return_value=json.dumps(release()).encode()) as fetch:
            self.assertIsNotNone(updater.check_latest('0.3.0'))
            fetch.assert_called_once_with(updater.API,512*1024)


if __name__=='__main__': unittest.main()
