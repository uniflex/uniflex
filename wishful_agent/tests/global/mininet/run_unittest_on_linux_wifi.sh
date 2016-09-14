#!/usr/bin/env bash

echo "Test global controller in mininet:"

sudo python unittest_on_linux_wifi_mn.py

if [ "$?" != "0" ]; then
  echo "Unittest failed !!!!"
fi

echo "cleaning up ..."
sudo mn -c 2>/dev/null
