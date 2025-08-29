FROM mcr.microsoft.com/playwright:v1.47.2-jammy

WORKDIR /app
COPY package*.json ./
RUN npm install
COPY tsconfig.json ./
COPY src ./src
RUN npx tsc
RUN npm prune --omit=dev

ENV NODE_ENV=production
EXPOSE 4005
CMD ["node", "dist/index.js"]
