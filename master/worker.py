from twisted.internet import defer
from twisted.python import log

from buildbot.worker import Worker


class ArchBuildWorker(Worker):
    @defer.inlineCallbacks
    def attached(self, conn):
        try:
            yield super().attached(conn)
            self.properties.setProperty('workerhost', conn.info.get('host'), 'Worker')
        except Exception as e:
            log.err(e, f'worker {self.name} cannot attach')
            return
