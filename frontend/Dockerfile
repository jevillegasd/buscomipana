# ---- base: shared dependency install ----
FROM node:20-alpine AS base
WORKDIR /app
COPY package.json ./
RUN npm install

# ---- dev: what docker-compose.yml runs locally (bind-mounted source, hot reload) ----
# The Vite dev server is explicitly not hardened for production use (no
# minification, permissive by default, meant to be run behind trusted local
# tooling only) -- this stage exists purely for local development.
FROM base AS dev
COPY . .
EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0"]

# ---- build: compiles the static production bundle ----
FROM base AS build
COPY . .
# Same-origin path routing in production (see ../Caddyfile: /api/* -> backend,
# everything else -> this app) means the built bundle can call a relative
# "/api/v1" instead of baking in a specific domain -- Vite inlines this at
# build time, so it's set here rather than left to a runtime env var.
ENV VITE_API_BASE_URL=/api/v1
RUN npm run build

# ---- runtime: minimal static file server, no Node/npm/source in the final image ----
FROM nginxinc/nginx-unprivileged:1.27-alpine AS runtime
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 8080
