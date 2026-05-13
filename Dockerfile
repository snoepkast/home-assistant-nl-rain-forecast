FROM ghcr.io/home-assistant/home-assistant:2026.3.2

# apexcharts-card is required by the bundled dev dashboard at
# config/dashboards/rain-forecast.yaml.
ARG APEXCHARTS_CARD_VERSION=v2.2.3
ADD --chmod=644 \
    https://github.com/RomRider/apexcharts-card/releases/download/${APEXCHARTS_CARD_VERSION}/apexcharts-card.js \
    /config/www/apexcharts-card.js

COPY config/ /config/
