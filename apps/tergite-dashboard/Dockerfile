#Building the react app
FROM node:20-alpine AS build

WORKDIR /app
ARG MSS_CONFIG_FILE
ARG VITE_API_BASE_URL
ARG VITE_COOKIE_DOMAIN
ARG VITE_COOKIE_NAME

COPY package*.json ./
COPY --from=parent-folder "$MSS_CONFIG_FILE"* ./

RUN npm ci

COPY . .

RUN apk --no-cache add curl yq

# If $MSS_CONFIG_FILE was copied, update .env.production.local
RUN \
    cookie_domain=""; \
    cookie_name=""; \
    if [ -f "$MSS_CONFIG_FILE" ]; then \
        # read the variables from the toml config file
        cookie_domain=$(yq -p=toml ".auth.cookie_domain" "$MSS_CONFIG_FILE" 2>/dev/null);\
        cookie_name=$(yq -p=toml ".auth.cookie_name" "$MSS_CONFIG_FILE" 2>/dev/null);\
    fi; \
    # add them to the .env.production.local file
    # cookie domain; try build arg VITE_COOKIE_DOMAIN first before falling back to value from MSS_CONFIG_FILE
    if [ -n "$VITE_COOKIE_DOMAIN" ]; then \
        echo "VITE_COOKIE_DOMAIN=$VITE_COOKIE_DOMAIN" >> .env.production.local; \
    elif [ -n "$cookie_domain" ]; then \
        echo "VITE_COOKIE_DOMAIN=$cookie_domain" >> .env.production.local; \
    else \
        echo "auth.cookie_domain is required in ${MSS_CONFIG_FILE} or you set --build-arg VITE_COOKIE_DOMAIN=...";\
        exit 1;\
    fi;\
    # cookie name; try build arg VITE_COOKIE_NAME first before falling back to value from MSS_CONFIG_FILE
    if [ -n "$VITE_COOKIE_NAME" ]; then \
        echo "VITE_COOKIE_NAME=$VITE_COOKIE_NAME" >> .env.production.local; \
    elif [ -n "$cookie_name" ]; then \
        echo "VITE_COOKIE_NAME=$cookie_name" >> .env.production.local; \
    else \
        echo "auth.cookie_name is required in ${MSS_CONFIG_FILE} or you set --build-arg VITE_COOKIE_NAME=...";\
        exit 1;\
    fi; \
    # VITE_API_BASE_URL build arg
    if [ -n "$VITE_API_BASE_URL" ]; \
    then echo "VITE_API_BASE_URL=$VITE_API_BASE_URL" >> .env.production.local; \
    else \
        echo "VITE_API_BASE_URL is required"; \
        exit 1; \
    fi; 

RUN npm run build

# Building the final image
FROM nginx:1.27.1-alpine-slim AS prod

COPY --from=build /app/dist /usr/share/nginx/html
COPY --from=build /app/.env.production.local /etc/nginx/.env.local
COPY nginx.conf /etc/nginx/nginx.conf
COPY run-nginx.sh /usr/sbin/run-nginx

RUN apk --no-cache add yq
RUN chmod +x /usr/sbin/run-nginx

EXPOSE 80/tcp

# expected env variables
ENV COOKIE_DOMAIN=""
ENV COOKIE_NAME=""
ENV API_BASE_URL=""
ENV MSS_CONFIG_FILE=""

ENTRYPOINT [ "/usr/sbin/run-nginx" ]

CMD ["-g", "daemon off;"]