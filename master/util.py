import os
import re
import subprocess
from pathlib import Path
from urllib.parse import urlparse

from buildbot.plugins import util
from psutil import process_iter


class ArchBuildUtil:
    FILENAME = ".SRCINFO"
    URL_PATTERN = re.compile(r"[^:]*:{0,2}(ht|f)tps?://.+")
    VCS_PATTERN_1 = re.compile(r"([^:]*):{0,2}((git|hg)://[^#]+)#?(.*)")
    VCS_PATTERN_2 = re.compile(r"([^:]*):{0,2}(git|hg)\+([^#]+)#?(.*)")

    @staticmethod
    def parse_srcinfo(basedir: str, group: str, pkg_base: str) -> dict:
        src_names = []
        install = ""
        vcs_type = ""
        vcs_url = ""
        vcs_name = ""
        pkg_names = []
        pkg_ver = ""
        pkg_rel = ""
        epoch = ""
        pkg_arch = ""

        git_branch = ""
        git_tag = False
        git_revision = False
        hg_branch = ""
        hg_tag = False
        hg_revision = False

        pkgdir = f"{group}/{pkg_base}"
        if group in ("community", "packages"):
            pkgdir += "/trunk"
        path = Path(basedir) / pkgdir / ArchBuildUtil.FILENAME

        if not path.is_file():
            subprocess.run(
                "makepkg --printsrcinfo > .SRCINFO", cwd=path.parent, shell=True
            )

        with open(path, "r") as f:
            line = f.readline()
            while line:
                if line.strip().startswith("source"):
                    source = "=".join(line.split("=")[1:]).strip()
                    match_1 = ArchBuildUtil.VCS_PATTERN_1.match(source)
                    match_2 = ArchBuildUtil.VCS_PATTERN_2.match(source)
                    if match_1 is not None:
                        # pick the first vcs as the main one
                        if not vcs_name:
                            vcs_type = match_1.group(3)
                            vcs_url = match_1.group(2)
                            vcs_name = match_1.group(1)
                            if not vcs_name:
                                vcs_name = Path(urlparse(vcs_url).path).stem
                            if match_1.group(4):
                                fragment = match_1.group(4).split("=")
                                if vcs_type == "git":
                                    if fragment[0] == "tag":
                                        git_tag = True
                                    elif fragment[0] == "commit":
                                        git_revision = True
                                elif vcs_type == "hg":
                                    if fragment[0] == "tag":
                                        hg_tag = True
                                    elif fragment[0] == "revision":
                                        hg_revision = True

                    elif match_2 is not None:
                        # pick the first vcs as the main one
                        if not vcs_name:
                            vcs_type = match_2.group(2)
                            vcs_url = match_2.group(3)
                            vcs_name = match_2.group(1)
                            if not vcs_name:
                                vcs_name = Path(urlparse(vcs_url).path).stem
                            if match_2.group(4):
                                fragment = match_2.group(4).split("=")
                                if vcs_type == "git":
                                    if fragment[0] == "tag":
                                        git_tag = True
                                    elif fragment[0] == "commit":
                                        git_revision = True
                                elif vcs_type == "hg":
                                    if fragment[0] == "tag":
                                        hg_tag = True
                                    elif fragment[0] == "revision":
                                        hg_revision = True
                    elif ArchBuildUtil.URL_PATTERN.match(source) is None:
                        src_names.append(source)
                elif line.strip().startswith("arch"):
                    pkg_arch = line.split("=")[1].strip()
                elif line.strip().startswith("pkgname"):
                    pkg_names.append(line.split("=")[1].strip())
                elif line.strip().startswith("pkgver"):
                    pkg_ver = line.split("=")[1].strip()
                elif line.strip().startswith("pkgrel"):
                    pkg_rel = line.split("=")[1].strip()
                elif line.strip().startswith("epoch"):
                    epoch = line.split("=")[1].strip() + ":"
                elif line.strip().startswith("install"):
                    install = line.split("=")[1].strip()
                line = f.readline()
        return {
            "src_names": src_names,
            "install": install,
            "vcs_type": vcs_type,
            "vcs_url": vcs_url,
            "vcs_name": vcs_name,
            "pkg_names": pkg_names,
            "pkg_arch": pkg_arch,
            "pkg_ver": pkg_ver,
            "pkg_rel": pkg_rel,
            "epoch": epoch,
            "git_branch": git_branch,
            "git_tag": git_tag,
            "git_revision": git_revision,
            "hg_branch": hg_branch,
            "hg_tag": hg_tag,
            "hg_revision": hg_revision,
        }

    @staticmethod
    @util.renderer
    def srcinfo(props):
        pkgbuilddir = props.getProperty("pkgbuilddir")
        group = props.getProperty("group")
        pkg_base = props.getProperty("pkg_base")
        properties = ArchBuildUtil.parse_srcinfo(pkgbuilddir, group, pkg_base)
        return properties

    @staticmethod
    @util.renderer
    def pkg(props):
        pkg_name = props.getProperty("pkg_name")
        pkg_ver = props.getProperty("pkg_ver")
        pkg_rel = props.getProperty("pkg_rel")
        epoch = props.getProperty("epoch")
        pkg_arch = props.getProperty("pkg_arch")
        return f"{pkg_name}-{epoch}{pkg_ver}-{pkg_rel}-{pkg_arch}.pkg.tar.zst"

    @staticmethod
    @util.renderer
    def sig(props):
        pkg_name = props.getProperty("pkg_name")
        pkg_ver = props.getProperty("pkg_ver")
        pkg_rel = props.getProperty("pkg_rel")
        epoch = props.getProperty("epoch")
        pkg_arch = props.getProperty("pkg_arch")
        return f"{pkg_name}-{epoch}{pkg_ver}-{pkg_rel}-{pkg_arch}.pkg.tar.zst.sig"

    @staticmethod
    @util.renderer
    def pkg_masterdest(props):
        pkgdir = props.getProperty("pkgdir")
        pkg_name = props.getProperty("pkg_name")
        pkg_ver = props.getProperty("pkg_ver")
        pkg_rel = props.getProperty("pkg_rel")
        epoch = props.getProperty("epoch")
        pkg_arch = props.getProperty("pkg_arch")
        return f"{pkgdir}/{pkg_name}-{epoch}{pkg_ver}-{pkg_rel}-{pkg_arch}.pkg.tar.zst"

    @staticmethod
    @util.renderer
    def sig_mastersrc(props):
        pkgdir = props.getProperty("pkgdir")
        pkg_name = props.getProperty("pkg_name")
        pkg_ver = props.getProperty("pkg_ver")
        pkg_rel = props.getProperty("pkg_rel")
        epoch = props.getProperty("epoch")
        pkg_arch = props.getProperty("pkg_arch")
        return (
            f"{pkgdir}/{pkg_name}-{epoch}{pkg_ver}-{pkg_rel}-{pkg_arch}.pkg.tar.zst.sig"
        )

    @staticmethod
    @util.renderer
    def sig_workerdest(props):
        repodir = props.getProperty("repodir")
        repo_name = props.getProperty("repo_name")
        suffix = props.getProperty("suffix")
        pkg_name = props.getProperty("pkg_name")
        pkg_ver = props.getProperty("pkg_ver")
        pkg_rel = props.getProperty("pkg_rel")
        epoch = props.getProperty("epoch")
        pkg_arch = props.getProperty("pkg_arch")
        return f"{repodir}/{repo_name}-{suffix}/x86_64/{pkg_name}-{epoch}{pkg_ver}-{pkg_rel}-{pkg_arch}.pkg.tar.zst.sig"

    @staticmethod
    @util.renderer
    def ssh_agent(props):
        uid = os.getuid()
        ssh_agent_proc = [
            p
            for p in process_iter(attrs=["name", "uids"])
            if p.info["name"] == "ssh-agent" and uid in p.info["uids"]
        ][0]
        return {
            "SSH_AUTH_SOCK": f"/tmp/ssh-agent.sock.{uid}",
            "SSH_AGENT_PID": str(ssh_agent_proc.pid),
        }
