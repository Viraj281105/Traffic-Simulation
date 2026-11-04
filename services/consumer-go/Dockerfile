# Build context: services/consumer-go (docker-compose.redpanda.yml does this).
#   docker build -t urbanflow-consumer:dev services/consumer-go
# go.sum is not committed yet: `go mod tidy` creates it (needs network). WRITTEN, not built.
FROM golang:1.23-bookworm AS build
WORKDIR /src
COPY . ./
RUN go mod tidy && go test ./... && CGO_ENABLED=0 go build -o /out/consumer .

FROM gcr.io/distroless/static-debian12:nonroot
COPY --from=build /out/consumer /consumer
ENTRYPOINT ["/consumer"]
