FROM mcr.microsoft.com/playwright:v1.55.0-jammy

WORKDIR /app
COPY package.json package-lock.json* ./
RUN if [ -f package-lock.json ]; then npm ci --no-audit --no-fund; else npm install --no-audit --no-fund; fi
COPY tsconfig.json ./tsconfig.json
COPY src ./src
RUN npx tsc -p tsconfig.json

ENV PORT=4005
CMD ["node", "dist/index.js"]
