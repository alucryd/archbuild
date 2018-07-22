# archbuild
Arch Linux build automation with Buildbot

## Introduction
This buildbot is intended for use with a build master where all your PKGBUILDs resides and a worker that does the handywork and hosts your custom repositories.

## Features
- Manual package building
- Automatic VCS package building
- Split PKGBUILD support
- Unattended GPG signing
- Email reports

## TODO
- Override repo per package in the configuration to handle `multilib` packages in the `community` logical group
- Add support for VCS url qualifiers (`#commit`, `#tag`, `#branch`, etc...)
- Automatically update packages built from VCS tags or commits

## Requirements
- Both master and worker need `python`, see `requirements.txt` for needed libraries
- Master optionally needs `git`, `hg` and `svn` for automatic VCS package building
- Master optionally needs `gpg` for unatended GPG signing
- Worker needs `devtools` and `pacman-contrib` to build in chroots and generate `.SRCINFO`

## Configuration
All configuration is done in `config.yml` in the master directory. You can use `config.example.yml` as base.

### pkgbuilddir
The root of your PKGBUILD collection, separated in logical groups (folders). For example, `packages` may contain PKGBUILDs from `[core]` and `[extra]`, `community` PKGBUILDs from `[community]` and `[multilib]`, and `unsupported` PKGBUILDs from AUR.

_Note: `packages` and `community` are special folders where PKGBUILDs will be looked up in a `trunk` subdirectory to match our SVN._

### srcdir
The root of all your sources, as defined by `SRCDIR` in `/etc/makepkg.conf`. Buildbot will monitor bare VCS repositories in this directory to automatically trigger builds when there are new commits.

### pkgdir
The root of all your packages, as defined by `PKGDIR` in `/etc/makepkg.conf`. The worker will upload all built packages in that location. Mandatory for signing, and useful if you want to use `extrapkg` and the likes afterwards.

### repodir
The root of your repositories on the worker, usually `~/public_html`. The path must be absolute.

### suffix
All repositories will be named after the official repository they target, plus this suffix.

### gpg_sign
Whether or not to sign packages. GPG must be configured for unattended use on the master, by increasing the cache TTL and possibly using a preset passphrase.

### mail_reports
Whether or not to send emails when a package fails to build.

#### sender
The email address buildbot will be using to send emails.

#### recipients
The email addresses of the report recipients.

### repos
The target repositories, all official repositories are defined by default but you may want to restrict, or expand them. Custom repositories need an associated `custom-x86_64-build` binary the likes of what's in `devtools`.

### groups
These are the logical groups (folders) mentioned earlier.

#### name
The name of the logcal group.

#### repo
The default target repo. It will be used for automatically triggered builds, and pre-selected in forced builds. You can always choose a different repo when doing forced builds.

#### pkgs
A list of the packages to be built.

##### name
The name of the package. `pkgname` or `pkgbase` for split PKGBUILDs.

##### depends
The name of the dependencies that will be fetched from the unofficial repo when they don't exist in official repositories, or when you need to override them.
