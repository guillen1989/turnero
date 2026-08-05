import sys

bind = "0.0.0.0:8080"
workers = 3
timeout = 60
accesslog = sys.stderr
access_log_format = '%(h)s "%(r)s" %(s)s %(D)sus'
errorlog = "-"
loglevel = "info"
