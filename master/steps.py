import os

from buildbot.plugins import steps, util


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
        pkgdir = props.getProperty("pkgdir")
        repo = props.getProperty("repo")
        testing = props.getProperty("testing")
        staging = props.getProperty("staging")
        if testing:
            repo += "-testing"
        elif staging:
            repo += "-staging"
        depends_name = props.getProperty("depends_name")
        return f"ls {pkgdir}/{depends_name}-*.pkg.tar.zst"

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
        testing = props.getProperty("testing")
        staging = props.getProperty("staging")
        pkgver = props.getProperty("pkg_ver")
        pkgrel = props.getProperty("pkg_rel")
        depends = props.getProperty("depends")
        command = [
            "pkgctl",
            "build",
            "-o",
        ]
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


class BumpPkgrel(steps.ShellCommand):
    name = "bump pkgrel"
    haltOnFailure = 1
    flunkOnFailure = 1
    description = ["bump pkgrel"]
    descriptionDone = ["pkgrel bumped"]

    @staticmethod
    @util.renderer
    def command(_props):
        return [
            "awk",
            "-i",
            "inplace",
            '{FS=OFS="=" }/pkgrel/{$2+=1}1',
            "PKGBUILD",
        ]

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
