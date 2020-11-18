FROM python:3.9.0

WORKDIR /usr/src/app

COPY requirements.txt ./

RUN pip install --no-cache-dir -r requirements.txt

COPY . .

ENV PORT=5000

ENV FLASK_APP=callboard.py

ENV FLASK_RUN_HOST=0.0.0.0

CMD [ "flask", "run" ]