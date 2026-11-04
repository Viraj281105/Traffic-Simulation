package server_test

import (
	"context"
	"net"
	"testing"
	"time"

	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"
	"google.golang.org/grpc/test/bufconn"

	"urbanflow/ingest/client"
	"urbanflow/ingest/gen/ingestpb"
	"urbanflow/ingest/internal/server"
	"urbanflow/ingest/internal/store"
)

// start runs a real gRPC server over an in-memory listener and returns a
// client wired to it, so the whole wire contract is exercised.
func start(t *testing.T) *client.Client {
	t.Helper()
	lis := bufconn.Listen(1 << 20)
	g := grpc.NewServer()
	ingestpb.RegisterIngestServer(g, server.New(store.New(4)))
	go func() { _ = g.Serve(lis) }()
	t.Cleanup(g.Stop)

	conn, err := grpc.NewClient("passthrough:///bufnet",
		grpc.WithContextDialer(func(context.Context, string) (net.Conn, error) { return lis.Dial() }),
		grpc.WithTransportCredentials(insecure.NewCredentials()))
	if err != nil {
		t.Fatal(err)
	}
	t.Cleanup(func() { _ = conn.Close() })
	return client.FromConn(conn)
}

func ctx(t *testing.T) context.Context {
	c, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	t.Cleanup(cancel)
	return c
}

func TestBatchStreamSummaryContract(t *testing.T) {
	c := start(t)
	x := ctx(t)

	events := []*ingestpb.Event{
		{RunId: "a", Seq: 0, SimTime: 0, Kind: "step", Metrics: map[string]float64{"speed": 10}},
		{RunId: "a", Seq: 1, SimTime: 0.1, Kind: "step", Metrics: map[string]float64{"speed": 20}},
		{RunId: "a", Seq: 1, SimTime: 0.1}, // duplicate
		{RunId: "", Seq: 0},                // rejected
	}
	r, err := c.IngestBatch(x, events)
	if err != nil {
		t.Fatal(err)
	}
	if r.Accepted != 2 || r.Duplicates != 1 || r.Rejected != 1 {
		t.Fatalf("batch response = %+v", r)
	}

	r, err = c.IngestStream(x, []*ingestpb.Event{
		{RunId: "a", Seq: 2, SimTime: 0.2, Metrics: map[string]float64{"speed": 30}},
		{RunId: "b", Seq: 0},
	})
	if err != nil {
		t.Fatal(err)
	}
	if r.Accepted != 2 {
		t.Fatalf("stream response = %+v", r)
	}

	sum, err := c.RunSummary(x, "a")
	if err != nil {
		t.Fatal(err)
	}
	if !sum.Found || sum.Events != 3 || sum.LastSeq != 2 || sum.MetricMeans["speed"] != 20 {
		t.Fatalf("summary = %+v", sum)
	}
	st, err := c.Stats(x)
	if err != nil {
		t.Fatal(err)
	}
	if st.Runs != 2 || st.Events != 4 {
		t.Fatalf("stats = %+v", st)
	}
}

func TestBatchLimit(t *testing.T) {
	c := start(t)
	big := make([]*ingestpb.Event, server.MaxBatch+1)
	for i := range big {
		big[i] = &ingestpb.Event{RunId: "x", Seq: int64(i)}
	}
	if _, err := c.IngestBatch(ctx(t), big); err == nil {
		t.Fatal("oversized batch accepted")
	}
}
