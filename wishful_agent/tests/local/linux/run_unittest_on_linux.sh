#!/usr/bin/env bash

echo "Test local controller:"

python3 unittest_on_linux.py

if [ "$?" != "0" ]; then
  echo "Unittest failed !!!!"
fi