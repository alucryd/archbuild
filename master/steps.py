import os

from buildbot.plugins import steps, util
from buildbot.process.properties import Interpolate


class FindDependency(steps.SetPropertyFromCommand):
    haltOnFailure = 1
    flunkOnFailure = 1
    description = ["finding dependency"]
    descriptionDone = ["dependency found"]

    def __init__(self, **kwargs):
        super().__init__(command=self.command, extract_fn=self.restrict_glob, **kwargs)

    @staticmethod
    @util.renderer
    def command(props):
        repodir = props.getProperty("repodir")
        repo = props.getProperty("repo")
        suffix = props.getProperty("suffix")
        depends_name = props.getProperty("depends_name")
        return f"ls {repodir}/{repo}-{suffix}/x86_64/{depends_name}-*.pkg.tar.zst"

    @staticmethod
    def restrict_glob(_rc, stdout, _stderr):
        pkgs = [l.strip() for l in stdout.split("\n") if l.strip()]
        pkg = sorted(pkgs, key=lambda pkg: pkg.count("-"))[0]
        pkg_name = "-".join(os.path.basename(pkg).split("-")[:-3])
        return {f"{pkg_name}_pkg": pkg}


class ArchBuild(steps.ShellCommand):
    name = "archbuild"
    haltOnFailure = 1
    flunkOnFailure = 1
    description = ["building package"]
    descriptionDone = ["package built"]
    timeout = None

    @staticmethod
    @util.renderer
    def command(props):
        repo = props.getProperty("repo")
        pkgver = props.getProperty("pkg_ver")
        pkgrel = props.getProperty("pkg_rel")
        testing = props.getProperty("testing")
        staging = props.getProperty("staging")
        depends = props.getProperty("depends")
        command = ["sudo", "pkgctl", "build", "--repo", repo]
        if pkgver:
            command.append(f"--pkgver={pkgver}")
        if pkgrel:
            command.append(f"--pkgrel={pkgrel}")
        if testing:
            command.append("-t")
        elif staging:
            command.append("-s")
        if depends is not None:
            command.append("--")
            for depends_name in depends:
                pkg = props.getProperty(f"{depends_name}_pkg")
                command += ["-I", pkg]
        return command


class MovePackage(steps.ShellCommand):
    haltOnFailure = 1
    flunkOnFailure = 1
    description = ["move package to repo"]
    descriptionDone = ["package moved to repo"]

    def __init__(self, **kwargs):
        super().__init__(command=self.command, **kwargs)

    @staticmethod
    @util.renderer
    def command(props):
        repodir = props.getProperty("repodir")
        suffix = props.getProperty("suffix")
        repo = props.getProperty("repo")
        pkg_name = props.getProperty("pkg_name")
        pkg_ver = props.getProperty("pkg_ver")
        pkg_rel = props.getProperty("pkg_rel")
        epoch = props.getProperty("epoch")
        pkg_arch = props.getProperty("pkg_arch")
        pkg = f"{pkg_name}-{epoch}{pkg_ver}-{pkg_rel}-{pkg_arch}.pkg.tar.zst"
        return ["mv", pkg, f"{repodir}/{repo}-{suffix}/x86_64/{pkg}"]


class RepoAdd(steps.ShellCommand):
    haltOnFailure = 1
    flunkOnFailure = 1
    description = ["add package to repo"]
    descriptionDone = ["package added to repo"]

    @staticmethod
    @util.renderer
    def command(props):
        repodir = props.getProperty("repodir")
        repo = props.getProperty("repo")
        suffix = props.getProperty("suffix")
        pkg_name = props.getProperty("pkg_name")
        pkg_ver = props.getProperty("pkg_ver")
        pkg_rel = props.getProperty("pkg_rel")
        epoch = props.getProperty("epoch")
        pkg_arch = props.getProperty("pkg_arch")
        pkg = f"{pkg_name}-{epoch}{pkg_ver}-{pkg_rel}-{pkg_arch}.pkg.tar.zst"
        return [
            "repo-add",
            "-R",
            f"{repodir}/{repo}-{suffix}/x86_64/{repo}-{suffix}.db.tar.gz",
            f"{repodir}/{repo}-{suffix}/x86_64/{pkg}",
        ]


class BumpPkgrel(steps.ShellCommand):
    name = "bump pkgrel"
    haltOnFailure = 1
    flunkOnFailure = 1
    description = ["bump pkgrel"]
    descriptionDone = ["pkgrel bumped"]

    @staticmethod
    @util.renderer
    def command(_props):
        return ["awk", "-i", "inplace", '{FS=OFS="=" }/pkgrel/{$2+=1}1', "PKGBUILD"]

    @staticmethod
    def doStepIf(step):
        return step.getProperty("bump_pkg_rel", False)


class SetTagRevision(steps.ShellCommand):
    name = "set tag revision"
    haltOnFailure = 1
    flunkOnFailure = 1
    description = ["set tag revision"]
    descriptionDone = ["tag revision set"]

    @staticmethod
    @util.renderer
    def command(props):
        revision = props.getProperty("revision")
        return [
            "sed",
            "-r",
            f"s/_tag=[a-f0-9]{{40}}/_tag={revision}/",
            "-i",
            "PKGBUILD",
        ]

    @staticmethod
    def doStepIf(step):
        revision = step.getProperty("revision")
        return bool(revision)


class SetCommitRevision(steps.ShellCommand):
    name = "set commit revision"
    haltOnFailure = 1
    flunkOnFailure = 1
    description = ["set commit revision"]
    descriptionDone = ["commit revision set"]

    @staticmethod
    @util.renderer
    def command(props):
        revision = props.getProperty("revision")
        return [
            "sed",
            "-r",
            f"s/_commit=[a-f0-9]{{40}}/_commit={revision}/",
            "-i",
            "PKGBUILD",
        ]

    @staticmethod
    def doStepIf(step):
        revision = step.getProperty("revision")
        return bool(revision)


class Srcinfo(steps.ShellCommand):
    name = "srcinfo"
    haltOnFailure = 1
    flunkOnFailure = 1
    description = ["generate .SRCINFO"]
    descriptionDone = [".SRCINFO generated"]
    command = "makepkg --printsrcinfo > .SRCINFO"


class Updpkgsums(steps.ShellCommand):
    name = "updpkgsums"
    haltOnFailure = 1
    flunkOnFailure = 1
    description = ["update source checksums"]
    descriptionDone = ["source checksums generated"]
    command = ["updpkgsums"]

    @staticmethod
    def doStepIf(step):
        pkgver = step.getProperty("pkg_ver")
        return bool(pkgver)


class GpgSign(steps.MasterShellCommand):
    haltOnFailure = 1
    flunkOnFailure = 1
    description = ["sign a package"]
    descriptionDone = ["package signed"]

    def __init__(self, **kwargs):
        super().__init__(command=self.command, **kwargs)

    @staticmethod
    @util.renderer
    def command(props):
        pkgdir = props.getProperty("pkgdir")
        pkg_name = props.getProperty("pkg_name")
        pkg_ver = props.getProperty("pkg_ver")
        pkg_rel = props.getProperty("pkg_rel")
        epoch = props.getProperty("epoch")
        pkg_arch = props.getProperty("pkg_arch")
        pkg = f"{pkg_name}-{epoch}{pkg_ver}-{pkg_rel}-{pkg_arch}.pkg.tar.zst"
        return ["gpg", "--detach-sign", "--yes", f"{pkgdir}/{pkg}"]


class CreateSshfsWorkerDirectory(steps.MasterShellCommand):
    name = "create sshfs worker directory"
    haltOnFailure = 1
    flunkOnFailure = 1
    description = ["create sshfs worker directory"]
    descriptionDone = ["sshfs worker directory created"]

    def __init__(self, **kwargs):
        super().__init__(command=self.command, **kwargs)

    @staticmethod
    @util.renderer
    def command(props):
        sshdir = props.getProperty("sshdir")
        workerhost = props.getProperty("workerhost")
        return [
            "mkdir",
            "-p",
            f"{sshdir}/{workerhost}",
        ]


class CreateSshfsRemoteDirectory(steps.MasterShellCommand):
    name = "create sshfs remote directory"
    haltOnFailure = 1
    flunkOnFailure = 1
    description = ["create sshfs remote directory"]
    descriptionDone = ["sshfs remote directory created"]

    def __init__(self, **kwargs):
        super().__init__(command=self.command, **kwargs)

    @staticmethod
    @util.renderer
    def command(props):
        sshdir = props.getProperty("sshdir")
        remotehost = props.getProperty("remotehost")
        return [
            "mkdir",
            "-p",
            f"{sshdir}/{remotehost}",
        ]


class MountWorkerDirectory(steps.MasterShellCommand):
    name = "mount worker directory"
    haltOnFailure = 1
    flunkOnFailure = 1
    description = ["mount worker directory"]
    descriptionDone = ["worker directory mounted"]

    def __init__(self, **kwargs):
        super().__init__(command=self.command, **kwargs)

    @staticmethod
    @util.renderer
    def command(props):
        sshdir = props.getProperty("sshdir")
        workerhost = props.getProperty("workerhost")
        return [
            "sshfs",
            "-C",
            f"{workerhost}:",
            f"{sshdir}/{workerhost}",
            "-o",
            "idmap=user",
        ]


class MountRemoteDirectory(steps.MasterShellCommand):
    name = "mount remote directory"
    haltOnFailure = 1
    flunkOnFailure = 1
    description = ["mount remote directory"]
    descriptionDone = ["remote directory mounted"]

    def __init__(self, **kwargs):
        super().__init__(command=self.command, **kwargs)

    @staticmethod
    @util.renderer
    def command(props):
        sshdir = props.getProperty("sshdir")
        remotehost = props.getProperty("remotehost")
        return [
            "sshfs",
            "-C",
            f"{remotehost}:",
            f"{sshdir}/{remotehost}",
            "-o",
            "idmap=user",
        ]


class UnmountWorkerDirectory(steps.MasterShellCommand):
    name = "unmount worker directory"
    haltOnFailure = 1
    flunkOnFailure = 1
    description = ["unmount worker directory"]
    descriptionDone = ["worker directory unmounted"]

    def __init__(self, **kwargs):
        super().__init__(command=self.command, **kwargs)

    @staticmethod
    @util.renderer
    def command(props):
        sshdir = props.getProperty("sshdir")
        workerhost = props.getProperty("workerhost")
        return [
            "fusermount3",
            "-u",
            f"{sshdir}/{workerhost}",
        ]


class UnmountRemoteDirectory(steps.MasterShellCommand):
    name = "unmount remote directory"
    haltOnFailure = 1
    flunkOnFailure = 1
    description = ["unmount remote directory"]
    descriptionDone = ["remote directory unmounted"]

    def __init__(self, **kwargs):
        super().__init__(command=self.command, **kwargs)

    @staticmethod
    @util.renderer
    def command(props):
        sshdir = props.getProperty("sshdir")
        remotehost = props.getProperty("remotehost")
        return [
            "fusermount3",
            "-u",
            f"{sshdir}/{remotehost}",
        ]


class RepoSync(steps.MasterShellCommand):
    name = "synchronize repository"
    haltOnFailure = 1
    flunkOnFailure = 1
    description = ["synchronize repository"]
    descriptionDone = ["repository synchronized"]

    def __init__(self, **kwargs):
        super().__init__(command=self.command, **kwargs)

    @staticmethod
    @util.renderer
    def command(props):
        sshdir = props.getProperty("sshdir")
        workerhost = props.getProperty("workerhost")
        remotehost = props.getProperty("remotehost")
        return [
            "rsync",
            "-avz",
            "--delete",
            f"{sshdir}/{workerhost}/public_html",
            f"{sshdir}/{remotehost}",
        ]


class Cleanup(steps.ShellCommand):
    name = "clean up"
    haltOnFailure = 1
    flunkOnFailure = 1
    description = ["clean up"]
    descriptionDone = ["cleaned up"]
    command = ["rm", "-rf", Interpolate("%(prop:builddir)s/build")]
