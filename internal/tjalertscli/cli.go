package tjalertscli

import (
	"bytes"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io"
	"net"
	"net/http"
	"net/url"
	"strconv"
	"strings"
	"time"
)

const (
	DefaultBaseURL      = "https://jobs.lvtd.dev/api"
	maxAPIResponseBytes = 4 << 20
)

type Config struct {
	APIKey     string
	BaseURL    string
	HTTPClient *http.Client
}

type searchOptions struct {
	query         string
	technologies  []string
	source        string
	minimumSalary int
	page          int
	pageSize      int
}

func Run(args []string, config Config, stdout, stderr io.Writer) int {
	if len(args) == 0 {
		printUsage(stderr)
		return 2
	}
	if args[0] == "help" || args[0] == "-h" || args[0] == "--help" {
		printUsage(stdout)
		return 0
	}

	if strings.TrimSpace(config.APIKey) == "" {
		fmt.Fprintln(stderr, "TJALERTS_API_KEY is required")
		return 1
	}
	if config.BaseURL == "" {
		config.BaseURL = DefaultBaseURL
	}
	if config.HTTPClient == nil {
		config.HTTPClient = &http.Client{Timeout: 30 * time.Second}
	}

	var err error
	switch args[0] {
	case "search":
		err = runSearch(args[1:], config, stdout, stderr, "")
	case "semantic-search":
		if len(args) < 2 || strings.TrimSpace(args[1]) == "" {
			fmt.Fprintln(stderr, "semantic-search requires a query")
			return 2
		}
		err = runSearch(args[2:], config, stdout, stderr, args[1])
	case "get":
		if len(args) != 2 {
			fmt.Fprintln(stderr, "get requires exactly one job ID")
			return 2
		}
		err = requestJSON(config, "/jobs/"+url.PathEscape(args[1]), nil, stdout)
	default:
		fmt.Fprintf(stderr, "unknown command %q\n\n", args[0])
		printUsage(stderr)
		return 2
	}

	if err != nil {
		fmt.Fprintln(stderr, err)
		return 1
	}
	return 0
}

func runSearch(args []string, config Config, stdout, stderr io.Writer, semanticQuery string) error {
	options := searchOptions{}
	var remoteSet, remoteValue bool
	flags := flag.NewFlagSet("search", flag.ContinueOnError)
	flags.SetOutput(stderr)
	flags.StringVar(&options.query, "query", "", "keyword query")
	flags.Func("technology", "required technology (repeatable)", func(value string) error {
		value = strings.TrimSpace(value)
		if value == "" {
			return errors.New("technology cannot be empty")
		}
		options.technologies = append(options.technologies, value)
		return nil
	})
	flags.StringVar(&options.source, "source", "", "job source")
	flags.BoolFunc("remote", "filter by remote status (true or false)", func(value string) error {
		parsed, err := strconv.ParseBool(value)
		if err != nil {
			return errors.New("must be true or false")
		}
		remoteSet = true
		remoteValue = parsed
		return nil
	})
	flags.IntVar(&options.minimumSalary, "minimum-salary", -1, "minimum acceptable upper salary")
	flags.IntVar(&options.page, "page", 1, "result page")
	flags.IntVar(&options.pageSize, "page-size", 20, "jobs per page (maximum 100)")
	if err := flags.Parse(args); err != nil {
		return err
	}
	if flags.NArg() != 0 {
		return fmt.Errorf("unexpected arguments: %s", strings.Join(flags.Args(), " "))
	}

	query := url.Values{}
	if options.query != "" {
		query.Set("query", options.query)
	}
	if semanticQuery != "" {
		query.Set("semantic_query", semanticQuery)
	}
	if len(options.technologies) > 0 {
		query.Set("technologies", strings.Join(options.technologies, ","))
	}
	if options.source != "" {
		query.Set("source", options.source)
	}
	if remoteSet {
		query.Set("remote", strconv.FormatBool(remoteValue))
	}
	if options.minimumSalary >= 0 {
		query.Set("minimum_salary", strconv.Itoa(options.minimumSalary))
	}
	query.Set("page", strconv.Itoa(options.page))
	query.Set("page_size", strconv.Itoa(options.pageSize))

	return requestJSON(config, "/jobs/search", query, stdout)
}

func requestJSON(config Config, path string, query url.Values, output io.Writer) error {
	endpoint, err := buildEndpoint(config.BaseURL, path, query)
	if err != nil {
		return err
	}

	request, err := http.NewRequest(http.MethodGet, endpoint, nil)
	if err != nil {
		return fmt.Errorf("build API request: %w", err)
	}
	request.Header.Set("Accept", "application/json")
	request.Header.Set("Authorization", "Bearer "+config.APIKey)

	client := *config.HTTPClient
	previousRedirectPolicy := client.CheckRedirect
	client.CheckRedirect = func(request *http.Request, via []*http.Request) error {
		if len(via) > 0 && via[len(via)-1].URL.Scheme == "https" && request.URL.Scheme != "https" {
			return errors.New("refusing HTTPS-to-HTTP redirect with API credentials")
		}
		if previousRedirectPolicy != nil {
			return previousRedirectPolicy(request, via)
		}
		return nil
	}

	response, err := client.Do(request)
	if err != nil {
		return fmt.Errorf("call API: %w", err)
	}
	defer response.Body.Close()

	body, err := io.ReadAll(io.LimitReader(response.Body, maxAPIResponseBytes+1))
	if err != nil {
		return fmt.Errorf("read API response: %w", err)
	}
	if len(body) > maxAPIResponseBytes {
		return fmt.Errorf("API response exceeds %d bytes", maxAPIResponseBytes)
	}

	var payload any
	decoder := json.NewDecoder(bytes.NewReader(body))
	decoder.UseNumber()
	decodeErr := decoder.Decode(&payload)
	if decodeErr == nil {
		var trailing any
		if err := decoder.Decode(&trailing); err != io.EOF {
			decodeErr = errors.New("response contains multiple JSON values")
		}
	}
	if response.StatusCode < http.StatusOK || response.StatusCode >= http.StatusMultipleChoices {
		if decodeErr != nil {
			message := strings.TrimSpace(string(body))
			if message == "" {
				message = http.StatusText(response.StatusCode)
			}
			return fmt.Errorf("API request failed (%d): %s", response.StatusCode, message)
		}
		return apiResponseError(response.StatusCode, payload)
	}
	if decodeErr != nil {
		return fmt.Errorf("decode API response: %w", decodeErr)
	}

	encoder := json.NewEncoder(output)
	encoder.SetIndent("", "  ")
	encoder.SetEscapeHTML(false)
	if err := encoder.Encode(payload); err != nil {
		return fmt.Errorf("write JSON response: %w", err)
	}
	return nil
}

func buildEndpoint(baseURL, path string, query url.Values) (string, error) {
	endpoint, err := url.Parse(baseURL)
	if err != nil {
		return "", fmt.Errorf("parse API URL: %w", err)
	}
	if endpoint.User != nil || endpoint.Hostname() == "" {
		return "", errors.New("TJALERTS_API_URL must be an absolute URL without credentials")
	}
	switch endpoint.Scheme {
	case "https":
	case "http":
		host := endpoint.Hostname()
		ip := net.ParseIP(host)
		if !strings.EqualFold(host, "localhost") && (ip == nil || !ip.IsLoopback()) {
			return "", errors.New("TJALERTS_API_URL must use HTTPS except for loopback development servers")
		}
	default:
		return "", errors.New("TJALERTS_API_URL must use HTTPS")
	}

	endpoint.Path = strings.TrimRight(endpoint.Path, "/") + path
	endpoint.RawQuery = query.Encode()
	endpoint.Fragment = ""
	return endpoint.String(), nil
}

func apiResponseError(statusCode int, payload any) error {
	message := http.StatusText(statusCode)
	if body, ok := payload.(map[string]any); ok {
		if detail, ok := body["detail"].(string); ok && detail != "" {
			message = detail
		}
	}
	return fmt.Errorf("API request failed (%d): %s", statusCode, message)
}

func printUsage(output io.Writer) {
	fmt.Fprintln(output, `Usage:
  tjalerts search [flags]
  tjalerts semantic-search QUERY [flags]
  tjalerts get JOB_ID

Authentication:
  Set TJALERTS_API_KEY to a key generated in Tech Job Alerts settings.

Search flags:
  --query TEXT
  --technology NAME       repeatable
  --source NAME
  --remote=true|false
  --minimum-salary AMOUNT
  --page NUMBER
  --page-size NUMBER`)
}
