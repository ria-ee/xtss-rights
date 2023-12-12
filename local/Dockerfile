FROM python:3.10

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

RUN mkdir -p /var/log/xtss-rights

CMD flask --app 'rights:create_app("/app/config.yaml")' run --reload --host 0.0.0.0 --port 5080
#CMD gunicorn --workers 4 --bind 0.0.0.0:5080 'rights:create_app("/app/config.yaml")'
