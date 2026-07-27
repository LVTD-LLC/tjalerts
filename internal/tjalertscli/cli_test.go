package tjalertscli

import (
	"bytes"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func TestSearchCommandSendsFiltersAndBearerAuthentication(t *testing.T) {
	var request *http.Request
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		request = r.Clone(r.Context())
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"count":1,"jobs":[{"id":"job-1"}]}`))
	}))
	defer server.Close()

	stdout := new(bytes.Buffer)
	stderr := new(bytes.Buffer)
	exitCode := Run(
		[]string{
			"search",
			"--query", "backend",
			"--technology", "Go",
			"--technology", "PostgreSQL",
			"--source", "Hacker News",
			"--remote=true",
			"--minimum-salary", "150000",
			"--page", "2",
			"--page-size", "25",
		},
		Config{APIKey: "tja_test", BaseURL: server.URL},
		stdout,
		stderr,
	)

	if exitCode != 0 {
		t.Fatalf("Run() exit code = %d, stderr = %q", exitCode, stderr.String())
	}
	if request == nil {
		t.Fatal("server did not receive a request")
	}
	if request.URL.Path != "/jobs/search" {
		t.Fatalf("path = %q, want /jobs/search", request.URL.Path)
	}
	if got := request.Header.Get("Authorization"); got != "Bearer tja_test" {
		t.Fatalf("Authorization = %q", got)
	}

	query := request.URL.Query()
	expected := map[string]string{
		"query":          "backend",
		"technologies":   "Go,PostgreSQL",
		"source":         "Hacker News",
		"remote":         "true",
		"minimum_salary": "150000",
		"page":           "2",
		"page_size":      "25",
	}
	for key, want := range expected {
		if got := query.Get(key); got != want {
			t.Errorf("%s = %q, want %q", key, got, want)
		}
	}

	var result map[string]any
	if err := json.Unmarshal(stdout.Bytes(), &result); err != nil {
		t.Fatalf("stdout is not JSON: %v\n%s", err, stdout.String())
	}
	if result["count"] != float64(1) {
		t.Fatalf("count = %#v", result["count"])
	}
}

func TestSemanticSearchCommandUsesSemanticQuery(t *testing.T) {
	var request *http.Request
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		request = r.Clone(r.Context())
		_, _ = w.Write([]byte(`{"count":0,"jobs":[]}`))
	}))
	defer server.Close()

	exitCode := Run(
		[]string{"semantic-search", "distributed systems engineer", "--remote=true"},
		Config{APIKey: "tja_test", BaseURL: server.URL + "/"},
		new(bytes.Buffer),
		new(bytes.Buffer),
	)

	if exitCode != 0 {
		t.Fatalf("Run() exit code = %d", exitCode)
	}
	if got := request.URL.Query().Get("semantic_query"); got != "distributed systems engineer" {
		t.Fatalf("semantic_query = %q", got)
	}
	if got := request.URL.Query().Get("remote"); got != "true" {
		t.Fatalf("remote = %q", got)
	}
}

func TestGetCommandReturnsJobJSON(t *testing.T) {
	var request *http.Request
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		request = r.Clone(r.Context())
		_, _ = w.Write([]byte(`{"id":"88dd2d09-3939-4431-905d-46f1ec5be75c","description":"Build APIs"}`))
	}))
	defer server.Close()

	stdout := new(bytes.Buffer)
	exitCode := Run(
		[]string{"get", "88dd2d09-3939-4431-905d-46f1ec5be75c"},
		Config{APIKey: "tja_test", BaseURL: server.URL},
		stdout,
		new(bytes.Buffer),
	)

	if exitCode != 0 {
		t.Fatalf("Run() exit code = %d", exitCode)
	}
	if request.URL.Path != "/jobs/88dd2d09-3939-4431-905d-46f1ec5be75c" {
		t.Fatalf("path = %q", request.URL.Path)
	}
	if !strings.Contains(stdout.String(), `"description": "Build APIs"`) {
		t.Fatalf("stdout = %q", stdout.String())
	}
}

func TestMissingAPIKeyFailsBeforeRequest(t *testing.T) {
	requests := 0
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		requests++
	}))
	defer server.Close()

	stderr := new(bytes.Buffer)
	exitCode := Run(
		[]string{"search"},
		Config{BaseURL: server.URL},
		new(bytes.Buffer),
		stderr,
	)

	if exitCode != 1 {
		t.Fatalf("Run() exit code = %d, want 1", exitCode)
	}
	if requests != 0 {
		t.Fatalf("server received %d requests", requests)
	}
	if !strings.Contains(stderr.String(), "TJALERTS_API_KEY") {
		t.Fatalf("stderr = %q", stderr.String())
	}
}

func TestAPIErrorIsWrittenToStderr(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusUnauthorized)
		_, _ = w.Write([]byte(`{"detail":"Unauthorized"}`))
	}))
	defer server.Close()

	stderr := new(bytes.Buffer)
	exitCode := Run(
		[]string{"search"},
		Config{APIKey: "invalid", BaseURL: server.URL},
		new(bytes.Buffer),
		stderr,
	)

	if exitCode != 1 {
		t.Fatalf("Run() exit code = %d, want 1", exitCode)
	}
	if !strings.Contains(stderr.String(), "API request failed (401): Unauthorized") {
		t.Fatalf("stderr = %q", stderr.String())
	}
}

func TestSemanticSearchRequiresQuery(t *testing.T) {
	stderr := new(bytes.Buffer)
	exitCode := Run(
		[]string{"semantic-search"},
		Config{APIKey: "tja_test", BaseURL: "https://example.invalid"},
		new(bytes.Buffer),
		stderr,
	)

	if exitCode != 2 {
		t.Fatalf("Run() exit code = %d, want 2", exitCode)
	}
	if !strings.Contains(stderr.String(), "semantic-search requires a query") {
		t.Fatalf("stderr = %q", stderr.String())
	}
}

func TestHelpDoesNotRequireAPIKey(t *testing.T) {
	stdout := new(bytes.Buffer)
	exitCode := Run(
		[]string{"help"},
		Config{},
		stdout,
		new(bytes.Buffer),
	)

	if exitCode != 0 {
		t.Fatalf("Run() exit code = %d, want 0", exitCode)
	}
	if !strings.Contains(stdout.String(), "tjalerts semantic-search") {
		t.Fatalf("stdout = %q", stdout.String())
	}
}

func TestNonJSONAPIErrorIncludesStatusAndBody(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusBadGateway)
		_, _ = w.Write([]byte("upstream unavailable"))
	}))
	defer server.Close()

	stderr := new(bytes.Buffer)
	exitCode := Run(
		[]string{"search"},
		Config{APIKey: "tja_test", BaseURL: server.URL},
		new(bytes.Buffer),
		stderr,
	)

	if exitCode != 1 {
		t.Fatalf("Run() exit code = %d, want 1", exitCode)
	}
	if !strings.Contains(stderr.String(), "API request failed (502): upstream unavailable") {
		t.Fatalf("stderr = %q", stderr.String())
	}
}

func TestOversizedAPIResponseIsRejected(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		_, _ = w.Write([]byte(strings.Repeat("x", maxAPIResponseBytes+1)))
	}))
	defer server.Close()

	stderr := new(bytes.Buffer)
	exitCode := Run(
		[]string{"search"},
		Config{APIKey: "tja_test", BaseURL: server.URL},
		new(bytes.Buffer),
		stderr,
	)

	if exitCode != 1 {
		t.Fatalf("Run() exit code = %d, want 1", exitCode)
	}
	if !strings.Contains(stderr.String(), "API response exceeds") {
		t.Fatalf("stderr = %q", stderr.String())
	}
}

func TestSuccessfulNonJSONResponseFailsWithoutStdout(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		_, _ = w.Write([]byte("<html>not json</html>"))
	}))
	defer server.Close()

	stdout := new(bytes.Buffer)
	stderr := new(bytes.Buffer)
	exitCode := Run(
		[]string{"search"},
		Config{APIKey: "tja_test", BaseURL: server.URL},
		stdout,
		stderr,
	)

	if exitCode != 1 {
		t.Fatalf("Run() exit code = %d, want 1", exitCode)
	}
	if !strings.Contains(stderr.String(), "decode API response") {
		t.Fatalf("stderr = %q", stderr.String())
	}
	if stdout.Len() != 0 {
		t.Fatalf("stdout = %q, want empty", stdout.String())
	}
}

func TestLargeJSONIntegersArePreserved(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		_, _ = w.Write([]byte(`{"job_details":{"big":9007199254740993}}`))
	}))
	defer server.Close()

	stdout := new(bytes.Buffer)
	exitCode := Run(
		[]string{"get", "job-1"},
		Config{APIKey: "tja_test", BaseURL: server.URL},
		stdout,
		new(bytes.Buffer),
	)

	if exitCode != 0 {
		t.Fatalf("Run() exit code = %d", exitCode)
	}
	if !strings.Contains(stdout.String(), "9007199254740993") {
		t.Fatalf("stdout = %q", stdout.String())
	}
}

func TestRemotePlaintextBaseURLIsRejected(t *testing.T) {
	requests := 0
	client := &http.Client{Transport: roundTripFunc(func(request *http.Request) (*http.Response, error) {
		requests++
		return nil, nil
	})}

	stderr := new(bytes.Buffer)
	exitCode := Run(
		[]string{"search"},
		Config{APIKey: "tja_test", BaseURL: "http://jobs.example/api", HTTPClient: client},
		new(bytes.Buffer),
		stderr,
	)

	if exitCode != 1 {
		t.Fatalf("Run() exit code = %d, want 1", exitCode)
	}
	if requests != 0 {
		t.Fatalf("HTTP client received %d requests", requests)
	}
	if !strings.Contains(stderr.String(), "HTTPS") {
		t.Fatalf("stderr = %q", stderr.String())
	}
}

func TestHTTPSRedirectToHTTPIsRejected(t *testing.T) {
	target := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		_, _ = w.Write([]byte(`{"count":0,"jobs":[]}`))
	}))
	defer target.Close()

	source := httptest.NewTLSServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		http.Redirect(w, r, target.URL+"/jobs/search", http.StatusFound)
	}))
	defer source.Close()

	stderr := new(bytes.Buffer)
	exitCode := Run(
		[]string{"search"},
		Config{APIKey: "tja_test", BaseURL: source.URL, HTTPClient: source.Client()},
		new(bytes.Buffer),
		stderr,
	)

	if exitCode != 1 {
		t.Fatalf("Run() exit code = %d, want 1", exitCode)
	}
	if !strings.Contains(stderr.String(), "HTTPS-to-HTTP redirect") {
		t.Fatalf("stderr = %q", stderr.String())
	}
}

type roundTripFunc func(*http.Request) (*http.Response, error)

func (function roundTripFunc) RoundTrip(request *http.Request) (*http.Response, error) {
	return function(request)
}
