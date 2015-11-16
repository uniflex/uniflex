import logging
import subprocess
import zmq

class Driver(object):
    def __init__(self, name, path, args, port):
        self.log = logging.getLogger("{module}.{name}".format(
            module=self.__class__.__module__, name=self.__class__.__name__))
        self.name = name
        self.path = path
        self.args = args
        self.port = port

        self.start_server_for_driver()
        self.start_driver_process()
        pass

    def start_server_for_driver(self):
        self.context = zmq.Context()
        self.socket = self.context.socket(zmq.PAIR)
        self.socket.bind("tcp://*:%s" % self.port)
        self.log.debug("Server for {0} started ".format(self.name))

    def start_driver_process(self):
        cmd = [self.path,
               '--port', str(self.port)
               ]
        cmd.extend(filter(None, [self.args]))
        self.pid = subprocess.Popen(cmd)
        self.log.debug("Driver: {0}, with args: {1}, PID: {2} started".format(self.name, self.args, self.pid.pid))

    def send_msg(self,msg):
        self.socket.send(msg)
        msg = self.socket.recv()
        print msg