import os
import re

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
        repo_name = props.getProperty("repo_name")
        suffix = props.getProperty("suffix")
        depends_name = props.getProperty("depends_name")
        return f"ls {repodir}/{repo_name}-{suffix}/x86_64/{depends_name}-*.pkg.tar.zst"

    @staticmethod
    def restrict_glob(rc, stdout, stderr):
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

    @staticmethod
    @util.renderer
    def command(props):
        command = ["sudo"]
        repo_name = props.getProperty("repo_name")
        pkg_arch = props.getProperty("pkg_arch")
        repo_arch = "x86_64" if pkg_arch == "any" else pkg_arch
        depends = props.getProperty("depends")
        if "multilib" in repo_name:
            command.append(f"{repo_name}-build")
        else:
            command.append(f"{repo_name}-{repo_arch}-build")
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
        repo_name = props.getProperty("repo_name")
        pkg_name = props.getProperty("pkg_name")
        pkg_ver = props.getProperty("pkg_ver")
        pkg_rel = props.getProperty("pkg_rel")
        epoch = props.getProperty("epoch")
        pkg_arch = props.getProperty("pkg_arch")
        pkg = f"{pkg_name}-{epoch}{pkg_ver}-{pkg_rel}-{pkg_arch}.pkg.tar.zst"
        return ["mv", pkg, f"{repodir}/{repo_name}-{suffix}/x86_64/{pkg}"]


class RepoAdd(steps.ShellCommand):
    haltOnFailure = 1
    flunkOnFailure = 1
    description = ["add package to repo"]
    descriptionDone = ["package added to repo"]

    @staticmethod
    @util.renderer
    def command(props):
        repodir = props.getProperty("repodir")
        suffix = props.getProperty("suffix")
        repo_name = props.getProperty("repo_name")
        pkg_name = props.getProperty("pkg_name")
        pkg_ver = props.getProperty("pkg_ver")
        pkg_rel = props.getProperty("pkg_rel")
        epoch = props.getProperty("epoch")
        pkg_arch = props.getProperty("pkg_arch")
        pkg = f"{pkg_name}-{epoch}{pkg_ver}-{pkg_rel}-{pkg_arch}.pkg.tar.zst"
        return [
            "repo-add",
            "-R",
            f"{repodir}/{repo_name}-{suffix}/x86_64/{repo_name}-{suffix}.db.tar.gz",
            f"{repodir}/{repo_name}-{suffix}/x86_64/{pkg}",
        ]


class SetPkgver(steps.ShellCommand):
    name = "set pkgver"
    haltOnFailure = 1
    flunkOnFailure = 1
    description = ["set pkgver"]
    descriptionDone = ["pkgver set"]

    @staticmethod
    @util.renderer
    def command(props):
        pkgver = props.getProperty("pkg_ver")
        return ["sed", f"/pkgver=/c pkgver={pkgver}", "-i", "PKGBUILD"]

    @staticmethod
    def doStepIf(step):
        pkgver = step.getProperty("pkg_ver")
        return bool(pkgver)


class SetPkgrel(steps.ShellCommand):
    name = "set pkgrel"
    haltOnFailure = 1
    flunkOnFailure = 1
    description = ["set pkgrel"]
    descriptionDone = ["pkgrel set"]

    @staticmethod
    @util.renderer
    def command(props):
        pkgrel = props.getProperty("pkg_rel")
        return ["sed", f"/pkgrel=/c pkgrel={pkgrel}", "-i", "PKGBUILD"]

    @staticmethod
    def doStepIf(step):
        pkgrel = step.getProperty("pkg_rel")
        return bool(pkgrel)


class BumpPkgrel(steps.ShellCommand):
    name = "bump pkgrel"
    haltOnFailure = 1
    flunkOnFailure = 1
    description = ["bump pkgrel"]
    descriptionDone = ["pkgrel bumped"]

    @staticmethod
    @util.renderer
    def command(props):
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


class CreateSshfsDirectory(steps.MasterShellCommand):
    name = "create sshfs directory"
    haltOnFailure = 1
    flunkOnFailure = 1
    description = ["create sshfs directory"]
    descriptionDone = ["sshfs directory created"]
    command = ["mkdir", "-p", Interpolate("%(prop:sshdir)s")]

    def __init__(self, **kwargs):
        super().__init__(command=self.command, **kwargs)


class MountPkgbuildCom(steps.MasterShellCommand):
    name = "mount pkgbuild.com"
    haltOnFailure = 1
    flunkOnFailure = 1
    description = ["mount pkgbuild.com"]
    descriptionDone = ["pkgbuild.com mounted"]
    command = [
        "sshfs",
        "-C",
        "pkgbuild.com:",
        Interpolate("%(prop:sshdir)s"),
        "-o",
        "idmap=user",
    ]

    def __init__(self, **kwargs):
        super().__init__(command=self.command, **kwargs)


class UnmountPkgbuildCom(steps.MasterShellCommand):
    name = "unmount pkgbuild.com"
    haltOnFailure = 1
    flunkOnFailure = 1
    description = ["unmount pkgbuild.com"]
    descriptionDone = ["pkgbuild.com unmounted"]
    command = ["fusermount3", "-u", Interpolate("%(prop:sshdir)s")]

    def __init__(self, **kwargs):
        super().__init__(command=self.command, **kwargs)


class RepoSync(steps.MasterShellCommand):
    name = "synchronize repository"
    haltOnFailure = 1
    flunkOnFailure = 1
    description = ["synchronize repository"]
    descriptionDone = ["repository synchronized"]
    command = [
        "rsync",
        "-avz",
        "--delete",
        Interpolate("%(prop:workerhost)s:~/public_html"),
        Interpolate("%(prop:sshdir)s"),
    ]

    def __init__(self, **kwargs):
        super().__init__(command=self.command, **kwargs)


class Cleanup(steps.ShellCommand):
    name = "clean up"
    haltOnFailure = 1
    flunkOnFailure = 1
    description = ["clean up"]
    descriptionDone = ["cleaned up"]
    command = ["rm", "-rf", Interpolate("%(prop:builddir)s/build")]
