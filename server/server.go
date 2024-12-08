package main

import (
	"bufio"        // For buffered I/O operations
	"encoding/json" // For JSON encoding
	"fmt"           // For formatted I/O
	"log"           // For logging
	"net"           // For networking (finding available ports)
	"net/http"      // For HTTP server
	"net/http/cgi"  // For CGI handling
	"os"            // For OS functions
	"os/exec"       // For executing commands
	"path/filepath" // For manipulating file paths
	"sync"          // For synchronizing access to shared resources
	"syscall"       // For low-level system calls
	"io"            // For general I/O operations
	"github.com/meilisearch/meilisearch-go",
)

type WebSocketResponse struct {
	WebSocketURL string `json:"websocket_url"`
}

var (
	activePort int
	cmd        *exec.Cmd
	mutex      sync.Mutex
)

func findFreePort() (int, error) {
	listener, err := net.Listen("tcp", ":0")
	if err != nil {
		return 0, err
	}
	defer listener.Close()
	return listener.Addr().(*net.TCPAddr).Port, nil
}

func handleWebSocket(w http.ResponseWriter, r *http.Request) {
	mutex.Lock()
	defer mutex.Unlock()

	if activePort == 0 {
		port, err := findFreePort()
		if err != nil {
			http.Error(w, "Failed to find a free port", http.StatusInternalServerError)
			log.Printf("Error finding free port: %v", err)
			return
		}
		activePort = port

		cmd = exec.Command("python3", "/home/yolo/local_llm/cgi/child/chat.py")
		cmd.Env = append(os.Environ(), fmt.Sprintf("PORT=%d", port))
		cmd.Stdout = os.Stdout
		cmd.Stderr = os.Stderr

		log.Printf("Launching chat.py on port %d...", port)
		if err := cmd.Start(); err != nil {
			http.Error(w, "Failed to start chat.py", http.StatusInternalServerError)
			log.Printf("Error starting chat.py: %v", err)
			activePort = 0
			return
		}
	}

	websocketURL := fmt.Sprintf("ws://localhost:%d", activePort)
	response := WebSocketResponse{WebSocketURL: websocketURL}
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	if err := json.NewEncoder(w).Encode(response); err != nil {
		http.Error(w, "Failed to encode WebSocket URL", http.StatusInternalServerError)
		log.Printf("Error encoding WebSocket URL: %v", err)
	}
	log.Printf("WebSocket URL returned: %s", websocketURL)
}

func cleanup() {
	mutex.Lock()
	defer mutex.Unlock()

	if cmd != nil && cmd.Process != nil {
		log.Println("Stopping chat.py process...")
		if err := cmd.Process.Kill(); err != nil {
			log.Printf("Error killing chat.py process: %v", err)
		} else {
			log.Println("chat.py process stopped successfully.")
		}
		cmd = nil
		activePort = 0
	}
}

func main() {
	// Register HTTP handlers
	http.Handle("/cgi/sse/", http.StripPrefix("/cgi/sse/", sseHandler("../bin/sse")))
	http.Handle("/cgi/child/", http.StripPrefix("/cgi/child/", childHandler("../bin/child")))
	http.Handle("/cgi/", http.StripPrefix("/cgi/", cgiHandler("../bin")))
	http.HandleFunc("/cgi/child/chat", handleWebSocket)
	http.Handle("/", http.FileServer(http.Dir("../public")))

	// Start the main HTTP server on port 8081
	log.Println("Server starting on port 8081...")
	if err := http.ListenAndServe(":8081", nil); err != nil {
		log.Fatalf("Server failed: %v", err)
	}

	// Handle cleanup on exit
	defer processManager.Cleanup()

	fmt.Println("Server starting...")
	fmt.Println("Serving static files from ../public")
	fmt.Println("Serving CGI files from ../bin for /cgi/ requests")

	// Start the main HTTP server on port 8081
	log.Println("Server starting on port 8081...")
	if err := http.ListenAndServe(":8081", nil); err != nil {
		log.Fatalf("Server failed: %v", err)
	}
	log.Fatal(http.ListenAndServe(":8081", nil))

	// Handle cleanup on exit
	defer cleanup()
	select {} // Keep the server running
}

// ChatResponse holds the WebSocket URL
type ChatResponse struct {
	WebSocketURL string `json:"websocket_url"`
}

// ProcessManager tracks spawned processes for cleanup
type ProcessManager struct {
	mu        sync.Mutex
	processes map[int]*os.Process
}

func NewProcessManager() *ProcessManager {
	return &ProcessManager{
		processes: make(map[int]*os.Process),
	}
}

func (pm *ProcessManager) Add(port int, process *os.Process) {
	pm.mu.Lock()
	defer pm.mu.Unlock()
	pm.processes[port] = process
	fmt.Printf("[DEBUG] Process added: PID=%d, Port=%d\n", process.Pid, port)
}

func (pm *ProcessManager) Remove(port int) {
	pm.mu.Lock()
	defer pm.mu.Unlock()
	if process, exists := pm.processes[port]; exists {
		fmt.Printf("[DEBUG] Removing process: PID=%d, Port=%d\n", process.Pid, port)
		delete(pm.processes, port)
	}
}

func (pm *ProcessManager) Cleanup() {
	pm.mu.Lock()
	defer pm.mu.Unlock()
	for port, process := range pm.processes {
		fmt.Printf("[DEBUG] Cleaning up process on port %d (PID=%d)\n", port, process.Pid)
		err := process.Kill()
		if err != nil {
			fmt.Printf("[ERROR] Error killing process on port %d: %v\n", port, err)
		} else {
			fmt.Printf("[DEBUG] Process on port %d killed successfully\n", port)
		}
		delete(pm.processes, port)
	}
}

// Global process manager
var processManager = NewProcessManager()

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
        w.WriteHeader(http.StatusAccepted) // Immediately return 202 Accepted
        w.Write([]byte("<html><body><h1>Request Accepted</h1></body></html>"))

        // Ensure the response is sent before starting the long-running process
        if f, ok := w.(http.Flusher); ok {
            f.Flush()
        }

        // Run the CGI script in a detached process using a goroutine
        go func() {
			// Create the command to execute the script
			cmd := exec.Command(path)

			// Pass the query string to the CGI script
			cmd.Env = append(os.Environ(), "QUERY_STRING="+r.URL.RawQuery)

			// Set process attributes to create a new process group
			cmd.SysProcAttr = &syscall.SysProcAttr{
				Setpgid: true,
				Pgid:    0,
			}

			// Open /dev/null for redirection (if needed)
			devnull, _ := os.OpenFile(os.DevNull, os.O_WRONLY, 0)
			defer devnull.Close() // Ensure it gets closed

			// Create pipes for stdout and stderr
			stdout, err := cmd.StdoutPipe()
			if err != nil {
				log.Println("Error creating stdout pipe:", err)
				return
			}

			stderr, err := cmd.StderrPipe()
			if err != nil {
				log.Println("Error creating stderr pipe:", err)
				return
			}

			cmd.Stdout = devnull
			cmd.Stderr = devnull

            // Start the command
            if err := cmd.Start(); err != nil {
                log.Println("Error starting CGI script:", err)
                return
            }

            log.Println("CGI script started successfully with PID:", cmd.Process.Pid)

			// Log the output of stdout and stderr
			go logOutput(stdout, "STDOUT")
			go logOutput(stderr, "STDERR")

            // Detach from the process
            if err := cmd.Process.Release(); err != nil {
                log.Println("Error releasing process:", err)
            }
        }()
    })
}

// logOutput reads and logs the output from a reader
func logOutput(reader io.ReadCloser, label string) {
	scanner := bufio.NewScanner(reader)
	for scanner.Scan() {
		log.Printf("[%s] %s", label, scanner.Text())
	}
	if err := scanner.Err(); err != nil {
		log.Printf("[%s] Error reading output: %v", label, err)
	}
}