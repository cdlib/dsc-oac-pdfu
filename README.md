## `pdfu`

creates a PDF from a URL to an EAD XML file

```
usage: pdfu [-h] [-t TEMPDIR] [-w] [--loglevel LOGLEVEL] url outfile

takes an EAD file and turn it into a PDF

positional arguments:
  url                   URL or path to source EAD XML file
  outfile               name for new PDF

optional arguments:
  -h, --help            show this help message and exit
  -t TEMPDIR, --tempdir TEMPDIR
  -w, --warnings        show python warnings supressed by default
  --loglevel LOGLEVEL
```

## `run_nightly_batch`

run from crontab on cloud control node

```
usage: run_nightly_batch [-h] [--simpledb-domain SIMPLEDB_DOMAIN]
                         [--shadow-prefix SHADOW_PREFIX]
                         eads bucket shadow

run the PDF batch

positional arguments:
  eads                  URL for crawler to start harvesting EAD XML, won't
                        follow redirects
  bucket                s3://bucket[/optional/path] where the generated PDF
                        files go
  shadow                .tar.gz filename to store "shadow" file archive for
                        XTF

optional arguments:
  -h, --help            show this help message and exit
  --simpledb-domain SIMPLEDB_DOMAIN
                        "domain"/name of Amazon Simple DB database
  --shadow-prefix SHADOW_PREFIX
                        path the .tar.gz will unpack to
```

## install

Requires `oac-ead-to-pdf` and some python modules, which are installed into a virtualenv and a subdirectory by running.

```bash
./init.sh
```
