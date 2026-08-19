FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json* ./
COPY apps/web/package.json apps/web/package.json
COPY packages/shared-ts/package.json packages/shared-ts/package.json
COPY packages/widget/package.json packages/widget/package.json
RUN npm install
COPY . .
ARG NEXT_PUBLIC_API_URL
ENV NEXT_PUBLIC_API_URL=$NEXT_PUBLIC_API_URL
RUN npm run build --workspace=@voiceos/dashboard
FROM node:22-alpine
WORKDIR /app
COPY --from=build /app ./
CMD ["npm", "run", "start", "--workspace=@voiceos/dashboard"]
