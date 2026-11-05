// Command ingest-bench measures ingest throughput and latency over gRPC and
// prints one JSON object, so it can be compared with the Python path's
// numbers on the same payload (see docs/operations-platform.md).
//
//	ingest-bench -addr localhost:9090 -workers 8 -batch 500 -batches 200
//
// With -addr "" it starts an in-process server on a loopback port, which
// measures the Go path alone without any deployment.
package main

import (
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"log"
	"net"
	"os"
	"sort"
	"sync"
	"time"

	"google.golang.org/grpc"

	"urbanflow/ingest/client"
	"urbanflow/ingest/gen/ingestpb"
	"urbanflow/ingest/internal/server"
	"urbanflow/ingest/internal/store"
)

type report struct {
	Workers        int     `json:"workers"`
	Batch          int     `json:"batch_size"`
	Batches        int     `json:"batches_per_worker"`
	Events         uint64  `json:"events"`
	Seconds        float64 `json:"seconds"`
	EventsPerSec   float64 `json:"events_per_sec"`
	LatencyP50Ms   float64 `json:"batch_latency_p50_ms"`
	LatencyP95Ms   float64 `json:"batch_latency_p95_ms"`
	LatencyP99Ms   float64 `json:"batch_latency_p99_ms"`
	Transport      string  `json:"transport"`
	AcceptedEvents uint64  `json:"accepted_events"`
}

func pct(sorted []time.Duration, p float64) float64 {
	if len(sorted) == 0 {
		return 0
	}
	i := int(float64(len(sorted)-1) * p)
	return float64(sorted[i].Microseconds()) / 1000
}

func main() {
	addr := flag.String("addr", "", "server address; empty starts an in-process server")
	workers := flag.Int("workers", 8, "concurrent producers")
	batch := flag.Int("batch", 500, "events per request")
	batches := flag.Int("batches", 200, "requests per worker")
	flag.Parse()

	transport := "remote"
	if *addr == "" {
		lis, err := net.Listen("tcp", "127.0.0.1:0")
		if err != nil {
			log.Fatal(err)
		}
		g := grpc.NewServer()
		ingestpb.RegisterIngestServer(g, server.New(store.New(16)))
		go func() { _ = g.Serve(lis) }()
		defer g.Stop()
		*addr = lis.Addr().String()
		transport = "in-process server over loopback gRPC"
	}

	c, err := client.Dial(*addr)
	if err != nil {
		log.Fatal(err)
	}
	defer c.Close()

	var (
		mu        sync.Mutex
		latencies []time.Duration
		accepted  uint64
		wg        sync.WaitGroup
	)
	start := time.Now()
	for w := 0; w < *workers; w++ {
		wg.Add(1)
		go func(w int) {
			defer wg.Done()
			run := fmt.Sprintf("bench-%d", w)
			var seq int64
			local := make([]time.Duration, 0, *batches)
			var acc uint64
			for b := 0; b < *batches; b++ {
				evs := make([]*ingestpb.Event, *batch)
				for i := range evs {
					evs[i] = &ingestpb.Event{
						RunId: run, Seq: seq, SimTime: float64(seq) * 0.1, Kind: "step",
						Metrics: map[string]float64{"speed": 12.5, "queue": 3},
					}
					seq++
				}
				t0 := time.Now()
				r, err := c.IngestBatch(context.Background(), evs)
				if err != nil {
					log.Printf("worker %d: %v", w, err)
					return
				}
				local = append(local, time.Since(t0))
				acc += r.Accepted
			}
			mu.Lock()
			latencies = append(latencies, local...)
			accepted += acc
			mu.Unlock()
		}(w)
	}
	wg.Wait()
	elapsed := time.Since(start).Seconds()

	sort.Slice(latencies, func(i, j int) bool { return latencies[i] < latencies[j] })
	total := uint64(*workers) * uint64(*batch) * uint64(*batches)
	out := report{
		Workers: *workers, Batch: *batch, Batches: *batches, Events: total,
		Seconds: elapsed, EventsPerSec: float64(accepted) / elapsed,
		LatencyP50Ms: pct(latencies, 0.50), LatencyP95Ms: pct(latencies, 0.95), LatencyP99Ms: pct(latencies, 0.99),
		Transport: transport, AcceptedEvents: accepted,
	}
	enc := json.NewEncoder(os.Stdout)
	enc.SetIndent("", "  ")
	_ = enc.Encode(out)
}
