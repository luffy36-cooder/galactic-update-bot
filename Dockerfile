FROM python:3.13-slim

WORKDIR /app

COPY imghdr.py ./ 

COPY . .

RUN python --version
RUN pip install -r requirements.txt

CMD ["python", "bot.py"]
