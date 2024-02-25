from buildbot.plugins import steps, util

from steps import (
    ArchBuild,
    BumpPkgrel,
    FindDependency,
    SetCommitRevision,
    SetTagRevision,
    Updpkgsums,
)


class ArchBuildFactory(util.BuildFactory):
    def __init__(self, pkgbuilddir: str, repo: str, pkg_base: str, properties: dict):
        super().__init__()

        workdir = f"{pkgbuilddir}/{repo}/{pkg_base}"

        # set initial properties
        self.addStep(steps.SetProperties(name="set properties from srcinfo", properties=properties))

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

        self.addSteps(
            [
                BumpPkgrel(workdir=workdir),
                Updpkgsums(workdir=workdir),
            ]
        )

        # update git tag revision
        if properties["git_tag"]:
            self.addStep(SetTagRevision(workdir=workdir))

        # update git commit revision
        if properties["git_revision"]:
            self.addStep(SetCommitRevision(workdir=workdir))

        # build
        self.addStep(ArchBuild(workdir=workdir))
