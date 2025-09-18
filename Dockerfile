FROM python:3.13-slim
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
RUN pip install --no-cache-dir uv
COPY pyproject.toml uv.lock ./
RUN uv --version
# Install from lockfile into the system environment
RUN uv pip compile pyproject.toml -o requirements.txt
RUN uv pip install --system -r requirements.txt
COPY . .
EXPOSE 8080
CMD ["uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8080"]