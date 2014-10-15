#!/bin/env python
# -*- coding: utf-8 -*-
import argparse
from run_nightly_batch import shadow
from pprint import pprint as pp
import os
import sys


def main(argv=None):
    parser = argparse.ArgumentParser(description="regen shadow")
    parser.add_argument(
        'bucket',
        nargs=1,
        help="s3://bucket[/optional/path] where the generated PDF files go"
    )
    parser.add_argument(
        'shadow',
        nargs=1,
        help=".tar.gz filename to store \"shadow\" file archive for XTF"
    )
    parser.add_argument('--shadow-prefix', default='pdf-shadow',
                        required=False, help="path the .tar.gz will unpack to")

    if argv is None:
        argv = parser.parse_args()

    shadow(argv.bucket[0], argv.shadow[0], argv.shadow_prefix)

# main() idiom for importing into REPL for debugging
if __name__ == "__main__":
    # http://stackoverflow.com/a/9462099/1763984 flush STDOUT
    sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', 0)
    sys.exit(main())
