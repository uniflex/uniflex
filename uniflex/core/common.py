import inspect
import threading
import netifaces as ni
from netifaces import AF_INET


__author__ = "Piotr Gawlowicz, Anatolij Zubow"
__copyright__ = "Copyright (c) 2015, Technische Universitat Berlin"
__version__ = "0.1.0"
__email__ = "{gawlowicz|zubow}@tkn.tu-berlin.de"


def override():
    '''
    with this decorator you make sure you are
    overriding a method form base class
    '''
    def overrider(method):
        # myClass = method.__self__.__class__
        # interface_class = myClass.__mro__[1]
        # assert(method.__name__ in dir(interface_class))
        return method
    return overrider


def is_func_implemented(func):
    code = inspect.getsourcelines(func)
    lines = code[0]
    lastLine = lines[-1]
    if "NotImplementedError" in lastLine:
        return False
    else:
        return True


def get_inheritors(klass):
    subclasses = {}
    work = [klass]
    while work:
        parent = work.pop()
        for child in parent.__subclasses__():
            if child not in subclasses:
                subclasses[str(child.__name__)] = child
                work.append(child)
    return subclasses


def get_inheritors_set(klass):
    subclasses = set()
    work = [klass]
    while work:
        parent = work.pop()
        for child in parent.__subclasses__():
            if child not in subclasses:
                subclasses.add(child)
                work.append(child)
    return subclasses


def get_ip_address(ifname):
    try:
        # AZU: old code was for Linux only; does not work with OSX
        # new solution is platform independent
        val = ni.ifaddresses(ifname)[AF_INET][0]['addr']
        return val
    except Exception as e:
        print("Failed to get IP address of iface: {} {}".format(ifname, e))
        raise e


class UniFlexThread():
    """docstring for UniFlexThread"""

    def __init__(self, module):
        super().__init__()
        self.module = module
        self.running = False

    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self.task)
        self.thread.setDaemon(True)
        self.thread.start()

    def task(self):
        return

    def stop(self):
        self.running = False

    def is_running(self):
        return self.running

    def is_stopped(self):
        return not self.running
