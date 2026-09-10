# Web Privacy API Crawler

## Setup
Build and run the docker image:

1. Built the docker image:
```
docker build -t webprivacy-crawler .
```
2. Run the docker container:
```
docker run -d -v ./output:/app/output webprivacy-crawler
```

You should see the output files in the `output` directory on your host machine.