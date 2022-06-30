set -eu

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )" # http://stackoverflow.com/questions/59895
cd $DIR

VER="7.3.9"
wget https://downloads.python.org/pypy/pypy2.7-v${VER}-linux64.tar.bz2

sha256sum -c pypy2.7-v${VER}-linux64.tar.bz2.sha256
tar jfx pypy2.7-v${VER}-linux64.tar.bz2

pip3 install virtualenv
virtualenv -p pypy2.7-v${VER}-linux64/bin/python ve
set +u
. ve/bin/activate
set -u
unset PYTHON_INSTALL_LAYOUT
pip install -r requirements.txt
git clone https://github.com/cdlib/dsc-oac-ead-to-pdf.git oac-ead-to-pdf
cd oac-ead-to-pdf
python fix_relative_css_paths.py
