package main

import (
	"bufio"
	"log"
	"net/http"
	"net/http/cgi"
	"os"
	"os/exec"
	"path/filepath"
)

func main() {
	// Serve SSE files from ../bin/sse for /cgi/sse/ requests
	http.Handle("/cgi/sse/", http.StripPrefix("/cgi/sse/", sseHandler("../cgi/sse")))

	// serve files that create child processes so go can spawn the processes
	http.Handle("/cgi/child/", http.StripPrefix("/cgi/child/", childHandler("../cgi/child")))

	// Serve CGI files from ../bin for /cgi/ requests
	http.Handle("/cgi/", http.StripPrefix("/cgi/", cgiHandler("../cgi")))

	// Serve static files from ../public for all other requests
	fs := http.FileServer(http.Dir("../public"))
	http.Handle("/", fs)

	// Start the server
	log.Println("Server started on :8081")
	log.Fatal(http.ListenAndServe(":8081", nil))
}

// cgiHandler returns an http.Handler that serves CGI scripts
func cgiHandler(dir string) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		path := filepath.Join(dir, r.URL.Path)
		if _, err := os.Stat(path); os.IsNotExist(err) {
			http.NotFound(w, r)
			return
		}

		h := &cgi.Handler{
			Path: path,
			Root: dir,
		}
		h.ServeHTTP(w, r)
	})
}

// sseHandler handles SSE requests by executing a CGI script and streaming its output incrementally
func sseHandler(dir string) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		path := filepath.Join(dir, r.URL.Path)

		// Set headers for SSE
		w.Header().Set("Content-Type", "text/event-stream")
		w.Header().Set("Cache-Control", "no-cache")
		w.Header().Set("Connection", "keep-alive")

		// Execute the CGI script
		cmd := exec.Command(path)

		// Get the stdout pipe for incremental reading
		stdoutPipe, err := cmd.StdoutPipe()
		if err != nil {
			log.Println("Error creating stdout pipe:", err)
			http.Error(w, "Internal server error", http.StatusInternalServerError)
			return
		}

		// Start the command
		if err := cmd.Start(); err != nil {
			log.Println("Error starting CGI script:", err)
			http.Error(w, "Internal server error", http.StatusInternalServerError)
			return
		}

		// Stream output line by line
		scanner := bufio.NewScanner(stdoutPipe)
		for scanner.Scan() {
			// Write each line to the SSE client
			line := scanner.Text()
			_, err := w.Write([]byte(line + "\n\n")) // SSE requires two newlines after each event
			if err != nil {
				log.Println("Error writing to client:", err)
				break
			}

			// Flush immediately to ensure data is sent incrementally
			if flusher, ok := w.(http.Flusher); ok {
				flusher.Flush()
			}
		}

		// Handle errors from the scanner
		if err := scanner.Err(); err != nil {
			log.Println("Error reading script output:", err)
		}

		// Wait for the command to finish
		if err := cmd.Wait(); err != nil {
			log.Println("Error waiting for CGI script:", err)
		}
	})
}

func childHandler(dir string) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		path := filepath.Join(dir, r.URL.Path)

		// Check if the script exists
		if _, err := os.Stat(path); os.IsNotExist(err) {
			http.NotFound(w, r)
			return
		}

		// Set headers for the HTTP response
		w.Header().Set("Content-Type", "text/html")
		w.Header().Set("Connection", "close") // Force the connection to close
		w.WriteHeader(http.StatusAccepted)    // Immediately return 202 Accepted
		w.Write([]byte("<html><body><h1>Request Accepted</h1></body></html>"))

		// Ensure the response is sent before starting the long-running process
		if f, ok := w.(http.Flusher); ok {
			f.Flush()
		}

		// Run the CGI script in a detached process using a goroutine
		go func() {
			cmd := exec.Command(path)
			devnull, _ := os.OpenFile(os.DevNull, os.O_WRONLY, 0)

			cmd.Stdout = devnull
			cmd.Stderr = devnull

			// Start the command
			if err := cmd.Start(); err != nil {
				log.Println("Error starting CGI script:", err)
				return
			}

			log.Println("CGI script started successfully with PID:", cmd.Process.Pid)

			// Detach from the process
			if err := cmd.Process.Release(); err != nil {
				log.Println("Error releasing process:", err)
			}
		}()
	})
}
