# syntax=docker/dockerfile:1
FROM node:22-alpine@sha256:fe4f6d74e20370acb04ad889077d14d0f64a9c8ea6a42bc60cddf1e844699914 AS build
WORKDIR /app
ADD https://github.com/maldorne/mud-web-proxy.git#6459d115f0cabda3b7a25580cf8dd022a7582bde /app
RUN apk add --no-cache patch
COPY web/proxy.patch /tmp/proxy.patch
COPY web/proxy.test.mjs /app/fd.test.mjs
RUN patch -p1 < /tmp/proxy.patch && npm ci && npm run build && LOG_LEVEL=silent node --test fd.test.mjs && npm prune --omit=dev

FROM node:22-alpine@sha256:fe4f6d74e20370acb04ad889077d14d0f64a9c8ea6a42bc60cddf1e844699914
WORKDIR /app
COPY --from=build /app/dist ./dist
COPY --from=build /app/node_modules ./node_modules
COPY --from=build /app/package.json /app/package-lock.json /app/LICENSE.md ./
ENV NODE_ENV=production
USER node
EXPOSE 6200
CMD ["node", "dist/index.js"]
