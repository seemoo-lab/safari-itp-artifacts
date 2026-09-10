FROM alpine
RUN apk add --no-cache wget tar

COPY download.sh /download.sh
RUN chmod +x /download.sh

WORKDIR /data
CMD ["/download.sh"]