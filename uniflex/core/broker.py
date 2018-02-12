import logging
import threading
import zmq
import zmq.auth

from zmq.auth.thread import ThreadAuthenticator

__author__ = "Piotr Gawlowicz"
__copyright__ = "Copyright (c) 2015, Technische Universitat Berlin"
__version__ = "0.1.0"
__email__ = "gawlowicz@tkn.tu-berlin.de"


class Broker(threading.Thread):
    """docstring for Broker"""

    def __init__(self,
                 xpub="tcp://127.0.0.1:8990",
                 xsub="tcp://127.0.0.1:8989",
                 server_key=None,
                 client_keys=None,
                 ):
        self.log = logging.getLogger("{module}.{name}".format(
            module=self.__class__.__module__, name=self.__class__.__name__))
        super(Broker, self).__init__()
        self.running = False
        self.xpub_url = xpub
        self.xsub_url = xsub
        self.ctx = zmq.Context()

        self.auth = None
        self.server_key = server_key
        self.client_keys = client_keys

    def run(self):
        self.log.debug("Broker starts XPUB:{}, XSUB:{}"
                       .format(self.xpub_url, self.xsub_url))

        self.xpub = self.ctx.socket(zmq.XPUB)
        self.xsub = self.ctx.socket(zmq.XSUB)

        if self.server_key is not None:
            self.auth = ThreadAuthenticator(self.ctx)
            self.auth.start()
            self.auth.allow('127.0.0.1')
            # Tell authenticator to use the certificate in a directory
            if self.client_keys is not None:
                self.auth.configure_curve(domain='*',
                    location=self.client_keys)
            else:
                self.auth.configure_curve(domain='*',
                    location=zmq.auth.CURVE_ALLOW_ANY)
            self.log.debug("Enabling encryption with certificate: {}"
                       .format(self.server_key))
            server_public, server_secret = zmq.auth.load_certificate(
                self.server_key)
            for sock in [self.xpub, self.xsub]:
                sock.curve_secretkey = server_secret
                sock.curve_publickey = server_public
                sock.curve_server = True  # must come before bind

        self.xpub.bind(self.xpub_url)
        self.xsub.bind(self.xsub_url)

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

        for sock in [self.xpub, self.xsub]:
            sock.close()
        if self.auth:
            self.auth.stop()

    def stop(self):
        self.running = False
