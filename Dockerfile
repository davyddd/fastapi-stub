ARG BASE_IMAGE_TAG
FROM $BASE_IMAGE_TAG

WORKDIR /app/src

COPY uv.lock pyproject.toml /app/

ARG DEVELOP_DEPENDENCIES
RUN cd /app && if [ "$DEVELOP_DEPENDENCIES" = "0" ]; then uv sync --frozen --no-dev; else uv sync --frozen; fi

COPY . /app

CMD python manage.py runserver
