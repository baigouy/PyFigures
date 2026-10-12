#!/bin/bash
# NB NOW USES THE TOKEN IN $HOME/.pypirc

# need to install twine python pacakge in the dev env !!!
#/usr/local/bin/python3.7 -m pip install --user --upgrade pip
#/usr/local/bin/python3.7 -m epyseg
#/usr/local/bin/python3.7 -m epyseg.ta

./clean.sh
#/usr/local/bin/python3.7 setup.py sdist bdistn_wheel
#/usr/local/bin/python3.7 -m pip install --upgrade dist/*.whl
#python setup.py sdist bdist_wheel
python -m build
#python -m pip install --upgrade dist/*.whl
read -p "Are you sure you want to update to the REAL pypi site ? " -n 1 -r
echo    # (optional) move to a new line
if [[ $REPLY =~ ^[Yy]$ ]]
then
  #	/usr/local/bin/python3.7 -m twine upload dist/* # real pypi upload
#	python -m twine upload dist/* # real pypi upload
  twine upload -r pypi dist/* # pypi upload
fi
# had to change python to python3.7 to get things to work
./clean.sh

# pb and bug fix -> does not work but bug is not dramatic --> forget...
#/bin/bash: /home/aigouy/miniconda3/lib/libtinfo.so.6: no version information available (required by /bin/bash)
#conda install -c conda-forge ncurses