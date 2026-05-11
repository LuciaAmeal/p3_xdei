FROM nginx:alpine

# Copy nginx configuration
COPY docker-entrypoint.sh /
RUN chmod +x /docker-entrypoint.sh

# Copy static files
COPY index.html /usr/share/nginx/html/index.html
COPY static/ /usr/share/nginx/html/static/

EXPOSE 80

ENTRYPOINT ["/docker-entrypoint.sh"]
