// Package server implements the Ingest gRPC service over internal/store.
// It needs the generated code in gen/ingestpb (run `make proto`).
package server

import (
	"context"
	"errors"
	"io"

	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"

	"urbanflow/ingest/gen/ingestpb"
	"urbanflow/ingest/internal/store"
)

// MaxBatch bounds one IngestBatch request so a client cannot pin the server.
const MaxBatch = 10000

type Server struct {
	ingestpb.UnimplementedIngestServer
	Store *store.Store
}

func New(s *store.Store) *Server { return &Server{Store: s} }

func toStore(e *ingestpb.Event) *store.Event {
	if e == nil {
		return nil
	}
	return &store.Event{
		RunID: e.GetRunId(), Seq: e.GetSeq(), SimTime: e.GetSimTime(),
		Kind: e.GetKind(), Metrics: e.GetMetrics(),
	}
}

func tally(resp *ingestpb.IngestBatchResponse, r store.Result) {
	switch r {
	case store.Accepted:
		resp.Accepted++
	case store.Duplicate:
		resp.Duplicates++
	default:
		resp.Rejected++
	}
}

func (s *Server) IngestBatch(_ context.Context, req *ingestpb.IngestBatchRequest) (*ingestpb.IngestBatchResponse, error) {
	if len(req.GetEvents()) > MaxBatch {
		return nil, status.Errorf(codes.InvalidArgument, "batch of %d exceeds limit %d", len(req.GetEvents()), MaxBatch)
	}
	resp := &ingestpb.IngestBatchResponse{}
	for _, e := range req.GetEvents() {
		tally(resp, s.Store.Append(toStore(e)))
	}
	return resp, nil
}

func (s *Server) IngestStream(stream ingestpb.Ingest_IngestStreamServer) error {
	resp := &ingestpb.IngestBatchResponse{}
	for {
		e, err := stream.Recv()
		if errors.Is(err, io.EOF) {
			return stream.SendAndClose(resp)
		}
		if err != nil {
			return err
		}
		tally(resp, s.Store.Append(toStore(e)))
	}
}

func (s *Server) RunSummary(_ context.Context, req *ingestpb.RunSummaryRequest) (*ingestpb.RunSummaryResponse, error) {
	sum := s.Store.Summary(req.GetRunId())
	return &ingestpb.RunSummaryResponse{
		RunId: sum.RunID, Found: sum.Found, Events: sum.Events, LastSeq: sum.LastSeq,
		FirstSimTime: sum.FirstSimTime, LastSimTime: sum.LastSimTime, MetricMeans: sum.MetricMeans,
	}, nil
}

func (s *Server) Stats(_ context.Context, _ *ingestpb.StatsRequest) (*ingestpb.StatsResponse, error) {
	runs, events := s.Store.Stats()
	return &ingestpb.StatsResponse{Runs: runs, Events: events}, nil
}
