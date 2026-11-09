# Image du traitement quotidien : dépendances de calcul, séparées de l'API.
FROM public.ecr.aws/lambda/python:3.12
COPY pyproject.toml ${LAMBDA_TASK_ROOT}/
COPY src ${LAMBDA_TASK_ROOT}/src
RUN pip install --no-cache-dir "${LAMBDA_TASK_ROOT}[job]"
CMD ["communitylens.jobs.daily.lambda_handler"]
