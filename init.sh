set -eu

virtualenv --system-site-packages ve
set +u
. ve/bin/activate
set -u
pip install -r requirements.txt
hg clone https://code.google.com/p/oac-ead-to-pdf/
cd oac-ead-to-pdf
python fix_relative_css_paths.py
