FROM nginx:alpine

# Install gettext for envsubst
RUN apk add --no-cache gettext

# Copy the built frontend
COPY frontend/build /usr/share/nginx/html

# Copy nginx configuration template
COPY nginx.conf /tmp/nginx.conf.template

# Create startup script to handle PORT env var
RUN echo '#!/bin/sh' > /docker-entrypoint.sh && \
    echo 'PORT=${PORT:-80}' >> /docker-entrypoint.sh && \
    echo 'envsubst '"'"'$$PORT'"'"' < /tmp/nginx.conf.template > /etc/nginx/nginx.conf' >> /docker-entrypoint.sh && \
    echo 'exec nginx -g "daemon off;"' >> /docker-entrypoint.sh && \
    chmod +x /docker-entrypoint.sh

EXPOSE 80

CMD ["/docker-entrypoint.sh"]
