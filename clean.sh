#!/bin/bash

# removes various build files and uninstalls epyseg
cd .
rm -rf build
rm -rf dist
rm -rf *.egg-info
#/usr/local/bin/python3.7 -m pip uninstall -y epyseg
python -m pip uninstall -y epyseg
python -m pip uninstall -y batoolset
python -m pip uninstall -y pyfigures
# had to change python to python3.7
