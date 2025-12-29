FROM node:20-slim

WORKDIR /app

# We'll use a shell script to initialize if node_modules don't exist
# But for now, let's assume standard Vite setup
COPY package*.json ./
RUN --mount=type=cache,target=/root/.npm \
    npm install

COPY . .

EXPOSE 5173

CMD ["npm", "run", "dev", "--", "--host"]
