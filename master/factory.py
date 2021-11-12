from buildbot.plugins import steps, util

from steps import (
    ArchBuild,
    BumpPkgrel,
    Cleanup,
    CreateSshfsRemoteDirectory,
    CreateSshfsWorkerDirectory,
    FindDependency,
    GpgSign,
    MountRemoteDirectory,
    MountWorkerDirectory,
    MovePackage,
    RepoAdd,
    RepoSync,
    SetCommitRevision,
    SetPkgrel,
    SetPkgver,
    SetTagRevision,
    Srcinfo,
    UnmountRemoteDirectory,
    UnmountWorkerDirectory,
    Updpkgsums,
)
from util import ArchBuildUtil


class ArchBuildFactory(util.BuildFactory):
    def __init__(self, pkgbuilddir: str, group: str, pkg_base: str, properties: dict):
        super().__init__()

        gpg_sign = properties["gpg_sign"]
        sshdir = properties["sshdir"]
        workdir = f"{pkgbuilddir}/{group}/{pkg_base}"

        if group in ("community", "packages"):
            workdir += "/trunk"

        # set initial properties
        self.addStep(
            steps.SetProperties(
                name="set properties from srcinfo", properties=properties
            )
        )

        # find dependencies
        depends = properties["depends"]
        if depends is not None:
            for depends_name in depends:
                self.addSteps(
                    [
                        steps.SetProperty(
                            name=f"set depends_name to {depends_name}",
                            property="depends_name",
                            value=depends_name,
                            hideStepIf=True,
                        ),
                        FindDependency(name=f"find {depends_name}"),
                    ]
                )

        # download build files
        self.addStep(
            steps.FileDownload(
                name="download PKGBUILD",
                mastersrc=f"{workdir}/PKGBUILD",
                workerdest="PKGBUILD",
            )
        )
        for src_name in properties["src_names"]:
            self.addStep(
                steps.FileDownload(
                    name=f"download {src_name}",
                    mastersrc=f"{workdir}/{src_name}",
                    workerdest=src_name,
                )
            )
        install = properties["install"]
        if install:
            self.addStep(
                steps.FileDownload(
                    name=f"download {install}",
                    mastersrc=f"{workdir}/{install}",
                    workerdest=install,
                )
            )

        self.addSteps([SetPkgver(), SetPkgrel(), BumpPkgrel(), Updpkgsums()])

        # update git tag revision
        if properties["git_tag"]:
            self.addStep(SetTagRevision())

        # update git commit revision
        if properties["git_revision"]:
            self.addStep(SetCommitRevision())

        # build
        self.addStep(ArchBuild())

        # update properties
        self.addSteps(
            [
                Srcinfo(),
                steps.FileUpload(
                    name="upload updated PKGBUILD",
                    workersrc="PKGBUILD",
                    masterdest=f"{workdir}/PKGBUILD",
                ),
                steps.FileUpload(
                    name="upload updated .SRCINFO",
                    workersrc=".SRCINFO",
                    masterdest=f"{workdir}/.SRCINFO",
                ),
                steps.SetProperties(
                    name="refresh properties from srcinfo",
                    properties=ArchBuildUtil.srcinfo,
                ),
            ]
        )

        # upload and optionally sign packages
        for pkg_name in properties["pkg_names"]:
            self.addSteps(
                [
                    steps.SetProperty(
                        name=f"set pkg_name to {pkg_name}",
                        property="pkg_name",
                        value=pkg_name,
                        hideStepIf=True,
                    ),
                    steps.FileUpload(
                        name=f"upload {pkg_name}",
                        workersrc=ArchBuildUtil.pkg,
                        masterdest=ArchBuildUtil.pkg_masterdest,
                    ),
                    MovePackage(name=f"move {pkg_name}"),
                ]
            )
            if gpg_sign:
                self.addSteps(
                    [
                        GpgSign(name=f"sign {pkg_name}"),
                        steps.FileDownload(
                            name=f"download {pkg_name} sig",
                            mastersrc=ArchBuildUtil.sig_mastersrc,
                            workerdest=ArchBuildUtil.sig_workerdest,
                        ),
                    ]
                )

            # update repository
            self.addStep(RepoAdd(name=f"add {pkg_name}"))

        # synchronize repository
        if sshdir:
            self.addStep(CreateSshfsWorkerDirectory())
            self.addStep(CreateSshfsRemoteDirectory())
            self.addStep(MountWorkerDirectory())
            self.addStep(MountRemoteDirectory())
            self.addStep(RepoSync())
            self.addStep(UnmountWorkerDirectory())
            self.addStep(UnmountRemoteDirectory())

        # cleanup
        self.addStep(Cleanup())
