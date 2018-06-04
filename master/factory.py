from buildbot.plugins import *

from steps import ArchBuild, MkSrcinfo, RepoAdd, GpgSign, MovePackage, FindDependency, Cleanup
from util import Srcinfo


class ArchBuildFactory(util.BuildFactory):

    def __init__(self, pkgbuilddir: str, group: str, pkg_base: str, properties: dict, build_lock: util.WorkerLock):
        super().__init__()

        workdir = f'{pkgbuilddir}/{group}/{pkg_base}'
        pkgdir = properties['pkgdir']
        if not pkgdir:
            pkgdir = workdir
        if group in ('community', 'packages'):
            workdir += '/trunk'
        gpg_sign = properties['gpg_sign']

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
                        value=depends_name
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

        # build
        self.addStep(
            ArchBuild(locks=[build_lock.access('counting')])
        )

        # update properties
        self.addSteps([
            MkSrcinfo(),
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
                properties=Srcinfo.properties
            )
        ])

        # upload and optionally sign packages
        for pkg_name in properties['pkg_names']:
            self.addSteps([
                steps.SetProperty(
                    name=f'set pkg_name to {pkg_name}',
                    property='pkg_name',
                    value=pkg_name
                ),
                steps.FileUpload(
                    name=f'upload {pkg_name}',
                    workersrc=util.Interpolate(
                        f'{pkg_name}-%(prop:pkg_ver)s-%(prop:pkg_rel)s-%(prop:pkg_arch)s.pkg.tar.xz'
                    ),
                    masterdest=util.Interpolate(
                        f'{pkgdir}/{pkg_name}-%(prop:pkg_ver)s-%(prop:pkg_rel)s-%(prop:pkg_arch)s.pkg.tar.xz'
                    )
                ),
                MovePackage(name=f'move {pkg_name} to repo')
            ])
            if gpg_sign:
                self.addSteps([
                    GpgSign(name=f'sign {pkg_name}'),
                    steps.FileDownload(
                        name=f'download {pkg_name} signature',
                        mastersrc=util.Interpolate(
                            f'{pkgdir}/{pkg_name}-%(prop:pkg_ver)s-%(prop:pkg_rel)s-%(prop:pkg_arch)s.pkg.tar.xz.sig'
                        ),
                        workerdest=util.Interpolate(
                            '/'.join([
                                '%(prop:repodir)s',
                                '%(prop:repo_name)s-%(prop:suffix)s',
                                'x86_64',
                                f'{pkg_name}-%(prop:pkg_ver)s-%(prop:pkg_rel)s-%(prop:pkg_arch)s.pkg.tar.xz.sig'
                            ])
                        )
                    )
                ])

            # update repository
            self.addStep(RepoAdd(name=f'add {pkg_name} to repo'))

        # cleanup
        self.addStep(Cleanup())
