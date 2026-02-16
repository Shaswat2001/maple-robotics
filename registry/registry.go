package registry

import (
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os/exec"
	"path/filepath"
	"strings"

	"github.com/maple-robotics/maple/storage"
)

// Number of parallel downloads
const maxParallel = 4

// Docker images for each architecture
var archImages = map[string]string{
	"openvla": "maplerobotics/openvla:latest",
	"smolvla": "maplerobotics/smolvla:latest",
	"groot":   "maplerobotics/groot:latest",
	"octo":    "maplerobotics/octo:latest",
	"openpi":  "maplerobotics/openpi:latest",
}

// Known models and their HuggingFace repos
var knownModels = map[string]string{
	"openvla:7b":           "openvla/openvla-7b",
	"openvla:latest":       "openvla/openvla-7b",
	"smolvla:base":         "HuggingFaceTB/SmolVLA-base",
	"smolvla:latest":       "HuggingFaceTB/SmolVLA-base",
	"groot:n1.5-3b":        "nvidia/GR00T-N1.5-3B",
	"groot:latest":         "nvidia/GR00T-N1.5-3B",
	"groot:libero_spatial": "Tacoin/GR00T-N1.5-3B-LIBERO-SPATIAL",
	"groot:libero_object":  "Tacoin/GR00T-N1.5-3B-LIBERO-OBJECT",
	"groot:libero_goal":    "Tacoin/GR00T-N1.5-3B-LIBERO-GOAL",
}

// Model configs (what we know about each model)
var modelConfigs = map[string]storage.Config{
	"openvla:7b": {
		Architecture:  "openvla",
		Family:        "llama",
		ParameterSize: "7B",
		ActionDim:     7,
		ImageSize:     224,
		Environments:  []string{"libero", "aloha", "bridge"},
		HFRepo:        "openvla/openvla-7b",
	},
	"smolvla:base": {
		Architecture:  "smolvla",
		Family:        "smollm",
		ParameterSize: "256M",
		ActionDim:     7,
		ImageSize:     224,
		Environments:  []string{"libero"},
		HFRepo:        "HuggingFaceTB/SmolVLA-base",
	},
	"groot:n1.5-3b": {
		Architecture:  "groot",
		Family:        "eagle",
		ParameterSize: "3B",
		ActionDim:     7,
		ImageSize:     224,
		Environments:  []string{"libero", "aloha"},
		HFRepo:        "nvidia/GR00T-N1.5-3B",
	},
}

// Registry handles pulling models from HuggingFace
type Registry struct{}

// New creates a new registry client
func New() *Registry {
	return &Registry{}
}

// Pull downloads a model from HuggingFace
func (r *Registry) Pull(ref string, progress func(status string, completed, total int64)) error {
	name, tag := storage.ParseModelRef(ref)
	fullRef := name + ":" + tag

	// Look up HuggingFace repo
	hfRepo, ok := knownModels[fullRef]
	if !ok {
		// Try as direct HuggingFace repo
		hfRepo = ref
	}

	// Determine architecture
	arch := name
	if cfg, ok := modelConfigs[fullRef]; ok {
		arch = cfg.Architecture
	}

	// Pull Docker image first
	if image, ok := archImages[arch]; ok {
		progress(fmt.Sprintf("pulling docker image %s", image), 0, 0)
		if err := pullDockerImage(image); err != nil {
			return fmt.Errorf("failed to pull docker image: %w", err)
		}
	}

	progress(fmt.Sprintf("pulling %s from %s", fullRef, hfRepo), 0, 0)

	// Get list of files from HuggingFace
	files, err := r.listFiles(hfRepo)
	if err != nil {
		return fmt.Errorf("failed to list files: %w", err)
	}

	// Download files sequentially with progress
	var layers []storage.Layer
	for i, file := range files {
		progress(fmt.Sprintf("pulling %s (%d/%d)", file.Name, i+1, len(files)), 0, 0)

		digest, size, err := r.pullFile(hfRepo, file, progress)
		if err != nil {
			return fmt.Errorf("failed to pull %s: %w", file.Name, err)
		}

		layers = append(layers, storage.Layer{
			MediaType: mediaTypeForFile(file.Name),
			Digest:    digest,
			Size:      size,
		})
	}

	// Create config
	cfg := modelConfigs[fullRef]
	if cfg.Architecture == "" {
		cfg.Architecture = name
		cfg.HFRepo = hfRepo
	}

	cfgData, _ := cfg.ToJSON()
	cfgDigest, cfgSize, err := storage.WriteBlob(strings.NewReader(string(cfgData)))
	if err != nil {
		return fmt.Errorf("failed to write config: %w", err)
	}

	// Create and save manifest
	manifest := &storage.Manifest{
		SchemaVersion: 1,
		MediaType:     storage.MediaTypeManifest,
		Config: storage.Layer{
			MediaType: storage.MediaTypeConfig,
			Digest:    cfgDigest,
			Size:      cfgSize,
		},
		Layers: layers,
	}

	progress("writing manifest", 0, 0)
	if err := storage.SaveManifest(name, tag, manifest); err != nil {
		return fmt.Errorf("failed to save manifest: %w", err)
	}

	progress("done", 0, 0)
	return nil
}

// HFFile represents a file in a HuggingFace repo
type HFFile struct {
	Name string
	Size int64
	URL  string
}

func (r *Registry) listFiles(repo string) ([]HFFile, error) {
	url := fmt.Sprintf("https://huggingface.co/api/models/%s", repo)

	resp, err := http.Get(url)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("model not found: %s", resp.Status)
	}

	var data struct {
		Siblings []struct {
			Filename string `json:"rfilename"`
			Size     int64  `json:"size"`
		} `json:"siblings"`
	}

	if err := json.NewDecoder(resp.Body).Decode(&data); err != nil {
		return nil, err
	}

	var files []HFFile
	for _, s := range data.Siblings {
		// Only pull model files
		if isModelFile(s.Filename) {
			files = append(files, HFFile{
				Name: s.Filename,
				Size: s.Size,
				URL:  fmt.Sprintf("https://huggingface.co/%s/resolve/main/%s", repo, s.Filename),
			})
		}
	}

	return files, nil
}

func (r *Registry) pullFile(repo string, file HFFile, progress func(string, int64, int64)) (string, int64, error) {
	// First, do a HEAD request to get the file size and ETag (which we could use as a hint)
	resp, err := http.Get(file.URL)
	if err != nil {
		return "", 0, err
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		return "", 0, fmt.Errorf("download failed: %s", resp.Status)
	}

	// Get actual size from Content-Length header
	total := resp.ContentLength

	// Write to blob storage with progress
	pr := &progressReader{
		reader:   resp.Body,
		total:    total,
		progress: progress,
	}

	digest, size, err := storage.WriteBlob(pr)
	if err != nil {
		return "", 0, err
	}

	// Check if this blob already existed (for logging purposes)
	// The WriteBlob will overwrite but that's OK - same content = same hash

	return digest, size, err
}

func isModelFile(name string) bool {
	// Include safetensors, bin, json config files
	exts := []string{".safetensors", ".bin", ".json", ".txt", ".model"}
	for _, ext := range exts {
		if strings.HasSuffix(name, ext) {
			return true
		}
	}
	return false
}

func mediaTypeForFile(name string) string {
	ext := filepath.Ext(name)
	switch ext {
	case ".safetensors", ".bin":
		return storage.MediaTypeWeights
	case ".json":
		return storage.MediaTypeConfig
	default:
		return "application/octet-stream"
	}
}

func pullDockerImage(image string) error {
	cmd := exec.Command("docker", "pull", image)
	return cmd.Run()
}

// progressReader wraps a reader to track progress
type progressReader struct {
	reader    io.Reader
	total     int64
	completed int64
	progress  func(string, int64, int64)
}

func (pr *progressReader) Read(p []byte) (int, error) {
	n, err := pr.reader.Read(p)
	pr.completed += int64(n)
	pr.progress("downloading", pr.completed, pr.total)
	return n, err
}
