from buildbot.plugins import *
from steps import ArchBuild, Cleanup, FindDependency, GpgSign, InferPkgverFromGitTag, MovePackage, RepoAdd, SetPkgrel, SetPkgver, Srcinfo, Updpkgsums
from util import Util


class ArchBuildFactory(util.BuildFactory):

    def __init__(self, pkgbuilddir: str, group: str, pkg_base: str, properties: dict, build_lock: util.WorkerLock):
        super().__init__()

        gpg_sign = properties['gpg_sign']
        workdir = f'{pkgbuilddir}/{group}/{pkg_base}'

        if group in ('community', 'packages'):
            workdir += '/trunk'

        # set initial properties
        self.addStep(
            steps.SetProperties(
                name='set properties from srcinfo',
                properties=properties
            )
        )

        # find dependencies
        depends = properties['depends']
        if depends is not None:
            for depends_name in depends:
                self.addSteps([
                    steps.SetProperty(
                        name=f'set depends_name to {depends_name}',
                        property='depends_name',
                        value=depends_name,
                        hideStepIf=True
                    ),
                    FindDependency(name=f'find {depends_name}')
                ])

        # download build files
        self.addStep(
            steps.FileDownload(
                name='download PKGBUILD',
                mastersrc=f'{workdir}/PKGBUILD',
                workerdest='PKGBUILD'
            )
        )
        for src_name in properties['src_names']:
            self.addStep(
                steps.FileDownload(
                    name=f'download {src_name}',
                    mastersrc=f'{workdir}/{src_name}',
                    workerdest=src_name
                )
            )
        install = properties['install']
        if install:
            self.addStep(
                steps.FileDownload(
                    name=f'download {install}',
                    mastersrc=f'{workdir}/{install}',
                    workerdest=install
                )
            )

        # update pkgver and pkgrel
        self.addSteps([
            InferPkgverFromGitTag(),
            SetPkgver(),
            SetPkgrel(),
            Updpkgsums()
        ])

        # build
        self.addStep(
            ArchBuild(locks=[build_lock.access('counting')])
        )

        # update properties
        self.addSteps([
            Srcinfo(),
            steps.FileUpload(
                name='upload updated PKGBUILD',
                workersrc='PKGBUILD',
                masterdest=f'{workdir}/PKGBUILD'
            ),
            steps.FileUpload(
                name='upload updated .SRCINFO',
                workersrc='.SRCINFO',
                masterdest=f'{workdir}/.SRCINFO'
            ),
            steps.SetProperties(
                name='refresh properties from srcinfo',
                properties=Util.srcinfo
            )
        ])

        # upload and optionally sign packages
        for pkg_name in properties['pkg_names']:
            self.addSteps([
                steps.SetProperty(
                    name=f'set pkg_name to {pkg_name}',
                    property='pkg_name',
                    value=pkg_name,
                    hideStepIf=True
                ),
                steps.FileUpload(
                    name=f'upload {pkg_name}',
                    workersrc=Util.pkg,
                    masterdest=Util.pkg_masterdest
                ),
                MovePackage(name=f'move {pkg_name}')
            ])
            if gpg_sign:
                self.addSteps([
                    GpgSign(name=f'sign {pkg_name}'),
                    steps.FileDownload(
                        name=f'download {pkg_name} sig',
                        mastersrc=Util.sig_mastersrc,
                        workerdest=Util.sig_workerdest
                    )
                ])

            # update repository
            self.addStep(RepoAdd(name=f'add {pkg_name}'))

        # cleanup
        self.addStep(Cleanup())
