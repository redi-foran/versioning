#!/bin/sh
this_dir=$(dirname $0)
#PYTHONPATH=$this_dir/service:$PYTHONPATH python3 -m aiohttp.web -H $(hostname).rdti.com -P 8081 service:run_server
PYTHONPATH=$this_dir/service:$PYTHONPATH python3 versioning.py
