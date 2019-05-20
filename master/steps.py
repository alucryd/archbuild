import os
import re

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
        epoch = props.getProperty('epoch')
        pkg_arch = props.getProperty('pkg_arch')
        pkg = f'{pkg_name}-{epoch}{pkg_ver}-{pkg_rel}-{pkg_arch}.pkg.tar.xz'
        return [
            'mv',
            pkg,
            f'{repodir}/{repo_name}-{suffix}/x86_64/{pkg}'
        ]


class RepoAdd(steps.ShellCommand):
    haltOnFailure = 1
    flunkOnFailure = 1
    description = ['add package to repo']
    descriptionDone = ['package added to repo']

    @staticmethod
    @util.renderer
    def command(props):
        repodir = props.getProperty('repodir')
        suffix = props.getProperty('suffix')
        repo_name = props.getProperty('repo_name')
        pkg_name = props.getProperty('pkg_name')
        pkg_ver = props.getProperty('pkg_ver')
        pkg_rel = props.getProperty('pkg_rel')
        epoch = props.getProperty('epoch')
        pkg_arch = props.getProperty('pkg_arch')
        pkg = f'{pkg_name}-{epoch}{pkg_ver}-{pkg_rel}-{pkg_arch}.pkg.tar.xz'
        return [
            'repo-add',
            '-R',
            '-d',
            f'{repodir}/{repo_name}-{suffix}/x86_64/{repo_name}-{suffix}.db.tar.gz',
            f'{repodir}/{repo_name}-{suffix}/x86_64/{pkg}'
        ]


class InferPkgverFromGitTag(steps.SetProperties):
    name = 'infer pkgver from git tag'
    description = ['inferring pkgver from git tag']
    descriptionDone = ['pkgver inferred from git tag']

    @staticmethod
    @util.renderer
    def properties(props):
        git_tag = props.getProperty('git_tag')
        tag = props.getProperty('tag')
        if git_tag and tag:
            tag_pattern = re.compile(git_tag)
            match = tag_pattern.match(tag)
            return {
                'pkg_ver': match.group(1),
                'pkg_rel': 1
            }
        return {}


class SetPkgver(steps.ShellCommand):
    name = 'set pkgver'
    haltOnFailure = 1
    flunkOnFailure = 1
    description = ['set pkgver']
    descriptionDone = ['pkgver set']

    @staticmethod
    @util.renderer
    def command(props):
        pkgver = props.getProperty('pkg_ver')
        return [
            'sed',
            f'/pkgver=/c pkgver={pkgver}',
            '-i',
            'PKGBUILD'
        ]

    @staticmethod
    def doStepIf(step):
        pkgver = step.getProperty('pkg_ver')
        return bool(pkgver)


class SetPkgrel(steps.ShellCommand):
    name = 'set pkgrel'
    haltOnFailure = 1
    flunkOnFailure = 1
    description = ['set pkgrel']
    descriptionDone = ['pkgrel set']

    @staticmethod
    @util.renderer
    def command(props):
        pkgrel = props.getProperty('pkg_rel')
        return [
            'sed',
            f'/pkgrel=/c pkgrel={pkgrel}',
            '-i',
            'PKGBUILD'
        ]

    @staticmethod
    def doStepIf(step):
        pkgrel = step.getProperty('pkg_rel')
        return bool(pkgrel)


class Srcinfo(steps.ShellCommand):
    name = 'srcinfo'
    haltOnFailure = 1
    flunkOnFailure = 1
    description = ['generate .SRCINFO']
    descriptionDone = ['.SRCINFO generated']
    command = 'makepkg --printsrcinfo > .SRCINFO'


class Updpkgsums(steps.ShellCommand):
    name = 'updpkgsums'
    haltOnFailure = 1
    flunkOnFailure = 1
    description = ['update source checksums']
    descriptionDone = ['source checksums generated']
    command = ['updpkgsums']

    @staticmethod
    def doStepIf(step):
        pkgver = step.getProperty('pkg_ver')
        return bool(pkgver)


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
        epoch = props.getProperty('epoch')
        pkg_arch = props.getProperty('pkg_arch')
        pkg = f'{pkg_name}-{epoch}{pkg_ver}-{pkg_rel}-{pkg_arch}.pkg.tar.xz'
        return [
            'gpg',
            '--detach-sign',
            '--yes',
            f'{pkgdir}/{pkg}'
        ]


class MountPkgbuildCom(steps.MasterShellCommand):
    name = 'mount pkgbuild.com'
    haltOnFailure = 1
    flunkOnFailure = 1
    description = ['mount pkgbuild.com']
    descriptionDone = ['pkgbuild.com mounted']
    command = [
        'sshfs',
        '-C',
        'pkgbuild.com:',
        Interpolate('%(prop:sshdir)s')
    ]

    def __init__(self, **kwargs):
        super().__init__(command=MountPkgbuildCom.command, **kwargs)


class UnmountPkgbuildCom(steps.MasterShellCommand):
    name = 'unmount pkgbuild.com'
    haltOnFailure = 1
    flunkOnFailure = 1
    description = ['unmount pkgbuild.com']
    descriptionDone = ['pkgbuild.com unmounted']
    command = [
        'fusermount3',
        '-u',
        Interpolate('%(prop:sshdir)s')
    ]

    def __init__(self, **kwargs):
        super().__init__(command=UnmountPkgbuildCom.command, **kwargs)


class RepoSync(steps.MasterShellCommand):
    name = 'synchronize repository'
    haltOnFailure = 1
    flunkOnFailure = 1
    description = ['synchronize repository']
    descriptionDone = ['repository synchronized']
    command = [
        'rsync',
        '-avz',
        '--delete',
        Interpolate('%(prop:workerhost)s:~/public_html'),
        Interpolate('%(prop:sshdir)s')
    ]

    def __init__(self, **kwargs):
        super().__init__(command=RepoSync.command, **kwargs)


class Cleanup(steps.ShellCommand):
    name = 'clean up'
    haltOnFailure = 1
    flunkOnFailure = 1
    description = ['clean up']
    descriptionDone = ['cleaned up']
    command = ['rm', '-rf', Interpolate('%(prop:builddir)s/build')]
