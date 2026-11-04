FROM python:3.12-slim
WORKDIR /app
COPY platform_lab /app/platform_lab
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
USER 10001:10001
EXPOSE 8080
HEALTHCHECK --interval=10s --timeout=3s --start-period=5s CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/livez', timeout=2)"
CMD ["python", "-m", "platform_lab.service", "--host", "0.0.0.0"]
