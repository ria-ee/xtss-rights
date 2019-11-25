FROM python:3.6

WORKDIR /app

COPY files/requirements.txt files/rights.py files/server.py ./
RUN pip install --no-cache-dir -r requirements.txt

COPY config.json config.json
RUN mkdir -p /var/log/xtss-rights

CMD gunicorn --workers 4 --bind 0.0.0.0:5080 server:app
