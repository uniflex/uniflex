import logging
import time
import sys
import zmq.green as zmq
import socket
import fcntl
import struct
import threading
import dill #for pickling what standard pickle can’t cope with
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
    if sys.version_info.major >= 3:
        ifname = bytes(ifname[:15], 'utf-8')
    else:
        ifname = ifname[:15]

    val = socket.inet_ntoa(fcntl.ioctl(
        s.fileno(),
        0x8915,  # SIOCGIFADDR
        struct.pack('256s', ifname)
        )[20:24])
    s.close()

    return val


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
        self.dl_socket = self.context.socket(zmq.SUB) # for downlink communication with controller
        if sys.version_info.major >= 3:
            self.dl_socket.setsockopt_string(zmq.SUBSCRIBE,  self.agent.uuid)
        else:
            self.dl_socket.setsockopt(zmq.SUBSCRIBE,  self.agent.uuid)
        self.dl_socket.setsockopt(zmq.LINGER, 100)
        self.ul_socket = self.context.socket(zmq.PUB) # for uplink communication with controller

        #register module socket in poller
        self.poller.register(self.dl_socket, zmq.POLLIN)


    def connect(self, downlink, uplink):
        if self.controllerDL and self.controllerUL:
            try:
                self.ul_socket.disconnect(self.controllerUL)
                self.dl_socket.disconnect(self.controllerDL)
            except:
                pass

        self.controllerDL = downlink
        self.controllerUL = uplink
        self.ul_socket.connect(self.controllerUL)
        self.dl_socket.connect(self.controllerDL)


    def disconnect(self):
        #disconnect
        if self.controllerDL and self.controllerUL:
            try:
                self.ul_socket.disconnect(self.controllerUL)
                self.dl_socket.disconnect(self.controllerDL)
            except:
                pass


    def subscribe_to(self, topic):
        self.log.debug("Agent subscribes to topic: {}".format(topic))
        if sys.version_info.major >= 3:
            self.dl_socket.setsockopt_string(zmq.SUBSCRIBE, str(topic))
        else:
            self.dl_socket.setsockopt(zmq.SUBSCRIBE, str(topic))
 

    def set_recv_callback(self, callback):
        self.recv_callback = callback


    def send_uplink(self, msgContainer):
        #TODO: it is quick fix; find better solution with socket per thread
        self.uplinkSocketLock.acquire()
        try:
            self.ul_socket.send_multipart(msgContainer)
        finally:
            self.uplinkSocketLock.release()


    def send_ctr_to_controller(self, msgContainer):
        msgContainer[0] = msgContainer[0].encode('utf-8')
        ## stamp with my uuid
        cmdDesc = msgContainer[1]
        msg = msgContainer[2]
        
        cmdDesc.caller_id = self.agent.uuid
        msgContainer[1] = cmdDesc.SerializeToString()

        if cmdDesc.serialization_type == msgs.CmdDesc.PICKLE:
            try:
                msg = pickle.dumps(msg)
            except:
                msg = dill.dumps(msg)
        elif cmdDesc.serialization_type == msgs.CmdDesc.PROTOBUF:
            msg = msg.SerializeToString()
        
        msgContainer[2] = msg

        self.send_uplink(msgContainer)


    def send_to_controller(self, msgContainer):
        msgContainer[0] = str(self.agent.controllerMonitor.controller_uuid)
        msgContainer[0] = msgContainer[0].encode('utf-8')
        ## stamp with my uuid
        cmdDesc = msgContainer[1]
        msg = msgContainer[2]
        
        cmdDesc.caller_id = self.agent.uuid
        msgContainer[1] = cmdDesc.SerializeToString()

        if cmdDesc.serialization_type == msgs.CmdDesc.PICKLE:
            try:
                msg = pickle.dumps(msg)
            except:
                msg = dill.dumps(msg)
        elif cmdDesc.serialization_type == msgs.CmdDesc.PROTOBUF:
            msg = msg.SerializeToString()
                    
        msgContainer[2] = msg

        self.send_uplink(msgContainer)


    def start(self):
        # Work on requests from controller
        while True:
            socks = dict(self.poller.poll())
            if self.dl_socket in socks and socks[self.dl_socket] == zmq.POLLIN:
                msgContainer = self.dl_socket.recv_multipart()

                assert len(msgContainer) == 3, msgContainer
                dest = msgContainer[0]
                cmdDesc = msgs.CmdDesc()
                cmdDesc.ParseFromString(msgContainer[1])
                msg = msgContainer[2]

                if cmdDesc.serialization_type == msgs.CmdDesc.PICKLE:
                    msg = pickle.loads(msg)

                msgContainer[0] = dest.decode('utf-8')
                msgContainer[1] = cmdDesc
                msgContainer[2] = msg
                self.recv_callback(msgContainer)


    def stop(self):
        try:
            self.dl_socket.setsockopt(zmq.LINGER, 0)
            self.ul_socket.setsockopt(zmq.LINGER, 0)
            self.dl_socket.close()
            self.ul_socket.close()
            self.context.term()
        except:
            pass