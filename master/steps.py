import os

from buildbot.plugins import *
from buildbot.process.properties import Interpolate


class FindDependency(steps.SetPropertyFromCommand):
    haltOnFailure = 1
    flunkOnFailure = 1
    description = ['finding dependency']
    descriptionDone = ['dependency found']

    def __init__(self, **kwargs):
        super().__init__(command=FindDependency.command, extract_fn=FindDependency.restrict_glob, **kwargs)

    @staticmethod
    @util.renderer
    def command(props):
        repodir = props.getProperty('repodir')
        repo_name = props.getProperty('repo_name')
        suffix = props.getProperty('suffix')
        depends_name = props.getProperty('depends_name')
        return f'ls {repodir}/{repo_name}-{suffix}/x86_64/{depends_name}-*.pkg.tar.xz'

    @staticmethod
    def restrict_glob(rc, stdout, stderr):
        pkgs = [l.strip() for l in stdout.split('\n') if l.strip()]
        pkg = sorted(pkgs, key=lambda pkg: pkg.count('-'))[0]
        pkg_name = '-'.join(os.path.basename(pkg).split('-')[:-3])
        return {f'{pkg_name}_pkg': pkg}


class ArchBuild(steps.ShellCommand):
    name = 'archbuild'
    haltOnFailure = 1
    flunkOnFailure = 1
    description = ['building package']
    descriptionDone = ['package built']

    @staticmethod
    @util.renderer
    def command(props):
        command = ['sudo']
        repo_name = props.getProperty('repo_name')
        pkg_arch = props.getProperty('pkg_arch')
        repo_arch = 'x86_64' if pkg_arch == 'any' else pkg_arch
        depends = props.getProperty('depends')
        if 'multilib' in repo_name:
            command.append(f'{repo_name}-build')
        else:
            command.append(f'{repo_name}-{repo_arch}-build')
        if depends is not None:
            command.append('--')
            for depends_name in depends:
                pkg = props.getProperty(f'{depends_name}_pkg')
                command += ['-I', pkg]
        return command


class MovePackage(steps.ShellCommand):
    haltOnFailure = 1
    flunkOnFailure = 1
    description = ['move package to repo']
    descriptionDone = ['package moved to repo']

    def __init__(self, **kwargs):
        super().__init__(command=MovePackage.command, **kwargs)

    @staticmethod
    @util.renderer
    def command(props):
        repodir = props.getProperty('repodir')
        suffix = props.getProperty('suffix')
        repo_name = props.getProperty('repo_name')
        pkg_name = props.getProperty('pkg_name')
        pkg_ver = props.getProperty('pkg_ver')
        pkg_rel = props.getProperty('pkg_rel')
        pkg_arch = props.getProperty('pkg_arch')
        return [
            'mv',
            f'{pkg_name}-{pkg_ver}-{pkg_rel}-{pkg_arch}.pkg.tar.xz',
            f'{repodir}/{repo_name}-{suffix}/x86_64/{pkg_name}-{pkg_ver}-{pkg_rel}-{pkg_arch}.pkg.tar.xz'
        ]


class RepoAdd(steps.ShellCommand):
    haltOnFailure = 1
    flunkOnFailure = 1
    description = ['add package to repo']
    descriptionDone = ['package added to repo']

    def __init__(self, **kwargs):
        super().__init__(command=RepoAdd.command, **kwargs)

    @staticmethod
    @util.renderer
    def command(props):
        repodir = props.getProperty('repodir')
        suffix = props.getProperty('suffix')
        repo_name = props.getProperty('repo_name')
        pkg_name = props.getProperty('pkg_name')
        pkg_ver = props.getProperty('pkg_ver')
        pkg_rel = props.getProperty('pkg_rel')
        pkg_arch = props.getProperty('pkg_arch')
        return [
            'repo-add',
            '-R',
            '-d',
            f'{repodir}/{repo_name}-{suffix}/x86_64/{repo_name}-{suffix}.db.tar.gz',
            f'{repodir}/{repo_name}-{suffix}/x86_64/{pkg_name}-{pkg_ver}-{pkg_rel}-{pkg_arch}.pkg.tar.xz'
        ]


class Srcinfo(steps.ShellCommand):
    name = 'srcinfo'
    haltOnFailure = 1
    flunkOnFailure = 1
    description = ['generate .SRCINFO']
    descriptionDone = ['.SRCINFO generated']
    command = 'makepkg --printsrcinfo > .SRCINFO'


class GpgSign(steps.MasterShellCommand):
    haltOnFailure = 1
    flunkOnFailure = 1
    description = ['sign a package']
    descriptionDone = ['package signed']

    def __init__(self, **kwargs):
        super().__init__(command=GpgSign.command, **kwargs)

    @staticmethod
    @util.renderer
    def command(props):
        pkgdir = props.getProperty('pkgdir')
        pkg_name = props.getProperty('pkg_name')
        pkg_ver = props.getProperty('pkg_ver')
        pkg_rel = props.getProperty('pkg_rel')
        pkg_arch = props.getProperty('pkg_arch')
        return [
            'gpg',
            '--detach-sign',
            '--yes',
            f'{pkgdir}/{pkg_name}-{pkg_ver}-{pkg_rel}-{pkg_arch}.pkg.tar.xz'
        ]


class Cleanup(steps.ShellCommand):
    name = 'clean up'
    haltOnFailure = 1
    flunkOnFailure = 1
    description = ['clean up']
    descriptionDone = ['cleaned up']
    command = ['rm', '-rf', Interpolate('%(prop:builddir)s/build')]
