#!/bin/bash

# NB NOW USES THE TOKEN IN $HOME/.pypirc
#/usr/local/bin/python3.7 -m pip install --user --upgrade pip
#/usr/local/bin/python3.7 -m epyseg
#/usr/local/bin/python3.7 -m epyseg.ta

#https://realpython.com/python-wheels/ py3 is the Python tag, meaning the wheel supports Python 2 and 3 with any Python implementation. --> do I have that ???
# epyseg-0.1.22-py3-none-any.whl

./clean.sh
#/usr/local/bin/python3.7 setup.py sdist bdist_wheel
#/usr/local/bin/python3.7 -m pip install --upgrade dist/*.whl # do I really need the upgrade --> not a very smart idea to do upgrade, maybe use force install instead...
#python setup.py sdist bdist_wheel
python -m build
python -m pip install --upgrade dist/*.whl # do I really need the upgrade --> not a very smart idea to do upgrade, maybe use force install instead... # IF I REMOVE python -m then I get the install in the current env -−> fo I want that ???
# had to change python to python3.7 to get things to work
# reclean afterwards may want to comment it though
./clean.sh