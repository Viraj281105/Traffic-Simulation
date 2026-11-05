# Generated code (gen/ingestpb) is not committed; `make proto` creates it.
# Needs: protoc, protoc-gen-go v1.36.6, protoc-gen-go-grpc v1.5.1 on PATH.
#   go install google.golang.org/protobuf/cmd/protoc-gen-go@v1.36.6
#   go install google.golang.org/grpc/cmd/protoc-gen-go-grpc@v1.5.1
PROTO_DIR := ../../proto

.PHONY: proto build test bench

proto:
	mkdir -p gen/ingestpb
	protoc -I $(PROTO_DIR) \
		--go_out=gen/ingestpb --go_opt=paths=source_relative \
		--go-grpc_out=gen/ingestpb --go-grpc_opt=paths=source_relative \
		$(PROTO_DIR)/ingest.proto

build: proto
	go mod tidy
	go build ./...

test: proto
	go mod tidy
	go vet ./...
	go test ./...

bench: proto
	go test -bench=. -benchmem ./internal/store/
	go run ./cmd/ingest-bench
