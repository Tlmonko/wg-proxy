# build
FROM node:22-alpine AS build
ARG VITE_VM_URL=""
ENV VITE_VM_URL=$VITE_VM_URL
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci || npm install
COPY . .
RUN npm run build

# serve
FROM nginx:alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
