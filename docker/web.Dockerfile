FROM node:22-alpine AS build

WORKDIR /app

COPY apps/web/package.json ./package.json
COPY apps/web/package-lock.json ./package-lock.json
# All dependency lifecycle scripts are blocked first. esbuild is the one
# documented exception because Vite needs its platform-specific binary to build.
RUN npm ci --ignore-scripts --audit=false \
    && npm rebuild esbuild --ignore-scripts=false --foreground-scripts --audit=false

COPY apps/web ./
RUN npm run build

FROM nginx:1.31-alpine AS runtime

COPY docker/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80
