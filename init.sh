set -eu

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )" # http://stackoverflow.com/questions/59895
cd $DIR

if [[ ! -z ${1-} ]]; then
    extra_opts="-p $1"
else
    extra_opts=""
fi

virtualenv-2.7 $extra_opts ve
set +u
. ve/bin/activate
set -u
unset PYTHON_INSTALL_LAYOUT
pip install -r requirements.txt
git clone https://github.com/mredar/oac-ead-to-pdf.git
cd oac-ead-to-pdf
python fix_relative_css_paths.py
