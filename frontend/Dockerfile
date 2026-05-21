FROM node:20-alpine

WORKDIR /app

COPY package.json ./
RUN npm install

COPY . .
RUN npm run build

EXPOSE 5173

# `vite preview` serves the production build and proxies /api to the backend.
CMD ["npm", "run", "preview"]
