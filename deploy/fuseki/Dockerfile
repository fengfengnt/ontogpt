FROM eclipse-temurin:21-jre@sha256:227118764cccd3c3294617061aaa93a08309c63a395eefa83e6b35032992ea99

LABEL org.opencontainers.image.title="Procurement Apache Jena Fuseki"
LABEL org.opencontainers.image.version="6.2.0"
LABEL org.opencontainers.image.source="https://jena.apache.org/download/"

ADD https://downloads.apache.org/jena/binaries/apache-jena-fuseki-6.2.0.tar.gz /tmp/fuseki.tar.gz
RUN echo 'ba65f5867d2d4741b2ed9e2af5a0d4fbb447909894ab2a0c6bc4dac8997f4fe339c87b13c48d45d054977769f0f8bf763ea346b1f7792d5cdc458041bd43a132  /tmp/fuseki.tar.gz' | sha512sum -c - \
    && mkdir -p /opt/fuseki /data \
    && tar -xzf /tmp/fuseki.tar.gz --strip-components=1 -C /opt/fuseki \
    && rm /tmp/fuseki.tar.gz \
    && chown -R 1000:1000 /data

WORKDIR /opt/fuseki
ENV FUSEKI_BASE=/data
USER 1000:1000
EXPOSE 3030
ENTRYPOINT ["java", "-Xmx1g", "-jar", "fuseki-server.jar"]
CMD ["--port=3030"]
