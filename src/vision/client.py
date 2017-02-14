import requests
import os
import datetime as dt
import subprocess
from Queue import Queue
from threading import Thread
from io import BytesIO
from itertools import repeat

import sys
reload(sys)
sys.setdefaultencoding('utf-8')

DEFAULT_HOST_URL = 'http://localhost:9001'

class Client(object):

    VERSION = 'v1.0'

    class Worker(Thread):

        def __init__(self, incoming_queue, results):
            super(Client.Worker, self).__init__()
            self.incoming_queue = incoming_queue
            self.results = results

        def run(self):
            while True:
                frame, image_file, url, callback = self.incoming_queue.get()
                try:
                    r = requests.post(
                        '{}/detect_face'.format(url), data=image_file, timeout=1)
                    ret = r.json().get('ret')
                    response = r.json().get('response')
                    if callable(callback):
                        callback(frame, response)
                    self.results.put((frame, response))
                    self.incoming_queue.task_done()
                except Exception as ex:
                    print ex

    def __init__(self, hosts=None):
        if not hosts:
            self.hosts = [DEFAULT_HOST_URL]
        else:
            self.hosts = hosts
        self.q = Queue()
        self.results = Queue()

        self.workers = {}
        for host in self.hosts:
            worker = Client.Worker(self.q, self.results)
            worker.daemon = True
            worker.start()
            self.workers[host] = worker

    def detect_faces(self, frame, image_file, callback=None):
        """
        image_file: file-like object
        """
        host = self.hosts[frame%len(self.hosts)]
        url = '{}/{}'.format(host, Client.VERSION)
        buf = BytesIO(image_file.read())
        self.q.put((frame, buf, url, callback))

if __name__ == '__main__':
    hosts = ['http://localhost:9001', 'http://localhost:9002']
    client = Client(hosts)
    start = dt.datetime.now()
    def callback(frame, response):
        print frame, response

    for i in range(100):
        with open('obama.png', 'rb') as f:
            client.detect_faces(i, f, callback)
    client.q.join()
    print dt.datetime.now() - start
