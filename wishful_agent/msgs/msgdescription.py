from enum import IntEnum

__author__ = "Piotr Gawlowicz"
__copyright__ = "Copyright (c) 2015, Technische Universitat Berlin"
__version__ = "0.1.0"
__email__ = "gawlowicz@tkn.tu-berlin.de"


class SerializationType(IntEnum):
    NONE = 0
    JSON = 1
    PICKLE = 2
    MSGPACK = 3
    PROTOBUF = 4


class MessageDescription(object):
    def __init__(self, msgType=None, sourceUuid=None,
                 serializationType=SerializationType.NONE):
        super().__init__()
        self.msgType = msgType
        self.sourceUuid = sourceUuid
        self.serializationType = serializationType

    def serialize(self):
        return {"msgType": self.msgType,
                "sourceUuid": self.sourceUuid,
                "serializationType": self.serializationType}

    @classmethod
    def parse(cls, buf):
        msgType = buf.get("msgType", None)
        sourceUuid = buf.get("sourceUuid", None)
        sType = buf.get("serializationType", 0)
        sType = SerializationType(sType)
        return cls(msgType, sourceUuid, sType)
