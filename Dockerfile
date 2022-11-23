FROM python:3.9

WORKDIR /usr/src/app
ENV TZ="Europe/Stockholm"

RUN set -eux; \
	apt-get update; \
	apt-get install -y libpango-1.0-0 libpangoft2-1.0-0 libjpeg-dev libopenjp2-7-dev libffi-dev

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

CMD [ "python", "./main.py" ]