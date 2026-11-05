# Build context: repository root (needs proto/ and services/ingest-go/).
#   docker build -f services/ingest-go/Dockerfile -t urbanflow-ingest:dev .
FROM golang:1.23-bookworm AS build
RUN apt-get update && apt-get install -y --no-install-recommends protobuf-compiler \
    && rm -rf /var/lib/apt/lists/*
RUN go install google.golang.org/protobuf/cmd/protoc-gen-go@v1.36.6 \
    && go install google.golang.org/grpc/cmd/protoc-gen-go-grpc@v1.5.1
WORKDIR /src
COPY proto/ /proto/
COPY services/ingest-go/ ./
RUN make proto && go mod tidy && CGO_ENABLED=0 go build -o /out/ingest-server ./cmd/ingest-server

FROM gcr.io/distroless/static-debian12:nonroot
COPY --from=build /out/ingest-server /ingest-server
EXPOSE 9090
ENTRYPOINT ["/ingest-server"]
