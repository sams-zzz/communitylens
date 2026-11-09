# Même image sur EC2, en local et sur Lambda : le Web Adapter ne s'active que dans Lambda.
FROM python:3.12-slim
COPY --from=public.ecr.aws/awsguru/aws-lambda-adapter:1.1.0 /lambda-adapter /opt/extensions/lambda-adapter
ENV AWS_LWA_PORT=8080 AWS_LWA_READINESS_CHECK_PATH=/health PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml ./
COPY src ./src
RUN pip install --no-cache-dir .
COPY frontend ./frontend
RUN useradd --create-home app
USER app
EXPOSE 8080
CMD ["uvicorn", "--factory", "communitylens.api.main:build_app", "--host", "0.0.0.0", "--port", "8080"]
