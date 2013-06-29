set -eu

DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )" # http://stackoverflow.com/questions/59895
cd $DIR

if [[ ! -z ${1-} ]]; then
    extra_opts="-p $1"
else
    extra_opts=""
fi

virtualenv $extra_opts --system-site-packages ve
set +u
. ve/bin/activate
set -u
pip install -r requirements.txt
hg clone https://code.google.com/p/oac-ead-to-pdf/
cd oac-ead-to-pdf
python fix_relative_css_paths.py
