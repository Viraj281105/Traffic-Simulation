// Package client is a small Go client for the Ingest service.
package client

import (
	"context"

	"google.golang.org/grpc"
	"google.golang.org/grpc/credentials/insecure"

	"urbanflow/ingest/gen/ingestpb"
)

type Client struct {
	conn *grpc.ClientConn // nil when built with FromConn
	rpc  ingestpb.IngestClient
}

// Dial connects to addr (host:port) without TLS; use it inside the cluster or
// on localhost. Production TLS would pass credentials via DialWithOptions.
func Dial(addr string) (*Client, error) {
	return DialWithOptions(addr, grpc.WithTransportCredentials(insecure.NewCredentials()))
}

func DialWithOptions(addr string, opts ...grpc.DialOption) (*Client, error) {
	conn, err := grpc.NewClient(addr, opts...)
	if err != nil {
		return nil, err
	}
	return &Client{conn: conn, rpc: ingestpb.NewIngestClient(conn)}, nil
}

// FromConn wraps an existing connection; the caller keeps ownership of it.
func FromConn(conn grpc.ClientConnInterface) *Client {
	return &Client{rpc: ingestpb.NewIngestClient(conn)}
}

func (c *Client) Close() error {
	if c.conn == nil {
		return nil
	}
	return c.conn.Close()
}

func (c *Client) IngestBatch(ctx context.Context, events []*ingestpb.Event) (*ingestpb.IngestBatchResponse, error) {
	return c.rpc.IngestBatch(ctx, &ingestpb.IngestBatchRequest{Events: events})
}

// IngestStream sends events over one client-streaming call.
func (c *Client) IngestStream(ctx context.Context, events []*ingestpb.Event) (*ingestpb.IngestBatchResponse, error) {
	s, err := c.rpc.IngestStream(ctx)
	if err != nil {
		return nil, err
	}
	for _, e := range events {
		if err := s.Send(e); err != nil {
			return nil, err
		}
	}
	return s.CloseAndRecv()
}

func (c *Client) RunSummary(ctx context.Context, runID string) (*ingestpb.RunSummaryResponse, error) {
	return c.rpc.RunSummary(ctx, &ingestpb.RunSummaryRequest{RunId: runID})
}

func (c *Client) Stats(ctx context.Context) (*ingestpb.StatsResponse, error) {
	return c.rpc.Stats(ctx, &ingestpb.StatsRequest{})
}
