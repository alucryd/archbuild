import re
from pathlib import Path
from urllib.parse import urlparse

from buildbot.plugins import *


class Srcinfo:
    FILENAME = '.SRCINFO'
    URL_PATTERN = re.compile(r'[^:]*:{0,2}(ht|f)tps?://.+')
    GIT_PATTERN = re.compile(r'([^:]*):{0,2}(git)\+(.+)')
    HG_PATTERN = re.compile(r'([^:]*):{0,2}(hg)\+(.+)')

    @staticmethod
    def parse(basedir: str, group: str, pkg_base: str) -> dict:
        src_names = []
        install = ''
        vcs_type = ''
        vcs_url = ''
        vcs_name = ''
        pkg_names = []
        pkg_ver = ''
        pkg_rel = ''
        pkg_arch = ''

        pkgdir = f'{group}/{pkg_base}'
        if group in ('community', 'packages'):
            pkgdir += '/trunk'
        path = Path(basedir) / pkgdir / Srcinfo.FILENAME

        with open(path, 'r') as f:
            line = f.readline()
            while line:
                if line.strip().startswith('source'):
                    source = line.split('=')[1].strip()
                    matches = (Srcinfo.GIT_PATTERN.match(source), Srcinfo.HG_PATTERN.match(source))
                    match = next((m for m in matches if m is not None), None)
                    if match is not None:
                        # pick the first vcs as the main one
                        if not vcs_name:
                            vcs_type = match.group(2)
                            vcs_url = match.group(3)
                            vcs_name = match.group(1)
                            if not vcs_name:
                                vcs_name = Path(urlparse(vcs_url).path).stem
                    elif Srcinfo.URL_PATTERN.match(source) is None:
                        src_names.append(source)
                elif line.strip().startswith('arch'):
                    pkg_arch = line.split('=')[1].strip()
                elif line.strip().startswith('pkgname'):
                    pkg_names.append(line.split('=')[1].strip())
                elif line.strip().startswith('pkgver'):
                    pkg_ver = line.split('=')[1].strip()
                elif line.strip().startswith('pkgrel'):
                    pkg_rel = line.split('=')[1].strip()
                elif line.strip().startswith('install'):
                    install = line.split('=')[1].strip()
                line = f.readline()
        return {
            'src_names': src_names,
            'install': install,
            'vcs_type': vcs_type,
            'vcs_url': vcs_url,
            'vcs_name': vcs_name,
            'pkg_names': pkg_names,
            'pkg_arch': pkg_arch,
            'pkg_ver': pkg_ver,
            'pkg_rel': pkg_rel
        }

    @staticmethod
    @util.renderer
    def properties(props):
        pkgbuilddir = props.getProperty('pkgbuilddir')
        group = props.getProperty('group')
        pkg_base = props.getProperty('pkg_base')
        properties = Srcinfo.parse(pkgbuilddir, group, pkg_base)
        print(properties)
        return properties
