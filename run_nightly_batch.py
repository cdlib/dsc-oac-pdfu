#!/bin/env python
# -*- coding: utf-8 -*-
""" run a batch of PDF generation

keeps an amazon simple DB with an inventory of EAD files and last
modified dates, this persists between runs

check_url is a recursive modifier function (with side effects) that is
a web crawler that adds all the new EAD to an array `files_to_generate`
and updates the amazon simple db as needed

If there are files_to_generate, a spot purchase of an 8 core 30G RAM
is initiated, and fabric is used to install `pdfu` and run the batch
in parallel using the -P option on xargs.

Once the batch has run, the spot machine is terminated.

The shadow file is regenerated even if there were no files to
generate detected.

July 1, 2013 is hardcoded as the epic for file changes, because a
complete batch was run at this time.

Epic reset to Dec 1, 2013 and simbledb domain re-set in order to
regenerate some backfiles.  Need to switch simble db to record what
actually gets created; not what gets batched.

Epic reset to October 5, 2014.  --generate-all added to rebuild files

Add --shadow-only command line paramater

Epic reset to October 1, 2016

Epic reset to April 1, 2018

October 7, 2019 -- simple-db and epic concept removed -- `shadow()` gets ran twice

"""

import argparse
from lxml.html import parse
import requests
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
import os
import sys
import boto.utils
import boto
import datetime
from time import sleep
from fabric.api import env, run, sudo, put
import paramiko
import fabric
import StringIO
import socket
import urlparse
import tarfile
import time
import tempfile
import shutil
from collections import namedtuple

from pprint import pprint as pp

BATCH = datetime.datetime.now().isoformat()

def main(argv=None):
    parser = argparse.ArgumentParser(description="run the PDF batch")
    parser.add_argument(
        'eads',
        nargs=1,
        help="URL for crawler to start harvesting EAD XML "
             "won't follow redirects"
    )
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
    parser.add_argument('--launch-only', dest='launch_only', action='store_true',
                        help='launch worker for manual batch',)
    parser.add_argument('--shadow-only', dest='shadow_only', action='store_true',
                        help='just reshadow all',)
    parser.add_argument('--generate-all', dest='all', action='store_true',
                        help='build all files',)
    parser.add_argument('--ondemand', dest='ondemand', action='store_true',
                        help='use EC2 ondemand rather than EC2 spot market',)

    if argv is None:
        argv = parser.parse_args()

    if argv.launch_only:
        instance, hostname = launch_ec2(argv.ondemand)
        print "workhost launched |{0}| |{1}|".format(instance, hostname)

        poll_for_ssh(hostname)
        print "can contact host with ssh to {0}".format(hostname)

        remote_setup(hostname, instance)
        print("remote machine ready for manual control")

        exit(0)

    print BATCH

    print("checking PDF files on S3 to update shadow file and get list of current PDFs")
    current_pdfs = shadow(argv.bucket[0], argv.shadow[0], argv.shadow_prefix)
    last_modified_domain = current_pdfs
    files_to_generate = []

    if not argv.shadow_only:
        print("checking EAD for PDF files to generate")
        with requests.Session() as session:
            # set up session and Retry for EAD crawling
            retry = Retry(
                #https://urllib3.readthedocs.io/en/latest/reference/urllib3.util.html
                connect=3,
                backoff_factor=1,
            )
            adapter = HTTPAdapter(max_retries=retry)
            session.mount('http://', adapter)
            session.mount('https://', adapter)
            check_url(
                argv.eads[0],
                last_modified_domain,
                files_to_generate,
                generate_all=argv.all,
                session=session,
            )

    if files_to_generate:  ## will be false if in shadow_only mode
        print("there are files to generate")

        batch = generate_batch(
            files_to_generate,
            argv.eads[0],
            argv.bucket[0],
        )
        print("batch generated")
        print(batch.getvalue())

        instance, hostname = launch_ec2(argv.ondemand)
        print "workhost launched |{0}| |{1}|".format(instance, hostname)

        poll_for_ssh(hostname)
        print "can contact host with ssh to {0}".format(hostname)

        remote_setup(hostname, instance)

        remote_process_pdf(hostname, batch, instance)

        print "okay; done, terminate workhost"
        terminate_ec2(instance)

        print "updating shadow file for a second time"
        shadow(argv.bucket[0], argv.shadow[0], argv.shadow_prefix)


def check_url(url, last_modified_domain,
              files_to_generate, generate_all=False, session=None):
    """check if a URL is an XML file or directory based on the string value """
    dir, ext = os.path.splitext(url)
    # prime 2002 directory will have only .xml files or sub-directories
    if ext == '.xml':
        check_xml(url, last_modified_domain,
                  files_to_generate, generate_all=generate_all, session=session)
    elif not ext:
        check_dir(url, last_modified_domain,
                  files_to_generate, generate_all=generate_all, session=session)


def check_dir(url, last_modified_domain,
              files_to_generate, generate_all=False, session=None):
    """scrape links from directory listing"""
    sys.stdout.write('•')
    doc = parse(url).getroot()
    doc.make_links_absolute()
    links = doc.xpath("//a[@href]/@href")
    for link in links:
        # skip links back to myself and don't go up directories
        if not link == url and link.startswith(url):
            check_url(link, last_modified_domain,
                      files_to_generate, generate_all=generate_all, session=session)


def check_xml(url, last_modified_domain,
              files_to_generate, generate_all=False, session=None):
    """compare last_modifed in head with PDFs on S3
    this needs processing"""

    if generate_all:
    # force regeneration of all files (skip any expensive steps)
        add_to_list(url, False, files_to_generate, None)
    else:
        # expensive steps
        # do a HEAD request and check last modified time
        r = session.head(url)
        last_modified_on_oac_header = r.headers['last-modified']
        r.close()
        last_modified_on_oac = boto.utils.parse_ts(last_modified_on_oac_header)
        # look up this URL in the simple DB domain
        new_key = url.replace('http://voro.cdlib.org/oac-ead/prime2002/', 'pdf/')
        new_key = new_key.replace('.xml', '.pdf')
        last_modified_item = last_modified_domain.get(new_key)

        # decide if this should get added to the list
        #
        if not last_modified_item:
        # the URL was not seen before
            add_to_list(url, last_modified_domain,
                        files_to_generate, last_modified_on_oac_header)
        elif last_modified_on_oac > boto.utils.parse_ts(
                str(last_modified_item)
        ):
        # OR last-modified is later than the database;
            add_to_list(url, last_modified_domain,
                        files_to_generate, last_modified_on_oac_header)

# [pdfu]$ aws sdb delete-domain --domain-name ead_last_modified --region us-east-1
# [pdfu]$ aws sdb create-domain --domain-name ead_last_modified --region us-east-1


def add_to_list(url, last_modified_domain,
                files_to_generate, last_modified_on_oac_header):
    """modify the files_to_generate list and last_modified_domain"""
    # TODO the logic here could be better... need to keep a list of succussful
    # batches so failed batches can be re-tried
    # but then also need a way to detect and mark pathological cases
    print(url)
    files_to_generate.append(url)


def shadow(bucketurl, archive, prefix):
    """create shadow artifact for XTF index (so XTF can know what files
    are in the bucket and the PDF sizes"""
    parts = urlparse.urlsplit(bucketurl)
    # SplitResult
    # (scheme='s3', netloc='test.pdf', path='/dkd', query='', fragment='')
    s3 = boto.connect_s3()
    bucket = s3.get_bucket(parts.netloc)
    tmp = tempfile.NamedTemporaryFile(delete=False)
    tar = tarfile.open(fileobj=tmp, mode="w:gz")
    current_pdfs = {}
    for key in bucket.list():
        # look for pdfs that match the user supplied path
        if (key.name.endswith(u'.pdf') and not
           parts.path or key.name.startswith(parts.path[1:])):
            # write directly to a tar file
            #  http://stackoverflow.com/a/740839/1763984
            shadowfile = StringIO.StringIO()
            shadowfile.write(str(key.size))
            shadowfile.seek(0)
            shadowname = os.path.join(prefix, os.path.splitext(key.name)[0])
            info = tarfile.TarInfo(shadowname)
            info.size = len(shadowfile.buf)
            # boto last_modified to Datetime
            #  http://stackoverflow.com/a/9688496/1763984
            # Datetime to unixtime
            #  http://stackoverflow.com/a/255053/1763984
            info.mtime = time.mktime(
                boto.utils.parse_ts(key.last_modified).timetuple()
            )
            tar.addfile(tarinfo=info, fileobj=shadowfile)
            current_pdfs[key.name] = key.last_modified
            shadowfile.close()
    tar.close()
    tmp.flush()
    os.chmod(tmp.name, 0664)
    # local('/bin/tar ztf {0}'.format(tmp.name), capture=False)
    if archive.startswith("s3://"):
        inner_parts = urlparse.urlsplit(archive)
        # SplitResult
        # (scheme='s3', netloc='test.pdf', path='/dkd', query='', fragment='')
        inner_bucket = s3.get_bucket(inner_parts.netloc)
        inner_key = inner_bucket.new_key(inner_parts.path)
        inner_key.set_contents_from_filename(tmp.name)
        inner_key.set_acl('public-read')
    else:
        shutil.move(tmp.name, archive)

    return current_pdfs


def launch_ec2(ondemand=False):
    ami = "ami-098e42ae54c764c35"
    arn = ("arn:aws:iam::563907706919:"
           "instance-profile/s3-read-write")
    key_name = "pdfu-worker"
    # check http://aws.amazon.com/amazon-linux-ami/ for current AMI
    instance_type = 'm5.2xlarge'
    # 1.00/hr on demand    8vCPU       26 ECPU     30 G RAM
    # see "xargs"

    if ondemand:
        instance = launch_instance_ondemand(ami, arn, key_name, instance_type)
    else:
        instance =  launch_instance_spot(ami, arn, key_name, instance_type)

    print('Waiting for instance to start...')
    pp(instance)

    sleep(10)
    status = instance.update()
    while status == 'pending':
        sleep(10)
        sys.stdout.write('·')
        status = instance.update()

    if status == 'running':
        instance.add_tag('Name', 'OAC_pdfu')
        instance.add_tag('project', 'OAC_pdfu')
    else:
        print('invalid instance status')
        exit(1)

    if not(instance.private_dns_name):
        print "needs hostname"
    while not(instance.private_dns_name):
        # TODO gets stuck in a loop right here sometimes
        sleep(20)
        sys.stdout.write('·')

    return instance.id, instance.private_dns_name


def launch_instance_ondemand(ami, arn, key_name, instance_type):
    connection = boto.connect_ec2()
    print "connected, about to launch on demand instance"

    reservation = connection.run_instances(
        ami,
        instance_profile_arn=arn,
        instance_type=instance_type,
        key_name=key_name,
        subnet_id='subnet-1bbe676c',
    )
    return reservation.instances[0]


def launch_instance_spot(ami, arn, key_name, instance_type):
    connection = boto.connect_ec2()
    #import pdb; pdb.set_trace();
    print "connected, about to reserve on spot market"

    reservation = connection.request_spot_instances(
        "1.00",          # bid at on-demand rate
        ami,
        instance_profile_arn=arn,
        instance_type=instance_type,
        key_name=key_name,
        subnet_id='subnet-1bbe676c',
    )
    spot_id = str(reservation[0].id)
    print spot_id

    # make a dummy spot_reservation using namedtuple
    # to jumpstart the polling because
    # connection.get_all_spot_instance_requests(spot_id)[0]
    # was not setting spot_reservation.instance_id
    Resholder = namedtuple('Resholder', 'instance_id status')
    spot_reservation = Resholder(None, 'jumpstarting')

    # poll for spot instance to start up
    while spot_reservation.instance_id is None:
        pp(spot_reservation.status)
        sleep(20)
        spot_reservation = connection.get_all_spot_instance_requests(
            spot_id
        )[0]

    return connection.get_all_instances(
        spot_reservation.instance_id
    )[0].instances[0]


def poll_for_ssh(host):
    # http://stackoverflow.com/a/2561727/1763984
    # Set the timeout
    original_timeout = socket.getdefaulttimeout()
    new_timeout = 3
    socket.setdefaulttimeout(new_timeout)
    host_status = False
    while not host_status:
        try:
            paramiko.Transport((host, 22))
            host_status = True
        except Exception as e:
            pp(e)
        sleep(20)
        sys.stdout.write('⋅')
    socket.setdefaulttimeout(original_timeout)
    return host_status


def terminate_ec2(instance):
    connection = boto.connect_ec2()
    return connection.get_all_instances(instance)[0].instances[0].terminate()


def remote_setup(hostname, instance):
    """use fabric to run commands on the remote working node"""
    SETUP_SUDO = [
        'echo poweroff | at now + 12 hours',
        'yum -y update',
        'amazon-linux-extras install -y corretto8',
        'yum -y groupinstall "Development Tools"',
        # 'yum -y install python27-devel python27-virtualenv',
        'yum -y install git ncurses-devel openssl-devel libjpeg-devel freetype-devel libtiff-devel lcms-devel mercurial libxslt-devel libxml2-devel libX11-devel',
    ]
    SETUP_RUN = [
        'git clone https://github.com/cdlib/dsc-oac-pdfu.git pdfu',
        './pdfu/init.sh',
    ]
    env.host_string = hostname
    env.user = 'ec2-user'
    # fabric docs say fabric could hang if a command fails and recommend
    # to use try/finally

    try:
        pp(SETUP_SUDO)
        for command in SETUP_SUDO:
            sudo(command)
            sleep(1)
        pp(SETUP_RUN)
        for command in SETUP_RUN:
            run(command)
    finally:
        fabric.network.disconnect_all()

        # TODO: need to deal with the fact that if the spot price exceeds
        # the bid price  that the instance might die during the main run.
        # This might be a place things stall out.
        # but... how?  start a child thread or fork that watches the
        # instance and makes sure it is still running?


def remote_process_pdf(hostname, batch, instance):
    env.host_string = hostname
    env.user = 'ec2-user'
    # fabric docs say fabric could hang if a command fails and recommend
    # to use try/finally
    try:
        put(batch, '/home/ec2-user/batch.txt')
        pp("remote xargs")
        # xargs deals with the parallelization;
        run('source ./pdfu/ve/bin/activate')
        command =  'xargs -a /home/ec2-user/batch.txt -P 7 -n 2 '
        command += 'timeout --preserve-status --kill-after=30 1h '
        command += './pdfu/ve/bin/python ./pdfu/pdfu'
        run(command)
        #    xargs                             -P 7
        #         use n-1 processors (leaves one open for forked saxon)
        #         ** adjust to match the CPU that is being launched **
        #    xargs                                  -n 2
        #         pass 2 arguments at a time to command
    finally:
        fabric.network.disconnect_all()


def generate_batch(files_to_generate, eads, bucket):
    """turn the array of URLs into the args that will
       be passed to xargs on the remote node"""
    batch = StringIO.StringIO()
    for url in files_to_generate:
        args = "%s %s\n" % (url, fixup_url(url, eads, bucket))
        batch.write(args)
    batch.seek(0)
    return batch


def fixup_url(url, eads, bucket):
    """dirty path hacking specific to Online Archive of California here"""
    dir, ext = os.path.splitext(url)
    fixup = url.replace(eads, bucket)
    return u"%s.pdf" % (os.path.splitext(fixup)[0])


# main() idiom for importing into REPL for debugging
if __name__ == "__main__":
    # http://stackoverflow.com/a/9462099/1763984
    sys.stdout = os.fdopen(sys.stdout.fileno(), 'w', 0)
    sys.exit(main())


"""
   Copyright (c) 2016, Regents of the University of California
   All rights reserved.

   Redistribution and use in source and binary forms, with or without
   modification, are permitted provided that the following conditions are
   met:

   - Redistributions of source code must retain the above copyright notice,
     this list of conditions and the following disclaimer.
   - Redistributions in binary form must reproduce the above copyright
     notice, this list of conditions and the following disclaimer in the
     documentation and/or other materials provided with the distribution.
   - Neither the name of the University of California nor the names of its
     contributors may be used to endorse or promote products derived from
     this software without specific prior written permission.

   THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS"
   AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
   IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
   ARE DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE
   LIABLE FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR
   CONSEQUENTIAL DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF
   SUBSTITUTE GOODS OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS
   INTERRUPTION) HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN
   CONTRACT, STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE)
   ARISING IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
   POSSIBILITY OF SUCH DAMAGE.
"""
