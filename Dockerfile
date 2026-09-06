FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
RUN useradd --create-home appuser
COPY --chown=appuser:appuser . .
RUN mkdir -p /app/data && chown appuser:appuser /app/data
USER appuser
EXPOSE 8501
CMD ["python", "-m", "streamlit", "run", "TrendWatcher.py", "--server.address=0.0.0.0", "--server.headless=true"]
