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
                         [--shadow-prefix SHADOW_PREFIX] [--generate-all]
                         [--ondemand]
                         eads bucket shadow

run the PDF batch

positional arguments:
  eads                  URL for crawler to start harvesting EAD XML won't
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
  --generate-all        build all files
  --ondemand            use EC2 ondemand rather than EC2 spot market

```

crontab

```crontab
# minute         0-59
#   hour           0-23
#     day of month   0-31
#       month          0-12 (or names, see below)
#         day of week    0-7 (0 or 7 is Sun, or use names)
# Eastern timzone

04 01 * * * ///appstrap/cronic/cronic ///code/pdfu/run_nightly_batch http:///oac-ead/prime2002/ s3:///pdf/ /usr/share/nginx/html/pdf-shadow.tar.gz 

```

## install

Requires `oac-ead-to-pdf` and some python modules, which are installed into a virtualenv and a subdirectory by running.

```bash
./init.sh
```
