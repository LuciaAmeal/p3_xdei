FROM nginx:alpine

# Install envsubst (gettext) to allow simple env substitution if needed
RUN apk add --no-cache gettext

COPY docker-entrypoint.sh /docker-entrypoint.sh
COPY . /usr/share/nginx/html/
RUN chmod +x /docker-entrypoint.sh

EXPOSE 80
ENTRYPOINT ["/docker-entrypoint.sh"]
