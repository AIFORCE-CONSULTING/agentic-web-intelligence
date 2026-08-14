FROM python:3.12-slim AS build

WORKDIR /workspace

COPY docs/requirements.lock ./docs/requirements.lock
RUN pip install --no-cache-dir --require-hashes --only-binary=:all: -r docs/requirements.lock

COPY mkdocs.yml ./
COPY docs ./docs
COPY diagrams ./diagrams
COPY PROJECT.md PRINCIPLES.md TECH_STACK.md ROADMAP.md ./
COPY ARCHITECTURE.md REPOSITORIES.md DECISIONS.md CONTRIBUTING.md STYLE_GUIDE.md ./

RUN mkdocs build --strict

FROM nginx:1.27-alpine AS runtime

COPY docker/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /workspace/site /usr/share/nginx/html

EXPOSE 80
