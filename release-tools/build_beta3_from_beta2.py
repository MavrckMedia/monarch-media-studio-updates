"""One-time byte-exact beta.3 distribution build from public beta.2.
This code does not execute any downloaded ZIP member. It refuses publishing if
the previous release or the reproduced build differs from SHA-pinned CI bytes.
"""
from __future__ import annotations
import hashlib
import io
import json
from pathlib import Path
import urllib.request
import zipfile

OLD_URL='https://github.com/MavrckMedia/monarch-media-studio-updates/releases/download/v0.1.0-beta.2/MonarchMediaStudio_UpdateEnabled_FriendsBeta_0.1.0-beta.2.zip'
OLD_SHA='98c668806eee39689092beb2f8b18ea44e95d9c241e34bae75895a417bd45000'
NEW_SHA='64a1e233e1746d22539b235e1ddddd944272af414cc7294ecdc41cc5772308d6'
NEW_NAME='MonarchMediaStudio_0.1.0-beta.3.zip'
PREFIX='MonarchMediaStudio/'
NOTE='''## YouTube Error 153: embedded player identity

**0.1.0-beta.3 candidate:** The Media Studio iframe previously forced `referrerpolicy=no-referrer`. YouTube reports **Error 153** when requests lack HTTP Referer or equivalent API client identification. This maintenance patch changes *only YouTube* frames to `strict-origin-when-cross-origin` (YouTube's recommended policy); other third-party frames retain their stricter no-referrer setting. The editor and credit features are unchanged.

**Limitations:** A local OBS Browser Source loaded from a `file://` HTML file may have an opaque local origin and no meaningful HTTP Referer. Consequently, the policy adjustment alone cannot guarantee YouTube playback. For reliable integration, serve the Media Studio page from a trusted HTTP(S) origin with a real Referer, ideally HTTPS, rather than using a local file. Hosted web pages expose their downloaded HTML/JS to visitors, so don't publish private/license material with them. Never forge an `origin` query parameter or use an unauthorized proxy as a substitute for proper client identification.

If YouTube still displays Error 153, test the exact video in YouTube's embed-enabled player from a reputable HTTPS webpage, then verify OBS/Cef behavior on Windows. This beta makes no claim of guaranteed local-file YouTube compatibility; the issue needs real OBS validation before release.

'''

def replace_once(value: str, before: str, after: str) -> str:
    if value.count(before)!=1:
        raise ValueError(f'Unexpected original source. Expected unique text: {before[:60]!r}')
    return value.replace(before, after, 1)

def build(previous:bytes, destination:Path) -> tuple[str,int]:
    if hashlib.sha256(previous).hexdigest()!=OLD_SHA:
        raise ValueError('Source release hash mismatch')
    with zipfile.ZipFile(io.BytesIO(previous)) as archive:
        entries={name:archive.read(name) for name in archive.namelist()}
    if len(entries)!=10 or not all(x.startswith(PREFIX) for x in entries):
        raise ValueError('Unexpected package contents')
    content=entries[PREFIX+'MonarchMediaStudio.html'].decode('utf-8')
    content=replace_once(content,'<meta name="viewport" content="width=device-width,initial-scale=1">',
        '<meta name="viewport" content="width=device-width,initial-scale=1">\n<meta name="referrer" content="strict-origin-when-cross-origin">')
    content=replace_once(content,
        "      v=node('iframe');v.src=safe;v.title=l.name;v.referrerPolicy='no-referrer';",
        "      v=node('iframe');v.title=l.name;\n"
        "      // YouTube requires HTTP Referer identification. Other third-party\n"
        "      // frames retain the original restrictive policy for privacy.\n"
        "      v.referrerPolicy=l.type==='youtube'?'strict-origin-when-cross-origin':'no-referrer';\n"
        "      v.src=safe;")
    entries[PREFIX+'MonarchMediaStudio.html']=content.encode('utf-8')
    readme=entries[PREFIX+'README.md'].decode('utf-8')
    readme=replace_once(readme,'## Supported layer types',NOTE+'## Supported layer types')
    entries[PREFIX+'README.md']=readme.encode('utf-8')
    entries[PREFIX+'VERSION.txt']=b'0.1.0-beta.3\n'
    js=entries[PREFIX+'update-core.js'].decode('utf-8')
    js=replace_once(js,"return '0.1.0-beta.2'","return '0.1.0-beta.3'")
    entries[PREFIX+'update-core.js']=js.encode('utf-8')
    m=json.loads(entries[PREFIX+'MANIFEST.json'])
    if m['release']!='0.1.0-beta.2':raise ValueError('Original release is not beta.2')
    m['release']='0.1.0-beta.3'
    m['files']={name:hashlib.sha256(data).hexdigest() for name,data in sorted(entries.items()) if name!=PREFIX+'MANIFEST.json'}
    entries[PREFIX+'MANIFEST.json']=(json.dumps(m,indent=2,sort_keys=True)+'\n').encode('utf-8')
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination,'w',compression=zipfile.ZIP_DEFLATED) as out:
        for name,data in sorted(entries.items()):
            meta=zipfile.ZipInfo(name,date_time=(2026,10,10,12,0,0))
            meta.compress_type=zipfile.ZIP_DEFLATED
            meta.external_attr=0o644<<16
            out.writestr(meta,data,compress_type=zipfile.ZIP_DEFLATED,compresslevel=8)
    binary=destination.read_bytes()
    sha=hashlib.sha256(binary).hexdigest()
    if sha!=NEW_SHA or len(binary)!=27035:
        destination.unlink(missing_ok=True)
        raise ValueError(f'Reproduced binary does not match tested CI build: {sha}, {len(binary)}')
    return sha,len(binary)

if __name__=='__main__':
    import sys
    if len(sys.argv)==3:
        previous=Path(sys.argv[1]).read_bytes();destination=Path(sys.argv[2])
    else:
        req=urllib.request.Request(OLD_URL,headers={'User-Agent':'MonarchMediaStudioRelease/1.0'})
        with urllib.request.urlopen(req,timeout=60) as response:
            previous=response.read(64*1024*1024+1)
        destination=Path('dist')/NEW_NAME
    print('Verified new binary:',build(previous,destination),'at',destination)
