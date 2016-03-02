import logging
import time
import sys
import zmq.green as zmq
import socket
import fcntl
import struct
import threading
try:
   import cPickle as pickle
except:
   import pickle

import wishful_framework as msgs

__author__ = "Piotr Gawlowicz"
__copyright__ = "Copyright (c) 2015, Technische Universitat Berlin"
__version__ = "0.1.0"
__email__ = "gawlowicz@tkn.tu-berlin.de"


def get_ip_address(ifname):
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    return socket.inet_ntoa(fcntl.ioctl(
        s.fileno(),
        0x8915,  # SIOCGIFADDR
        struct.pack('256s', ifname[:15])
    )[20:24])


class TransportChannel(object):
    def __init__(self, agent):
        self.log = logging.getLogger("{module}.{name}".format(
            module=self.__class__.__module__, name=self.__class__.__name__))

        self.agent = agent
        self.controllerDL = None
        self.controllerUL = None

        self.uplinkSocketLock = threading.Lock()
        self.poller = zmq.Poller()
        self.context = zmq.Context()
        self.socket_sub = self.context.socket(zmq.SUB) # for downlink communication with controller
        self.socket_sub.setsockopt(zmq.SUBSCRIBE,  self.agent.uuid)
        self.socket_sub.setsockopt(zmq.LINGER, 100)
        self.socket_pub = self.context.socket(zmq.PUB) # for uplink communication with controller

        #register module socket in poller
        self.poller.register(self.socket_sub, zmq.POLLIN)


    def connect(self, downlink, uplink):
        if self.controllerDL and self.controllerUL:
            try:
                self.socket_pub.disconnect(self.controllerDL)
                self.socket_sub.disconnect(self.controllerUL)
            except:
                pass

        self.controllerDL = downlink
        self.controllerUL = uplink
        self.socket_pub.connect(self.controllerDL)
        self.socket_sub.connect(self.controllerUL)


    def disconnect(self):
        #disconnect
        if self.controllerDL and self.controllerUL:
            try:
                self.socket_pub.disconnect(self.controllerDL)
                self.socket_sub.disconnect(self.controllerUL)
            except:
                pass


    def subscribe_to(self, topic):
        self.log.debug("Agent subscribes to topic: {}".format(topic))
        self.socket_sub.setsockopt(zmq.SUBSCRIBE, str(topic))
 

    def set_recv_callback(self, callback):
        self.recv_callback = callback


    def send_uplink(self, msgContainer):
        #TODO: it is quick fix; find better solution with socket per thread
        self.uplinkSocketLock.acquire()
        try:
            self.socket_pub.send_multipart(msgContainer)
        finally:
            self.uplinkSocketLock.release()


    def send_ctr_to_controller(self, msgContainer):
        ## stamp with my uuid
        cmdDesc = msgs.CmdDesc()
        cmdDesc.ParseFromString(msgContainer[1])
        cmdDesc.caller_id = self.agent.uuid
        msgContainer[1] = cmdDesc.SerializeToString()
        self.send_uplink(msgContainer)


    def send_to_controller(self, msgContainer):
        msgContainer[0] = str(self.agent.controllerMonitor.controller_uuid)
        ## stamp with my uuid
        cmdDesc = msgs.CmdDesc()
        cmdDesc.ParseFromString(msgContainer[1])
        cmdDesc.caller_id = self.agent.uuid
        msgContainer[1] = cmdDesc.SerializeToString()
        self.send_uplink(msgContainer)


    def start(self):
        # Work on requests from controller
        while True:
            socks = dict(self.poller.poll())
            if self.socket_sub in socks and socks[self.socket_sub] == zmq.POLLIN:
                msgContainer = self.socket_sub.recv_multipart()

                assert len(msgContainer) == 3
                dest = msgContainer[0]
                cmdDesc = msgs.CmdDesc()
                cmdDesc.ParseFromString(msgContainer[1])
                msg = msgContainer[2]

                if cmdDesc.serialization_type == msgs.CmdDesc.PICKLE:
                    msg = pickle.loads(msg)

                msgContainer[0] = dest
                msgContainer[1] = cmdDesc
                msgContainer[2] = msg
                self.recv_callback(msgContainer)


    def stop(self):
        try:
            self.socket_sub.setsockopt(zmq.LINGER, 0)
            self.socket_pub.setsockopt(zmq.LINGER, 0)
            self.socket_sub.close()
            self.socket_pub.close()
            self.context.term()
        except:
            pass