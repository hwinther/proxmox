#!/usr/bin/python3
import os
import sys
import urllib.request

import dns.resolver

"""
Dependencies:
apt install dnsutils python3-pip && pip3 install dnspython

Configure:
set ddns_key_secret

Cron:
@hourly /usr/bin/python3 /root/ddns.py
"""

# Settings:

# ddns_key_path = '/etc/ddns.key'
ddns_key_path = None
# OR
ddns_key_algorithm = 'hmac-md5'
ddns_key_name = 'ddnswsh-key'
ddns_key_secret = 'x'
# Only the zone name
zone_name = 'wsh.no'
# Postfix here if using subdomain
domain_name = 'dynamic.oh'
nsserver = '167.172.166.129'
# Set False to avoid crontab sending emails when nothing is changed
verbose = False

# No need to edit after this line

ddns_domain = '%s.%s' % (domain_name, zone_name)
url = 'http://checkip.dyndns.org'
filehandle = urllib.request.urlopen(url)
data = filehandle.read().decode('utf-8')
ip = data.split(': ')[1].split('<')[0]
if verbose:
    print('External IP found: %s' % ip)

resolver = dns.resolver.Resolver()
resolver.nameservers = [nsserver]
try:
    answer = resolver.resolve(ddns_domain + '.', 'A')
except dns.resolver.NXDOMAIN:
    answer = None

if answer is not None:
    resolved_ip = answer.rrset[0].to_text()
    if resolved_ip == ip:
        if verbose:
            print('DNS record matches current IP, not updating')
        sys.exit(0)

nsupdate_script_path = '/tmp/nsupdate.script'
nsupdate_script = 'server %s\n' \
                  'zone %s\n' \
                  'update delete %s. A\n' \
                  'update add %s. 3600 A %s\n' \
                  'show\n' \
                  'send\n' % (nsserver, zone_name, ddns_domain, ddns_domain, ip)

if verbose:
    print('Writing to script file %s, content:' % nsupdate_script_path)
    print(nsupdate_script)
open(nsupdate_script_path, 'w').write(nsupdate_script)

print('Updating A record for %s to %s' % (ddns_domain, ip))
if ddns_key_path is None:
    cmd = '/usr/bin/nsupdate -y hmac-md5:%s:%s %s' % (ddns_key_name, ddns_key_secret, nsupdate_script_path)
else:
    cmd = '/usr/bin/nsupdate -k %s %s' % (ddns_key_path, nsupdate_script_path)
if verbose:
    print('Executing: %s' % cmd)
os.system(cmd)
