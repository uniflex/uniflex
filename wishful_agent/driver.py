import logging
import subprocess
import zmq.green as zmq


class Driver(object):
    def __init__(self, name, path, args, port):
        self.log = logging.getLogger("{module}.{name}".format(
            module=self.__class__.__module__, name=self.__class__.__name__))
        self.name = name
        self.path = path
        self.args = args
        self.port = port

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

    def kill_driver_subprocess(self):
        self.pid.kill()
        pass


    def send_msg_to_driver(self, msgContainer):
        group = msgContainer[0]
        msgType = msgContainer[1]
        msg = msgContainer[2]
        self.log.debug("Driver: {0} sends msg: {1}::{2}".format(self.name, msgType, msg))
        msgContainer = []
        msgContainer = [group, msgType, msg] # driver does not need to know exec time
        self.socket.send_multipart(msgContainer)