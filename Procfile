web: export PYTHONUNBUFFERED=1 && flask db upgrade && flask seed-demo && gunicorn --workers 3 --timeout 60 --access-logfile - --access-logformat '%(h)s "%(r)s" %(s)s %(D)sus' run:app
