FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY shared/ shared/
COPY data_fetcher/ data_fetcher/

EXPOSE 8082

CMD ["uvicorn", "data_fetcher.main:app", "--host", "0.0.0.0", "--port", "8082"]
