import os

from buildbot_worker.bot import Worker
from twisted.application import service
from twisted.python.log import FileLogObserver, ILogObserver
from twisted.python.logfile import LogFile

basedir = '.'
rotateLength = 10000000
maxRotatedFiles = 10

# if this is a relocatable tac file, get the directory containing the TAC
if basedir == '.':
    import os.path

    basedir = os.path.abspath(os.path.dirname(__file__))

# note: this line is matched against to check that this is a worker
# directory; do not edit it.
application = service.Application('buildbot-worker')

logfile = LogFile.fromFullPath(
    os.path.join(basedir, "twistd.log"), rotateLength=rotateLength,
    maxRotatedFiles=maxRotatedFiles)
application.setComponent(ILogObserver, FileLogObserver(logfile).emit)

buildmaster_host = 'localhost'
port = 8011
workername = 'worker'
passwd = 'worker'
keepalive = 600
umask = None
maxdelay = 300
numcpus = None
allow_shutdown = None
maxretries = None

s = Worker(buildmaster_host, port, workername, passwd, basedir,
           keepalive, umask=umask, maxdelay=maxdelay,
           numcpus=numcpus, allow_shutdown=allow_shutdown,
           maxRetries=maxretries)
s.setServiceParent(application)
