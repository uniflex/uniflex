# Generated by the protocol buffer compiler.  DO NOT EDIT!
# source: messages.proto

import sys
_b=sys.version_info[0]<3 and (lambda x:x) or (lambda x:x.encode('latin1'))
from google.protobuf import descriptor as _descriptor
from google.protobuf import message as _message
from google.protobuf import reflection as _reflection
from google.protobuf import symbol_database as _symbol_database
from google.protobuf import descriptor_pb2
# @@protoc_insertion_point(imports)

_sym_db = _symbol_database.Default()




DESCRIPTOR = _descriptor.FileDescriptor(
  name='messages.proto',
  package='wishful_framework',
  serialized_pb=_b('\n\x0emessages.proto\x12\x11wishful_framework\"\x19\n\tAttribute\x12\x0c\n\x04name\x18\x01 \x02(\t\"\x18\n\x08\x46unction\x12\x0c\n\x04name\x18\x01 \x02(\t\"\x15\n\x05\x45vent\x12\x0c\n\x04name\x18\x01 \x02(\t\"\x17\n\x07Service\x12\x0c\n\x04name\x18\x01 \x02(\t\"\"\n\x06\x44\x65vice\x12\n\n\x02id\x18\x01 \x02(\r\x12\x0c\n\x04name\x18\x02 \x02(\t\"\xb1\x03\n\x06Module\x12\x0c\n\x04uuid\x18\x01 \x02(\t\x12\n\n\x02id\x18\x02 \x02(\r\x12\x0c\n\x04name\x18\x03 \x02(\t\x12\x32\n\x04type\x18\x04 \x02(\x0e\x32$.wishful_framework.Module.ModuleType\x12)\n\x06\x64\x65vice\x18\x05 \x01(\x0b\x32\x19.wishful_framework.Device\x12\x30\n\nattributes\x18\x06 \x03(\x0b\x32\x1c.wishful_framework.Attribute\x12.\n\tfunctions\x18\x07 \x03(\x0b\x32\x1b.wishful_framework.Function\x12+\n\tin_events\x18\x08 \x03(\x0b\x32\x18.wishful_framework.Event\x12,\n\nout_events\x18\t \x03(\x0b\x32\x18.wishful_framework.Event\x12,\n\x08services\x18\n \x03(\x0b\x32\x1a.wishful_framework.Service\"5\n\nModuleType\x12\n\n\x06MODULE\x10\x00\x12\n\n\x06\x44\x45VICE\x10\x01\x12\x0f\n\x0b\x41PPLICATION\x10\x02\"\xe4\x01\n\x0bNodeInfoMsg\x12\x12\n\nagent_uuid\x18\x01 \x02(\t\x12\n\n\x02ip\x18\x02 \x02(\t\x12\x0c\n\x04name\x18\x03 \x02(\t\x12\x10\n\x08hostname\x18\x04 \x02(\t\x12\x0c\n\x04info\x18\x05 \x01(\t\x12*\n\x07\x64\x65vices\x18\x06 \x03(\x0b\x32\x19.wishful_framework.Module\x12*\n\x07modules\x18\x07 \x03(\x0b\x32\x19.wishful_framework.Module\x12/\n\x0c\x61pplications\x18\x08 \x03(\x0b\x32\x19.wishful_framework.Module\"%\n\x0fNodeInfoRequest\x12\x12\n\nagent_uuid\x18\x01 \x02(\t\")\n\x13NodeAddNotification\x12\x12\n\nagent_uuid\x18\x01 \x02(\t\"1\n\x0bNodeExitMsg\x12\x12\n\nagent_uuid\x18\x01 \x02(\t\x12\x0e\n\x06reason\x18\x02 \x01(\t\")\n\x08HelloMsg\x12\x0c\n\x04uuid\x18\x01 \x02(\t\x12\x0f\n\x07timeout\x18\x02 \x02(\r')
)
_sym_db.RegisterFileDescriptor(DESCRIPTOR)



_MODULE_MODULETYPE = _descriptor.EnumDescriptor(
  name='ModuleType',
  full_name='wishful_framework.Module.ModuleType',
  filename=None,
  file=DESCRIPTOR,
  values=[
    _descriptor.EnumValueDescriptor(
      name='MODULE', index=0, number=0,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='DEVICE', index=1, number=1,
      options=None,
      type=None),
    _descriptor.EnumValueDescriptor(
      name='APPLICATION', index=2, number=2,
      options=None,
      type=None),
  ],
  containing_type=None,
  options=None,
  serialized_start=555,
  serialized_end=608,
)
_sym_db.RegisterEnumDescriptor(_MODULE_MODULETYPE)


_ATTRIBUTE = _descriptor.Descriptor(
  name='Attribute',
  full_name='wishful_framework.Attribute',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='name', full_name='wishful_framework.Attribute.name', index=0,
      number=1, type=9, cpp_type=9, label=2,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=37,
  serialized_end=62,
)


_FUNCTION = _descriptor.Descriptor(
  name='Function',
  full_name='wishful_framework.Function',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='name', full_name='wishful_framework.Function.name', index=0,
      number=1, type=9, cpp_type=9, label=2,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=64,
  serialized_end=88,
)


_EVENT = _descriptor.Descriptor(
  name='Event',
  full_name='wishful_framework.Event',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='name', full_name='wishful_framework.Event.name', index=0,
      number=1, type=9, cpp_type=9, label=2,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=90,
  serialized_end=111,
)


_SERVICE = _descriptor.Descriptor(
  name='Service',
  full_name='wishful_framework.Service',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='name', full_name='wishful_framework.Service.name', index=0,
      number=1, type=9, cpp_type=9, label=2,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=113,
  serialized_end=136,
)


_DEVICE = _descriptor.Descriptor(
  name='Device',
  full_name='wishful_framework.Device',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='id', full_name='wishful_framework.Device.id', index=0,
      number=1, type=13, cpp_type=3, label=2,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='name', full_name='wishful_framework.Device.name', index=1,
      number=2, type=9, cpp_type=9, label=2,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=138,
  serialized_end=172,
)


_MODULE = _descriptor.Descriptor(
  name='Module',
  full_name='wishful_framework.Module',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='uuid', full_name='wishful_framework.Module.uuid', index=0,
      number=1, type=9, cpp_type=9, label=2,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='id', full_name='wishful_framework.Module.id', index=1,
      number=2, type=13, cpp_type=3, label=2,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='name', full_name='wishful_framework.Module.name', index=2,
      number=3, type=9, cpp_type=9, label=2,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='type', full_name='wishful_framework.Module.type', index=3,
      number=4, type=14, cpp_type=8, label=2,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='device', full_name='wishful_framework.Module.device', index=4,
      number=5, type=11, cpp_type=10, label=1,
      has_default_value=False, default_value=None,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='attributes', full_name='wishful_framework.Module.attributes', index=5,
      number=6, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='functions', full_name='wishful_framework.Module.functions', index=6,
      number=7, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='in_events', full_name='wishful_framework.Module.in_events', index=7,
      number=8, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='out_events', full_name='wishful_framework.Module.out_events', index=8,
      number=9, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='services', full_name='wishful_framework.Module.services', index=9,
      number=10, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
    _MODULE_MODULETYPE,
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=175,
  serialized_end=608,
)


_NODEINFOMSG = _descriptor.Descriptor(
  name='NodeInfoMsg',
  full_name='wishful_framework.NodeInfoMsg',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='agent_uuid', full_name='wishful_framework.NodeInfoMsg.agent_uuid', index=0,
      number=1, type=9, cpp_type=9, label=2,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='ip', full_name='wishful_framework.NodeInfoMsg.ip', index=1,
      number=2, type=9, cpp_type=9, label=2,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='name', full_name='wishful_framework.NodeInfoMsg.name', index=2,
      number=3, type=9, cpp_type=9, label=2,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='hostname', full_name='wishful_framework.NodeInfoMsg.hostname', index=3,
      number=4, type=9, cpp_type=9, label=2,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='info', full_name='wishful_framework.NodeInfoMsg.info', index=4,
      number=5, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='devices', full_name='wishful_framework.NodeInfoMsg.devices', index=5,
      number=6, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='modules', full_name='wishful_framework.NodeInfoMsg.modules', index=6,
      number=7, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='applications', full_name='wishful_framework.NodeInfoMsg.applications', index=7,
      number=8, type=11, cpp_type=10, label=3,
      has_default_value=False, default_value=[],
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=611,
  serialized_end=839,
)


_NODEINFOREQUEST = _descriptor.Descriptor(
  name='NodeInfoRequest',
  full_name='wishful_framework.NodeInfoRequest',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='agent_uuid', full_name='wishful_framework.NodeInfoRequest.agent_uuid', index=0,
      number=1, type=9, cpp_type=9, label=2,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=841,
  serialized_end=878,
)


_NODEADDNOTIFICATION = _descriptor.Descriptor(
  name='NodeAddNotification',
  full_name='wishful_framework.NodeAddNotification',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='agent_uuid', full_name='wishful_framework.NodeAddNotification.agent_uuid', index=0,
      number=1, type=9, cpp_type=9, label=2,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=880,
  serialized_end=921,
)


_NODEEXITMSG = _descriptor.Descriptor(
  name='NodeExitMsg',
  full_name='wishful_framework.NodeExitMsg',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='agent_uuid', full_name='wishful_framework.NodeExitMsg.agent_uuid', index=0,
      number=1, type=9, cpp_type=9, label=2,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='reason', full_name='wishful_framework.NodeExitMsg.reason', index=1,
      number=2, type=9, cpp_type=9, label=1,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=923,
  serialized_end=972,
)


_HELLOMSG = _descriptor.Descriptor(
  name='HelloMsg',
  full_name='wishful_framework.HelloMsg',
  filename=None,
  file=DESCRIPTOR,
  containing_type=None,
  fields=[
    _descriptor.FieldDescriptor(
      name='uuid', full_name='wishful_framework.HelloMsg.uuid', index=0,
      number=1, type=9, cpp_type=9, label=2,
      has_default_value=False, default_value=_b("").decode('utf-8'),
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
    _descriptor.FieldDescriptor(
      name='timeout', full_name='wishful_framework.HelloMsg.timeout', index=1,
      number=2, type=13, cpp_type=3, label=2,
      has_default_value=False, default_value=0,
      message_type=None, enum_type=None, containing_type=None,
      is_extension=False, extension_scope=None,
      options=None),
  ],
  extensions=[
  ],
  nested_types=[],
  enum_types=[
  ],
  options=None,
  is_extendable=False,
  extension_ranges=[],
  oneofs=[
  ],
  serialized_start=974,
  serialized_end=1015,
)

_MODULE.fields_by_name['type'].enum_type = _MODULE_MODULETYPE
_MODULE.fields_by_name['device'].message_type = _DEVICE
_MODULE.fields_by_name['attributes'].message_type = _ATTRIBUTE
_MODULE.fields_by_name['functions'].message_type = _FUNCTION
_MODULE.fields_by_name['in_events'].message_type = _EVENT
_MODULE.fields_by_name['out_events'].message_type = _EVENT
_MODULE.fields_by_name['services'].message_type = _SERVICE
_MODULE_MODULETYPE.containing_type = _MODULE
_NODEINFOMSG.fields_by_name['devices'].message_type = _MODULE
_NODEINFOMSG.fields_by_name['modules'].message_type = _MODULE
_NODEINFOMSG.fields_by_name['applications'].message_type = _MODULE
DESCRIPTOR.message_types_by_name['Attribute'] = _ATTRIBUTE
DESCRIPTOR.message_types_by_name['Function'] = _FUNCTION
DESCRIPTOR.message_types_by_name['Event'] = _EVENT
DESCRIPTOR.message_types_by_name['Service'] = _SERVICE
DESCRIPTOR.message_types_by_name['Device'] = _DEVICE
DESCRIPTOR.message_types_by_name['Module'] = _MODULE
DESCRIPTOR.message_types_by_name['NodeInfoMsg'] = _NODEINFOMSG
DESCRIPTOR.message_types_by_name['NodeInfoRequest'] = _NODEINFOREQUEST
DESCRIPTOR.message_types_by_name['NodeAddNotification'] = _NODEADDNOTIFICATION
DESCRIPTOR.message_types_by_name['NodeExitMsg'] = _NODEEXITMSG
DESCRIPTOR.message_types_by_name['HelloMsg'] = _HELLOMSG

Attribute = _reflection.GeneratedProtocolMessageType('Attribute', (_message.Message,), dict(
  DESCRIPTOR = _ATTRIBUTE,
  __module__ = 'messages_pb2'
  # @@protoc_insertion_point(class_scope:wishful_framework.Attribute)
  ))
_sym_db.RegisterMessage(Attribute)

Function = _reflection.GeneratedProtocolMessageType('Function', (_message.Message,), dict(
  DESCRIPTOR = _FUNCTION,
  __module__ = 'messages_pb2'
  # @@protoc_insertion_point(class_scope:wishful_framework.Function)
  ))
_sym_db.RegisterMessage(Function)

Event = _reflection.GeneratedProtocolMessageType('Event', (_message.Message,), dict(
  DESCRIPTOR = _EVENT,
  __module__ = 'messages_pb2'
  # @@protoc_insertion_point(class_scope:wishful_framework.Event)
  ))
_sym_db.RegisterMessage(Event)

Service = _reflection.GeneratedProtocolMessageType('Service', (_message.Message,), dict(
  DESCRIPTOR = _SERVICE,
  __module__ = 'messages_pb2'
  # @@protoc_insertion_point(class_scope:wishful_framework.Service)
  ))
_sym_db.RegisterMessage(Service)

Device = _reflection.GeneratedProtocolMessageType('Device', (_message.Message,), dict(
  DESCRIPTOR = _DEVICE,
  __module__ = 'messages_pb2'
  # @@protoc_insertion_point(class_scope:wishful_framework.Device)
  ))
_sym_db.RegisterMessage(Device)

Module = _reflection.GeneratedProtocolMessageType('Module', (_message.Message,), dict(
  DESCRIPTOR = _MODULE,
  __module__ = 'messages_pb2'
  # @@protoc_insertion_point(class_scope:wishful_framework.Module)
  ))
_sym_db.RegisterMessage(Module)

NodeInfoMsg = _reflection.GeneratedProtocolMessageType('NodeInfoMsg', (_message.Message,), dict(
  DESCRIPTOR = _NODEINFOMSG,
  __module__ = 'messages_pb2'
  # @@protoc_insertion_point(class_scope:wishful_framework.NodeInfoMsg)
  ))
_sym_db.RegisterMessage(NodeInfoMsg)

NodeInfoRequest = _reflection.GeneratedProtocolMessageType('NodeInfoRequest', (_message.Message,), dict(
  DESCRIPTOR = _NODEINFOREQUEST,
  __module__ = 'messages_pb2'
  # @@protoc_insertion_point(class_scope:wishful_framework.NodeInfoRequest)
  ))
_sym_db.RegisterMessage(NodeInfoRequest)

NodeAddNotification = _reflection.GeneratedProtocolMessageType('NodeAddNotification', (_message.Message,), dict(
  DESCRIPTOR = _NODEADDNOTIFICATION,
  __module__ = 'messages_pb2'
  # @@protoc_insertion_point(class_scope:wishful_framework.NodeAddNotification)
  ))
_sym_db.RegisterMessage(NodeAddNotification)

NodeExitMsg = _reflection.GeneratedProtocolMessageType('NodeExitMsg', (_message.Message,), dict(
  DESCRIPTOR = _NODEEXITMSG,
  __module__ = 'messages_pb2'
  # @@protoc_insertion_point(class_scope:wishful_framework.NodeExitMsg)
  ))
_sym_db.RegisterMessage(NodeExitMsg)

HelloMsg = _reflection.GeneratedProtocolMessageType('HelloMsg', (_message.Message,), dict(
  DESCRIPTOR = _HELLOMSG,
  __module__ = 'messages_pb2'
  # @@protoc_insertion_point(class_scope:wishful_framework.HelloMsg)
  ))
_sym_db.RegisterMessage(HelloMsg)


# @@protoc_insertion_point(module_scope)
