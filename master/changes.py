from email.message import EmailMessage
from smtplib import SMTP

from buildbot.changes.gitpoller import GitPoller
from buildbot.util import bytes2unicode
from future.utils import itervalues
from twisted.internet import defer
from twisted.python import log


class CustomGitPoller(GitPoller):

    def __init__(self, host: str, port: int, user: str, password: str, sender: str, recipients: list, **kwargs):
        super().__init__(**kwargs)
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.sender = sender
        self.recipients = recipients

    @defer.inlineCallbacks
    def _process_changes(self, newRev, branch):
        """
        Read changes since last change.
        - Read list of commit hashes.
        - Extract details from each commit.
        - Add changes to database.
        """

        # initial run, don't parse all history
        if not self.lastRev:
            return

        # get the change list
        revListArgs = (['--format=%H', '{}'.format(newRev)] +
                       ['^' + rev
                        for rev in sorted(self.lastRev.values())] +
                       ['--'])
        self.changeCount = 0
        results = yield self._dovccmd('log', revListArgs, path=self.workdir)

        # process oldest change first
        revList = results.split()
        revList.reverse()

        if self.buildPushesWithNoCommits and not revList:
            existingRev = self.lastRev.get(branch)
            if existingRev != newRev:
                revList = [newRev]
                if existingRev is None:
                    # This branch was completely unknown, rebuild
                    log.msg('gitpoller: rebuilding {} for new branch "{}"'.format(
                        newRev, branch))
                else:
                    # This branch is known, but it now points to a different
                    # commit than last time we saw it, rebuild.
                    log.msg('gitpoller: rebuilding {} for updated branch "{}"'.format(
                        newRev, branch))

        self.changeCount = len(revList)
        self.lastRev[branch] = newRev

        if self.changeCount:
            log.msg('gitpoller: processing {} changes: {} from "{}" branch "{}"'.format(
                self.changeCount, revList, self.repourl, branch))

        for rev in revList:
            dl = defer.DeferredList([
                self._get_commit_timestamp(rev),
                self._get_commit_author(rev),
                self._get_commit_committer(rev),
                self._get_commit_files(rev),
                self._get_commit_comments(rev),
                self._get_commit_tag(rev)
            ], consumeErrors=True)

            results = yield dl

            # check for failures
            failures = [r[1] for r in results if not r[0]]
            if failures:
                for failure in failures:
                    log.err(
                        failure, "while processing changes for {} {}".format(newRev, branch))
                # just fail on the first error; they're probably all related!
                failures[0].raiseException()

            timestamp, author, committer, files, comments, tag = [r[1] for r in results]

            if rev == revList[-1]:
                self._sendmail(f'[{self.category}] New release', f'{self.category} has got a new release: {tag}')

            yield self.master.data.updates.addChange(
                author=author,
                committer=committer,
                revision=bytes2unicode(rev, encoding=self.encoding),
                files=files, comments=comments, when_timestamp=timestamp,
                branch=bytes2unicode(self._removeHeads(branch)),
                project=self.project,
                repository=bytes2unicode(self.repourl, encoding=self.encoding),
                category=self.category,
                src='git'
            )

    def _get_commit_tag(self, rev):
        args = ['--tags', rev, '--']
        d = self._dovccmd('describe', args, path=self.workdir)

        @d.addCallback
        def process(git_output):
            if not git_output:
                raise EnvironmentError('could not get commit tag for rev')
            return git_output

        return d

    def _sendmail(self, subject: str, text: str) -> None:
        msg = EmailMessage()
        msg.set_content(text)
        msg['Subject'] = subject
        with SMTP(self.host, self.port) as s:
            s.starttls()
            s.login(self.user, self.password)
            s.send_message(msg, from_addr=self.sender, to_addrs=self.recipients)
