# syntax=docker/dockerfile:1
FROM node:22-alpine@sha256:fe4f6d74e20370acb04ad889077d14d0f64a9c8ea6a42bc60cddf1e844699914 AS build
WORKDIR /app
ADD https://github.com/maldorne/mud-web-client.git#ca4b94caf03c265c72c181f4949e6ef2c7c15c18 /app
RUN apk add --no-cache patch
COPY web/client.patch /tmp/client.patch
RUN patch -p1 < /tmp/client.patch && npm ci && npm run build

FROM nginx:alpine@sha256:a3554c0d0b48177b1413c26e01f695334428020d9df01243fbae3e11cfd17417
COPY --from=build /app/dist /usr/share/nginx/html
COPY --from=build /app/LICENSE.md /usr/share/nginx/html/LICENSE-client.txt
COPY mud/license.* NOTICE /usr/share/nginx/html/licenses/
COPY web/credits.html /usr/share/nginx/html/credits.html
COPY web/nginx.conf /etc/nginx/nginx.conf
USER nginx
EXPOSE 8080
ENTRYPOINT ["nginx"]
CMD ["-g", "daemon off;"]
