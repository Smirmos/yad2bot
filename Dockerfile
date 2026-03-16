FROM mcr.microsoft.com/playwright/python:v1.58.0-noble

WORKDIR /app
COPY requirements.txt .
RUN pip install "setuptools<81" -r requirements.txt
COPY . .

CMD ["python", "main.py"]
