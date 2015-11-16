import logging
import subprocess
import zmq.green as zmq
import gevent
from gevent.queue import Queue

class Driver(object):
    def __init__(self, name, path, args, port, queue):
        self.log = logging.getLogger("{module}.{name}".format(
            module=self.__class__.__module__, name=self.__class__.__name__))
        self.name = name
        self.path = path
        self.args = args
        self.port = port
        self.uplinkMsgQueue = queue

        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.PAIR)

        self.start_server_for_driver()
        self.start_driver_process()
        pass

    def start_server_for_driver(self):
        self.socket.bind("tcp://*:%s" % self.port)
        self.log.debug("Server for {0} started ".format(self.name))

    def start_driver_process(self):
        cmd = [self.path,
               '--port', str(self.port)
               ]
        cmd.extend(filter(None, [self.args]))
        self.pid = subprocess.Popen(cmd)
        self.log.debug("Driver: {0}, with args: {1}, PID: {2} started".format(self.name, self.args, self.pid.pid))

    def receive_msg_from_driver(self):
         while True:
                msg = self.socket.recv()
                self.log.debug("Driver: {0} received msg: {1} and put it on Uplink Msg Queue".format(self.name, msg))
                self.uplinkMsgQueue.put(msg)

    def send_msg_to_driver(self,msg):
        self.log.debug("Driver: {0} sends msg: {1}".format(self.name, msg))
        self.socket.send(msg)