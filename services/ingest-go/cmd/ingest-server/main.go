// Command ingest-server serves the Ingest gRPC API.
package main

import (
	"context"
	"flag"
	"log"
	"net"
	"os"
	"os/signal"
	"syscall"

	"google.golang.org/grpc"

	"urbanflow/ingest/gen/ingestpb"
	"urbanflow/ingest/internal/server"
	"urbanflow/ingest/internal/store"
)

func main() {
	addr := flag.String("addr", ":9090", "listen address")
	shards := flag.Int("shards", 16, "store shards")
	flag.Parse()

	lis, err := net.Listen("tcp", *addr)
	if err != nil {
		log.Fatalf("listen %s: %v", *addr, err)
	}
	g := grpc.NewServer()
	ingestpb.RegisterIngestServer(g, server.New(store.New(*shards)))

	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()
	go func() {
		<-ctx.Done()
		log.Println("shutting down")
		g.GracefulStop()
	}()

	log.Printf("ingest server listening on %s", lis.Addr())
	if err := g.Serve(lis); err != nil {
		log.Fatalf("serve: %v", err)
	}
}
