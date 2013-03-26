#-------------------------------------------------------------------------------
# Copyright (c) 2013 Zubair Nabi <zn.zubairnabi@gmail.com>
# 
# Permission to use, copy, modify, and distribute this software for any
# purpose with or without fee is hereby granted, provided that the above
# copyright notice and this permission notice appear in all copies.
# 
# THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
# WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
# MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
# ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
# WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
# ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
# OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.
#-------------------------------------------------------------------------------

URL = 'http://propakistani.pk/wp-content/uploads/2010/05/blocked.html'
INDEXES = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 165, 284, 301, 302, 
           303, 304, 305, 306, 307, 308, 309, 322, 323, 324, 325, 326, 327, 
           329, 330, 331, 332]
DNS_SERVERS = ['8.8.8.8', '8.26.56.26', '208.67.222.222', '209.244.0.3', '198.153.192.40']
CORAL_LOOKUP = True

class Website(object):
    
    def __init__(self, url):
        self.url = url
        self.dns_lookup = False
        self.dns_lookup_failure = ''
        self.ips = []
        self.dns_server = 'Default'
        self.ip_connect = False
        self.url_keyword = False
        self.http_code = 0
        self.redirect_ip = ''
        self.coral_http_code = 0
        self.coral_redirect_ip = ''
    
    def separate(self):
        return [self.url, self.dns_lookup, self.dns_lookup_failure, 
                self.dns_server, self.ips, self.ip_connect, self.url_keyword,
                self.http_code, self.redirect_ip, self.coral_http_code,
                self.coral_redirect_ip]
                

def retrieve_content(url):
    import urllib2
    print 'Retrieving website list'
    return urllib2.urlopen(url).read()

def parse_content(content):
    import re
    return re.findall(r'href=[\'"]?([^\'" >]+)', content)

def get_list():
    return filter_list(parse_content(retrieve_content(URL)))

def filter_list(list__):
    import re
    return [re.sub(r'http://|https://', r'', list__[index]).rstrip('/')
            for index, _ in enumerate(list__) if index not in INDEXES]

def dns_lookup(url, progress_count, total_count, csvfile, log, server=None):
    print 'Processing website %d of %d' % (progress_count, total_count)
    # To ensure that we flush the CSV regularly
    if progress_count % 20 == 0:
        csvfile.flush()
    import dns.resolver
    result = Website(url)
    resolver = dns.resolver
    if server:
        resolver = dns.resolver.Resolver()
        resolver.nameservers = [server]
        result.dns_server = server
    else:
        # Check whether accessible via Coral
        if CORAL_LOOKUP:    
            result.coral_http_code, result.coral_redirect_ip = coral_status(url, log)
    try:
        answers = resolver.query(url, 'A')
        result.dns_lookup = True
        [result.ips.append(str(rdata)) for rdata in answers]
        # DNS look up successful, now try to connect to each IP on port 80
        result.ip_connect = ip_connect(result.ips)
        if result.ip_connect:
            # IP connection successful, now check URL keyword filtering
            result.url_keyword = url_keyword(url)
            # Now check HTTP status
            result.http_code, result.redirect_ip = http_status(url, log)
    except dns.resolver.NXDOMAIN:
        result.dns_lookup_failure = 'NXDomain'
    except dns.name.LabelTooLong:
        result.dns_lookup_failure = 'LabelTooLong'
    except dns.name.EmptyLabel:
        result.dns_lookup_failure = 'EmptyLabel'
    except dns.exception.Timeout:
        result.dns_lookup_failure = 'Timeout'
    return result

def ip_connect(ips):
    import socket 
    status = True
    for ip in ips:       
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            s.connect((ip, 80))
        except:
            status = False
        s.close()    
    return status

def url_keyword(url):
    import urllib2
    status = True
    url = 'http://www.google.com/' + url
    try:
        urllib2.urlopen(url)
    except urllib2.HTTPError as e:
        if e.code != 404:
            status = False
    return status

def dns_lookup_list(list__, log, server=None):
    print 'Performing DNS tests using server %s for %d sites' % (server, len(list__))
    import csv
    with open('results.csv', 'a+b') as csvfile:
        csv_writer = csv.writer(csvfile)
        if not server:
            csv_writer.writerow(['URL', 'DNS_Status', 'Failure_Code', 
                                 'DNS_Server', 'IPs', 'IP_Connect', 'URL_Keyword',
                                 'HTTP_Code', 'HTTP_Redirect', 'Coral_HTTP_Code',
                                 'Coral_HTTP_Redirect'])
            csvfile.flush()
        [csv_writer.writerow(map(str, dns_lookup(url, count, len(list__), csvfile, log, server).separate())) 
         for count, url in enumerate(list__)]
        
def http_status(url, log):
    import httplib
    code = 0
    redirect_ip = ''
    try:
        conn = httplib.HTTPConnection(url)
        conn.request("GET", "/index.html")
        res = conn.getresponse()
        code = res.status
        if code == httplib.FOUND:
            redirect_ip = res.getheader('location')   
    except Exception as e:
        log.error(str(e) + ' URL: %s' % url)
    return code, redirect_ip

def coral_status(url, log):
    import urllib2
    class RedirectHandler(urllib2.HTTPRedirectHandler):
        def http_error_301(self, req, fp, code, msg, headers):  
            result = urllib2.HTTPRedirectHandler.http_error_301( 
                self, req, fp, code, msg, headers)              
            result.status = code
            result.original_headers = headers                                
            return result
    
        def http_error_302(self, req, fp, code, msg, headers):
            result = urllib2.HTTPRedirectHandler.http_error_302(
                self, req, fp, code, msg, headers)          
            result.status = code 
            result.original_headers = headers                               
            return result
        
    code = 0
    redirect_ip = ''
    splits = url.split('/', 1)
    coral_url = 'http://' + splits[0] + '.nyud.net' 
    if len(splits) == 2:
        coral_url += '/' + splits[1]
    opener = urllib2.build_opener(RedirectHandler)
    urllib2.install_opener(opener)
    try:
        req = urllib2.Request(coral_url)
        response = urllib2.urlopen(req)
        if hasattr(response, 'status'):
            code = response.status
            redirect_ip = response.original_headers['location']
        else:
            code = response.code
    except urllib2.HTTPError, e:
        code = e.code
    except Exception as e:
        log.error(str(e) + ' URL: %s' % coral_url)
    return code, redirect_ip

   
if __name__ == '__main__':
    import logging
    log = logging.getLogger('errors')
    log.setLevel(logging.INFO)
    fh = logging.FileHandler('errors.log')
    log.addHandler(fh)
    formatter = logging.Formatter('%(asctime)s, %(funcName)s, %(lineno)d, %(message)s')
    fh.setFormatter(formatter)
    url_list = get_list()
    dns_lookup_list(url_list, log)
    [dns_lookup_list(url_list, log, server) for server in DNS_SERVERS]
    print 'Finished tests'
    