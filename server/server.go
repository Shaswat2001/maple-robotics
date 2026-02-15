package server

import (
	"encoding/json"
	"fmt"
	"net/http"

	"github.com/maple-robotics/maple/storage"
)

// Server is the MAPLE HTTP server
type Server struct {
	port int
}

// New creates a new server
func New(port int) *Server {
	return &Server{port: port}
}

// Start starts the HTTP server
func (s *Server) Start() error {
	mux := http.NewServeMux()

	// API routes
	mux.HandleFunc("/", s.handleRoot)
	mux.HandleFunc("/api/tags", s.handleTags)
	mux.HandleFunc("/api/show", s.handleShow)
	mux.HandleFunc("/api/pull", s.handlePull)
	mux.HandleFunc("/api/act", s.handleAct)

	addr := fmt.Sprintf("127.0.0.1:%d", s.port)
	fmt.Printf("MAPLE server running on http://%s\n", addr)

	return http.ListenAndServe(addr, mux)
}

func (s *Server) handleRoot(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]string{
		"status": "MAPLE is running",
	})
}

func (s *Server) handleTags(w http.ResponseWriter, r *http.Request) {
	refs, err := storage.ListManifests()
	if err != nil {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusInternalServerError)
		json.NewEncoder(w).Encode(map[string]string{"error": err.Error()})
		return
	}

	type modelInfo struct {
		Name         string `json:"name"`
		Size         int64  `json:"size"`
		Architecture string `json:"architecture"`
	}

	models := []modelInfo{}
	for _, ref := range refs {
		name, tag := storage.ParseModelRef(ref)
		info := modelInfo{Name: ref}

		if m, err := storage.LoadManifest(name, tag); err == nil {
			for _, l := range m.Layers {
				info.Size += l.Size
			}
			if cfg, err := storage.LoadConfig(name, tag); err == nil {
				info.Architecture = cfg.Architecture
			}
		}
		models = append(models, info)
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]any{
		"models": models,
	})
}

func (s *Server) handleShow(w http.ResponseWriter, r *http.Request) {
	if r.Method != http.MethodPost {
		w.WriteHeader(http.StatusMethodNotAllowed)
		return
	}

	var req struct {
		Name string `json:"name"`
	}
	if err := json.NewDecoder(r.Body).Decode(&req); err != nil {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusBadRequest)
		json.NewEncoder(w).Encode(map[string]string{"error": "invalid request"})
		return
	}

	name, tag := storage.ParseModelRef(req.Name)

	m, err := storage.LoadManifest(name, tag)
	if err != nil {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusNotFound)
		json.NewEncoder(w).Encode(map[string]string{"error": "model not found"})
		return
	}

	var totalSize int64
	for _, l := range m.Layers {
		totalSize += l.Size
	}

	response := map[string]any{
		"name":   req.Name,
		"size":   totalSize,
		"layers": len(m.Layers),
	}

	if cfg, err := storage.LoadConfig(name, tag); err == nil {
		response["architecture"] = cfg.Architecture
		response["family"] = cfg.Family
		response["parameter_size"] = cfg.ParameterSize
		response["action_dim"] = cfg.ActionDim
		response["image_size"] = cfg.ImageSize
		response["environments"] = cfg.Environments
	}

	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(response)
}

func (s *Server) handlePull(w http.ResponseWriter, r *http.Request) {
	// TODO: pull model
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]string{
		"error": "not implemented",
	})
}

func (s *Server) handleAct(w http.ResponseWriter, r *http.Request) {
	// TODO: run inference
	w.Header().Set("Content-Type", "application/json")
	json.NewEncoder(w).Encode(map[string]string{
		"error": "not implemented",
	})
}