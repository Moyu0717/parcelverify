FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
ENV PORT=8501 PV_DATA_DIR=/data/workspaces
EXPOSE 8501
CMD ["python", "start.py"]
