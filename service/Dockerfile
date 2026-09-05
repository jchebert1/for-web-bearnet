FROM node:24-alpine
RUN apk add --no-cache ffmpeg
WORKDIR /app
RUN npm install --omit=dev express@4 multer@1
COPY server.js ./
COPY builtin ./builtin
ENV NODE_ENV=production
EXPOSE 8600
CMD ["node", "server.js"]
