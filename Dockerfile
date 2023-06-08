FROM python:3.11-alpine

WORKDIR /app

COPY entrypoint.sh .

CMD ["./entrypoint.sh"]
