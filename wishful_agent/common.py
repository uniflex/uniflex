import sys
import socket
import fcntl
import struct

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
