FROM node:24.14.0-bookworm-slim AS build
WORKDIR /app
COPY --chown=node:node package.json package-lock.json ./
COPY --chown=node:node apps/web/package.json apps/web/package.json
RUN --mount=type=secret,id=build_ca \
    if [ -s /run/secrets/build_ca ]; then export NODE_EXTRA_CA_CERTS=/run/secrets/build_ca; fi; \
    npm ci
COPY --chown=node:node apps/web apps/web
COPY --chown=node:node packages/api-contract packages/api-contract
ENV NEXT_TELEMETRY_DISABLED=1
RUN npm run build
USER node
CMD ["npm", "run", "start", "--workspace", "apps/web"]
