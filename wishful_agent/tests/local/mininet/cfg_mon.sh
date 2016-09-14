#!/bin/bash

phydev=`iw list | grep Wiphy | awk  '{ print $2 }'`
echo $phydev

iw phy $phydev interface add mon0 type monitor
ifconfig mon0 up
