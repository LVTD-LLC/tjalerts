package main

import (
	"os"

	"github.com/rasulkireev/hn-jobs/internal/tjalertscli"
)

func main() {
	os.Exit(tjalertscli.Run(
		os.Args[1:],
		tjalertscli.Config{
			APIKey:  os.Getenv("TJALERTS_API_KEY"),
			BaseURL: os.Getenv("TJALERTS_API_URL"),
		},
		os.Stdout,
		os.Stderr,
	))
}
