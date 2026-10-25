# syntax=docker/dockerfile:1
FROM node:22-alpine AS build
WORKDIR /app
ADD https://github.com/maldorne/mud-web-client.git#ca4b94caf03c265c72c181f4949e6ef2c7c15c18 /app
RUN apk add --no-cache patch
COPY web/client.patch /tmp/client.patch
RUN patch -p1 < /tmp/client.patch && npm ci && npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY --from=build /app/LICENSE.md /usr/share/nginx/html/LICENSE-client.txt
COPY web/nginx.conf /etc/nginx/nginx.conf
USER nginx
EXPOSE 8080
ENTRYPOINT ["nginx"]
CMD ["-g", "daemon off;"]
