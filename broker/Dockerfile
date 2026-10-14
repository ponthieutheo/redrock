FROM python:3.12-slim
RUN pip install --no-cache-dir hyperliquid-python-sdk==0.24.0 "mcp[cli]<2" pandas pandas-ta-classic requests feedparser websockets tzdata trafilatura
WORKDIR /app
COPY broker.py .
CMD ["python", "-u", "broker.py"]
