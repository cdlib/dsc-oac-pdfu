set -eu

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )" # http://stackoverflow.com/questions/59895
cd $DIR


wget https://bitbucket.org/squeaky/portable-pypy/downloads/pypy-7.1.1-linux_x86_64-portable.tar.bz2
sha256sum -c pypy-7.1.1-linux_x86_64-portable.tar.bz2.sha256
tar jfx pypy-7.1.1-linux_x86_64-portable.tar.bz2
./pypy-7.1.1-linux_x86_64-portable/bin/virtualenv-pypy ve
set +u
. ve/bin/activate
set -u
unset PYTHON_INSTALL_LAYOUT
pip install -r requirements.txt
git clone https://github.com/mredar/oac-ead-to-pdf.git
cd oac-ead-to-pdf
python fix_relative_css_paths.py
