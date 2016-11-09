import netifaces as ni
from netifaces import AF_INET


__author__ = "Piotr Gawlowicz, Anatolij Zubow"
__copyright__ = "Copyright (c) 2015, Technische Universitat Berlin"
__version__ = "0.1.0"
__email__ = "{gawlowicz|zubow}@tkn.tu-berlin.de"


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
