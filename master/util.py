import re
import subprocess
from pathlib import Path
from urllib.parse import urlparse

from buildbot.plugins import *


class Util:
    FILENAME = '.SRCINFO'
    URL_PATTERN = re.compile(r'[^:]*:{0,2}(ht|f)tps?://.+')
    GIT_PATTERN = re.compile(r'([^:]*):{0,2}(git)\+([^#]+)#?(.*)')
    HG_PATTERN = re.compile(r'([^:]*):{0,2}(hg)\+([^#]+)#?(.*)')

    @staticmethod
    def parse_srcinfo(basedir: str, group: str, pkg_base: str) -> dict:
        src_names = []
        install = ''
        vcs_type = ''
        vcs_url = ''
        vcs_name = ''
        pkg_names = []
        pkg_ver = ''
        pkg_rel = ''
        epoch = ''
        pkg_arch = ''

        git_branch = ''
        git_tag = ''
        hg_branch = ''

        pkgdir = f'{group}/{pkg_base}'
        if group in ('community', 'packages'):
            pkgdir += '/trunk'
        path = Path(basedir) / pkgdir / Util.FILENAME

        if not path.is_file():
            subprocess.run('makepkg --printsrcinfo > .SRCINFO', cwd=path.parent, shell=True)

        with open(path, 'r') as f:
            line = f.readline()
            while line:
                if line.strip().startswith('source'):
                    source = '='.join(line.split('=')[1:]).strip()
                    matches = (Util.GIT_PATTERN.match(source), Util.HG_PATTERN.match(source))
                    match = next((m for m in matches if m is not None), None)
                    if match is not None:
                        # pick the first vcs as the main one
                        if not vcs_name:
                            vcs_type = match.group(2)
                            vcs_url = match.group(3)
                            vcs_name = match.group(1)
                            if not vcs_name:
                                vcs_name = Path(urlparse(vcs_url).path).stem
                            if match.group(4):
                                fragment = match.group(4).split('=')
                                if vcs_type == 'git' and fragment[0] == 'tag':
                                    git_tag = fragment[1].replace(pkg_ver, '(.+)')
                                elif vcs_type == 'hg' and fragment[0] == 'tag':
                                    git_tag = fragment[1].replace(pkg_ver, '(.+)')
                    elif Util.URL_PATTERN.match(source) is None:
                        src_names.append(source)
                elif line.strip().startswith('arch'):
                    pkg_arch = line.split('=')[1].strip()
                elif line.strip().startswith('pkgname'):
                    pkg_names.append(line.split('=')[1].strip())
                elif line.strip().startswith('pkgver'):
                    pkg_ver = line.split('=')[1].strip()
                elif line.strip().startswith('pkgrel'):
                    pkg_rel = line.split('=')[1].strip()
                elif line.strip().startswith('epoch'):
                    epoch = line.split('=')[1].strip() + ':'
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
            'pkg_rel': pkg_rel,
            'epoch': epoch,
            'git_branch': git_branch,
            'git_tag': git_tag,
            'hg_branch': hg_branch
        }

    @staticmethod
    @util.renderer
    def srcinfo(props):
        pkgbuilddir = props.getProperty('pkgbuilddir')
        group = props.getProperty('group')
        pkg_base = props.getProperty('pkg_base')
        properties = Util.parse_srcinfo(pkgbuilddir, group, pkg_base)
        return properties

    @staticmethod
    @util.renderer
    def pkg(props):
        pkg_name = props.getProperty('pkg_name')
        pkg_ver = props.getProperty('pkg_ver')
        pkg_rel = props.getProperty('pkg_rel')
        epoch = props.getProperty('epoch')
        pkg_arch = props.getProperty('pkg_arch')
        return f'{pkg_name}-{epoch}{pkg_ver}-{pkg_rel}-{pkg_arch}.pkg.tar.xz'

    @staticmethod
    @util.renderer
    def sig(props):
        pkg_name = props.getProperty('pkg_name')
        pkg_ver = props.getProperty('pkg_ver')
        pkg_rel = props.getProperty('pkg_rel')
        epoch = props.getProperty('epoch')
        pkg_arch = props.getProperty('pkg_arch')
        return f'{pkg_name}-{epoch}{pkg_ver}-{pkg_rel}-{pkg_arch}.pkg.tar.xz.sig'

    @staticmethod
    @util.renderer
    def pkg_masterdest(props):
        pkgdir = props.getProperty('pkgdir')
        pkg_name = props.getProperty('pkg_name')
        pkg_ver = props.getProperty('pkg_ver')
        pkg_rel = props.getProperty('pkg_rel')
        epoch = props.getProperty('epoch')
        pkg_arch = props.getProperty('pkg_arch')
        return f'{pkgdir}/{pkg_name}-{epoch}{pkg_ver}-{pkg_rel}-{pkg_arch}.pkg.tar.xz'

    @staticmethod
    @util.renderer
    def sig_mastersrc(props):
        pkgdir = props.getProperty('pkgdir')
        pkg_name = props.getProperty('pkg_name')
        pkg_ver = props.getProperty('pkg_ver')
        pkg_rel = props.getProperty('pkg_rel')
        epoch = props.getProperty('epoch')
        pkg_arch = props.getProperty('pkg_arch')
        return f'{pkgdir}/{pkg_name}-{epoch}{pkg_ver}-{pkg_rel}-{pkg_arch}.pkg.tar.xz.sig'

    @staticmethod
    @util.renderer
    def sig_workerdest(props):
        repodir = props.getProperty('repodir')
        repo_name = props.getProperty('repo_name')
        suffix = props.getProperty('suffix')
        pkg_name = props.getProperty('pkg_name')
        pkg_ver = props.getProperty('pkg_ver')
        pkg_rel = props.getProperty('pkg_rel')
        epoch = props.getProperty('epoch')
        pkg_arch = props.getProperty('pkg_arch')
        return f'{repodir}/{repo_name}-{suffix}/x86_64/{pkg_name}-{epoch}{pkg_ver}-{pkg_rel}-{pkg_arch}.pkg.tar.xz.sig'
