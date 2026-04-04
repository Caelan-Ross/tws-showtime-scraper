FROM python:3.12-slim
WORKDIR /app
RUN pip install requests
COPY scraper.py .
CMD ["python3", "scraper.py"]
