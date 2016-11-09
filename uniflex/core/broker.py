import zmq
import logging
import threading

__author__ = "Piotr Gawlowicz"
__copyright__ = "Copyright (c) 2015, Technische Universitat Berlin"
__version__ = "0.1.0"
__email__ = "gawlowicz@tkn.tu-berlin.de"


class Broker(threading.Thread):
    """docstring for Broker"""

    def __init__(self, xpub="tcp://127.0.0.1:8990",
                 xsub="tcp://127.0.0.1:8989"):
        self.log = logging.getLogger("{module}.{name}".format(
            module=self.__class__.__module__, name=self.__class__.__name__))
        super(Broker, self).__init__()
        self.running = False
        self.xpub_url = xpub
        self.xsub_url = xsub
        self.ctx = zmq.Context()
        self.xpub = self.ctx.socket(zmq.XPUB)
        self.xpub.bind(self.xpub_url)
        self.xsub = self.ctx.socket(zmq.XSUB)
        self.xsub.bind(self.xsub_url)
        # self.proxy = zmq.proxy(xpub, xsub)

    def run(self):
        self.log.debug("Broker starts XPUB:{}, XSUB:{}"
                       .format(self.xpub_url, self.xsub_url))
        # self.proxy.start()
        poller = zmq.Poller()
        poller.register(self.xpub, zmq.POLLIN)
        poller.register(self.xsub, zmq.POLLIN)
        self.running = True
        while self.running:
            events = dict(poller.poll(1000))
            if self.xpub in events:
                message = self.xpub.recv_multipart()
                self.log.debug("subscription message: {}".format(message[0]))
                self.xsub.send_multipart(message)
            if self.xsub in events:
                message = self.xsub.recv_multipart()
                self.log.debug("publishing message: {}".format(message))
                self.xpub.send_multipart(message)

    def stop(self):
        self.running = False
