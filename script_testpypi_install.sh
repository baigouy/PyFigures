#!/bin/bash

# NB NOW USES THE TOKEN IN $HOME/.pypirc

#/usr/local/bin/python3.7 -m pip install --user --upgrade pip
#/usr/local/bin/python3.7 -m epyseg
#/usr/local/bin/python3.7 -m epyseg.ta

./clean.sh
#/usr/local/bin/python3.7 setup.py sdist bdist_wheel
#/usr/local/bin/python3.7 -m pip install --upgrade dist/*.whl #local install
#python setup.py sdist bdist_wheel
python -m build
#python -m pip install --upgrade dist/*.whl #local install
read -p "Are you sure you want to update to the 'test.pypi' site ? " -n 1 -r
echo    # (optional) move to a new line
if [[ $REPLY =~ ^[Yy]$ ]]
then
  #	/usr/local/bin/python3.7 -m twine upload --verbose --repository-url https://test.pypi.org/legacy/ dist/* # testpypi upload
#	python -m twine upload  --verbose --repository-url https://test.pypi.org/legacy/ dist/* # testpypi upload
#  twine register --config-file=/home/aigouy/.pypirc dist/*
#	twine upload  --config-file=/home/aigouy/.pypirc --verbose --repository-url https://test.pypi.org/legacy/ dist/* # testpypi upload
#	twine upload  --config-file=/home/aigouy/.pypirc --repository-url https://test.pypi.org/legacy/ dist/* # testpypi upload
	twine upload -r testpypi dist/* # testpypi upload
fi
# had to change python to python3.7 to get things to work
./clean.sh